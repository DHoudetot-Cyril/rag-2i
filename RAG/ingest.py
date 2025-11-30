import os
import json
import hashlib
from datetime import datetime
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct, Filter, FieldCondition, MatchValue
from sentence_transformers import SentenceTransformer

from docling.document_converter import DocumentConverter
from docling.chunking import HybridChunker

# -------------------
# CONFIGURATION
# -------------------
COLLECTION_NAME = "wiki_docs_production"
DATA_FOLDER = "./wiki"
MANIFEST_FILE = "manifest.json"
QDRANT_HOST = "qdrant"
QDRANT_PORT = 6333
EMBEDDING_MODEL_ID = "Qwen/Qwen3-Embedding-0.6B"
MAX_TOKENS = 512  # Align with model limit

SUPPORTED_EXTENSIONS = {
    ".doc", ".docx", ".pdf", ".md", ".txt", ".ppt", ".pptx", ".xlsx"
}

# -------------------
# INITIALIZATION
# -------------------
# 1. Vector DB
client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

# 2. Embedding Model
embedding_model = SentenceTransformer(EMBEDDING_MODEL_ID, trust_remote_code=True)

# 3. Docling Converter & Chunker
converter = DocumentConverter()
# HybridChunker uses the model's tokenizer to ensure chunks fit context window physically
chunker = HybridChunker(
    tokenizer=embedding_model.tokenizer,
    max_tokens=MAX_TOKENS,
    merge_peers=True  # Merges small semantic units (e.g. titles + paragraph)
)

# -------------------
# CORE FUNCTIONS
# -------------------
def init_collection():
    collections = [col.name for col in client.get_collections().collections]
    if COLLECTION_NAME not in collections:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=embedding_model.get_sentence_embedding_dimension(), distance=Distance.COSINE),
        )
        print(f"[Init] Collection '{COLLECTION_NAME}' created.")

def load_manifest():
    if os.path.exists(MANIFEST_FILE):
        with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def update_manifest(filepath, doc_hash, chunks_count):
    manifest = load_manifest()
    manifest[filepath] = {
        "hash": doc_hash,
        "ingested_at": datetime.now().isoformat(),
        "chunks_count": chunks_count
    }
    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=4)

def get_file_hash(filepath):
    hasher = hashlib.md5()
    with open(filepath, "rb") as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()

def process_file(filepath):
    # 1. Check processing necessity via Hash
    current_hash = get_file_hash(filepath)
    manifest = load_manifest()
    
    if filepath in manifest and manifest[filepath]["hash"] == current_hash:
        print(f"[Skip] {filepath} (Unchanged)")
        return

    print(f"[Processing] {filepath} ...")

    try:
        # 2. Docling Conversion
        doc_result = converter.convert(filepath)
        doc = doc_result.document
        
        # 3. Intelligent Chunking
        chunk_iter = chunker.chunk(doc)
        chunks_list = list(chunk_iter)
        
        if not chunks_list:
            print(f"[Warn] No chunks found in {filepath}")
            return

        # 4. Vectorization (Batch)
        texts = [chunk.text for chunk in chunks_list]
        # Qwen-3 typically works well without "passage:" prefix, adding purely for compatibility if needed
        embeddings = embedding_model.encode(texts, convert_to_numpy=True, show_progress_bar=False)

        # 5. Point Construction
        points = []
        file_name = os.path.basename(filepath)
        
        for i, (chunk, vector) in enumerate(zip(chunks_list, embeddings)):
            # Extract distinct page numbers from Docling provenance
            page_numbers = list(set([prov.page_no for prov in chunk.prov])) if chunk.prov else []
            
            # Deterministic ID generation
            point_id = int(hashlib.md5(f"{filepath}_{i}".encode()).hexdigest(), 16) % (10**18)
            
            payload = {
                "text": chunk.text,
                "file_path": filepath,
                "file_name": file_name,
                "page_numbers": page_numbers,
                "chunk_index": i,
                "is_table": any("Table" in str(type(item)) for item in chunk.meta.doc_items) if hasattr(chunk.meta, 'doc_items') else False
            }
            
            points.append(PointStruct(id=point_id, vector=vector.tolist(), payload=payload))

        # 6. Database Upsert
        # Delete old chunks for this file before upserting new ones to avoid ghosts
        client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=Filter(
                must=[FieldCondition(key="file_path", match=MatchValue(value=filepath))]
            )
        )
        
        client.upsert(collection_name=COLLECTION_NAME, points=points)
        update_manifest(filepath, current_hash, len(points))
        print(f"[Done] {filepath} -> {len(points)} chunks.")

    except Exception as e:
        print(f"[Error] Failed to process {filepath}: {e}")

# -------------------
# MAIN EXECUTION
# -------------------
if __name__ == "__main__":
    init_collection()
    
    if not os.path.exists(DATA_FOLDER):
        print(f"Folder {DATA_FOLDER} not found.")
        exit(1)

    for root, _, files in os.walk(DATA_FOLDER):
        for file in files:
            file_path = os.path.join(root, file)
            if Path(file_path).suffix.lower() in SUPPORTED_EXTENSIONS:
                process_file(file_path)