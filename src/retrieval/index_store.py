from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any

import faiss
from sentence_transformers import SentenceTransformer


EMBED_MODEL = os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")

PROFILE_TO_INDEX_DIR = {
    "external": "data/indexes/external",
    "humaneval_clean": "data/indexes/humaneval_clean",
    "mbpp_clean": "data/indexes/mbpp_clean",
    "quixbugs_clean": "data/indexes/quixbugs_clean",
    "repair_clean": "data/indexes/repair_clean",
}


def resolve_index_dir(
    profile: str | None = None,
    index_dir: str | None = None,
) -> str:
    if index_dir:
        return index_dir

    env_index_dir = os.getenv("RETRIEVAL_INDEX_DIR")
    if env_index_dir:
        return env_index_dir

    resolved_profile = profile or os.getenv("RETRIEVAL_PROFILE", "repair_clean")
    return PROFILE_TO_INDEX_DIR.get(
        resolved_profile,
        os.path.join("data", "indexes", resolved_profile),
    )


def resolve_index_paths(
    profile: str | None = None,
    index_dir: str | None = None,
) -> dict[str, str]:
    resolved_dir = resolve_index_dir(profile=profile, index_dir=index_dir)
    return {
        "dir": resolved_dir,
        "index": os.path.join(resolved_dir, "faiss.index"),
        "meta": os.path.join(resolved_dir, "meta.jsonl"),
        "info": os.path.join(resolved_dir, "info.txt"),
    }


@lru_cache(maxsize=1)
def load_embedder() -> SentenceTransformer:
    try:
        return SentenceTransformer(EMBED_MODEL, local_files_only=True)
    except Exception:
        print(f"Local cache miss for embedding model {EMBED_MODEL}; attempting download...")
        return SentenceTransformer(EMBED_MODEL)


def embed_text(text: str):
    return load_embedder().encode(text, convert_to_numpy=True).astype("float32")


@lru_cache(maxsize=16)
def load_index_bundle(
    profile: str | None = None,
    index_dir: str | None = None,
) -> tuple[Any, list[dict[str, Any]]]:
    paths = resolve_index_paths(profile=profile, index_dir=index_dir)
    print(f"Loading FAISS index from {paths['index']}...")

    try:
        index = faiss.read_index(paths["index"])
        with open(paths["meta"]) as handle:
            metadata = [json.loads(line) for line in handle]
        return index, metadata
    except Exception as exc:
        print(f"ERROR loading index bundle: {exc}")
        return None, []
