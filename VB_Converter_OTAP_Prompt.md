# OPDRACHT: VB_Converter Productierijp Maken met OTAP/CI-CD Pipeline

Je werkt aan de VB_Converter applicatie (https://github.com/StefHienfeld/VB_Converter).
Dit is een interne bedrijfstool voor het analyseren van vrije polísteksten.

---

## APPLICATIE CONTEXT

### Tech Stack
- **Frontend:** Vite + React + TypeScript + Tailwind CSS + shadcn-ui (port 5173)
- **Backend:** Python FastAPI (hienfeld_api, port 8000) + Reflex framework (hienfeld_app)
- **NLP:** SpaCy, Gensim, Sentence-transformers, RapidFuzz
- **Package Managers:** npm/bun (frontend), pip (backend)

### Huidige Structuur
```
VB_Converter/
├── hienfeld_app/        # Reflex UI applicatie
│   ├── components/      # UI componenten
│   ├── state.py         # State management
│   └── styles.py        # Design system
├── hienfeld/            # Backend Python package
│   ├── domain/          # Domeinmodellen (Clause, Cluster, AnalysisAdvice)
│   ├── services/        # Business logic services
│   │   ├── ai/          # AI-extensies
│   │   └── ...
│   ├── utils/           # Hulpfuncties
│   └── config.py        # Configuratie
├── hienfeld_api/        # FastAPI REST API
├── src/                 # React frontend
├── public/              # Static files
├── tests/               # Tests
├── docs/                # Documentatie
├── scripts/             # Helper scripts
├── requirements.txt     # Python dependencies
├── package.json         # Node.js dependencies
└── CLAUDE.md            # Bestaande Claude instructies
```

### Hoe de app nu draait
```bash
# Backend
uvicorn hienfeld_api.app:app --reload --port 8000

# Frontend
npm run dev  # http://localhost:5173

# OF Reflex app
python -m reflex run
```

---

## FASE 0: INVENTARISATIE (VERPLICHT EERSTE STAP)

Voordat je IETS wijzigt, analyseer de codebase grondig:

### 0.1 Analyseer en Documenteer
Maak `docs/DEPLOYMENT_ANALYSIS.md` met:

#### 1. Dependency Audit
- Lijst alle Python dependencies uit `requirements.txt`
- Lijst alle Node.js dependencies uit `package.json`
- Identificeer verouderde of kwetsbare packages
- Check Python versie vereisten

#### 2. Environment Variables Audit
- Zoek ALLE hardcoded configuratie/secrets in de code
- Check: API keys, database URLs, ports, hosts
- Zoek naar: `os.getenv`, `process.env`, hardcoded strings
- Documenteer wat configureerbaar moet worden

#### 3. Endpoints & Poorten
- Map alle API endpoints in `hienfeld_api/`
- Identificeer welke poorten worden gebruikt
- Check CORS configuratie

#### 4. Data & Privacy
- Welke data wordt verwerkt? (polísteksten = mogelijk gevoelig)
- Waar wordt data tijdelijk opgeslagen?
- Worden er externe API's aangeroepen?

#### 5. Huidige Test Coverage
- Analyseer `tests/` directory
- Welke tests bestaan er al?
- Wat ontbreekt?

### 0.2 Maak Migratieplan
Maak `docs/OTAP_MIGRATION_PLAN.md` met:
- Prioritering van taken
- Risico's per wijziging
- Rollback strategie

**⏸️ STOP NA FASE 0 - VRAAG GOEDKEURING VOORDAT JE VERDERGAAT**

---

## FASE 1: ENVIRONMENT CONFIGURATIE

### 1.1 Backend Configuratie (Python)

Maak/update `hienfeld/config/settings.py`:

```python
"""
Centrale configuratie voor VB_Converter.
Alle environment-specifieke settings op één plek.
"""
from enum import Enum
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings

class Environment(str, Enum):
    DEVELOPMENT = "development"
    TEST = "test"
    ACCEPTANCE = "acceptance"
    PRODUCTION = "production"

class Settings(BaseSettings):
    # === Application ===
    APP_NAME: str = "VB_Converter"
    APP_VERSION: str = "3.0.0"
    ENVIRONMENT: Environment = Environment.DEVELOPMENT
    DEBUG: bool = False
    
    # === Server ===
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173"]
    
    # === Security ===
    SECRET_KEY: str  # VERPLICHT - geen default!
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 8
    
    # === SSO/Authentication ===
    SSO_ENABLED: bool = False
    SSO_PROVIDER: str = ""  # "azure_ad", "okta"
    SSO_CLIENT_ID: str = ""
    SSO_CLIENT_SECRET: str = ""
    SSO_TENANT_ID: str = ""
    
    # === NLP/AI Settings ===
    SPACY_MODEL: str = "nl_core_news_md"
    SEMANTIC_ENABLED: bool = True
    EMBEDDING_MODEL: str = "paraphrase-multilingual-MiniLM-L12-v2"
    
    # === Clustering ===
    SIMILARITY_THRESHOLD: float = 0.90
    LEADER_WINDOW_SIZE: int = 100
    FREQUENCY_STANDARDIZE_THRESHOLD: int = 20
    
    # === Logging ===
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # "json" voor productie, "text" voor dev
    AUDIT_LOG_ENABLED: bool = True
    
    # === Rate Limiting ===
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60
    
    # === Feature Flags ===
    FEATURE_AI_EXTENSIONS: bool = False
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    return Settings()
```

### 1.2 Frontend Configuratie (TypeScript)

Maak `src/config/settings.ts`:

```typescript
/**
 * Frontend configuratie voor VB_Converter
 */

type Environment = 'development' | 'test' | 'acceptance' | 'production';

interface Config {
  environment: Environment;
  apiBaseUrl: string;
  appVersion: string;
  features: {
    aiExtensions: boolean;
  };
}

const getConfig = (): Config => {
  const env = (import.meta.env.VITE_ENVIRONMENT || 'development') as Environment;
  
  const apiUrls: Record<Environment, string> = {
    development: 'http://localhost:8000',
    test: import.meta.env.VITE_API_URL || 'https://test-api.vb-converter.company.nl',
    acceptance: import.meta.env.VITE_API_URL || 'https://acc-api.vb-converter.company.nl',
    production: import.meta.env.VITE_API_URL || 'https://api.vb-converter.company.nl',
  };

  return {
    environment: env,
    apiBaseUrl: apiUrls[env],
    appVersion: import.meta.env.VITE_APP_VERSION || '3.0.0',
    features: {
      aiExtensions: import.meta.env.VITE_FEATURE_AI === 'true',
    },
  };
};

export const config = getConfig();
export default config;
```

### 1.3 Environment Files

Maak `environments/.env.example`:

```bash
# =============================================================================
# VB_CONVERTER ENVIRONMENT CONFIGURATION
# Kopieer dit bestand naar .env en vul de waarden in
# =============================================================================

# --- Application ---
ENVIRONMENT=development
DEBUG=true
SECRET_KEY=CHANGE_THIS_TO_A_SECURE_RANDOM_STRING

# --- Server ---
API_HOST=0.0.0.0
API_PORT=8000
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000

# --- Authentication (optioneel) ---
SSO_ENABLED=false
SSO_PROVIDER=
SSO_CLIENT_ID=
SSO_CLIENT_SECRET=
SSO_TENANT_ID=

# --- NLP ---
SPACY_MODEL=nl_core_news_md
SEMANTIC_ENABLED=true

# --- Frontend (Vite) ---
VITE_ENVIRONMENT=development
VITE_API_URL=http://localhost:8000
VITE_APP_VERSION=3.0.0
VITE_FEATURE_AI=false

# --- Logging ---
LOG_LEVEL=DEBUG
LOG_FORMAT=text
```

### 1.4 Update .gitignore

Voeg toe aan `.gitignore`:

```gitignore
# === Environment & Secrets - KRITIEK ===
.env
.env.*
!.env.example
*.pem
*.key
.secrets/

# === Python ===
__pycache__/
*.py[cod]
*$py.class
.venv/
venv/
ENV/
*.egg-info/
dist/
build/
.eggs/
.coverage
htmlcov/
.pytest_cache/
.mypy_cache/

# === Node.js ===
node_modules/
.npm
.yarn
npm-debug.log*
yarn-debug.log*
yarn-error.log*

# === Build outputs ===
/dist/
/build/
.reflex/

# === IDE ===
.idea/
.vscode/
*.swp
*.swo

# === Docker ===
docker-compose.override.yml

# === Terraform ===
*.tfstate
*.tfstate.*
.terraform/

# === Logs & Temp ===
logs/
*.log
tmp/
temp/
uploads/
*.tmp

# === OS ===
.DS_Store
Thumbs.db
```

**⏸️ STOP NA FASE 1 - VRAAG GOEDKEURING**

---

## FASE 2: DOCKER CONTAINERISATIE

### 2.1 Backend Dockerfile

Maak `infrastructure/docker/Dockerfile.backend`:

```dockerfile
# =============================================================================
# VB_CONVERTER BACKEND - MULTI-STAGE PRODUCTION BUILD
# =============================================================================

# --- Stage 1: Base ---
FROM python:3.11-slim-bookworm AS base

# Security: non-root user
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

# System dependencies voor NLP
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        build-essential \
        && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# --- Stage 2: Dependencies ---
FROM base AS dependencies

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download SpaCy model
RUN python -m spacy download nl_core_news_md

# --- Stage 3: Production ---
FROM base AS production

# Kopieer dependencies
COPY --from=dependencies /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin

# Kopieer SpaCy model data
COPY --from=dependencies /root/.cache /home/appuser/.cache

# Applicatie code
COPY --chown=appuser:appgroup hienfeld/ ./hienfeld/
COPY --chown=appuser:appgroup hienfeld_api/ ./hienfeld_api/
COPY --chown=appuser:appgroup hienfeld_app/ ./hienfeld_app/

# Switch to non-root
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:${API_PORT:-8000}/health || exit 1

EXPOSE ${API_PORT:-8000}

CMD ["uvicorn", "hienfeld_api.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 2.2 Frontend Dockerfile

Maak `infrastructure/docker/Dockerfile.frontend`:

```dockerfile
# =============================================================================
# VB_CONVERTER FRONTEND - MULTI-STAGE BUILD
# =============================================================================

# --- Stage 1: Build ---
FROM node:20-alpine AS builder

WORKDIR /app

# Dependencies first (cache layer)
COPY package*.json ./
COPY bun.lockb* ./
RUN npm ci --legacy-peer-deps

# Build arguments voor environment
ARG VITE_ENVIRONMENT=production
ARG VITE_API_URL
ARG VITE_APP_VERSION

ENV VITE_ENVIRONMENT=$VITE_ENVIRONMENT
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_APP_VERSION=$VITE_APP_VERSION

# Source code & build
COPY . .
RUN npm run build

# --- Stage 2: Production (nginx) ---
FROM nginx:alpine AS production

# Custom nginx config
COPY infrastructure/docker/nginx.conf /etc/nginx/conf.d/default.conf

# Copy built assets
COPY --from=builder /app/dist /usr/share/nginx/html

# Security headers via nginx config
RUN chown -R nginx:nginx /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

### 2.3 Nginx Config

Maak `infrastructure/docker/nginx.conf`:

```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # Security headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' https://*.company.nl;" always;

    # Gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;

    # SPA routing
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API proxy (optioneel, als frontend en backend op zelfde domein)
    location /api/ {
        proxy_pass http://backend:8000/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    # Health check
    location /health {
        access_log off;
        return 200 "healthy";
        add_header Content-Type text/plain;
    }
}
```

### 2.4 Docker Compose - Development

Maak `infrastructure/docker/docker-compose.yml`:

```yaml
version: '3.8'

services:
  backend:
    build:
      context: ../..
      dockerfile: infrastructure/docker/Dockerfile.backend
      target: production
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=development
      - DEBUG=true
      - SECRET_KEY=dev-secret-key-change-in-production
      - LOG_LEVEL=DEBUG
      - LOG_FORMAT=text
      - ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
    volumes:
      - ../../hienfeld:/app/hienfeld:ro
      - ../../hienfeld_api:/app/hienfeld_api:ro
      - upload_data:/app/uploads
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    networks:
      - vb-network

  frontend:
    build:
      context: ../..
      dockerfile: infrastructure/docker/Dockerfile.frontend
      args:
        - VITE_ENVIRONMENT=development
        - VITE_API_URL=http://localhost:8000
    ports:
      - "3000:80"
    depends_on:
      backend:
        condition: service_healthy
    networks:
      - vb-network

volumes:
  upload_data:

networks:
  vb-network:
    driver: bridge
```

### 2.5 Docker Compose - Production

Maak `infrastructure/docker/docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  backend:
    image: ${REGISTRY:-ghcr.io}/stefhienfeld/vb-converter-backend:${TAG:-latest}
    restart: always
    environment:
      - ENVIRONMENT=production
      - DEBUG=false
      - SECRET_KEY=${SECRET_KEY}
      - SSO_ENABLED=${SSO_ENABLED:-true}
      - SSO_PROVIDER=${SSO_PROVIDER}
      - SSO_CLIENT_ID=${SSO_CLIENT_ID}
      - SSO_CLIENT_SECRET=${SSO_CLIENT_SECRET}
      - SSO_TENANT_ID=${SSO_TENANT_ID}
      - LOG_LEVEL=INFO
      - LOG_FORMAT=json
      - RATE_LIMIT_ENABLED=true
    volumes:
      - upload_data:/app/uploads
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    networks:
      - vb-network
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G

  frontend:
    image: ${REGISTRY:-ghcr.io}/stefhienfeld/vb-converter-frontend:${TAG:-latest}
    restart: always
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      backend:
        condition: service_healthy
    networks:
      - vb-network

volumes:
  upload_data:
    driver: local

networks:
  vb-network:
    driver: bridge
```

**⏸️ STOP NA FASE 2 - VRAAG GOEDKEURING**

---

## FASE 3: CI/CD PIPELINE (GitHub Actions)

### 3.1 CI Pipeline

Maak `.github/workflows/ci.yml`:

```yaml
name: CI Pipeline

on:
  push:
    branches: [main, develop, 'release/**']
  pull_request:
    branches: [main, develop]

env:
  PYTHON_VERSION: '3.11'
  NODE_VERSION: '20'
  REGISTRY: ghcr.io
  IMAGE_NAME_BACKEND: ${{ github.repository }}-backend
  IMAGE_NAME_FRONTEND: ${{ github.repository }}-frontend

jobs:
  # ===========================================================================
  # BACKEND CHECKS
  # ===========================================================================
  backend-lint:
    name: Backend Lint & Type Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: 'pip'

      - name: Install linting tools
        run: |
          pip install flake8 black isort mypy pylint bandit safety

      - name: Run Black
        run: black --check hienfeld/ hienfeld_api/ hienfeld_app/ tests/

      - name: Run isort
        run: isort --check-only hienfeld/ hienfeld_api/ hienfeld_app/

      - name: Run Flake8
        run: flake8 hienfeld/ hienfeld_api/ --max-line-length=120

      - name: Run MyPy
        run: mypy hienfeld/ hienfeld_api/ --ignore-missing-imports
        continue-on-error: true

      - name: Run Bandit (Security)
        run: bandit -r hienfeld/ hienfeld_api/ -ll
        continue-on-error: true

  backend-test:
    name: Backend Tests
    runs-on: ubuntu-latest
    needs: backend-lint
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: 'pip'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov pytest-asyncio httpx

      - name: Download SpaCy model
        run: python -m spacy download nl_core_news_md

      - name: Run tests
        env:
          SECRET_KEY: test-secret-key
          ENVIRONMENT: test
        run: |
          pytest tests/ \
            --cov=hienfeld \
            --cov=hienfeld_api \
            --cov-report=xml \
            --cov-report=html \
            --cov-fail-under=60 \
            -v

      - name: Upload coverage
        uses: actions/upload-artifact@v4
        with:
          name: backend-coverage
          path: htmlcov/

  # ===========================================================================
  # FRONTEND CHECKS
  # ===========================================================================
  frontend-lint:
    name: Frontend Lint & Type Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: 'npm'

      - name: Install dependencies
        run: npm ci --legacy-peer-deps

      - name: Run ESLint
        run: npm run lint

      - name: Run TypeScript check
        run: npm run type-check || npx tsc --noEmit

  frontend-test:
    name: Frontend Tests
    runs-on: ubuntu-latest
    needs: frontend-lint
    steps:
      - uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: 'npm'

      - name: Install dependencies
        run: npm ci --legacy-peer-deps

      - name: Run tests
        run: npm test -- --passWithNoTests
        continue-on-error: true

  frontend-build:
    name: Frontend Build
    runs-on: ubuntu-latest
    needs: frontend-lint
    steps:
      - uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: 'npm'

      - name: Install dependencies
        run: npm ci --legacy-peer-deps

      - name: Build
        run: npm run build
        env:
          VITE_ENVIRONMENT: production
          VITE_API_URL: https://api.vb-converter.company.nl

      - name: Upload build
        uses: actions/upload-artifact@v4
        with:
          name: frontend-build
          path: dist/

  # ===========================================================================
  # SECURITY SCAN
  # ===========================================================================
  security-scan:
    name: Security Scan
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Check Python dependencies
        run: |
          pip install safety pip-audit
          safety check -r requirements.txt --full-report || true
          pip-audit -r requirements.txt || true

      - name: Run Trivy (filesystem)
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'
          severity: 'CRITICAL,HIGH'
        continue-on-error: true

  # ===========================================================================
  # BUILD DOCKER IMAGES
  # ===========================================================================
  build-images:
    name: Build Docker Images
    runs-on: ubuntu-latest
    needs: [backend-test, frontend-build, security-scan]
    if: github.event_name == 'push'
    permissions:
      contents: read
      packages: write

    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata (Backend)
        id: meta-backend
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME_BACKEND }}
          tags: |
            type=ref,event=branch
            type=sha,prefix=
            type=semver,pattern={{version}}

      - name: Build Backend
        uses: docker/build-push-action@v5
        with:
          context: .
          file: infrastructure/docker/Dockerfile.backend
          push: true
          tags: ${{ steps.meta-backend.outputs.tags }}
          labels: ${{ steps.meta-backend.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Extract metadata (Frontend)
        id: meta-frontend
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME_FRONTEND }}
          tags: |
            type=ref,event=branch
            type=sha,prefix=
            type=semver,pattern={{version}}

      - name: Build Frontend
        uses: docker/build-push-action@v5
        with:
          context: .
          file: infrastructure/docker/Dockerfile.frontend
          push: true
          tags: ${{ steps.meta-frontend.outputs.tags }}
          labels: ${{ steps.meta-frontend.outputs.labels }}
          build-args: |
            VITE_ENVIRONMENT=production
            VITE_API_URL=https://api.vb-converter.company.nl
            VITE_APP_VERSION=${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

### 3.2 CD Pipeline - Test Environment

Maak `.github/workflows/cd-test.yml`:

```yaml
name: Deploy to Test

on:
  push:
    branches: [develop]
  workflow_dispatch:

env:
  ENVIRONMENT: test

jobs:
  deploy:
    name: Deploy to Test
    runs-on: ubuntu-latest
    environment:
      name: test
      url: https://test.vb-converter.company.nl

    steps:
      - uses: actions/checkout@v4

      - name: Deploy to Test Server
        run: |
          echo "Deploying to Test environment..."
          # Voeg hier je deployment logica toe, bijvoorbeeld:
          # - SSH naar server
          # - docker-compose pull && docker-compose up -d
          # - of kubectl apply

      - name: Run smoke tests
        run: |
          echo "Running smoke tests..."
          # curl -f https://test.vb-converter.company.nl/health

      - name: Notify team
        if: always()
        run: |
          echo "Deployment to Test: ${{ job.status }}"
          # Voeg Slack/Teams webhook toe
```

### 3.3 CD Pipeline - Acceptatie

Maak `.github/workflows/cd-acceptance.yml`:

```yaml
name: Deploy to Acceptance

on:
  push:
    branches: ['release/**']
  workflow_dispatch:

env:
  ENVIRONMENT: acceptance

jobs:
  deploy:
    name: Deploy to Acceptance
    runs-on: ubuntu-latest
    environment:
      name: acceptance
      url: https://acc.vb-converter.company.nl

    steps:
      - uses: actions/checkout@v4

      - name: Deploy to Acceptance
        run: |
          echo "Deploying to Acceptance environment..."

      - name: Run acceptance tests
        run: |
          echo "Running acceptance tests..."
```

### 3.4 CD Pipeline - Productie

Maak `.github/workflows/cd-production.yml`:

```yaml
name: Deploy to Production

on:
  push:
    tags: ['v*.*.*']
  workflow_dispatch:
    inputs:
      version:
        description: 'Version tag to deploy'
        required: true

env:
  ENVIRONMENT: production

jobs:
  pre-checks:
    name: Pre-Deployment Checks
    runs-on: ubuntu-latest
    steps:
      - name: Verify acceptance sign-off
        run: echo "Checking acceptance approval..."

  deploy:
    name: Deploy to Production
    runs-on: ubuntu-latest
    needs: pre-checks
    environment:
      name: production
      url: https://vb-converter.company.nl

    steps:
      - uses: actions/checkout@v4

      - name: Create deployment record
        run: |
          echo "=== PRODUCTION DEPLOYMENT ==="
          echo "Deployed by: ${{ github.actor }}"
          echo "Version: ${{ github.ref_name }}"
          echo "Time: $(date -u)"

      - name: Deploy to Production
        run: |
          echo "Deploying to Production..."
          # Blue-green deployment logic

      - name: Verify deployment
        run: |
          echo "Verifying production health..."
          # Health checks

      - name: Rollback on failure
        if: failure()
        run: |
          echo "Rolling back deployment..."
```

**⏸️ STOP NA FASE 3 - VRAAG GOEDKEURING**

---

## FASE 4: SECURITY IMPLEMENTATIE

### 4.1 API Security Middleware

Maak `hienfeld_api/middleware/security.py`:

```python
"""
Security middleware voor VB_Converter API.
"""
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import time
import logging

from hienfeld.config.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


def setup_security(app: FastAPI) -> None:
    """Configureer alle security middleware."""
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    
    # Security Headers
    app.add_middleware(SecurityHeadersMiddleware)
    
    # Request Logging
    app.add_middleware(RequestLoggingMiddleware)
    
    # Rate Limiting (indien enabled)
    if settings.RATE_LIMIT_ENABLED:
        app.add_middleware(RateLimitMiddleware)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Voegt security headers toe aan responses."""
    
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        if settings.ENVIRONMENT.value == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logt alle requests voor audit trail."""
    
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID", str(time.time_ns()))
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        # Log
        duration = time.time() - start_time
        logger.info(
            f"request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration * 1000, 2),
                "client_ip": request.client.host if request.client else "unknown",
            }
        )
        
        response.headers["X-Request-ID"] = request_id
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simpele in-memory rate limiter."""
    
    def __init__(self, app):
        super().__init__(app)
        self._requests: dict = {}
    
    async def dispatch(self, request: Request, call_next) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()
        window_start = current_time - settings.RATE_LIMIT_WINDOW
        
        # Cleanup oude entries
        self._requests = {
            k: [t for t in v if t > window_start]
            for k, v in self._requests.items()
        }
        
        # Check rate limit
        requests = self._requests.get(client_ip, [])
        if len(requests) >= settings.RATE_LIMIT_REQUESTS:
            return Response(
                content='{"detail": "Too many requests"}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": str(settings.RATE_LIMIT_WINDOW)}
            )
        
        # Record request
        self._requests.setdefault(client_ip, []).append(current_time)
        
        return await call_next(request)
```

### 4.2 Health Endpoints

Maak/update `hienfeld_api/routes/health.py`:

```python
"""
Health check endpoints voor monitoring.
"""
from datetime import datetime
from fastapi import APIRouter, Response
from pydantic import BaseModel

from hienfeld.config.settings import get_settings

router = APIRouter(tags=["Health"])
settings = get_settings()


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    version: str
    environment: str


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Volledige health check."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT.value,
    )


@router.get("/health/live")
async def liveness():
    """Kubernetes liveness probe."""
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness(response: Response):
    """Kubernetes readiness probe."""
    # Check of SpaCy model geladen is
    try:
        import spacy
        nlp = spacy.load(settings.SPACY_MODEL)
        return {"status": "ready"}
    except Exception as e:
        response.status_code = 503
        return {"status": "not ready", "reason": str(e)}
```

### 4.3 Update Main App

Update `hienfeld_api/app.py`:

```python
"""
VB_Converter FastAPI Application
"""
from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging

from hienfeld.config.settings import get_settings
from hienfeld_api.middleware.security import setup_security
from hienfeld_api.routes import health  # , analysis, etc.

settings = get_settings()

# Logging setup
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    if settings.LOG_FORMAT == "text" else
    '{"timestamp":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown."""
    logger.info(f"Starting VB_Converter v{settings.APP_VERSION} ({settings.ENVIRONMENT.value})")
    
    # Preload SpaCy model
    if settings.SEMANTIC_ENABLED:
        import spacy
        logger.info(f"Loading SpaCy model: {settings.SPACY_MODEL}")
        spacy.load(settings.SPACY_MODEL)
    
    yield
    
    logger.info("Shutting down VB_Converter")


