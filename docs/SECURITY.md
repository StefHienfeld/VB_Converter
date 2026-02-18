# Security Procedures

Dit document beschrijft de beveiligingsmaatregelen en procedures voor de VB Converter applicatie.

---

## Inhoudsopgave

1. [Secret Management](#secret-management)
2. [JWT Authenticatie](#jwt-authenticatie)
3. [CORS Beleid](#cors-beleid)
4. [Rate Limiting](#rate-limiting)
5. [Security Headers](#security-headers)
6. [Input Validatie](#input-validatie)
7. [GDPR Compliance](#gdpr-compliance)
8. [Incident Response](#incident-response)

---

## Secret Management

### Overzicht

| Secret Type | Opslag | Rotatie |
|-------------|--------|---------|
| `SECRET_KEY` | Environment variable | Elke 90 dagen |
| Database credentials | Environment variable | Elke 90 dagen |
| API tokens | Environment variable | Bij compromittering |

### Secret Generatie

```bash
# Genereer een veilige SECRET_KEY (32 bytes hex)
# Linux/macOS:
openssl rand -hex 32

# Windows PowerShell:
[System.Convert]::ToBase64String([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32))

# Python:
python -c "import secrets; print(secrets.token_hex(32))"
```

### Environment Variables

**Vereiste variabelen voor productie:**

```env
# VERPLICHT
SECRET_KEY=<64-char-hex-string>
ENVIRONMENT=production
DEBUG=false

# Database
DATABASE_URL=postgresql://user:password@host:5432/dbname

# CORS
ALLOWED_ORIGINS=https://jouw-domein.nl
```

### Verboden Praktijken

**NOOIT:**
- Secrets committen naar git (ook niet in comments)
- Secrets loggen of printen
- Secrets hardcoden in code
- `.env` files delen via email/Slack
- Default/test secrets gebruiken in productie

**Detectie in git:**
```bash
# Check voor mogelijke secrets in git history
git log -p | grep -E "(SECRET|KEY|PASSWORD|TOKEN)" | head -50

# Gebruik git-secrets voor preventie
git secrets --install
git secrets --register-aws
```

### Secret Rotatie Procedure

1. **Genereer nieuwe secret**
   ```bash
   NEW_SECRET=$(openssl rand -hex 32)
   ```

2. **Update in secret manager/environment**

3. **Deploy nieuwe versie**

4. **Verifieer applicatie werkt**

5. **Revoke oude secret** (indien extern)

---

## JWT Authenticatie

### Overzicht

De applicatie gebruikt JWT (JSON Web Tokens) voor authenticatie:

```
+--------+                              +--------+
| Client |                              | Server |
+---+----+                              +---+----+
    |                                       |
    | POST /api/auth/login                  |
    | {username, password}                  |
    |-------------------------------------->|
    |                                       |
    |     {access_token, refresh_token}     |
    |<--------------------------------------|
    |                                       |
    | GET /api/analyze                      |
    | Authorization: Bearer <access_token>  |
    |-------------------------------------->|
    |                                       |
    |     {results}                         |
    |<--------------------------------------|
```

### Token Configuratie

| Parameter | Waarde | Beschrijving |
|-----------|--------|--------------|
| Algorithm | HS256 | HMAC-SHA256 |
| Access Token TTL | 480 min (8 uur) | Werkdag sessie |
| Refresh Token TTL | 7 dagen | Hernieuwing zonder login |

### Implementatie

**Token aanmaken:**
```python
from hienfeld_api.auth import create_access_token, hash_password

# Bij login
access_token = create_access_token(
    subject=user.username,
    secret_key=settings.secret_key,
    expires_minutes=480
)
```

**Token valideren (FastAPI dependency):**
```python
from hienfeld_api.auth import get_current_user_dependency

@app.get("/api/protected")
async def protected_route(
    user: str = Depends(get_current_user_dependency(settings))
):
    return {"user": user}
```

### Password Hashing

Wachtwoorden worden gehasht met bcrypt:

```python
from hienfeld_api.auth import hash_password, verify_password

# Nieuwe gebruiker
hashed = hash_password("plain_password")
# Opslaan in database: $2b$12$...

# Login verificatie
if verify_password("plain_password", stored_hash):
    # Geldig
```

**Admin password hash genereren:**
```bash
python -c "from passlib.context import CryptContext; c=CryptContext(schemes=['bcrypt']); print(c.hash('admin-password'))"
```

### Token in Development

In development mode (`AUTH_ENABLED=false`) wordt authenticatie overgeslagen:
- Alle requests krijgen user `dev-user`
- Handig voor lokale ontwikkeling

**NOOIT** `AUTH_ENABLED=false` in productie!

---

## CORS Beleid

### Configuratie

Cross-Origin Resource Sharing (CORS) beperkt welke origins de API mogen aanroepen.

**Development:**
```env
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000,http://localhost:8080
```

**Production:**
```env
ALLOWED_ORIGINS=https://app.hienfeld.nl
```

### Toegestane Methodes

```python
CORS_CONFIG = {
    "allow_origins": settings.allowed_origins,
    "allow_credentials": True,
    "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    "allow_headers": ["Authorization", "Content-Type", "X-Request-ID"],
    "max_age": 600,  # Preflight cache: 10 minuten
}
```

### Troubleshooting

**CORS error in browser:**
1. Check of origin exact matcht (inclusief protocol en poort)
2. Geen trailing slash in `ALLOWED_ORIGINS`
3. Backend moet draaien

```bash
# Test CORS headers
curl -I -X OPTIONS \
  -H "Origin: https://app.hienfeld.nl" \
  -H "Access-Control-Request-Method: POST" \
  http://localhost:8000/api/analyze
```

Verwacht:
```
Access-Control-Allow-Origin: https://app.hienfeld.nl
Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS
```

---

## Rate Limiting

### Configuratie

Rate limiting beschermt tegen DoS en brute force aanvallen.

```env
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60
```

Dit betekent: maximaal 100 requests per 60 seconden per IP.

### Endpoint-specifieke Limits

| Endpoint | Limit | Reden |
|----------|-------|-------|
| `/api/auth/login` | 5/min | Brute force preventie |
| `/api/analyze` | 10/min | Resource-intensief |
| `/api/health` | Geen limit | Monitoring |
| Default | 100/min | Algemene bescherming |

### Implementatie

```python
from hienfeld_api.middleware import limiter

@app.post("/api/auth/login")
@limiter.limit("5/minute")
async def login(request: Request, ...):
    ...

@app.post("/api/analyze")
@limiter.limit("10/minute")
async def analyze(request: Request, ...):
    ...
```

### Response bij Overlimit

```json
HTTP/1.1 429 Too Many Requests
Retry-After: 45
Content-Type: application/json

{
  "detail": "Te veel verzoeken. Probeer het over 45 seconden opnieuw."
}
```

---

## Security Headers

### Overzicht

Alle responses bevatten security headers:

| Header | Waarde | Bescherming |
|--------|--------|-------------|
| `X-Frame-Options` | `DENY` | Clickjacking |
| `X-Content-Type-Options` | `nosniff` | MIME sniffing |
| `X-XSS-Protection` | `1; mode=block` | XSS (legacy) |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Referrer leakage |
| `Content-Security-Policy` | `default-src 'none'` | XSS, injection |
| `Permissions-Policy` | `camera=(), microphone=()` | Feature access |
| `X-Request-ID` | `<uuid>` | Tracing |

### Verificatie

```bash
# Check security headers
curl -I http://localhost:8000/api/health

# Verwacht output:
# X-Frame-Options: DENY
# X-Content-Type-Options: nosniff
# X-XSS-Protection: 1; mode=block
# Content-Security-Policy: default-src 'none'...
# X-Request-ID: 550e8400-e29b-41d4-a716-446655440000
```

### CSP Details

Content Security Policy voor de API backend:

```
default-src 'none';
frame-ancestors 'none';
form-action 'none'
```

**Let op:** De frontend (React) heeft een eigen, minder restrictief CSP.

---

## Input Validatie

### Bestandsvalidatie

```python
# Maximale bestandsgrootte
MAX_FILE_SIZE_MB = 50

# Toegestane extensies
ALLOWED_EXTENSIONS = {
    "policy_file": [".xlsx", ".csv", ".xls"],
    "conditions_files": [".pdf", ".docx", ".txt"],
    "clause_library_files": [".xlsx", ".csv", ".pdf", ".docx"],
}

# Validatie
def validate_upload(file: UploadFile, file_type: str) -> None:
    # Check extensie
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS[file_type]:
        raise HTTPException(400, f"Bestandstype niet toegestaan: {ext}")

    # Check grootte
    file.file.seek(0, 2)  # Seek to end
    size_mb = file.file.tell() / (1024 * 1024)
    file.file.seek(0)  # Reset
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(400, f"Bestand te groot: {size_mb:.1f}MB > {MAX_FILE_SIZE_MB}MB")
```

### Parameter Validatie

```python
from pydantic import BaseModel, Field, validator

class AnalysisRequest(BaseModel):
    cluster_accuracy: int = Field(80, ge=50, le=100)
    min_frequency: int = Field(1, ge=1, le=1000)
    window_size: int = Field(100, ge=10, le=500)
    analysis_mode: str = Field("BALANCED")

    @validator("analysis_mode")
    def validate_mode(cls, v):
        allowed = ["FAST", "BALANCED", "ACCURATE"]
        if v.upper() not in allowed:
            raise ValueError(f"Mode moet een van {allowed} zijn")
        return v.upper()

    @validator("cluster_accuracy")
    def validate_accuracy(cls, v):
        if v % 10 != 0:
            raise ValueError("Accuracy moet een veelvoud van 10 zijn")
        return v
```

### SQL Injection Preventie

SQLAlchemy parameters worden automatisch geescaped:

```python
# GOED - Parameters
query = select(Job).where(Job.user_id == user_id)

# FOUT - String concatenatie
query = f"SELECT * FROM jobs WHERE user_id = '{user_id}'"  # NOOIT!
```

---

## GDPR Compliance

### Overzicht

De VB Converter verwerkt polisgegevens die onder de AVG/GDPR vallen.

### Data Minimalisatie (Art. 5)

| Principe | Implementatie |
|----------|---------------|
| Doel | Alleen analyse van polisclausules |
| Beperking | Geen opslag van persoonsgegevens |
| Opslag | Alleen tekst, geen namen/BSN |

### Bewaartermijn (Art. 5(1)(e))

Analyse resultaten worden automatisch verwijderd na 24 uur:

```python
# Job configuratie
ttl_until = datetime.utcnow() + timedelta(hours=24)

# Automatische cleanup (PostgreSQL)
CREATE OR REPLACE FUNCTION cleanup_expired_jobs()
RETURNS void AS $$
BEGIN
    DELETE FROM jobs WHERE ttl_until < NOW();
    DELETE FROM audit_log WHERE timestamp < NOW() - INTERVAL '90 days';
END;
$$ LANGUAGE plpgsql;
```

### Recht op Verwijdering (Art. 17)

Gebruikers kunnen hun data verwijderen:

```python
@app.delete("/api/jobs/{job_id}")
@limiter.limit("10/minute")
async def delete_job(
    job_id: str,
    user: str = Depends(get_current_user)
):
    job = await repo.get_job(job_id)
    if job.user_id != user:
        raise HTTPException(403, "Geen toegang")
    await repo.delete_job(job_id)
    audit_log.info(f"Job {job_id} verwijderd door {user}")
    return {"status": "deleted"}
```

### GDPR Compliance Checklist

**Technisch:**
- [x] Data encryptie in transit (HTTPS)
- [x] Data encryptie at rest (PostgreSQL)
- [x] Automatische data verwijdering (24h TTL)
- [x] Access logging (audit trail)
- [x] Role-based access control
- [ ] Data export functie (Art. 20)
- [ ] Consent tracking

**Organisatorisch:**
- [ ] Verwerkingsovereenkomst
- [ ] Privacy beleid gepubliceerd
- [ ] DPO aangesteld
- [ ] DPIA uitgevoerd
- [ ] Breach notification procedure

### Audit Logging

Alle acties worden gelogd voor compliance:

```python
# Audit log entry
{
    "timestamp": "2026-02-18T14:30:00Z",
    "user_id": "user@hienfeld.nl",
    "action": "ANALYSIS_STARTED",
    "job_id": "abc123",
    "details": {
        "rows": 1660,
        "mode": "BALANCED",
        "ip": "192.168.1.100"
    }
}
```

**Bewaartermijn audit logs:** 90 dagen (configureerbaar)

---

## Incident Response

### Classificatie

| Niveau | Beschrijving | Response Tijd |
|--------|--------------|---------------|
| **P0 - Kritiek** | Data breach, systeem down | < 1 uur |
| **P1 - Hoog** | Security vulnerability, data loss | < 4 uur |
| **P2 - Medium** | Performance issue, partial outage | < 24 uur |
| **P3 - Laag** | Minor bug, enhancement | < 1 week |

### Incident Procedure

#### 1. Detectie & Triage

```bash
# Check system status
curl https://api.hienfeld.nl/api/health/ready

# Check logs voor errors
docker logs vb-backend --since 1h | grep ERROR

# Check rate limit hits
docker logs vb-backend --since 1h | grep "429"
```

#### 2. Containment

**Bij vermoeden van breach:**

```bash
# 1. Disable external access (indien mogelijk)
# Pas nginx config aan om alle traffic te blokkeren

# 2. Revoke alle active tokens
# Update SECRET_KEY -> alle JWTs invalid

# 3. Disable user accounts (indien nodig)
```

#### 3. Eradication

```bash
# 1. Identificeer root cause via logs
docker logs vb-backend --since 24h > incident_logs.txt

# 2. Patch vulnerability
# 3. Update dependencies
pip install --upgrade <package>

# 4. Rotate alle secrets
```

#### 4. Recovery

```bash
# 1. Deploy patched version
docker-compose pull && docker-compose up -d

# 2. Verify system health
curl https://api.hienfeld.nl/api/health/ready

# 3. Monitor closely voor 24-48 uur
```

#### 5. Post-Incident

- [ ] Incident rapport schrijven
- [ ] Timeline documenteren
- [ ] Root cause analysis
- [ ] Preventieve maatregelen identificeren
- [ ] Team debrief

### Contact bij Security Incident

| Rol | Contact | Wanneer |
|-----|---------|---------|
| Security Lead | security@hienfeld.nl | Alle security issues |
| CTO | Via intern | P0/P1 incidents |
| DPO | privacy@hienfeld.nl | Data breaches |
| Extern CERT | Afhankelijk van contract | Bij grote breaches |

### Data Breach Notification

Bij een data breach (Art. 33/34 AVG):

1. **Documenteer** alle details binnen 24 uur
2. **Meld aan AP** binnen 72 uur (indien vereist)
3. **Informeer betrokkenen** indien hoog risico
4. **Rapporteer** aan management

---

## Security Checklist

### Development

- [ ] Geen secrets in code/commits
- [ ] Input validatie op alle endpoints
- [ ] SQL queries via ORM (geen raw queries)
- [ ] Dependencies up-to-date
- [ ] HTTPS in alle environments

### Deployment

- [ ] `SECRET_KEY` gegenereerd en veilig opgeslagen
- [ ] `DEBUG=false` in productie
- [ ] `ALLOWED_ORIGINS` bevat alleen productie URL
- [ ] Rate limiting actief
- [ ] SSL/TLS certificaat geldig
- [ ] Security headers gevalideerd

### Monitoring

- [ ] Failed login attempts monitoren
- [ ] Rate limit hits monitoren
- [ ] Error rates monitoren
- [ ] Audit logs reviewen (wekelijks)

---

## Zie Ook

- [DEPLOYMENT.md](DEPLOYMENT.md) - Deployment procedures
- [RUNBOOK.md](RUNBOOK.md) - Operations handleiding
- [ARCHITECTURE.md](ARCHITECTURE.md) - Systeem architectuur
- [AUDIT_REPORT.md](AUDIT_REPORT.md) - Volledige security audit
