import os
import json
import hashlib
import subprocess
import torch
from datetime import datetime
from pathlib import Path

# --- CLIENTS & MODELS ---
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct, Filter, FieldCondition, MatchValue
from sentence_transformers import SentenceTransformer

# --- DOCLING V2 IMPORTS ---
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.chunking import HybridChunker
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions, 
    AcceleratorOptions, 
    AcceleratorDevice
)

# -------------------
# CONFIGURATION
# -------------------
COLLECTION_USAGERS = "wiki_usagers"
COLLECTION_DIRECTION = "wiki_direction"
DATA_FOLDER = os.getenv("DATA_FOLDER", "./wiki")

FOLDER_MAPPING = {
    "niveau1-usagers": COLLECTION_USAGERS,
    "niveau2-direction": COLLECTION_DIRECTION
}

MANIFEST_FILE = "manifest.json"
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost") 
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
EMBEDDING_MODEL_ID = "jinaai/jina-embeddings-v3"
MAX_TOKENS = 8192

SUPPORTED_EXTENSIONS = {
    ".doc", ".docx", ".pdf", ".md", ".txt", ".ppt", ".pptx", ".xlsx"
}

# -------------------
# INITIALISATION
# -------------------
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
print(f"[Init] Peripherique d'inference detecte : {DEVICE.upper()}")
if DEVICE == "cuda":
    print(f"[Init] GPU : {torch.cuda.get_device_name(0)}")

print("[Init] Connexion a Qdrant...")
client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

print("[Init] Chargement du modele d'embedding...")
embedding_model = SentenceTransformer(
    EMBEDDING_MODEL_ID, 
    trust_remote_code=True, 
    device=DEVICE 
)
embedding_model.max_seq_length = MAX_TOKENS

print("[Init] Configuration de Docling (OCR & Layout)...")
accelerator_options = AcceleratorOptions(
    num_threads=8, 
    device=AcceleratorDevice.CUDA if DEVICE == "cuda" else AcceleratorDevice.AUTO
)

pipeline_options = PdfPipelineOptions(accelerator_options=accelerator_options)
# --- OPTIMISATION VITESSE ---
pipeline_options.do_ocr = False  # Lecture rapide du texte natif
pipeline_options.do_table_structure = True 

converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
    }
)

chunker = HybridChunker(
    tokenizer=embedding_model.tokenizer,
    max_tokens=MAX_TOKENS,
    merge_peers=True
)

# -------------------
# FONCTIONS UTILITAIRES
# -------------------
def convert_doc_to_docx(filepath):
    print(f"[Convert] {filepath} -> .docx")
    out_dir = os.path.dirname(filepath)
    cmd = ["libreoffice", "--headless", "--convert-to", "docx", filepath, "--outdir", out_dir]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        expected_path = os.path.splitext(filepath)[0] + ".docx"
        return expected_path if os.path.exists(expected_path) else None
    except Exception as e:
        print(f"[Error] Conversion echouee pour {filepath}: {e}")
        return None

def regrouper_chunks(chunks_list, min_words=300, max_words=500):
    """Fusionne les petits chunks pour atteindre une taille cible."""
    regrouped_chunks = []
    current_buffer = []
    current_word_count = 0
    current_meta_start = None 

    for chunk in chunks_list:
        text = chunk.text.strip()
        if not text:
            continue
            
        words = len(text.split())
        
        if not current_buffer:
            current_meta_start = chunk 
        
        if current_word_count + words > (max_words + 50): 
            full_text = "\n\n".join(current_buffer)
            regrouped_chunks.append({
                "text": full_text,
                "original_chunk": current_meta_start
            })
            current_buffer = [text]
            current_word_count = words
            current_meta_start = chunk
        else:
            current_buffer.append(text)
            current_word_count += words
            
            if min_words <= current_word_count:
                full_text = "\n\n".join(current_buffer)
                regrouped_chunks.append({
                    "text": full_text,
                    "original_chunk": current_meta_start
                })
                current_buffer = []
                current_word_count = 0
                current_meta_start = None

    # Sécurité pour les petits fichiers ou la fin des gros fichiers
    if current_buffer:
        full_text = "\n\n".join(current_buffer)
        regrouped_chunks.append({
            "text": full_text,
            "original_chunk": current_meta_start
        })

    return regrouped_chunks

def init_collections():
    existing_collections = [col.name for col in client.get_collections().collections]
    targets = [COLLECTION_USAGERS, COLLECTION_DIRECTION]
    
    for col_name in targets:
        if col_name not in existing_collections:
            client.create_collection(
                collection_name=col_name,
                vectors_config=VectorParams(size=embedding_model.get_sentence_embedding_dimension(), distance=Distance.COSINE),
            )
            print(f"[Init] Collection '{col_name}' creee.")
        else:
            print(f"[Init] Collection '{col_name}' existe deja.")

