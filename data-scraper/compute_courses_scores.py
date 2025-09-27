"""Compute aspect scores for courses using BGEM3 embeddings.

The script expects ``data/courses_scores.csv`` to contain at least ``row_id``,
``text`` and (optionally) ``embedding`` columns. It makes sure each course has a
BGEM3 embedding (reusing the existing JSON-encoded vector or creating one on the
fly), encodes four aspect descriptions from ``data/aspects.json``, and writes
per-aspect cosine/dot similarities plus a softmax score back into the CSV.

Usage::

    python compute_courses_scores.py [--csv-path PATH] [--aspects-path PATH]
                                     [--batch-size N] [--tau 0.1]
                                     [--device auto|cpu|mps|cuda]
                                     [--max-length 8192]
                                     [--mode single|multi]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Iterable, List, Sequence

import numpy as np
import torch
from FlagEmbedding import BGEM3FlagModel

DEFAULT_CSV_PATH = Path(__file__).resolve().parent / "data" / "courses_scores.csv"
DEFAULT_ASPECTS_PATH = Path(__file__).resolve().parent / "data" / "aspects.json"
TEXT_COLUMN = "text"
EMBEDDING_COLUMN = "embedding"
DEFAULT_BATCH_SIZE = 8
DEFAULT_TAU = 0.5
DEFAULT_DEVICE = "auto"
MAX_LENGTH = 8192

ASPECT_CONFIG = [
    ("skills", "personal_development"),
    ("product", "product_development"),
    ("venture", "venture_building"),
    ("foundations", "entrepreneurship_foundations"),
]
MODEL_NAME = "BAAI/bge-m3"


def _parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute aspect scores for course texts.")
    parser.add_argument(
        "--csv-path",
        type=Path,
        default=DEFAULT_CSV_PATH,
        help="Path to the courses_scores.csv file (default: data/courses_scores.csv).",
    )
    parser.add_argument(
        "--aspects-path",
        type=Path,
        default=DEFAULT_ASPECTS_PATH,
        help="Path to aspects.json describing the four aspect texts (default: data/aspects.json).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Batch size when encoding missing course embeddings (default: %(default)s).",
    )
    parser.add_argument(
        "--tau",
        type=float,
        default=DEFAULT_TAU,
        help="Softmax temperature for aspect scores (default: %(default)s).",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["single", "multi"],
        default="multi",
        help="Scoring mode: 'single' uses softmax over 4 aspects (mutually exclusive); 'multi' uses per-aspect sigmoid for multi-label scenarios (default: %(default)s).",
    )
    parser.add_argument(
        "--calibrate",
        type=str,
        choices=["none", "zscore", "minmax"],
        default="zscore",
        help="Per-aspect score calibration before sigmoid/softmax: none|zscore|minmax (default: zscore).",
    )
    parser.add_argument(
        "--bias-json",
        type=Path,
        default=None,
        help="Optional JSON file mapping aspect labels to bias values to subtract from raw cosine (e.g., {\"skills\":0.05}).",
    )
    parser.add_argument(
        "--device",
        type=str,
        choices=["auto", "cpu", "mps", "cuda"],
        default=DEFAULT_DEVICE,
        help="Device to run inference on (default: %(default)s).",
    )
    parser.add_argument(
        "--max-length",
        type=int,
        default=MAX_LENGTH,
        help="Maximum token length per text when encoding (default: %(default)s).",
    )
    return parser.parse_args(argv)


def _load_rows(csv_path: Path) -> tuple[List[dict], List[str]]:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    with csv_path.open("r", newline="", encoding="utf-8") as fp:
        reader = csv.DictReader(fp)
        fieldnames = list(reader.fieldnames or [])
        if TEXT_COLUMN not in fieldnames:
            raise ValueError(f"Missing '{TEXT_COLUMN}' column in {csv_path}")
        rows = [row for row in reader]
    return rows, fieldnames


def _load_aspects(aspects_path: Path) -> List[str]:
    with aspects_path.open("r", encoding="utf-8") as fp:
        data = json.load(fp)
    texts = []
    for _, key in ASPECT_CONFIG:
        if key not in data:
            raise KeyError(f"Aspect key '{key}' missing from {aspects_path}")
        texts.append(data[key])
    return texts


def _normalize_rows(mat: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms


def _encode_texts(
    model: BGEM3FlagModel, texts: Sequence[str], batch_size: int, max_length: int
) -> np.ndarray:
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)
    outputs: List[List[float]] = []
    total = len(texts)
    for start in range(0, total, batch_size):
        batch = texts[start : start + batch_size]
        enc = model.encode(
            batch,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
            max_length=max_length,
        )
        dense = enc["dense_vecs"]
        if hasattr(dense, "tolist"):
            dense = dense.tolist()
        outputs.extend(dense)
        print(
            f"[ok] Encoded batch {start // batch_size + 1}/"
            f"{(total + batch_size - 1) // batch_size}"
        )
    arr = np.asarray(outputs, dtype=np.float32)
    return _normalize_rows(arr)


def _resolve_device(choice: str) -> str:
    if choice != "auto":
        return choice
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _parse_embedding(value: str | None) -> np.ndarray | None:
    if not value:
        return None
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return None
    if isinstance(data, list):
        arr = np.asarray(data, dtype=np.float32)
        if arr.ndim == 1 and arr.size:
            return arr
    return None


def _softmax(scores: np.ndarray, tau: float) -> np.ndarray:
    if tau <= 0:
        raise ValueError("tau must be positive")
    scaled = scores / tau
    scaled = scaled - scaled.max(axis=1, keepdims=True)
    exp = np.exp(scaled)
    return exp / exp.sum(axis=1, keepdims=True)


def _sigmoid(scores: np.ndarray, tau: float) -> np.ndarray:
    scaled = scores / tau
    return 1.0 / (1.0 + np.exp(-scaled))


def _ensure_fieldnames(fieldnames: List[str], extra: Sequence[str]) -> List[str]:
    for col in extra:
        if col not in fieldnames:
            fieldnames.append(col)
    return fieldnames


def _write_rows(csv_path: Path, rows: List[dict], fieldnames: List[str]) -> None:
    with csv_path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _load_biases(bias_path: Path | None) -> dict[str, float]:
    if not bias_path:
        return {}
    if not bias_path.exists():
        raise FileNotFoundError(f"Bias JSON not found: {bias_path}")
    with bias_path.open("r", encoding="utf-8") as fp:
        data = json.load(fp)
    if not isinstance(data, dict):
        raise ValueError("Bias JSON must be an object mapping label->bias float")
    out: dict[str, float] = {}
    for label, _ in ASPECT_CONFIG:
        val = data.get(label, 0.0)
        try:
            out[label] = float(val)
        except Exception as e:
            raise ValueError(f"Bias for label '{label}' must be a float, got {val!r}") from e
    return out


def _apply_calibration(raw: np.ndarray, mode: str) -> tuple[np.ndarray, dict]:
    if mode == "none":
        return raw, {"type": "none"}
    if mode == "zscore":
        mu = raw.mean(axis=0, keepdims=True)
        sd = raw.std(axis=0, keepdims=True)
        sd[sd == 0] = 1.0
        adj = (raw - mu) / sd
        return adj, {"type": "zscore", "mean": mu.squeeze().tolist(), "std": sd.squeeze().tolist()}
    if mode == "minmax":
        mn = raw.min(axis=0, keepdims=True)
        mx = raw.max(axis=0, keepdims=True)
        denom = (mx - mn)
        denom[denom == 0] = 1.0
        adj = (raw - mn) / denom
        # scale to roughly center at 0 using affine map to [-1,1]
        adj = adj * 2.0 - 1.0
        return adj, {"type": "minmax", "min": mn.squeeze().tolist(), "max": mx.squeeze().tolist()}
    raise ValueError(f"Unknown calibration mode: {mode}")


def main(argv: Iterable[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    csv_path = args.csv_path
    aspects_path = args.aspects_path
    batch_size = max(1, args.batch_size)
    tau = float(args.tau)
    max_length = max(1, args.max_length)
    mode = args.mode
    calib_mode = args.calibrate
    bias_map = _load_biases(args.bias_json)

    rows, fieldnames = _load_rows(csv_path)
    if EMBEDDING_COLUMN not in fieldnames:
        fieldnames.append(EMBEDDING_COLUMN)

    aspect_texts = _load_aspects(aspects_path)
    device = _resolve_device(args.device)
    print(f"[info] Loading model '{MODEL_NAME}' on {device}...")
    model = BGEM3FlagModel(MODEL_NAME, use_fp16=False, device=device)

    print("[info] Encoding aspect texts...")
    aspect_vectors = _encode_texts(model, aspect_texts, batch_size=4, max_length=max_length)
    if aspect_vectors.shape[0] != len(ASPECT_CONFIG):
        raise RuntimeError("Aspect encoding failed: unexpected shape")

    course_vectors: List[np.ndarray | None] = [None] * len(rows)
    missing_indices: List[int] = []
    missing_texts: List[str] = []

    for idx, row in enumerate(rows):
        emb = _parse_embedding(row.get(EMBEDDING_COLUMN))
        if emb is None:
            missing_indices.append(idx)
            missing_texts.append(row.get(TEXT_COLUMN, "") or "")
        else:
            course_vectors[idx] = emb

    if missing_indices:
        print(f"[info] Encoding {len(missing_indices)} course texts missing embeddings...")
        new_embs = _encode_texts(model, missing_texts, batch_size=batch_size, max_length=max_length)
        for idx, emb in zip(missing_indices, new_embs):
            course_vectors[idx] = emb
            rows[idx][EMBEDDING_COLUMN] = json.dumps(emb.tolist(), ensure_ascii=False, separators=(",", ":"))

    if any(vec is None for vec in course_vectors):
        raise RuntimeError("Some course embeddings are still missing after encoding.")

    course_matrix = np.vstack([vec for vec in course_vectors if vec is not None])
    course_matrix = _normalize_rows(course_matrix)
    aspect_matrix = _normalize_rows(aspect_vectors)

    raw_scores = course_matrix @ aspect_matrix.T

    # subtract per-aspect biases if provided
    if bias_map:
        bias_vec = np.array([bias_map[label] for label, _ in ASPECT_CONFIG], dtype=np.float32)
        raw_scores = raw_scores - bias_vec[None, :]

    # apply calibration over the dataset if requested
    cal_scores, cal_stats = _apply_calibration(raw_scores, calib_mode)

    if mode == "single":
        softmax_scores = _softmax(cal_scores, tau)
        sigmoid_scores = None
    else:  # multi
        softmax_scores = None
        sigmoid_scores = _sigmoid(cal_scores, tau)

    new_columns = []
    if mode == "single":
        for label, _ in ASPECT_CONFIG:
            new_columns.extend([
                f"score_{label}_cos",
                f"score_{label}",  # softmax
            ])
    else:  # multi
        for label, _ in ASPECT_CONFIG:
            new_columns.extend([
                f"score_{label}_cos",
                f"score_{label}_sigmoid",
            ])

    fieldnames = _ensure_fieldnames(fieldnames, new_columns)

    for idx, row in enumerate(rows):
        raw = raw_scores[idx]
        cal = cal_scores[idx]
        if mode == "single":
            soft = _softmax(cal[np.newaxis, :], tau)[0]
            for aspect_idx, (label, _) in enumerate(ASPECT_CONFIG):
                row[f"score_{label}_cos"] = float(raw[aspect_idx])
                row[f"score_{label}"] = float(soft[aspect_idx])
        else:  # multi
            sig = _sigmoid(cal[np.newaxis, :], tau)[0]
            for aspect_idx, (label, _) in enumerate(ASPECT_CONFIG):
                row[f"score_{label}_cos"] = float(raw[aspect_idx])
                row[f"score_{label}_sigmoid"] = float(sig[aspect_idx])

    _write_rows(csv_path, rows, fieldnames)
    if calib_mode != "none":
        print(f"[info] Applied calibration: {cal_stats.get('type')}.")
    print(f"[done] Updated {csv_path} with aspect scores using tau={tau}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
