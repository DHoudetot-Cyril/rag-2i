import os
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
from openai import OpenAI

# ---------------------------
# Config
# ---------------------------
QDRANT_HOST = "qdrant"
QDRANT_PORT = 6333
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "wiki_docs")
EMBEDDING_MODEL = "intfloat/multilingual-e5-large"

# Config du LLM (compatible OpenAI API)
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://llama:8080/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "sk-1234")  # peu importe si local
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "qwen:latest")

TOP_K = 1

# Globals for lifespan
client = None
model = None
llm_client = None

# ---------------------------
# Lifespan (Startup/Shutdown)
# ---------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global client, model, llm_client
    
    print("Startup: Initialisation des clients et modèles...")
    
    # 1. Qdrant
    print(f"Connexion à Qdrant ({QDRANT_HOST}:{QDRANT_PORT})...")
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

    # 2. Embedding Model - FORCE CPU pour éviter les OOM/conflits GPU
    print(f"Chargement du modèle d'embedding {EMBEDDING_MODEL} (sur CPU)...")
    model = SentenceTransformer(EMBEDDING_MODEL, trust_remote_code=True, device="cpu")

    # 3. LLM Client
    print("Initialisation du client OpenAI compatible...")
    llm_client = OpenAI(
        api_key=LLM_API_KEY,
        base_url=LLM_BASE_URL
    )
    
    print("Startup: Terminé. Serveur prêt à recevoir des requêtes.")
    yield
    print("Shutdown: Nettoyage des ressources...")
    # Clean up if needed

# ---------------------------
# API
# ---------------------------
app = FastAPI(
    title="RAG API with Qdrant + OpenAI-Compatible LLM", 
    version="1.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    question: str
    min_score: float | None = 0.01


@app.get("/")
def root():
    return {"message": "RAG API with Qdrant + OpenAI LLM is running"}


@app.get("/documents")
def get_documents():
    manifest_file = "manifest.json"

    if os.path.exists(manifest_file):
        try:
            with open(manifest_file, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            
            # Transformation du dict en liste pour le frontend
            documents = []
            for file_path, data in manifest.items():
                doc = data.copy()
                doc["file_path"] = file_path
                doc["file_name"] = os.path.basename(file_path)
                documents.append(doc)
                
            return documents
        except Exception as e:
            return {"error": str(e)}
    return []


@app.post("/query")
def query_rag(req: QueryRequest):
    global model, client, llm_client

    if not model or not client or not llm_client:
        return {"error": "Server is still starting up, please try again in a few seconds."}

    # 1️ Embedding de la question
    query_vector = model.encode(f"query: {req.question}").tolist()

    # 2️ Recherche dans Qdrant
    hits = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        limit=TOP_K,
    )

    # 3️ Filtrer les résultats sous le seuil
    filtered_hits = [hit for hit in hits if hit.score >= req.min_score]

    if not filtered_hits:
        return {
            "question": req.question,
            "answer": "Aucun résultat suffisamment pertinent n’a été trouvé.",
            "files_used": [],
            "min_score": req.min_score
        }

    # 4️ Récupération du contexte et des métadonnées
    context = "\n\n".join([hit.payload["text"] for hit in filtered_hits if "text" in hit.payload])
    files_used = [
        {
            "file_path": hit.payload.get("file_path", ""),
            "file_date": hit.payload.get("file_date", ""),
            "score": hit.score
        }
        for hit in filtered_hits
    ]

    # 5️ Préparation du prompt
    prompt = f"""Tu es un assistant qui répond à des questions à partir des documents suivants. 
Si tu ne sais pas, n'invente pas. Limite-toi à 10 lignes.

Contexte :
{context}

Question : {req.question}
Réponse :
"""

    # 6️ Appel au modèle OpenAI-compatible
    try:
        completion = llm_client.chat.completions.create(
            model=LLM_MODEL_NAME,
            messages=[
                {"role": "system", "content": "Tu es un assistant utile et factuel, tu réponds uniquement en français."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=1024
        )
        answer = completion.choices[0].message.content.strip()

    except Exception as e:
        return {"error": f"Erreur lors de l'appel au modèle : {str(e)}"}

    # 7️ Réponse finale
    return {
        "question": req.question,
        "answer": answer,
        "files_used": files_used
    }