def load_manifest():
    if os.path.exists(MANIFEST_FILE):
        with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def update_manifest(filepath, doc_hash, chunks_count, collection_name):
    manifest = load_manifest()
    manifest[filepath] = {
        "hash": doc_hash,
        "ingested_at": datetime.now().isoformat(),
        "chunks_count": chunks_count,
        "collection": collection_name 
    }
    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=4)

def get_file_hash(filepath):
    hasher = hashlib.md5()
    with open(filepath, "rb") as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()

def get_target_collection(filepath):
    path_str = str(filepath).replace('\\', '/')
    for folder_key, collection_name in FOLDER_MAPPING.items():
        if folder_key in path_str:
            return collection_name
    return None

# -------------------
# PROCESSUS PRINCIPAL
# -------------------
def process_file(filepath):
    target_collection = get_target_collection(filepath)
    if not target_collection:
        return

    current_hash = get_file_hash(filepath)
    manifest = load_manifest()
    
    if (filepath in manifest and 
        manifest[filepath]["hash"] == current_hash and 
        manifest[filepath].get("collection") == target_collection):
        print(f"[Skip] {filepath} (Inchange)")
        return

    print(f"[Processing] {filepath} -> {target_collection}")

    actual_filepath = filepath
    temp_docx = None
    if filepath.lower().endswith(".doc"):
        temp_docx = convert_doc_to_docx(filepath)
        if temp_docx:
            actual_filepath = temp_docx
        else:
            return

    try:
        # 1. Extraction (Rapide)
        doc_result = converter.convert(actual_filepath)
        doc = doc_result.document
        
        # 2. Chunking Brut
        chunk_iter = chunker.chunk(doc)
        raw_chunks = list(chunk_iter)
        
        if not raw_chunks:
            print(f"[Warn] Aucun texte trouve dans {filepath}")
            return

        # 3. Regroupement Intelligent
        grouped_chunks = regrouper_chunks(raw_chunks, min_words=300, max_words=500)
        
        # 4. Vectorisation GPU
        texts = [g["text"] for g in grouped_chunks]
        embeddings = embedding_model.encode(
            texts, 
            convert_to_numpy=True, 
            show_progress_bar=False,
            task="retrieval.passage"
        )

        # 5. Préparation des points
        points = []
        file_name = os.path.basename(filepath)
        
        for i, (group, vector) in enumerate(zip(grouped_chunks, embeddings)):
            point_id = int(hashlib.md5(f"{filepath}_{i}".encode()).hexdigest(), 16) % (10**18)
            
            # Gestion numero de page
            original = group["original_chunk"]
            page_no = -1
            if original and original.meta and original.meta.doc_items:
                first_item = original.meta.doc_items[0]
                if hasattr(first_item, "prov") and first_item.prov:
                    page_no = first_item.prov[0].page_no

            payload = {
                "text": group["text"],
                "file_path": filepath,
                "file_name": file_name,
                "category": "usagers" if target_collection == COLLECTION_USAGERS else "direction",
                "chunk_index": i,
                "page_number": page_no,
                "is_table": False
            }
            points.append(PointStruct(id=point_id, vector=vector.tolist(), payload=payload))

        # 6. Envoi Sécurisé par Batchs (ROBUSTESSE AJOUTÉE)
        client.delete(
            collection_name=target_collection,
            points_selector=Filter(
                must=[FieldCondition(key="file_path", match=MatchValue(value=filepath))]
            )
        )
        
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            client.upsert(collection_name=target_collection, points=batch)
        
        update_manifest(filepath, current_hash, len(points), target_collection)
        print(f"[Done] {filepath} ({len(points)} chunks)")

    except Exception as e:
        print(f"[Error] Echec sur {filepath}: {e}")
    finally:
        if temp_docx and os.path.exists(temp_docx):
            os.remove(temp_docx)

if __name__ == "__main__":
    init_collections()
    if not os.path.exists(DATA_FOLDER):
        print(f"[Error] Dossier {DATA_FOLDER} introuvable.")
        exit(1)

    print(f"[Start] Scan de '{DATA_FOLDER}'...")
    for root, _, files in os.walk(DATA_FOLDER):
        for file in files:
            file_path = os.path.join(root, file)
            if Path(file_path).suffix.lower() in SUPPORTED_EXTENSIONS and not file.startswith("~$"):
                process_file(file_path)