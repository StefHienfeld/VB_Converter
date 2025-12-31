# VB Converter Runbook

Operations handleiding voor beheer en troubleshooting van de VB Converter applicatie.

---

## Inhoudsopgave

1. [Health Checks](#health-checks)
2. [Startup & Shutdown](#startup--shutdown)
3. [Monitoring](#monitoring)
4. [Troubleshooting](#troubleshooting)
5. [Backup & Recovery](#backup--recovery)
6. [Security](#security)

---

## Health Checks

### Endpoints

| Endpoint | Doel | Verwachte Response |
|----------|------|-------------------|
| `/api/health` | Algemene status | `{"status": "healthy", "version": "3.1.0"}` |
| `/api/health/live` | Kubernetes liveness | `{"status": "alive"}` |
| `/api/health/ready` | Kubernetes readiness | `{"status": "ready", "checks": {...}}` |

### Handmatige check

```bash
# Lokaal
curl http://localhost:8000/api/health

# Docker
docker exec vb-backend curl http://localhost:8000/api/health

# Met jq voor leesbaarheid
curl -s http://localhost:8000/api/health | jq
```

### Readiness checks

De `/api/health/ready` endpoint controleert:
- SpaCy model geladen
- Cache service beschikbaar
- Geheugen < 90%

---

## Startup & Shutdown

### Docker Compose

```bash
# Start services
cd infrastructure/docker
docker-compose up -d

# Bekijk logs
docker-compose logs -f

# Stop services (behoud data)
docker-compose stop

# Stop en verwijder containers
docker-compose down

# Stop en verwijder ALLES (incl. volumes)
docker-compose down -v
```

### Individuele containers

```bash
# Backend herstarten
docker restart vb-backend

# Frontend herstarten
docker restart vb-frontend

# Forceer rebuild
docker-compose up -d --build --force-recreate
```

### Startup volgorde

1. Backend start eerst (depends_on in docker-compose)
2. Backend laadt SpaCy model (~30 sec)
3. Health check wordt groen
4. Frontend start en proxyt naar backend

---

## Monitoring

### Logs bekijken

```bash
# Alle logs
docker-compose logs -f

# Alleen backend
docker-compose logs -f backend

# Laatste 100 regels
docker-compose logs --tail=100 backend

# Met timestamp
docker-compose logs -t backend
```

### Resource gebruik

```bash
# Container stats
docker stats vb-backend vb-frontend

# Gedetailleerd
docker inspect vb-backend | jq '.[0].State'
```

### Metrics

Request metrics via logs:
```
INFO: Request ID: abc123 - GET /api/health - 200 - 15ms
INFO: Request ID: def456 - POST /api/analyze - 200 - 4523ms
```

### Rate limiting

Bij teveel requests:
```json
{"detail": "Too many requests. Please try again later."}
```

Default: 100 requests per minuut per IP.

---

## Troubleshooting

### Backend start niet

**Symptoom:** Container restart loop

**Check:**
```bash
docker logs vb-backend --tail=50
```

**Veelvoorkomende oorzaken:**

1. **SpaCy model niet gevonden**
   ```
   OSError: [E050] Can't find model 'nl_core_news_md'
   ```
   **Fix:** Rebuild image of manual download:
   ```bash
   docker exec vb-backend python -m spacy download nl_core_news_md
   ```

2. **Port al in gebruik**
   ```
   Address already in use
   ```
   **Fix:** Stop conflicterende service of wijzig poort in docker-compose.yml

3. **Geheugen te laag**
   ```
   MemoryError
   ```
   **Fix:** Verhoog Docker memory limit naar minimaal 2GB

### Frontend bereikt backend niet

**Symptoom:** 502 Bad Gateway of CORS errors

**Check:**
```bash
# Backend draait?
docker ps | grep backend

# Network OK?
docker network inspect docker_default
```

**Fix:**
1. Controleer `ALLOWED_ORIGINS` in .env
2. Controleer nginx proxy_pass URL
3. Herstart beide containers

### Analyse hangt

**Symptoom:** Lange analyse zonder voortgang

**Check:**
```bash
# CPU/Memory
docker stats vb-backend

# Actieve processen
docker exec vb-backend ps aux
```

**Mogelijke oorzaken:**
- Te groot bestand (>10MB Excel)
- Te veel teksten (>5000 rijen)
- Geheugen vol

**Fix:**
1. Splits grote bestanden
2. Verhoog container geheugen
3. Herstart backend

### Cache problemen

**Endpoint:** `/api/cache/stats`

**Clear cache:**
```bash
# Via API (indien geimplementeerd)
curl -X DELETE http://localhost:8000/api/cache

# Of herstart container
docker restart vb-backend
```

---

## Backup & Recovery

### Geen persistente data

Deze applicatie slaat geen data persistent op:
- Uploads zijn tijdelijk (in-memory of temp files)
- Analyses worden niet bewaard
- Configuratie komt uit environment variables

### Configuratie backup

```bash
# Backup .env
cp environments/.env environments/.env.backup

# Backup docker-compose overrides
cp infrastructure/docker/docker-compose.override.yml backup/
```

### Disaster recovery

1. Pull images opnieuw:
   ```bash
   docker-compose pull
   ```

2. Restore .env configuratie

3. Start services:
   ```bash
   docker-compose up -d
   ```

---

## Security

### Security headers

Alle responses bevatten:
- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `X-Request-ID: <uuid>` (voor tracing)

### Rate limiting

Configureerbaar via environment:
```
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60
```

### CORS

Alleen toegestane origins kunnen API aanroepen:
```
ALLOWED_ORIGINS=https://app.hienfeld.nl,http://localhost:5173
```

### Secrets beheer

**NOOIT in git:**
- `.env` files met secrets
- API keys
- Credentials

**Wel in git:**
- `.env.example` (template zonder waarden)

### Container security

- Non-root user in containers
- Read-only filesystem waar mogelijk
- Minimale base images (slim/alpine)
- Geen shell in production images (optioneel)

---

## Contact

Bij problemen die niet opgelost kunnen worden:
1. Check GitHub Issues
2. Maak nieuw issue met logs en stappen om te reproduceren
