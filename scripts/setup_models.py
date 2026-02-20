#!/usr/bin/env python3
"""
Pre-download alle ML/NLP modellen voor Hienfeld VB Converter.

Draai dit script NA pip install -r requirements.txt:
    python scripts/setup_models.py

Dit voorkomt lange wachttijden bij eerste gebruik van de applicatie.
"""
import subprocess
import sys
import os
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def print_header(text: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")


def print_status(success: bool, name: str) -> None:
    icon = "[OK]" if success else "[FAIL]"
    print(f"{icon} {name}")


def download_spacy_model() -> bool:
    """Download SpaCy Dutch model."""
    print("Downloading SpaCy nl_core_news_md (~50 MB)...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "spacy", "download", "nl_core_news_md"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return True
        print(f"  Error: {result.stderr}")
        return False
    except Exception as e:
        print(f"  Error: {e}")
        return False


def download_sentence_transformers() -> bool:
    """Download sentence-transformers embedding model."""
    print("Downloading sentence-transformers model (~2.5 GB)...")
    print("  Model: intfloat/multilingual-e5-large-instruct")
    print("  Dit kan 5-10 minuten duren bij eerste download...")
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer('intfloat/multilingual-e5-large-instruct')
        # Quick test
        _ = model.encode(["test"])
        return True
    except Exception as e:
        print(f"  Error: {e}")
        return False


def download_wordnet() -> bool:
    """Download Open Dutch WordNet and dependencies."""
    print("Downloading Open Dutch WordNet + dependencies (~5 MB)...")
    try:
        import wn
        # Download English WordNet first (dependency for Dutch)
        print("  - Downloading English WordNet (dependency)...")
        wn.download('omw-en:1.4')
        # Download Dutch WordNet
        print("  - Downloading Dutch WordNet...")
        wn.download('omw-nl:1.4')
        # Verify it works
        _ = wn.Wordnet('omw-nl')
        return True
    except Exception as e:
        print(f"  Error: {e}")
        return False


def verify_models() -> dict:
    """Verify all models are installed and working."""
    results = {}

    # SpaCy
    try:
        import spacy
        nlp = spacy.load("nl_core_news_md")
        _ = nlp("Test zin voor verificatie.")
        results['spacy'] = True
    except Exception:
        results['spacy'] = False

    # Sentence Transformers
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer('intfloat/multilingual-e5-large-instruct')
        _ = model.encode(["test"])
        results['embeddings'] = True
    except Exception:
        results['embeddings'] = False

    # WordNet
    try:
        import wn
        _ = wn.Wordnet('omw-nl')
        results['wordnet'] = True
    except Exception:
        results['wordnet'] = False

    return results


def main():
    print_header("Hienfeld VB Converter - Model Setup")
    print("Dit script downloadt alle benodigde ML/NLP modellen.\n")

    # Check if running from correct directory
    if not Path("requirements.txt").exists():
        print("❌ Draai dit script vanuit de project root directory!")
        print("   cd C:\\Users\\Stef\\Desktop\\Vb agent")
        print("   python scripts/setup_models.py")
        sys.exit(1)

    results = {}

    # 1. SpaCy
    print_header("1/3 - SpaCy Dutch Model")
    results['spacy'] = download_spacy_model()

    # 2. Sentence Transformers (largest, do this one last conceptually but it's important)
    print_header("2/3 - Sentence Transformers Embeddings")
    results['embeddings'] = download_sentence_transformers()

    # 3. WordNet
    print_header("3/3 - Dutch WordNet")
    results['wordnet'] = download_wordnet()

    # Summary
    print_header("Resultaat")
    print_status(results.get('spacy', False), "SpaCy nl_core_news_md")
    print_status(results.get('embeddings', False), "Sentence Transformers (multilingual-e5-large-instruct)")
    print_status(results.get('wordnet', False), "Open Dutch WordNet (omw-nl)")

    # Verify
    print_header("Verificatie")
    print("Alle modellen testen...")
    verified = verify_models()

    all_ok = all(verified.values())

    print()
    print_status(verified.get('spacy', False), "SpaCy werkt")
    print_status(verified.get('embeddings', False), "Embeddings werken")
    print_status(verified.get('wordnet', False), "WordNet werkt")

    print()
    if all_ok:
        print("=" * 60)
        print("  [OK] ALLE MODELLEN KLAAR - App is productie-ready!")
        print("=" * 60)
        print("\nStart de applicatie met: start.bat")
    else:
        print("=" * 60)
        print("  [!] SOMMIGE MODELLEN ONTBREKEN")
        print("=" * 60)
        print("\nDe app werkt nog steeds, maar met beperkte functionaliteit.")
        print("Probeer het script opnieuw te draaien of installeer handmatig.")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
