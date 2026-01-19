# RAG-2i : Assistant Documentaire Intelligent

**RAG-2i** est un système de **Retrieval-Augmented Generation (RAG)** conçu pour interroger une base de connaissances documentaire interne en toute confidentialité. Il combine la puissance des LLMs locaux avec une base de données vectorielle pour fournir des réponses factuelles et sourcées.

## 🚀 Fonctionnalités
- **Chat en langage naturel** : Posez vos questions en français.
- **Sources citées** : Chaque réponse indique précisément les documents utilisés.
- **Architecture Locale** : Vos données ne sortent pas de votre infrastructure (sauf si configuré autrement).
- **Multi-formats** : Support des fichiers PDF, DOCX, PPTX.

## 🛠 Stack Technique
- **Frontend** : React + Vite
- **Backend API** : FastAPI (Python)
- **Base Vectorielle** : Qdrant (Docker)
- **Ingestion (OCR/Parsing)** : Docling + SentenceTransformers (GPU recommandé)
- **LLM** : Llama.cpp (Qwen 30B - ou autre modèle GGUF)

## 📋 Prérequis Rapides
- **GPU NVIDIA** (Recommandé avec `nvidia-container-toolkit`)
- **RAM** : 24 Go minimum
- **Docker & Docker Compose**
- **Python 3.10+**

## ⚡ Quick Start

Pour une installation détaillée, voir le [Manuel d'Utilisation](./MANUEL_UTILISATION.md).

1. **Préparer les données** :
   Placez vos documents dans le dossier `wiki/` (ex: `wiki/niveau1-usagers/`).

2. **Lancer le LLM** :
   ```bash
   ./bin/llama-server --model <votre_modele.gguf> --port 8080 ...
   ```

3. **Démarrer l'infrastructure** :
   ```bash
   docker-compose up -d
   ```

4. **Ingérer les documents** :
   ```bash
   sudo docker exec -it rag_api_usagers python ingest_with_nvidia.py
   ```

5. **Accéder à l'interface** :
   Rendez-vous sur `http://localhost:5173`.

## 📚 Documentation
- [Manuel d'Utilisation](./MANUEL_UTILISATION.md) : Guide complet d'installation et de dépannage.
- [API Docs](http://localhost:8000/docs) : Documentation Swagger de l'API.

## 👤 Auteur
Projet développé pour RAG-2i.
