"""
Compute aspect scores for courses using BGEM3 embeddings.

What it does
- Reads `data/courses_embedding.csv` (columns: at least `row_id`, `text`; optional `embedding`).
- Loads four aspect texts (Skills, Product, Venture, Foundations) from a JSON file.
- Computes BGEM3 embeddings for the four aspect texts (v_scale per aspect).
- For each course, obtains its embedding (reuse existing `embedding` column if present; otherwise compute from `text`).
- Adds dot, cosine, and fused probabilities per aspect:
  - `score_skills_dot`, `score_skills_cos`, `score_skills`
  - `score_product_dot`, `score_product_cos`, `score_product`
  - `score_venture_dot`, `score_venture_cos`, `score_venture`
  - `score_foundations_dot`, `score_foundations_cos`, `score_foundations`
- Writes results back to `data/courses_embedding.csv` in place, preserving existing columns and embedding.

Model and encode call match tests in `data-scraper/tests/test_bgem3.py`:
- Model: BGEM3FlagModel('BAAI/bge-m3', use_fp16=False)
- Call: model.encode(..., return_dense=True, return_sparse=False,
         return_colbert_vecs=False, max_length=8192)

Aspect JSON format (default path: data/aspects.json):
{
  "personal_development": "...",
  "product_development": "...",
  "venture_building": "...",
  "entrepreneurship_foundations": "..."
}

Usage examples (Python API):
  from data_scraper.compute_courses_scores import compute_course_scores
  compute_course_scores()

  # Recompute embeddings first and tweak fusion parameters
  compute_course_scores(update_embeddings=True, fuse_weight=0.6, fuse_temperature=2.5)
"""

from __future__ import annotations
import os
import json
from typing import Dict, List, Sequence, Tuple

import pandas as pd
from FlagEmbedding import BGEM3FlagModel
import numpy as np


ASPECT_KEYS = (
    "personal_development",  # Skills
    "product_development",  # Tech, Design, Prototyping, MAKE
    "venture_building",  # Management Functions
    "entrepreneurship_foundations",  # General and Industry-Specific
)


FUSE_WEIGHT = 0.65
DOT_SIGMOID_GAMMA = 1.0
FUSE_TEMPERATURE = 2.2
FUSE_LOGIT_BIAS = -0.35
DOT_MODE = "percentile"
DOT_TRIM_FRACTION = 0.05
MIN_STD = 1e-6
NUM_STABILITY_EPS = 1e-12

_BASE_DIR = os.path.dirname(__file__)
DEFAULT_CSV_PATH = os.path.join(_BASE_DIR, "data", "courses_embedding.csv")
DEFAULT_ASPECTS_PATH = os.path.join(_BASE_DIR, "data", "aspects.json")


