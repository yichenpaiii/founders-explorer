"""Compute BGEM3 embeddings for each course text and append them to the CSV.

Usage:
    python compute_courses_scores.py [--csv-path PATH] [--batch-size N]

By default, this script reads ``data/courses_scores.csv`` relative to its own
location, generates a dense embedding for the ``text`` column of each row using
``BAAI/bge-m3`` (matching ``tests/test_bgem3.py``), and writes the embeddings
back into the same CSV under a new ``embedding`` column.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Iterable, List
import torch

from FlagEmbedding import BGEM3FlagModel

DEFAULT_CSV_PATH = Path(__file__).resolve().parent / "data" / "courses_scores.csv"
EMBEDDING_COLUMN = "embedding"
TEXT_COLUMN = "text"
DEFAULT_BATCH_SIZE = 8
MODEL_NAME = "BAAI/bge-m3"
MAX_LENGTH = 8192
DEFAULT_DEVICE = "auto"  # auto | cpu | mps | cuda


def _parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute embeddings for course texts.")
    parser.add_argument(
        "--csv-path",
        type=Path,
        default=DEFAULT_CSV_PATH,
        help="Path to the courses_scores.csv file (default: data/courses_scores.csv).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Number of texts to encode per batch (default: %(default)s).",
    )
    parser.add_argument(
        "--max-length",
        type=int,
        default=MAX_LENGTH,
        help="Maximum token length per text fed to the model (default: %(default)s).",
    )
    parser.add_argument(
        "--device",
        type=str,
        choices=["auto", "cpu", "mps", "cuda"],
        default=DEFAULT_DEVICE,
        help="Device to run inference on: auto|cpu|mps|cuda (default: %(default)s).",
    )
    return parser.parse_args(argv)


def _load_rows(csv_path: Path) -> tuple[List[dict], List[str]]:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    with csv_path.open("r", newline="", encoding="utf-8") as fp:
        reader = csv.DictReader(fp)
        if TEXT_COLUMN not in reader.fieldnames:
            raise ValueError(f"Missing '{TEXT_COLUMN}' column in {csv_path}")
        rows = [row for row in reader]
    return rows, list(reader.fieldnames or [])


def _encode_batches(model: BGEM3FlagModel, texts: List[str], batch_size: int, max_length: int) -> List[List[float]]:
    embeddings: List[List[float]] = []
    total = len(texts)
    for start in range(0, total, batch_size):
        batch = texts[start : start + batch_size]
        # Note: BGEM3 returns L2-normalized dense embeddings by default; no need to pass normalize flag here.
        output = model.encode(
            batch,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
            max_length=max_length,
        )
        dense = output["dense_vecs"]
        if hasattr(dense, "tolist"):
            dense = dense.tolist()
        embeddings.extend(dense)
        print(f"[ok] Encoded batch {start // batch_size + 1}/{(total + batch_size - 1) // batch_size}")
    return embeddings


def _write_rows(csv_path: Path, rows: List[dict], fieldnames: List[str]) -> None:
    if EMBEDDING_COLUMN not in fieldnames:
        fieldnames = fieldnames + [EMBEDDING_COLUMN]

    with csv_path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main(argv: Iterable[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    csv_path = args.csv_path
    batch_size = max(1, args.batch_size)
    max_length = max(1, args.max_length)

    # Resolve device
    if args.device == "auto":
        if torch.cuda.is_available():
            resolved_device = "cuda"
        elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            resolved_device = "mps"
        else:
            resolved_device = "cpu"
    else:
        resolved_device = args.device

    rows, fieldnames = _load_rows(csv_path)
    texts = [row.get(TEXT_COLUMN, "") or "" for row in rows]

    print(f"[info] Loading model '{MODEL_NAME}' on {resolved_device}...")
    model = BGEM3FlagModel(MODEL_NAME, use_fp16=False, device=resolved_device)

    print(f"[info] Encoding {len(texts)} course texts (batch size {batch_size})...")
    embeddings = _encode_batches(model, texts, batch_size, max_length)

    if len(embeddings) != len(rows):
        raise RuntimeError("Embedding count does not match row count.")

    for row, vector in zip(rows, embeddings):
        row[EMBEDDING_COLUMN] = json.dumps(vector, ensure_ascii=False, separators=(",", ":"))

    _write_rows(csv_path, rows, fieldnames)
    print(f"[done] Updated {csv_path} with '{EMBEDDING_COLUMN}' column.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