app = FastAPI(
    title="VB_Converter API",
    description="API voor het analyseren van vrije polísteksten",
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# Security middleware
setup_security(app)

# Routes
app.include_router(health.router)
# app.include_router(analysis.router, prefix="/api")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.API_HOST, port=settings.API_PORT)
```

### 4.4 Authentication Middleware (Optioneel - SSO)

Maak `hienfeld_api/middleware/authentication.py`:

```python
"""
SSO Authentication middleware.
Ondersteunt Azure AD, Okta, Keycloak.
"""
import logging
from typing import Optional
from datetime import datetime

import jwt
from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from hienfeld.config.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


class UserInfo(BaseModel):
    """Geauthenticeerde gebruiker info."""
    user_id: str
    email: str
    name: str
    roles: list[str] = []
    groups: list[str] = []


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[UserInfo]:
    """
    Haal huidige gebruiker op uit JWT token.
    Returns None als SSO niet enabled is.
    """
    if not settings.SSO_ENABLED:
        return None
    
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        # Decode JWT (verificatie tegen SSO provider)
        payload = jwt.decode(
            credentials.credentials,
            options={"verify_signature": False},  # Signature wordt door SSO provider geverifieerd
            algorithms=["RS256"]
        )
        
        return UserInfo(
            user_id=payload.get("sub", payload.get("oid", "")),
            email=payload.get("email", payload.get("preferred_username", "")),
            name=payload.get("name", ""),
            roles=payload.get("roles", []),
            groups=payload.get("groups", []),
        )
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")


def require_roles(*required_roles: str):
    """
    Decorator voor role-based access control.
    
    Usage:
        @app.get("/admin")
        @require_roles("admin")
        async def admin_route():
            ...
    """
    async def role_checker(user: UserInfo = Depends(get_current_user)):
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        if not any(role in user.roles for role in required_roles):
            logger.warning(f"Access denied for {user.email}. Required: {required_roles}")
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        
        return user
    
    return role_checker
```

**⏸️ STOP NA FASE 4 - VRAAG GOEDKEURING**

---

## FASE 5: TESTS UITBREIDEN

### 5.1 Pytest Configuratie

Maak `tests/conftest.py`:

```python
"""
Pytest configuratie en fixtures voor VB_Converter.
"""
import pytest
from fastapi.testclient import TestClient
from hienfeld_api.app import app
from hienfeld.config.settings import Settings, Environment


@pytest.fixture(scope="session")
def test_settings():
    """Test settings."""
    return Settings(
        ENVIRONMENT=Environment.TEST,
        DEBUG=False,
        SECRET_KEY="test-secret-key",
        SSO_ENABLED=False,
        RATE_LIMIT_ENABLED=False,
        SEMANTIC_ENABLED=False,  # Skip NLP voor snellere tests
    )


@pytest.fixture
def client():
    """FastAPI test client."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_policy_text():
    """Sample polístekst voor tests."""
    return "Dekking voor schade aan het motorrijtuig is meeverzekerd conform artikel 5."


@pytest.fixture
def sample_conditions_text():
    """Sample voorwaarden tekst."""
    return """
    Artikel 5 - Dekking motorrijtuigen
    Wij verzekeren schade aan het motorrijtuig volgens de voorwaarden van deze polis.
    """
```

### 5.2 API Tests

Maak `tests/integration/test_api.py`:

```python
"""
Integration tests voor VB_Converter API.
"""
import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoints:
    """Tests voor health endpoints."""
    
    def test_health_returns_200(self, client: TestClient):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
    
    def test_liveness_returns_alive(self, client: TestClient):
        response = client.get("/health/live")
        assert response.status_code == 200
        assert response.json()["status"] == "alive"


class TestSecurityHeaders:
    """Tests voor security headers."""
    
    def test_security_headers_present(self, client: TestClient):
        response = client.get("/health")
        assert "X-Frame-Options" in response.headers
        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Frame-Options"] == "DENY"
```

### 5.3 Unit Tests voor Services

Maak `tests/unit/test_clustering_service.py`:

```python
"""
Unit tests voor ClusteringService.
"""
import pytest
from hienfeld.services.clustering_service import ClusteringService


class TestClusteringService:
    """Tests voor clustering functionaliteit."""
    
    @pytest.fixture
    def service(self):
        return ClusteringService()
    
    def test_similar_texts_cluster_together(self, service):
        texts = [
            "Dekking voor auto is meeverzekerd",
            "Dekking voor auto is meeverzekerd.",
            "Schade aan gebouwen is uitgesloten",
        ]
        
        clusters = service.cluster_texts(texts, similarity_threshold=0.9)
        
        # Eerste twee teksten moeten in zelfde cluster
        assert len(clusters) == 2
    
    def test_empty_input_returns_empty(self, service):
        clusters = service.cluster_texts([])
        assert clusters == []
```

### 5.4 Test Requirements

Maak `requirements-dev.txt`:

```txt
# Testing
pytest>=7.4.0
pytest-cov>=4.1.0
pytest-asyncio>=0.21.0
httpx>=0.24.0

# Linting & Formatting
black>=23.0.0
isort>=5.12.0
flake8>=6.0.0
mypy>=1.5.0
pylint>=2.17.0

# Security
bandit>=1.7.0
safety>=2.3.0
pip-audit>=2.6.0

# Type stubs
types-requests>=2.31.0
```

**⏸️ STOP NA FASE 5 - VRAAG GOEDKEURING**

---

## FASE 6: DOCUMENTATIE

### 6.1 Update README.md

Voeg deployment sectie toe aan bestaande `README.md`:

```markdown
---

## 🚀 Deployment

### Environments

| Environment | URL | Branch | Auto-deploy |
|-------------|-----|--------|-------------|
| Development | localhost | - | - |
| Test | https://test.vb-converter.company.nl | develop | ✅ |
| Acceptatie | https://acc.vb-converter.company.nl | release/* | ✅ |
| Productie | https://vb-converter.company.nl | tags (v*) | Manual approval |

### Docker

```bash
# Development
cd infrastructure/docker
docker-compose up -d

# Production
docker-compose -f docker-compose.prod.yml up -d
```

### CI/CD

De applicatie gebruikt GitHub Actions voor CI/CD:
- **CI:** Lint, test, security scan, build
- **CD:** Automatische deployment naar test/acceptatie, manual approval voor productie

---

## 🔒 Security

- Authenticatie via SSO (Azure AD / Okta) - optioneel
- Rate limiting op API endpoints
- Security headers (CSP, HSTS, X-Frame-Options, etc.)
- Audit logging van alle requests
- Data wordt alleen lokaal verwerkt - geen externe API calls

---
```

### 6.2 Deployment Guide

Maak `docs/DEPLOYMENT.md`:

```markdown
# VB_Converter Deployment Guide

## Vereisten

- Docker & Docker Compose
- Toegang tot GitHub Container Registry
- Environment secrets geconfigureerd in GitHub

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| SECRET_KEY | ✅ | Random string voor JWT signing (min 32 chars) |
| ENVIRONMENT | ✅ | development / test / acceptance / production |
| SSO_ENABLED | ❌ | Enable SSO authentication (default: false) |
| SSO_CLIENT_ID | Als SSO | OAuth client ID |
| SSO_CLIENT_SECRET | Als SSO | OAuth client secret |
| SSO_TENANT_ID | Als SSO (Azure) | Azure AD tenant ID |

## GitHub Secrets Configureren

Ga naar Repository > Settings > Secrets and variables > Actions:

1. `SECRET_KEY` - Genereer met: `openssl rand -hex 32`
2. `SSO_CLIENT_SECRET` - Indien SSO gebruikt wordt

## Deployment Stappen

### Test Environment

1. Push naar `develop` branch
2. CI pipeline draait automatisch
3. Na success: automatische deployment naar test

### Acceptatie Environment

1. Maak release branch: `git checkout -b release/v1.2.0`
2. Push naar GitHub: `git push -u origin release/v1.2.0`
3. Automatische deployment naar acceptatie
4. Test en valideer met stakeholders

### Productie Environment

1. Merge release naar main: `git checkout main && git merge release/v1.2.0`
2. Maak tag: `git tag -a v1.2.0 -m "Release v1.2.0"`
3. Push tag: `git push origin v1.2.0`
4. Wacht op approval in GitHub Actions
5. Deployment start na approval

## Rollback

### Via Docker

```bash
# Bekijk beschikbare images
docker images | grep vb-converter

# Pull vorige versie
docker-compose pull

# Start vorige versie
docker-compose up -d
```

### Via GitHub Actions

1. Ga naar Actions > Deploy to Production
2. Klik op "Run workflow"
3. Vul de vorige versie tag in (bijv. v1.1.0)

## Monitoring

- Health check: `GET /health`
- Liveness: `GET /health/live`
- Readiness: `GET /health/ready`

## Troubleshooting

### Container start niet

```bash
# Check logs
docker-compose logs backend

# Check health
curl http://localhost:8000/health
```

### SpaCy model laadt niet

```bash
# Check of model aanwezig is
docker-compose exec backend python -c "import spacy; spacy.load('nl_core_news_md')"
```
```

### 6.3 Runbook

Maak `docs/RUNBOOK.md`:

```markdown
# VB_Converter Operational Runbook

## Incident Response

### Severity Levels

| Level | Description | Response Time |
|-------|-------------|---------------|
| SEV1 | Productie volledig down | < 15 min |
| SEV2 | Functionaliteit beperkt | < 1 uur |
| SEV3 | Niet-kritieke issues | < 4 uur |
| SEV4 | Cosmetische issues | Next business day |

### SEV1 Checklist

1. [ ] Bevestig de issue
2. [ ] Check health endpoint: `curl https://vb-converter.company.nl/health`
3. [ ] Check container status: `docker-compose ps`
4. [ ] Check logs: `docker-compose logs --tail=100`
5. [ ] Probeer restart: `docker-compose restart`
6. [ ] Indien nodig: rollback naar vorige versie
7. [ ] Notify stakeholders
8. [ ] Schedule post-mortem

## Common Procedures

### Restart Services

```bash
cd /opt/vb-converter
docker-compose restart
```

### View Logs

```bash
# All logs
docker-compose logs -f

# Backend only
docker-compose logs -f backend

# Last 100 lines
docker-compose logs --tail=100 backend
```

### Manual Deployment

```bash
# Pull latest images
docker-compose pull

# Restart with new images
docker-compose up -d
```

### Database/File Cleanup

```bash
# Clear upload directory
docker-compose exec backend rm -rf /app/uploads/*
```

## Contacts

| Role | Contact |
|------|---------|
| Tech Lead | [email] |
| DevOps | [email] |
| Product Owner | [email] |
```

**⏸️ IMPLEMENTATIE COMPLEET**

---

## VALIDATIE CHECKLIST

Na afronding, controleer:

### Code
- [ ] Geen hardcoded secrets in code
- [ ] Environment configuratie werkt
- [ ] Linting passed (`black`, `flake8`, `eslint`)
- [ ] Type checking passed (`mypy`, `tsc`)
- [ ] Tests draaien en slagen

### Docker
- [ ] Backend image bouwt succesvol
- [ ] Frontend image bouwt succesvol
- [ ] Docker Compose werkt lokaal
- [ ] Health checks werken

### CI/CD
- [ ] CI pipeline is groen
- [ ] CD naar test werkt
- [ ] GitHub secrets geconfigureerd
- [ ] Environments aangemaakt in GitHub

### Security
- [ ] Security headers aanwezig in responses
- [ ] CORS correct geconfigureerd
- [ ] Rate limiting werkt (test met meerdere requests)
- [ ] Audit logging actief

### Documentatie
- [ ] README.md up-to-date
- [ ] DEPLOYMENT.md compleet
- [ ] RUNBOOK.md aanwezig
- [ ] CHANGELOG.md bijgewerkt

---

## BELANGRIJKE OPMERKINGEN

1. **Bestaande code behouden** - De VB_Converter heeft al goede architectuur (MVC/DDD), we voegen alleen DevOps/security/infra toe
2. **SpaCy model** - Is groot (~50MB), zorg voor voldoende resources en tijd in Docker builds
3. **NLP dependencies** - Kunnen lang duren om te installeren; gebruik caching in CI
4. **Vraag altijd om goedkeuring** tussen fases voordat je verdergaat
5. **Test na elke fase** of de applicatie nog correct werkt
6. **Commit regelmatig** zodat je kunt terugdraaien indien nodig

---

## BEGIN

Start nu met **FASE 0: INVENTARISATIE**.

Analyseer de complete codebase en maak de documentatie voordat je enige wijzigingen doorvoert. Vraag om goedkeuring voordat je naar de volgende fase gaat.
