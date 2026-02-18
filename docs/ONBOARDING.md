# Developer Onboarding Guide

Welkom bij het VB Converter project! Deze gids helpt je om snel aan de slag te gaan.

---

## Inhoudsopgave

1. [Systeemvereisten](#systeemvereisten)
2. [Lokale Setup](#lokale-setup)
3. [IDE Configuratie](#ide-configuratie)
4. [Git Workflow](#git-workflow)
5. [Eerste Taken](#eerste-taken)
6. [Veelgestelde Vragen](#veelgestelde-vragen)

---

## Systeemvereisten

### Minimale Vereisten

| Component | Versie | Verificatie |
|-----------|--------|-------------|
| **Python** | 3.10+ | `python --version` |
| **Node.js** | 18+ (20+ aanbevolen) | `node --version` |
| **npm** | 9+ | `npm --version` |
| **Git** | 2.30+ | `git --version` |
| **RAM** | 8GB minimum | Voor SpaCy + embeddings |
| **Disk** | 5GB vrij | Voor models en dependencies |

### Optioneel (voor Docker deployment)

| Component | Versie | Verificatie |
|-----------|--------|-------------|
| Docker | 20.10+ | `docker --version` |
| Docker Compose | 2.0+ | `docker compose version` |

### Windows-specifiek

Op Windows heb je ook nodig:
- **Visual Studio Build Tools** (voor sommige Python packages)
- **pywin32** (wordt automatisch geinstalleerd)

```powershell
# Check of alles geinstalleerd is
python --version
node --version
git --version
```

---

## Lokale Setup

### Stap 1: Repository Clonen

```bash
# Clone de repository
git clone https://github.com/stefhienfeld/vb-converter.git
cd vb-converter

# Bekijk de structuur
ls -la
```

### Stap 2: Backend Setup (Python)

```bash
# 1. Maak een virtuele environment aan
python -m venv .venv

# 2. Activeer de environment
# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# Windows (CMD):
.\.venv\Scripts\activate.bat
# Linux/macOS:
source .venv/bin/activate

# 3. Installeer dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 4. Download het Nederlandse SpaCy model (VERPLICHT)
python -m spacy download nl_core_news_md

# 5. Verifieer installatie
python -c "import spacy; nlp = spacy.load('nl_core_news_md'); print('SpaCy OK!')"
```

**Let op:** De eerste keer dat je de applicatie start, worden embedding models gedownload (~500MB). Dit kan enkele minuten duren.

### Stap 3: Frontend Setup (Node.js)

```bash
# Installeer Node dependencies
npm install

# Verifieer installatie
npm run lint
```

### Stap 4: Environment Configuratie

```bash
# Kopieer de example config
cp environments/.env.example .env

# Bewerk .env indien nodig (defaults zijn OK voor development)
```

**Belangrijke .env variabelen voor development:**

```env
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000,http://localhost:8080
```

### Stap 5: Services Starten

**Terminal 1 - Backend:**
```bash
# Activeer environment (indien nog niet actief)
.\.venv\Scripts\Activate.ps1  # Windows
source .venv/bin/activate       # Linux/macOS

# Start de FastAPI server
uvicorn hienfeld_api.app:app --reload --port 8000

# Of met developer mode (meer logging):
$env:HIENFELD_DEV_MODE=1; uvicorn hienfeld_api.app:app --reload --port 8000
```

**Terminal 2 - Frontend:**
```bash
npm run dev
```

### Stap 6: Verificatie

Open je browser en ga naar:

| URL | Beschrijving |
|-----|--------------|
| http://localhost:5173 | Frontend (React) |
| http://localhost:8000/docs | API documentatie (Swagger) |
| http://localhost:8000/api/health | Health check endpoint |

**Test de health check:**
```bash
curl http://localhost:8000/api/health
# Verwacht: {"status":"healthy","version":"3.1.0",...}
```

---

## IDE Configuratie

### VS Code (Aanbevolen)

**Installeer deze extensies:**

```json
// .vscode/extensions.json
{
  "recommendations": [
    "ms-python.python",
    "ms-python.vscode-pylance",
    "ms-python.black-formatter",
    "esbenp.prettier-vscode",
    "bradlc.vscode-tailwindcss",
    "dbaeumer.vscode-eslint"
  ]
}
```

**Aanbevolen settings:**

```json
// .vscode/settings.json
{
  "python.defaultInterpreterPath": ".venv/Scripts/python.exe",
  "python.analysis.typeCheckingMode": "basic",
  "[python]": {
    "editor.formatOnSave": true,
    "editor.defaultFormatter": "ms-python.black-formatter"
  },
  "[typescript]": {
    "editor.formatOnSave": true,
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  },
  "[typescriptreact]": {
    "editor.formatOnSave": true,
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  },
  "tailwindCSS.experimental.classRegex": [
    ["cva\\(([^)]*)\\)", "[\"'`]([^\"'`]*).*?[\"'`]"]
  ]
}
```

### PyCharm

1. Open het project als Python project
2. Configureer interpreter: `.venv/Scripts/python.exe`
3. Installeer plugin: **Python Black Formatter**
4. Enable auto-format on save

### Debugging Configuratie

**VS Code launch.json:**
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "FastAPI Backend",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["hienfeld_api.app:app", "--reload", "--port", "8000"],
      "env": {
        "HIENFELD_DEV_MODE": "1"
      }
    },
    {
      "name": "Run Tests",
      "type": "python",
      "request": "launch",
      "module": "pytest",
      "args": ["-v", "tests/"]
    }
  ]
}
```

---

## Git Workflow

### Branch Strategie

```
main            - Productie code (protected)
  |
  +-- develop   - Development branch (merge target)
       |
       +-- feature/xyz    - Nieuwe features
       +-- fix/xyz        - Bug fixes
       +-- docs/xyz       - Documentatie
```

### Nieuwe Feature Maken

```bash
# 1. Zorg dat develop up-to-date is
git checkout develop
git pull origin develop

# 2. Maak een feature branch
git checkout -b feature/mijn-feature

# 3. Maak je wijzigingen
# ... code ...

# 4. Commit met duidelijke message
git add -A
git commit -m "feat: beschrijving van de feature"

# 5. Push naar remote
git push -u origin feature/mijn-feature

# 6. Maak een Pull Request op GitHub
```

### Commit Message Conventies

Volg de [Conventional Commits](https://www.conventionalcommits.org/) standaard:

| Prefix | Gebruik |
|--------|---------|
| `feat:` | Nieuwe feature |
| `fix:` | Bug fix |
| `docs:` | Documentatie |
| `refactor:` | Code refactoring |
| `test:` | Tests toevoegen |
| `chore:` | Maintenance taken |
| `perf:` | Performance verbetering |

**Voorbeelden:**
```bash
git commit -m "feat: add custom instructions parser"
git commit -m "fix: resolve clustering timeout for large files"
git commit -m "docs: update onboarding guide"
```

### Code Review Checklist

Voordat je een PR maakt, controleer:

- [ ] Alle tests slagen (`pytest tests/`)
- [ ] Linting is OK (`npm run lint` en `black --check hienfeld/`)
- [ ] Documentatie is bijgewerkt indien nodig
- [ ] Geen hardcoded secrets of credentials
- [ ] Commit messages volgen conventie

---

## Eerste Taken

### Beginner (Week 1)

1. **Maak de lokale setup compleet**
   - Volg alle stappen in deze guide
   - Verifieer dat beide services draaien
   - Test een analyse met een sample Excel file

2. **Lees de architectuur documentatie**
   - `docs/ARCHITECTURE.md` - Systeem overzicht
   - `CLAUDE.md` - Codebase referentie
   - `docs/RUNBOOK.md` - Operations procedures

3. **Verken de codebase**
   - Bekijk `hienfeld/services/analysis_service.py`
   - Bekijk `src/pages/Index.tsx`
   - Run de tests: `pytest tests/ -v`

### Intermediate (Week 2-3)

4. **Fix een "good first issue"**
   - Check GitHub Issues met label `good-first-issue`
   - Vaak kleine bug fixes of documentatie updates

5. **Voeg een test toe**
   - Kies een service zonder test coverage
   - Schrijf unit tests in `tests/unit/`
   - Doel: 70%+ coverage

6. **Verbeter de documentatie**
   - Update inline comments
   - Voeg docstrings toe aan functies

### Advanced (Week 4+)

7. **Implementeer een feature**
   - Check het roadmap in `docs/AUDIT_REPORT.md`
   - Bespreek met team lead voor toewijzing

8. **Performance optimalisatie**
   - Profile met `HIENFELD_DEV_MODE=1`
   - Identificeer bottlenecks
   - Implementeer verbeteringen

---

## Veelgestelde Vragen

### Q: SpaCy model download faalt

**A:** Probeer handmatig:
```bash
python -m spacy download nl_core_news_md --direct
```

Of download via pip:
```bash
pip install https://github.com/explosion/spacy-models/releases/download/nl_core_news_md-3.7.0/nl_core_news_md-3.7.0-py3-none-any.whl
```

### Q: "Module not found" errors in Python

**A:** Controleer of je virtual environment actief is:
```bash
# Windows
.\.venv\Scripts\Activate.ps1

# Verifieer
which python  # Moet naar .venv wijzen
```

### Q: Frontend kan backend niet bereiken

**A:** Controleer:
1. Backend draait op poort 8000: `curl http://localhost:8000/api/health`
2. CORS is correct geconfigureerd in `.env`
3. Geen firewall blokkades

### Q: Analyse duurt lang (>10 minuten)

**A:** De eerste analyse duurt langer door model loading. Daarna:
- FAST mode: ~4 seconden
- BALANCED mode: ~10 minuten (normaal)
- Check `HIENFELD_DEV_MODE=1` logs voor bottlenecks

### Q: Hoe kan ik debugging inschakelen?

**A:** Gebruik developer mode:
```bash
# Windows PowerShell
$env:HIENFELD_DEV_MODE=1
uvicorn hienfeld_api.app:app --reload --port 8000

# Linux/macOS
HIENFELD_DEV_MODE=1 uvicorn hienfeld_api.app:app --reload --port 8000
```

Dit geeft:
- DEBUG level logging
- Gekleurde console output
- Performance timing per fase

### Q: Hoe maak ik een password hash voor AUTH?

**A:**
```python
python -c "from passlib.context import CryptContext; c=CryptContext(schemes=['bcrypt']); print(c.hash('jouw-wachtwoord'))"
```

---

## Contacten

| Rol | Contact |
|-----|---------|
| Tech Lead | Via GitHub Issues |
| Code Review | Via Pull Requests |
| Security Issues | Security@hienfeld.nl |

---

## Volgende Stappen

1. Voltooi de lokale setup
2. Lees `docs/ARCHITECTURE.md`
3. Run de test suite: `pytest tests/ -v`
4. Maak je eerste commit!

**Veel succes!**
