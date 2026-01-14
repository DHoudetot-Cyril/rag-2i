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

# --- DOCLING V2 IMPORTS (CORRIGÉS) ---
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
# Noms des deux collections Qdrant
COLLECTION_USAGERS = "wiki_usagers"
COLLECTION_DIRECTION = "wiki_direction"

# Dossier racine
DATA_FOLDER = os.getenv("DATA_FOLDER", "./wiki")

# Mapping : Partie du chemin -> Nom de la collection
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
# 1. Detection du GPU
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
print(f"[Init] Peripherique d'inference detecte : {DEVICE.upper()}")
if DEVICE == "cuda":
    print(f"[Init] GPU : {torch.cuda.get_device_name(0)}")

print("[Init] Connexion a Qdrant...")
client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

print("[Init] Chargement du modele d'embedding...")
# On charge le modele sur le GPU
embedding_model = SentenceTransformer(
    EMBEDDING_MODEL_ID, 
    trust_remote_code=True, 
    device=DEVICE 
)
embedding_model.max_seq_length = MAX_TOKENS

# 2. Configuration Docling pour GPU
print("[Init] Configuration de Docling (OCR & Layout)...")
accelerator_options = AcceleratorOptions(
    num_threads=8, 
    device=AcceleratorDevice.CUDA if DEVICE == "cuda" else AcceleratorDevice.AUTO
)

# Utilisation de PdfPipelineOptions pour les PDF
pipeline_options = PdfPipelineOptions(accelerator_options=accelerator_options)
pipeline_options.do_ocr = True
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
    """Convertit un .doc en .docx via LibreOffice."""
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

def init_collections():
    """Initialise les collections si elles n'existent pas."""
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
    """Determine la collection cible en fonction du dossier parent."""
    path_str = str(filepath).replace('\\', '/')
    for folder_key, collection_name in FOLDER_MAPPING.items():
        if folder_key in path_str:
            return collection_name
    return None

# -------------------
# COEUR DU TRAITEMENT
# -------------------
def process_file(filepath):
    # 1. Verification de la collection cible
    target_collection = get_target_collection(filepath)
    if not target_collection:
        return

    # 2. Verification du Hash
    current_hash = get_file_hash(filepath)
    manifest = load_manifest()
    
    if (filepath in manifest and 
        manifest[filepath]["hash"] == current_hash and 
        manifest[filepath].get("collection") == target_collection):
        print(f"[Skip] {filepath} (Inchange)")
        return

    print(f"[Processing] {filepath} -> {target_collection}")

    # 3. Gestion conversion .doc
    actual_filepath = filepath
    temp_docx = None
    if filepath.lower().endswith(".doc"):
        temp_docx = convert_doc_to_docx(filepath)
        if temp_docx:
            actual_filepath = temp_docx
        else:
            return

    try:
        # 4. Conversion Docling
        # Docling utilise maintenant les options GPU definies plus haut
        doc_result = converter.convert(actual_filepath)
        doc = doc_result.document
        
        # 5. Decoupage intelligent
        chunk_iter = chunker.chunk(doc)
        chunks_list = list(chunk_iter)
        
        if not chunks_list:
            print(f"[Warn] Aucun texte trouve dans {filepath}")
            return

        # 6. Vectorisation (Embedding)
        texts = [chunk.text for chunk in chunks_list]
        
        embeddings = embedding_model.encode(
            texts, 
            convert_to_numpy=True, 
            show_progress_bar=False,
            task="retrieval.passage"
        )

        # 7. Construction des Points Qdrant
        points = []
        file_name = os.path.basename(filepath)
        
        for i, (chunk, vector) in enumerate(zip(chunks_list, embeddings)):
            point_id = int(hashlib.md5(f"{filepath}_{i}".encode()).hexdigest(), 16) % (10**18)
            
            payload = {
                "text": chunk.text,
                "file_path": filepath,
                "file_name": file_name,
                "category": "usagers" if target_collection == COLLECTION_USAGERS else "direction",
                "chunk_index": i,
                "is_table": False
            }
            points.append(PointStruct(id=point_id, vector=vector.tolist(), payload=payload))

        # 8. Mise a jour base de donnees
        client.delete(
            collection_name=target_collection,
            points_selector=Filter(
                must=[FieldCondition(key="file_path", match=MatchValue(value=filepath))]
            )
        )
        
        client.upsert(collection_name=target_collection, points=points)
        update_manifest(filepath, current_hash, len(points), target_collection)
        print(f"[Done] {filepath} ({len(points)} chunks)")

    except Exception as e:
        print(f"[Error] Echec sur {filepath}: {e}")
    finally:
        if temp_docx and os.path.exists(temp_docx):
            os.remove(temp_docx)

# -------------------
# MAIN EXECUTION
# -------------------
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