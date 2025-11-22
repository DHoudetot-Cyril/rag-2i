FROM python:3.12-slim

# ---------------------------------------
# Dépendances système nécessaires à Docling
# ---------------------------------------
RUN apt-get update && apt-get install -y \
    libreoffice \
    poppler-utils \
    unrar-free \
    unzip \
    tesseract-ocr \
    ghostscript \
    libxml2 \
    libxslt1.1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------
# Installation Python
# ---------------------------------------
WORKDIR /app

COPY requirements.txt .

# Installer toutes les libs du projet + Docling complet
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir "docling[all]" --upgrade

# Copier le code
COPY . .

EXPOSE 8000

CMD ["uvicorn", "rag:app", "--host", "0.0.0.0", "--port", "8000"]
