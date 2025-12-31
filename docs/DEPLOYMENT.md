# VB Converter Deployment Guide

Complete handleiding voor het deployen van de VB Converter applicatie.

---

## Inhoudsopgave

1. [Vereisten](#vereisten)
2. [Environment Configuratie](#environment-configuratie)
3. [Lokale Development](#lokale-development)
4. [Docker Deployment](#docker-deployment)
5. [CI/CD Pipeline](#cicd-pipeline)
6. [Productie Checklist](#productie-checklist)

---

## Vereisten

### Systeem
- Docker 20.10+ en Docker Compose 2.0+
- 4GB RAM minimum (8GB aanbevolen voor SpaCy)
- 10GB disk space

### Development
- Python 3.11+
- Node.js 20+
- Git

---

## Environment Configuratie

### 1. Kopieer .env.example

```bash
cp environments/.env.example .env
```

### 2. Configureer essentiële variabelen

| Variabele | Vereist | Beschrijving |
|-----------|---------|--------------|
| `SECRET_KEY` | **Ja** | Random string voor security (min 32 chars) |
| `ENVIRONMENT` | Ja | `development`, `test`, `acceptance`, `production` |
| `ALLOWED_ORIGINS` | Ja | Comma-separated lijst van frontend URLs |
| `DEBUG` | Nee | `true` voor dev, `false` voor productie |

### 3. Genereer SECRET_KEY

```bash
# Linux/macOS
openssl rand -hex 32

# Windows PowerShell
[guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N")
```

### Environment-specifieke settings

**Development:**
```bash
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG
LOG_FORMAT=text
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
```

**Production:**
```bash
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
LOG_FORMAT=json
ALLOWED_ORIGINS=https://jouw-domein.nl
SECRET_KEY=<gegenereerde-key>
```

---

## Lokale Development

### Backend starten

```bash
# Virtuele environment aanmaken
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Dependencies installeren
pip install -r requirements.txt
pip install -r requirements-dev.txt

# SpaCy model downloaden
python -m spacy download nl_core_news_md

# Server starten
uvicorn hienfeld_api.app:app --reload --port 8000
```

### Frontend starten

```bash
npm install
npm run dev
```

Toegang:
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

---

## Docker Deployment

### Development Mode

```bash
cd infrastructure/docker
docker-compose up -d
```

Dit start:
- Backend op poort 8000
- Frontend op poort 3000
- Hot-reload enabled via volume mounts

### Production Mode

```bash
cd infrastructure/docker

# Met environment file
docker-compose -f docker-compose.prod.yml --env-file ../../.env up -d
```

### Images handmatig bouwen

```bash
# Backend
docker build -f infrastructure/docker/Dockerfile.backend -t vb-converter-backend .

# Frontend
docker build -f infrastructure/docker/Dockerfile.frontend \
  --build-arg VITE_ENVIRONMENT=production \
  --build-arg VITE_API_URL=https://api.jouw-domein.nl \
  -t vb-converter-frontend .
```

### Container management

```bash
# Status bekijken
docker-compose ps

# Logs volgen
docker-compose logs -f

# Herstarten
docker-compose restart

# Stoppen
docker-compose down

# Volledig opschonen (incl. volumes)
docker-compose down -v
```

---

## CI/CD Pipeline

### GitHub Actions Workflows

| Workflow | Trigger | Actie |
|----------|---------|-------|
| `ci.yml` | Push naar main/develop, PR | Lint, test, security scan, build images |
| `release.yml` | Tag `v*.*.*` | Build en push production images naar GHCR |

### CI Pipeline Stappen

1. **Backend Lint** - Black, Flake8 code style
2. **Backend Test** - Pytest met SpaCy model
3. **Security Scan** - safety, pip-audit, Trivy
4. **Frontend Lint** - ESLint, TypeScript check
5. **Frontend Build** - Vite production build
6. **Docker Build** - Build en push naar GHCR

### Release maken

```bash
# 1. Zorg dat main up-to-date is
git checkout main
git pull

# 2. Maak versie tag
git tag -a v3.2.0 -m "Release v3.2.0: Feature X, Fix Y"

# 3. Push tag
git push origin v3.2.0
```

De `release.yml` workflow bouwt automatisch:
- `ghcr.io/<repo>-backend:v3.2.0`
- `ghcr.io/<repo>-frontend:v3.2.0`

### Images ophalen

```bash
# Login bij GHCR
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin

# Pull images
docker pull ghcr.io/stefhienfeld/vb-converter-backend:latest
docker pull ghcr.io/stefhienfeld/vb-converter-frontend:latest
```

---

## Productie Checklist

### Pre-deployment

- [ ] `SECRET_KEY` gegenereerd en geconfigureerd
- [ ] `ENVIRONMENT=production` ingesteld
- [ ] `DEBUG=false` ingesteld
- [ ] `ALLOWED_ORIGINS` bevat alleen productie URLs
- [ ] `LOG_FORMAT=json` voor structured logging
- [ ] SSL/TLS certificaat geconfigureerd

### Security

- [ ] Geen hardcoded secrets in code
- [ ] `.env` file NIET in git
- [ ] Security headers actief (test met curl -I)
- [ ] Rate limiting geconfigureerd
- [ ] CORS correct ingesteld

### Monitoring

- [ ] Health endpoint bereikbaar: `/api/health`
- [ ] Liveness probe: `/api/health/live`
- [ ] Readiness probe: `/api/health/ready`
- [ ] Logging geconfigureerd

### Performance

- [ ] Minimaal 4GB RAM voor backend container
- [ ] SpaCy model succesvol geladen (check readiness)
- [ ] Rate limiting niet te restrictief

### Backup

- [ ] `.env` file gebackupt (veilige locatie)
- [ ] Docker volumes indien nodig

---

## Troubleshooting

### SpaCy model laadt niet

```bash
# Check of model aanwezig is
docker exec vb-backend python -c "import spacy; spacy.load('nl_core_news_md')"

# Handmatig downloaden
docker exec vb-backend python -m spacy download nl_core_news_md
```

### Container start niet

```bash
# Check logs
docker logs vb-backend --tail=50

# Check resource usage
docker stats
```

### CORS errors

1. Check `ALLOWED_ORIGINS` in .env
2. Zorg dat protocol (http/https) klopt
3. Check of frontend URL exact overeenkomt

### Rate limiting problemen

Verhoog limits in .env:
```bash
RATE_LIMIT_REQUESTS=200
RATE_LIMIT_WINDOW=60
```

---

## Support

Bij problemen:
1. Check [docs/RUNBOOK.md](RUNBOOK.md) voor operations procedures
2. Check GitHub Issues
3. Controleer logs via `docker-compose logs`
