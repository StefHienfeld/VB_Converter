"""
Download alle benodigde modellen voor semantische analyse.
Draai dit eenmalig voor demo/productie om startup delays te voorkomen.
"""
import sys

print("Downloading semantic analysis models...")
print("Dit duurt ~5 minuten, maar hoeft maar 1x\n")

# 1. Sentence transformers embedding model
print("[1/2] Downloading sentence-transformers model (90MB)...")
try:
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer('all-MiniLM-L6-v2')
    print(f"OK - Embedding model ready: {model.get_sentence_embedding_dimension()}D vectors\n")
except Exception as e:
    print(f"FAILED to download embeddings: {e}\n")
    sys.exit(1)

# 2. SpaCy Nederlands model
print("[2/2] Checking spaCy Dutch model...")
try:
    import spacy
    try:
        nlp = spacy.load('nl_core_news_md')
        print("OK - SpaCy model already installed\n")
    except OSError:
        print("Installing SpaCy Dutch model (45MB)...")
        import subprocess
        subprocess.check_call([sys.executable, '-m', 'spacy', 'download', 'nl_core_news_md'])
        print("OK - SpaCy model installed\n")
except Exception as e:
    print(f"FAILED with spaCy: {e}\n")
    sys.exit(1)

print("=" * 60)
print("KLAAR! Alle modellen zijn gedownload.")
print("Je app start nu snel zonder delays.")
print("=" * 60)

