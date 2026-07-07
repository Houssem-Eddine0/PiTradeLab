# 1. On passe sur Python 3.11, car les paquets pré-compilés (wheels) pour ARMv6
# sont beaucoup plus stables et complets que sur la 3.12 pour le moment.
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# ... (début du fichier identique)

# 2. On installe les outils de base et les librairies de développement C
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libssl-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# ... (suite du fichier identique)

# Choix du fichier de dépendances :
#   PC  : REQ=requirements.txt     (avec scikit-learn, pour entraîner)
#   Pi  : REQ=requirements-pi.txt  (sans scikit-learn, inférence numpy)
ARG REQ=requirements.txt

# Dépendances d'abord (cache de build)
COPY requirements*.txt ./

# 3. LA LIGNE MAGIQUE : on ajoute piwheels pour dire à pip de télécharger 
# les versions déjà compilées pour le Raspberry Pi.
RUN pip install --no-cache-dir --extra-index-url https://www.piwheels.org/simple -r ${REQ}

# Code applicatif
COPY app ./app
COPY web ./web

RUN mkdir -p data

EXPOSE 8000

# 1 seul worker : tout l'état (threads collector/trader/ML, SQLite) vit dans le process.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]