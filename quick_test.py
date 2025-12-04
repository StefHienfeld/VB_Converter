#!/usr/bin/env python3
"""
Quick test of semantic similarity for Dutch insurance texts.

Tests whether the semantic similarity service can recognize that two
differently-worded texts have the same meaning.
"""
import sys
import os

# Suppress warnings
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'

def main():
    print("=" * 60)
    print("TEST: Semantische Similarity voor Evacuatie Teksten")
    print("=" * 60)
    print()
    
    print("Loading model...")
    from sentence_transformers import SentenceTransformer
    import numpy as np
    
    # Using all-MiniLM-L6-v2 - smaller model that's already cached
    # Note: For production with Dutch texts, use paraphrase-multilingual-MiniLM-L12-v2 (needs more disk space)
    model = SentenceTransformer('all-MiniLM-L6-v2')
    print("Model loaded!")
    print()
    
    # Original text from conditions
    original = """Kosten gedwongen evacuatie. Indien het gebouw niet bewoond kan worden doordat het bevoegd gezag dit verbiedt, kosten van een vergelijkbaar verblijf elders voor verzekerde. Het verbod moet een direct gevolg zijn van een gebeurtenis bij een naburig pand. De kosten worden voor maximaal 30 dagen vergoed. Gederfde huur wordt ook vergoed."""
    
    # Rewritten text (same meaning, different words)
    rewritten = """Dekking bij noodgedwongen evacuatie. Wij vergoeden de kosten voor vervangende huisvesting als het bevoegd gezag het verblijf in het gebouw verbiedt. Dit verbod moet het directe gevolg zijn van een gebeurtenis bij een naastgelegen pand. De vergoeding geldt voor maximaal 30 dagen. Ook huurderving wordt vergoed."""
    
    # Unrelated text for comparison
    unrelated = """Schade door brand wordt vergoed inclusief bluswater en rook. De maximale vergoeding bedraagt 100.000 euro."""
    
    print("ORIGINELE TEKST (uit voorwaarden):")
    print("-" * 50)
    print(original[:100] + "...")
    print()
    
    print("HERSCHREVEN TEKST (op de polis):")
    print("-" * 50)
    print(rewritten[:100] + "...")
    print()
    
    print("Computing embeddings...")
    embeddings = model.encode([original, rewritten, unrelated])
    
    def cosine_sim(a, b):
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
    
    sim_orig_rewritten = cosine_sim(embeddings[0], embeddings[1])
    sim_orig_unrelated = cosine_sim(embeddings[0], embeddings[2])
    
    print()
    print("=" * 60)
    print("RESULTATEN:")
    print("=" * 60)
    print(f"Origineel vs Herschreven:   {sim_orig_rewritten:.2%}")
    print(f"Origineel vs Ongerelateerd: {sim_orig_unrelated:.2%}")
    print()
    
    THRESHOLD = 0.70
    
    if sim_orig_rewritten >= THRESHOLD:
        print(f"✅ SUCCESS! Score ({sim_orig_rewritten:.2%}) >= threshold ({THRESHOLD:.0%})")
        print("   De teksten worden herkend als SEMANTISCH GELIJK!")
        print("   Dit leidt tot advies: VERWIJDEREN")
    else:
        print(f"❌ Score ({sim_orig_rewritten:.2%}) < threshold ({THRESHOLD:.0%})")
    
    print()
    print(f"Verschil met ongerelateerde tekst: +{sim_orig_rewritten - sim_orig_unrelated:.2%}")

if __name__ == "__main__":
    main()

