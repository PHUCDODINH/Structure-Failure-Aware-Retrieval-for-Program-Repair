import json
import os
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

# ============================================================
# CONFIG
# ============================================================

# Combined code generation dataset
DATASET_PATH = "data/codegen_examples.jsonl"

# Output directory
INDEX_DIR = "data/codegen_index"
INDEX_PATH = f"{INDEX_DIR}/faiss.index"
META_PATH = f"{INDEX_DIR}/meta.jsonl"
INFO_PATH = f"{INDEX_DIR}/info.txt"

# Embedding model
EMBED_MODEL = "all-MiniLM-L6-v2"

# ============================================================
# LOAD EMBEDDING MODEL
# ============================================================
print(f"Loading embedding model: {EMBED_MODEL}")
model = SentenceTransformer(EMBED_MODEL)

def embed(text: str):
    """Embed text into a dense vector."""
    if not text:
        text = " " # Avoid error on empty string
    return model.encode(text, convert_to_numpy=True)

# ============================================================
# PREPARE OUTPUT FOLDER
# ============================================================
os.makedirs(INDEX_DIR, exist_ok=True)

# ============================================================
# LOAD AND EMBED DATA
# ============================================================
print(f"\nReading dataset: {DATASET_PATH}")

vectors = []
meta = []
count = 0

if os.path.exists(DATASET_PATH):
    with open(DATASET_PATH, "r") as f:
        for line in f:
            item = json.loads(line)

            # CRITICAL: For code generation, we embed the PROMPT (problem description)
            # This allows retrieving relevant examples when users ask "Write a function to..."
            text_to_embed = item.get("prompt", "")
            
            vec = embed(text_to_embed)
            vectors.append(vec)
            meta.append(item)

            count += 1
            if count % 100 == 0:
                print(f"Embedded {count} examples...")

    vectors = np.array(vectors).astype("float32")

    print(f"\nTotal embedded examples: {len(vectors)}")
    print(f"Vector dimension: {vectors.shape[1]}")

    # ============================================================
    # BUILD FAISS INDEX
    # ============================================================
    print("\nBuilding FAISS index...")

    index = faiss.IndexFlatL2(vectors.shape[1])
    index.add(vectors)

    faiss.write_index(index, INDEX_PATH)
    print(f"Saved FAISS index → {INDEX_PATH}")

    # ============================================================
    # SAVE META INFO
    # ============================================================
    with open(META_PATH, "w") as m:
        for entry in meta:
            m.write(json.dumps(entry) + "\n")

    print(f"Saved metadata → {META_PATH}")

    # ============================================================
    # SAVE SUMMARY INFO
    # ============================================================
    with open(INFO_PATH, "w") as info:
        info.write("Code Generation FAISS index built successfully.\n")
        info.write(f"Embedding model: {EMBED_MODEL}\n")
        info.write(f"Entries indexed: {len(vectors)}\n")
        info.write(f"Vector dimension: {vectors.shape[1]}\n")
        info.write("Embedding Target: PROMPTS (Problem Descriptions)\n")

    print(f"Saved info → {INFO_PATH}")
    print("\n🎉 Finished building Code Gen FAISS index!")

else:
    print(f"ERROR: Dataset not found at {DATASET_PATH}")
