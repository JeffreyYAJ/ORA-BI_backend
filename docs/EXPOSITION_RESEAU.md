# Exposer le backend à vos collègues (sans Docker)

## Principe

| Composant | Où tourne | Accessible par les collègues ? |
|-----------|-----------|--------------------------------|
| **API FastAPI** | Votre machine, `0.0.0.0:8000` | **Oui** (même réseau Wi‑Fi / LAN) |
| **PostgreSQL** | Votre machine, `localhost:5432` | **Non** (reste local, plus sûr) |

Les collègues pointent leur frontend vers `http://<VOTRE_IP>:8000`, pas vers votre base de données.

---

## 1. PostgreSQL en local

### Ubuntu / Debian

```bash
sudo apt update
sudo apt install -y postgresql postgresql-contrib
sudo systemctl enable --now postgresql
sudo -u postgres psql -f scripts/setup_postgres.sql
```

### macOS (Homebrew)

```bash
brew install postgresql@16
brew services start postgresql@16
createuser -s datapipe 2>/dev/null || true
createdb -O datapipe datapipe 2>/dev/null || true
```

Adaptez `DATABASE_URL` dans `.env` si utilisateur / mot de passe différents.

---

## 2. Configuration `.env`

```bash
cp .env.example .env
```

Minimum pour le partage en équipe :

```env
API_HOST=0.0.0.0
API_PORT=8000
CORS_ALLOW_ALL=true
```

Ou listez les frontends de vos collègues :

```env
CORS_ORIGINS=http://localhost:5173,http://192.168.1.42:5173,http://192.168.1.15:3000
CORS_ALLOW_ALL=false
```

---

## 3. Démarrer l’API

```bash
source .venv/bin/activate
alembic upgrade head
chmod +x scripts/run.sh
./scripts/run.sh
```

Équivalent manuel :

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 4. Trouver votre adresse IP

```bash
hostname -I | awk '{print $1}'
# ou
ip -4 addr show | grep inet
```

Exemple : `192.168.1.42`

---

## 5. Ce que vos collègues configurent

| Élément | Valeur exemple |
|---------|----------------|
| URL API REST | `http://192.168.1.42:8000/api/v1` |
| Swagger | `http://192.168.1.42:8000/docs` |
| WebSocket | `ws://192.168.1.42:8000/api/v1/ws/pipelines/{id}` |
| Health check | `http://192.168.1.42:8000/health` |

Test depuis le poste d’un collègue :

```bash
curl http://192.168.1.42:8000/health
```

---

## 6. Pare-feu (si connexion refusée)

### Linux (ufw)

```bash
sudo ufw allow 8000/tcp
sudo ufw status
```

### Windows

Autoriser le port **8000** entrant pour Python / uvicorn dans le pare-feu Windows.

---

## 7. Sécurité (MVP)

- Pas d’authentification sur l’API : limitez-vous au **réseau de confiance** (bureau, VPN).
- Ne pas exposer sur Internet sans reverse proxy + HTTPS + auth.
- PostgreSQL ne doit **pas** écouter sur `0.0.0.0` pour ce cas d’usage.

---

## Dépannage

| Problème | Piste |
|----------|--------|
| Collègue timeout | Pare-feu, mauvaise IP, API pas sur `0.0.0.0` |
| Erreur CORS navigateur | Ajouter l’URL du frontend dans `CORS_ORIGINS` ou `CORS_ALLOW_ALL=true` |
| `connection refused` DB | PostgreSQL arrêté ou mauvais `DATABASE_URL` |
| WebSocket échoue | Utiliser `ws://` et la même IP que l’API (pas `localhost` depuis un autre PC) |
