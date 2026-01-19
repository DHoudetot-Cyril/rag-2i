# Manuel d'Utilisation - RAG-2i

## 1. Introduction

Bienvenue dans le manuel de **RAG-2i**. Ce logiciel est une solution de **Retrieval-Augmented Generation (RAG)** conçue pour vous permettre d'interroger votre base de connaissances interne (fichiers PDF, Word, etc.) en langage naturel.

**Proposition de valeur :**
- **Gain de temps** : Trouvez instantanément l'information pertinente sans ouvrir manuellement des dizaines de fichiers.
- **Réponses factuelles** : Le système génère des réponses basées *uniquement* sur vos documents, réduisant les hallucinations.
- **Transparence** : Chaque réponse cite les documents sources utilisés.

**Public visé :**
- Utilisateurs finaux (pour la recherche d'information).
- Administrateurs (pour l'alimentation de la base documentaire).

---

## 2. Prérequis / Exigences du système

Avant de commencer, assurez-vous de disposer de l'environnement suivant :

### Matériel
- **Processeur** : CPU moderne (Intel i5/i7 ou AMD Ryzen).
- **Carte Graphique (Recommandé)** : NVIDIA GPU avec support CUDA pour accélérer l'ingestion des documents.
- **RAM** : 24 Go minimum recommandés.

### Logiciel
- **Docker & Docker Compose** : Pour exécuter la base de données vectorielle (Qdrant) et l'API.
- **NVIDIA Container Toolkit** : Indispensable pour que Docker puisse utiliser le GPU.
- **Llama.cpp** : Pour exécuter le modèle de langage localement.
- **Accès réseau** : Ports 6333 (Qdrant) et 8080 (LLM) doivent être libres.
- **Ngrok (Optionnel)** : Peut être utilisé pour rendre l'interface accessible depuis l'extérieur.

---

## 3. Installation / Démarrage

Suivez ces étapes pour mettre en place le système RAG-2i.

### Étape 0 : Préparation des documents
Avant toute chose, vous devez organiser les documents que le système doit ingérer.
1. Créez un dossier `wiki` à la racine du projet.
2. À l'intérieur, organisez vos fichiers dans les sous-dossiers correspondants aux niveaux d'accès (ex: `niveau1-usagers`, `niveau2-direction`).
3. Déposez-y vos fichiers (`.pdf`, `.docx`, `.pptx`).

### Étape 1 : Lancement du modèle LLM (LlamaCPP)
Le modèle de langage doit tourner en tâche de fond. Lancez `llama-server` avec la commande suivante :

```bash
./bin/llama-server \
  --model /home/pfeiris/Bureau/rag-2i/models/Qwen3-30B-A3B-Thinking-2507-Q4_K_M.gguf \
  --n-gpu-layers 99 \
  --ctx-size 8192 \
  --host 0.0.0.0 \
  --port 8080
```
*Assurez-vous que le chemin vers le fichier `.gguf` est correct sur votre machine.*

### Étape 2 : Lancement des services Docker
Démarrez l'infrastructure (Base de données vectorielle et API) :
```bash
docker-compose up -d
```

### Étape 3 : Alimentation de la base (Ingestion)
C'est l'étape cruciale pour que le système "apprenne" vos documents. Exécutez le script d'ingestion directement dans le conteneur Docker :
```bash
sudo docker exec -it rag_api_usagers python ingest_with_nvidia.py
```
*Le script va traiter les fichiers présents dans le dossier `wiki` (monté dans le conteneur), créer les embeddings et générer le fichier `manifest.json`.*

### Étape 4 : Utilisation
Une fois le script d'ingestion terminé (message "Done" ou invite de commande revenue), l'API est automatiquement à jour car elle lit le `manifest.json` fraîchement créé.

Vous pouvez accéder à l'interface web (généralement sur `http://localhost:5173`).
> **Note** : L'URL de l'API utilisée par le frontend est à configurer dans le fichier [frontend/vite.config.js](file:///c:/Users/cyrd6/OneDrive/Documents/rag-2i/frontend/vite.config.js) (section `proxy`).

---

## 4. Interface Utilisateur / Fonctionnalités Clés

### Recherche Documentaire (Web)
L'interface web est votre point d'entrée principal.
- **Zone de question** : Posez votre question en français courant (ex: *"Quelles sont les modalités de télétravail ?"*).
- **Réponse** : Le système vous répond en 10 lignes maximum, de manière factuelle.
- **Sources** : La liste des fichiers utilisés pour construire la réponse est affichée.

### Consultation du catalogue
- L'onglet **Documents** affiche la liste de tous les fichiers actuellement indexés et disponibles pour la recherche (basé sur `manifest.json`).

---

## 5. Gestion des erreurs / FAQ

### Q: Je ne vois pas mes documents sur la page web.
**R:** Vérifiez que le script d'ingestion (Étape 3) s'est bien terminé et a créé le fichier `manifest.json`. L'API lit ce fichier pour lister les documents. Relancez la commande `docker exec` si vous avez ajouté de nouveaux fichiers.

### Q: J'ai une erreur de "Tensor size mismatch" ou de "Token limit".
**R:** Le modèle d'embedding utilisé (`e5-large`) est limité à 512 tokens. Le script est configuré pour respecter cette limite. Assurez-vous d'avoir la dernière version de [ingest_with_nvidia.py](file:///c:/Users/cyrd6/OneDrive/Documents/rag-2i/RAG/ingest_with_nvidia.py).

### Q: Le système répond "Désolé, je ne trouve pas d'information pertinente".
**R:** Cela signifie que la réponse n'est pas explicitement dans vos documents. Le système a pour consigne stricte de ne pas inventer.

---

## 6. Glossaire

- **Embedding** : Conversion d'un texte en une liste de nombres (vecteur).
- **Ingestion** : Processus de lecture et d'indexation des documents.
- **LlamaCPP** : Logiciel permettant de faire tourner des modèles d'IA sur des ordinateurs standards.
- **Qdrant** : Base de données vectorielle stockant les index de vos documents.
