import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import faiss

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.retrieval.index_store import EMBED_MODEL, embed_text, resolve_index_paths

# ============================================================
# CONFIG
# ============================================================

DEFAULT_INPUT = "data/all_bugfix_pairs.jsonl"


def build_index(input_path: str, profile: str | None = None, index_dir: str | None = None):
    paths = resolve_index_paths(profile=profile, index_dir=index_dir)
    os.makedirs(paths["dir"], exist_ok=True)

    print(f"Loading embedding model: {EMBED_MODEL}")
    print(f"\nReading dataset: {input_path}")

    vectors = []
    meta = []
    count = 0

    with open(input_path) as handle:
        for line in handle:
            item = json.loads(line)
            code_to_embed = item.get("buggy_code") or item.get("code") or ""
            vectors.append(embed_text(code_to_embed))
            meta.append(item)

            count += 1
            if count % 100 == 0:
                print(f"Embedded {count} examples...")

    vectors = np.array(vectors).astype("float32")

    print(f"\nTotal embedded examples: {len(vectors)}")
    print(f"Vector dimension: {vectors.shape[1]}")

    print("\nBuilding FAISS index...")
    index = faiss.IndexFlatL2(vectors.shape[1])
    index.add(vectors)

    faiss.write_index(index, paths["index"])
    print(f"Saved FAISS index → {paths['index']}")

    with open(paths["meta"], "w") as handle:
        for entry in meta:
            handle.write(json.dumps(entry) + "\n")
    print(f"Saved metadata → {paths['meta']}")

    with open(paths["info"], "w") as handle:
        handle.write("FAISS index built successfully.\n")
        handle.write(f"Embedding model: {EMBED_MODEL}\n")
        handle.write(f"Entries indexed: {len(vectors)}\n")
        handle.write(f"Vector dimension: {vectors.shape[1]}\n")
        handle.write(f"Input path: {input_path}\n")
        if profile:
            handle.write(f"Profile: {profile}\n")
    print(f"Saved info → {paths['info']}")
    print("\nFinished building FAISS index.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-path", default=DEFAULT_INPUT)
    parser.add_argument("--profile", default=None)
    parser.add_argument("--index-dir", default=None)
    args = parser.parse_args()
    build_index(args.input_path, profile=args.profile, index_dir=args.index_dir)
