# RAG (Retrieval-Augmented Generation) Project

Ce projet implémente un système RAG (Retrieval-Augmented Generation) qui permet d'interroger intelligemment une base de connaissances documentaire. Le système utilise des techniques avancées de traitement du langage naturel pour fournir des réponses précises et contextuelles aux questions des utilisateurs.

## Architecture

Le projet est composé de deux composants principaux :
- Un système d'ingestion de documents (`ingest.py`)
- Une API de requête RAG (`rag.py`)

### Architecture Docker

Le projet utilise Docker Compose pour orchestrer plusieurs services :

#### Services Docker

1. **qdrant** (Base de données vectorielle)
   - Image : `qdrant/qdrant:latest`
   - Port : 6333
   - Rôle : Stockage et recherche des embeddings vectoriels
   - Volume : `./qdrant_data` pour la persistance des données

2. **llama** (Serveur LLM)
   - Image : `ghcr.io/ggerganov/llama.cpp:server`
   - Port : 8080
   - Rôle : Service de génération de texte utilisant le modèle Qwen3-30B
   - Configuration : 16 threads, contexte de 4096 tokens
   - Volume : `./models/BF16` contenant le modèle GGUF Qwen3-30B-A3B-Thinking-2507-GGUF

3. **rag_api** (API RAG principale)
   - Basée sur : `Python 3.12-slim`
   - Port : 8000
   - Rôle : API REST pour les requêtes RAG
   - Framework : Uvicorn/FastAPI
   - Dépendances : qdrant et llama
   - Variables d'environnement :
     - `QDRANT_HOST=qdrant`
     - `QDRANT_PORT=6333`
     - `LLAMA_SERVER=http://llama:8080/completion`

4. **bot_teams** (Bot Microsoft Teams)
   - Basée sur : `Python 3.12-slim`
   - Port : 3978
   - Rôle : Interface de chatbot Teams
   - Dépendances : rag_api
   - Configuration : Fichier `config.env`

#### Flux de Communication

```
[User] 
  ↓
[rag_api:8000] (FastAPI)
  ├─→ [qdrant:6333] (Recherche vectorielle)
  └─→ [llama:8080] (Génération de texte)
  ↓
[Réponse RAG]
```

## Test du POC en Local

Pour tester le système RAG localement, vous pouvez utiliser la commande curl suivante dans une invite de commande Windows :

```bash
curl -X POST "https://ruben-subdialectal-holoblastically.ngrok-free.dev/query" -H "Content-Type: application/json" -d "{\"question\": \"Que peux-tu me dire de l'Authentification Active Directory en Intranet\"}" -k
```

Vous pouvez également tester l'API avec Postman :
- Méthode : POST
- URL : `https://ruben-subdialectal-holoblastically.ngrok-free.dev/query`
- Headers :
	- `Content-Type: application/json`
- Body (raw, JSON) :
```json
{
	"question": "Que peux-tu me dire de l'Authentification Active Directory en Intranet"
}
```

![Image Postman](Readme_Attachments\image.png)

Cette commande envoie une requête POST à l'API avec une question exemple sur l'Authentification Active Directory.

## Structure du Projet

```
RAG/
├── config.env       # Configuration du projet
├── Dockerfile       # Configuration Docker
├── ingest.py        # Script d'ingestion des documents
├── rag.md           # Documentation détaillée
├── rag.py           # API principale
└── requirements.txt # Dépendances Python
```