def _parse_embedding(val) -> List[float] | None:
    """Parse an existing embedding cell which is a JSON array string.
    Returns a Python list[float] or None if unavailable/invalid."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    if isinstance(val, (list, tuple)):
        return list(map(float, val))
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return None
        try:
            arr = json.loads(s)
            if isinstance(arr, list):
                return list(map(float, arr))
        except Exception:
            return None
    return None


def _encode_texts(model: BGEM3FlagModel, texts: List[str]) -> List[List[float]]:
    out = model.encode(
        texts,
        return_dense=True,
        return_sparse=False,
        return_colbert_vecs=False,
        max_length=8192,
    )
    vecs = out["dense_vecs"]
    # Ensure plain lists of floats
    def to_list(v):
        try:
            return getattr(v, "tolist", lambda: v)()
        except Exception:
            return v
    return [list(map(float, to_list(v))) for v in vecs]


def _load_aspects(aspects_path: str) -> Dict[str, str]:
    with open(aspects_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    missing = [k for k in ASPECT_KEYS if k not in data or not str(data[k]).strip()]
    if missing:
        raise SystemExit(
            f"Missing or empty aspect text(s) in {aspects_path}: {', '.join(missing)}"
        )
    return {k: str(data[k]) for k in ASPECT_KEYS}


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return float("nan")
    return float(np.dot(a, b) / denom)


def _validate_vector(vec: Sequence[float], label: str, expected_dim: int | None = None) -> np.ndarray:
    arr = np.asarray(vec, dtype=np.float32)
    if arr.ndim != 1 or arr.size == 0:
        raise SystemExit(f"{label} must be a 1-D vector with at least one value")
    if expected_dim is not None and arr.size != expected_dim:
        raise SystemExit(
            f"{label} must have dimension {expected_dim}, got {arr.size}."
        )
    if not np.all(np.isfinite(arr)):
        raise SystemExit(f"{label} contains non-finite values")
    return arr


def _robust_mean_std(values: Sequence[float], trim_fraction: float = DOT_TRIM_FRACTION) -> Tuple[float, float]:
    """Return a trimmed mean/std pair that ignores NaNs and extreme outliers."""
    arr = np.asarray(values, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return 0.0, 1.0

    trim_fraction = float(trim_fraction)
    if trim_fraction < 0.0:
        trim_fraction = 0.0
    if trim_fraction >= 0.5:
        trim_fraction = 0.49

    if 0.0 < trim_fraction < 0.5 and arr.size > 4:
        lower = np.quantile(arr, trim_fraction)
        upper = np.quantile(arr, 1.0 - trim_fraction)
        trimmed = arr[(arr >= lower) & (arr <= upper)]
        if trimmed.size >= max(3, int(arr.size * 0.5)):
            arr = trimmed

    mean_val = float(arr.mean())
    std_val = float(arr.std(ddof=0))
    if not np.isfinite(std_val) or std_val < MIN_STD:
        std_val = 1.0
    return mean_val, std_val


def _combine_scores(
    cos_vals: pd.Series,
    dot_vals: pd.Series,
    *,
    weight: float = FUSE_WEIGHT,
    gamma: float = DOT_SIGMOID_GAMMA,
    temperature: float = FUSE_TEMPERATURE,
    trim_fraction: float = DOT_TRIM_FRACTION,
    dot_mode: str = DOT_MODE,
    bias: float = FUSE_LOGIT_BIAS,
) -> Tuple[pd.Series, Tuple[float, float]]:
    """Return fused scores plus (mean, std) stats used for dot normalization."""
    cos_series = cos_vals.astype(float)
    dot_series = dot_vals.astype(float)
    cos_arr = cos_series.to_numpy()
    dot_arr = dot_series.to_numpy()

    c = np.clip((cos_arr + 1.0) / 2.0, 0.0, 1.0)
    mode = (dot_mode or "zscore").strip().lower()
    if mode == "percentile":
        ranks = dot_series.rank(method="average", pct=True)
        d = np.clip(ranks.to_numpy(), 0.0, 1.0)
        mu = float(ranks.mean())
        sigma = float(ranks.std(ddof=0))
        if sigma < MIN_STD:
            sigma = 0.288675  # std of uniform(0,1)
    else:
        mu, sigma = _robust_mean_std(dot_arr, trim_fraction=trim_fraction)
        sigma = max(sigma, MIN_STD)
        z = (dot_arr - mu) / sigma
        d = 1.0 / (1.0 + np.exp(-gamma * z))
        d = np.clip(d, 0.0, 1.0)

    log_pos = weight * np.log(c + NUM_STABILITY_EPS) + (1.0 - weight) * np.log(d + NUM_STABILITY_EPS)
    log_neg = weight * np.log(1.0 - c + NUM_STABILITY_EPS) + (1.0 - weight) * np.log(1.0 - d + NUM_STABILITY_EPS)

    temp = max(temperature, MIN_STD)
    scaled_pos = log_pos / temp
    scaled_neg = log_neg / temp
    # Apply bias to sharpen strictness on the high end
    logit = (scaled_pos - scaled_neg) + float(bias)
    logit = np.clip(logit, -60.0, 60.0)

    fused = np.empty_like(logit)
    mask = logit >= 0
    fused[mask] = 1.0 / (1.0 + np.exp(-logit[mask]))
    exp_logit = np.exp(logit[~mask])
    fused[~mask] = exp_logit / (1.0 + exp_logit)

    return pd.Series(fused, index=cos_vals.index), (mu, sigma)


def compute_course_scores(
    csv_path: str | None = None,
    aspects_path: str | None = None,
    *,
    update_embeddings: bool = False,
    fuse_weight: float = FUSE_WEIGHT,
    fuse_temperature: float = FUSE_TEMPERATURE,
    fuse_bias: float = FUSE_LOGIT_BIAS,
    dot_gamma: float = DOT_SIGMOID_GAMMA,
    dot_trim: float = DOT_TRIM_FRACTION,
    dot_mode: str = DOT_MODE,
    verbose: bool = True,
) -> pd.DataFrame:
    """Compute BGEM3 scores for all courses and persist the CSV.

    Returns the updated DataFrame for convenience."""

    csv_path = csv_path or DEFAULT_CSV_PATH
    aspects_path = aspects_path or DEFAULT_ASPECTS_PATH

    in_path = os.path.realpath(csv_path)
    if not os.path.exists(in_path):
        raise FileNotFoundError(
            f"Input CSV not found: {in_path}\n"
            "Tip: ensure data/courses_embedding.csv exists next to this script."
        )

    aspects_path = os.path.realpath(aspects_path)
    if not os.path.exists(aspects_path):
        raise FileNotFoundError(
            f"Aspects JSON not found: {aspects_path}\n"
            "Provide four texts under required keys. See file header for format."
        )

    if not (0.0 < float(fuse_weight) < 1.0):
        raise ValueError("fuse_weight must be between 0 and 1 (exclusive)")
    if float(fuse_temperature) <= 0.0:
        raise ValueError("fuse_temperature must be > 0")
    if float(dot_gamma) <= 0.0:
        raise ValueError("dot_gamma must be > 0")

    dot_trim = float(dot_trim)
    if dot_trim < 0.0:
        dot_trim = 0.0
    if dot_trim >= 0.5:
        dot_trim = 0.49

    dot_mode = (dot_mode or DOT_MODE).lower()
    if dot_mode not in {"zscore", "percentile"}:
        raise ValueError("dot_mode must be one of {'zscore', 'percentile'}")

    fuse_bias = float(fuse_bias)
    fuse_weight = float(fuse_weight)
    fuse_temperature = float(fuse_temperature)
    dot_gamma = float(dot_gamma)

    # Load data
    df = pd.read_csv(in_path)
    if df.empty:
        raise ValueError(f"Input CSV {in_path} is empty")
    if "text" not in df.columns:
        raise ValueError("Input CSV must contain a 'text' column")
    if "row_id" in df.columns and df["row_id"].duplicated().any():
        dup_ids = df.loc[df["row_id"].duplicated(), "row_id"].head(5).tolist()
        raise ValueError(
            "Input CSV contains duplicate row_id values. Examples: "
            + ", ".join(map(str, dup_ids))
        )

    # Load aspects and initialize model
    aspects = _load_aspects(aspects_path)
    model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=False)

    # Ensure course embeddings are available
    need_embeddings = update_embeddings or ("embedding" not in df.columns)
    if need_embeddings:
        if verbose:
            print("[info] Computing embeddings for all courses (update enabled or missing column)")
        texts = ["" if pd.isna(t) else str(t) for t in df["text"].tolist()]
        vecs = _encode_texts(model, texts)
        df["embedding"] = [
            json.dumps(v, ensure_ascii=False, separators=(",", ":")) for v in vecs
        ]
    else:
        # Validate/patch any missing embeddings
        miss_idx = []
        for i, val in enumerate(df["embedding"].tolist()):
            if _parse_embedding(val) is None:
                miss_idx.append(i)
        if miss_idx and verbose:
            print(f"[info] Found {len(miss_idx)} rows with missing/invalid embedding; recomputing those")
        for i in miss_idx:
            text = df.at[i, "text"]
            text = "" if pd.isna(text) else str(text)
            v = _encode_texts(model, [text])[0]
            df.at[i, "embedding"] = json.dumps(v, ensure_ascii=False, separators=(",", ":"))

    # Encode the four aspects
    aspect_texts = [aspects[k] for k in ASPECT_KEYS]
    aspect_vecs = _encode_texts(model, aspect_texts)
    aspect_arrs: List[np.ndarray] = []
    embedding_dim: int | None = None
    for key, vec in zip(ASPECT_KEYS, aspect_vecs):
        arr = _validate_vector(vec, f"Aspect '{key}' embedding")
        if embedding_dim is None:
            embedding_dim = arr.size
        elif arr.size != embedding_dim:
            raise ValueError("Aspect embeddings must all share the same dimensionality")
        aspect_arrs.append(arr)

    assert embedding_dim is not None  # ensured by ASPECT_KEYS

    score_column_pairs = [
        ("score_skills_dot", "score_skills_cos"),
        ("score_product_dot", "score_product_cos"),
        ("score_venture_dot", "score_venture_cos"),
        ("score_foundations_dot", "score_foundations_cos"),
    ]
    fused_column_map = {
        "score_skills": score_column_pairs[0],
        "score_product": score_column_pairs[1],
        "score_venture": score_column_pairs[2],
        "score_foundations": score_column_pairs[3],
    }

    for dot_col, cos_col in score_column_pairs:
        if dot_col not in df.columns:
            df[dot_col] = np.nan
        if cos_col not in df.columns:
            df[cos_col] = np.nan
    for fused_col in fused_column_map:
        if fused_col not in df.columns:
            df[fused_col] = np.nan

    for idx, row in df.iterrows():
        v = _parse_embedding(row.get("embedding"))
        if v is None:
            text = row.get("text")
            text = "" if pd.isna(text) else str(text)
            v = _encode_texts(model, [text])[0]
            df.at[idx, "embedding"] = json.dumps(v, ensure_ascii=False, separators=(",", ":"))
        v_doc = _validate_vector(v, f"Embedding for row {idx}", expected_dim=embedding_dim)
        for (dot_col, cos_col), v_scale in zip(score_column_pairs, aspect_arrs):
            dot_val = float(np.dot(v_doc, v_scale))
            cos_val = _cosine(v_doc, v_scale)
            if not np.isfinite(dot_val):
                raise ValueError(
                    f"Dot product for row {idx} and aspect column '{dot_col}' is not finite"
                )
            if not np.isfinite(cos_val):
                raise ValueError(
                    f"Cosine similarity for row {idx} and aspect column '{cos_col}' is not finite"
                )
            df.at[idx, dot_col] = dot_val
            df.at[idx, cos_col] = cos_val

        if idx == 0 and verbose:
            print(
                "[sample-scores]",
                {
                    score_column_pairs[0][0]: df.at[idx, score_column_pairs[0][0]],
                    score_column_pairs[0][1]: df.at[idx, score_column_pairs[0][1]],
                },
            )

    for fused_col, (dot_col, cos_col) in fused_column_map.items():
        fused_series, (mu, sigma) = _combine_scores(
            df[cos_col],
            df[dot_col],
            weight=fuse_weight,
            gamma=dot_gamma,
            temperature=fuse_temperature,
            trim_fraction=dot_trim,
            dot_mode=dot_mode,
            bias=fuse_bias,
        )
        df[fused_col] = fused_series
        if fused_col == "score_skills" and verbose:
            print(
                "[stats-skills]",
                {
                    "mu_dot": round(mu, 6),
                    "sigma_dot": round(sigma, 6),
                    fused_col: float(fused_series.iloc[0]),
                    "gamma": dot_gamma,
                    "temperature": fuse_temperature,
                    "dot_mode": dot_mode,
                    "bias": fuse_bias,
                },
            )

    os.makedirs(os.path.dirname(in_path) or ".", exist_ok=True)
    df.to_csv(in_path, index=False)
    if verbose:
        print(f"[ok] Updated {len(df)} rows with aspect scores in {in_path}")

    return df


if __name__ == "__main__":
    compute_course_scores()
