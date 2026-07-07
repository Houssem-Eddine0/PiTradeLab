# Déployer PiTradeLab sur un Raspberry Pi Zero (v1 / W)

Le Pi Zero (ARMv6, 512 Mo, 1 cœur) **ne peut pas compiler** numpy/pandas/pydantic-core :
on **construit l'image sur le PC** puis on l'**envoie déjà prête** au Pi.

---

## 1. Sur le PC (une fois) — construire l'image

Prérequis : **Docker Desktop** (backend WSL2) démarré.

```powershell
# depuis le dossier du projet
powershell -ExecutionPolicy Bypass -File build-pi.ps1
```

Le script :
1. active l'émulation ARM (QEMU),
2. construit l'image **ARMv6** via `Dockerfile.pi` (base Raspbian ARMv6 + wheels piwheels, donc **aucune compilation**),
3. exporte le tout dans **`pitradelab-pi.tar`**.

> L'émulation ARMv6 est lente : compte ~5–15 min la première fois.
> Équivalent manuel si tu préfères sans script :
> ```
> docker run --privileged --rm tonistiigi/binfmt --install arm
> docker buildx create --name pizero --driver docker-container --use
> docker buildx build --platform linux/arm/v6 -f Dockerfile.pi -t pitradelab:pi --output type=docker,dest=pitradelab-pi.tar .
> ```

---

## 2. Envoyer sur le Pi

Remplace `<IP>` par l'adresse de ton Pi (ex. `192.168.1.42`) :

```bash
ssh pi@<IP> "mkdir -p ~/pitradelab"
scp pitradelab-pi.tar docker-compose.pi.yml .env  pi@<IP>:~/pitradelab/
```

> `.env` contient ta clé Gemini (optionnelle). S'il n'existe pas, copie `.env.example` en `.env`.
> Le transfert du `.tar` (~400–500 Mo) peut être long sur le Wi-Fi du Pi Zero.

---

## 3. Sur le Pi (une fois) — installer Docker si besoin

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER   # puis se déconnecter/reconnecter
```

---

## 4. Sur le Pi — charger et lancer

```bash
cd ~/pitradelab
docker load -i pitradelab-pi.tar
docker compose -f docker-compose.pi.yml up -d
```

Dashboard : **http://\<IP\>:8000**

Ça tourne en continu (`restart: unless-stopped`), même après reboot. Rien d'autre à faire.

---

## 5. Machine Learning sur le Pi

Le Pi fait **l'inférence** (numpy pur), pas l'entraînement. Sur le **PC** :

```bash
docker compose up            # ou lancer l'app en local
# entraîne les modèles depuis l'onglet 📈 Apprentissage → bouton « Entraîner »
```

Les modèles sont écrits dans `data/models/<actif>.json`. Copie-les sur le Pi :

```bash
scp data/models/*.json  pi@<IP>:~/pitradelab/data/models/
```

Le Pi les charge automatiquement au cycle suivant (proba affichée dans 📈 Apprentissage,
et prise en compte si `ML_WEIGHT > 0`).

---

## Mettre à jour plus tard

Rebuild sur PC (`build-pi.ps1`), recopie le `.tar`, puis sur le Pi :

```bash
docker load -i pitradelab-pi.tar
docker compose -f docker-compose.pi.yml up -d   # recrée le conteneur avec la nouvelle image
```

---

## Dépannage

- **`exec format error` / « illegal instruction »** au démarrage → l'image n'est pas ARMv6.
  Vérifie que tu as bien buildé avec `--platform linux/arm/v6` et `Dockerfile.pi` (base balenalib).
- **Le Pi rame / OOM** → c'est un Pi Zero (512 Mo). Réduis à 1–2 actifs (page Configuration),
  garde `ML_TRAIN_ENABLED=false`, et une seule aventure. `mem_limit` est déjà posé à 450 Mo.
- **Build très lent** → normal (émulation). Il n'est fait qu'une fois sur le PC.
