import os
import hashlib
from datetime import datetime
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct, Filter, FieldCondition, MatchValue
from sentence_transformers import SentenceTransformer
from docling.document_converter import DocumentConverter

# -------------------
# CONFIG
# -------------------
COLLECTION_NAME = "wiki_docs"
DATA_FOLDER = "./wiki"  # dossier contenant les documents
QDRANT_HOST = "qdrant"
QDRANT_PORT = 6333

# Extensions de fichiers supportées
SUPPORTED_EXTENSIONS = {
    ".doc", ".docx", ".md", ".pdf", 
    ".ppt", ".pptx", ".txt", ".xls", 
    ".xlsx", ".msg"
}

# Docling converter
converter = DocumentConverter()

# Embedding model (e5-large-v2, 1024 dimensions, haute qualité)
embedding_model = SentenceTransformer("intfloat/e5-large-v2")

# Init Qdrant client
client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

# -------------------
# Créer la collection si elle n'existe pas
# -------------------
def init_collection():
    collections = [col.name for col in client.get_collections().collections]
    if COLLECTION_NAME not in collections:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
        )
        print(f" Collection '{COLLECTION_NAME}' créée")
    else:
        print(f"Collection '{COLLECTION_NAME}' déjà existante")
        
# -------------------
# Extraction de texte avec Docling
# -------------------
def extract_text_docling(filepath):
    """
    Extrait le texte du document en utilisant Docling
    Supporte : PDF, DOCX, PPTX, XLSX, DOC, PPT, XLS, TXT, MD, MSG
    """
    try:
        result = converter.convert(filepath)
        # Récupère le contenu en Markdown
        return result.document.export_to_markdown()
    except Exception as e:
        print(f"  Erreur lors de l'extraction avec Docling pour {filepath}: {e}")
        # Fallback : lecture simple pour les fichiers texte
        if filepath.endswith((".txt", ".md")):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e2:
                print(f"  Erreur fallback : {e2}")
        return None

# -------------------
# Chunking intelligent basé sur Docling
# -------------------
def chunk_text_docling(text, max_length=500):
    """
    Découpe le texte de manière intelligente en respectant les sections
    et les paragraphes (extraction de Docling)
    """
    if not text:
        return []
    
    # Découper par sections (tirets de niveau 1, 2, 3)
    chunks = []
    current_chunk = ""
    lines = text.split("\n")
    
    for line in lines:
        # Si on rencontre un titre et que le chunk actuel est trop long
        if line.strip().startswith("#") and len(current_chunk.split()) > max_length:
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
            current_chunk = line + "\n"
        else:
            current_chunk += line + "\n"
    
    # Ajouter le dernier chunk
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    # Si les chunks sont encore trop grands, les diviser par mots
    final_chunks = []
    for chunk in chunks:
        words = chunk.split()
        if len(words) > max_length:
            # Découper par mots si nécessaire
            for i in range(0, len(words), max_length):
                final_chunks.append(" ".join(words[i:i+max_length]))
        else:
            final_chunks.append(chunk)
    
    return final_chunks

# -------------------
# Vérifier si un fichier est déjà ingéré
# -------------------
def is_file_already_ingested(filepath):
    """
    Vérifie si un fichier a déjà été ingéré dans Qdrant
    en cherchant un point avec le même file_path dans le payload
    """
    try:
        points, _ = client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=Filter(
                must=[FieldCondition(key="file_path", match=MatchValue(value=filepath))]
            ),
            limit=1
        )
        return len(points) > 0
    except Exception as e:
        print(f"  Erreur lors de la vérification du fichier : {e}")
        return False

# -------------------
# Ingestion d'un fichier
# -------------------
def ingest_file(filepath):
    if is_file_already_ingested(filepath):
        print(f"  Fichier déjà ingéré : {filepath}")
        return

    # Extraire le texte avec Docling
    content = extract_text_docling(filepath)
    if not content:
        print(f"  Impossible d'extraire le contenu de {filepath}")
        return

    file_date = datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat()
    # Utiliser le chunking intelligent de Docling
    chunks = chunk_text_docling(content)
    
    if not chunks:
        print(f"  Aucun chunk généré pour {filepath}, fichier ignoré")
        return
    
    # Ajouter le préfixe "passage:" pour e5-large-v2 (recommandé pour les documents)
    chunks_with_prefix = [f"passage: {chunk}" for chunk in chunks]
    embeddings = embedding_model.encode(chunks_with_prefix, convert_to_numpy=True)

    points = []
    for i, (chunk, vector) in enumerate(zip(chunks, embeddings)):
        uid = int(hashlib.md5(f"{filepath}-{i}".encode()).hexdigest(), 16) % (10**18)
        points.append(
            PointStruct(
                id=uid,
                vector=vector.tolist(),
                payload={
                    "text": chunk,
                    "file_path": filepath,
                    "file_date": file_date
                }
            )
        )

    client.upsert(collection_name=COLLECTION_NAME, points=points)
    print(f"  Fichier ingéré : {filepath} ({len(chunks)} chunks)")


# -------------------
# Ingestion d'un dossier
# -------------------
def ingest_folder(folder_path):
    for root, _, files in os.walk(folder_path):
        for file in files:
            file_ext = Path(file).suffix.lower()
            if file_ext in SUPPORTED_EXTENSIONS:
                ingest_file(os.path.join(root, file))

# -------------------
# MAIN
# -------------------
if __name__ == "__main__":
    init_collection()
    print(f"\nFormats supportés : {', '.join(sorted(SUPPORTED_EXTENSIONS))}")
    print(f"Dossier source : {DATA_FOLDER}\n")
    ingest_folder(DATA_FOLDER)
    print("\n Ingestion terminée")
