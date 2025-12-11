#!/usr/bin/env python3
"""
Test script to verify that FAST, BALANCED, and ACCURATE modes produce different results.
"""
import sys
sys.path.insert(0, '/Users/stef/Desktop/dev/VB_Converter')

from hienfeld.config import load_config, AnalysisMode
from hienfeld.services.hybrid_similarity_service import HybridSimilarityService
from hienfeld.services.document_similarity_service import DocumentSimilarityService

# Test texts (typical insurance clauses)
TEXT_A = "De verzekerde som voor inboedel bedraagt maximaal 50.000 euro per gebeurtenis."
TEXT_B = "Het verzekerd bedrag voor huisraad is ten hoogste vijftigduizend euro per schade."

TEXT_C = "Bij diefstal met braak wordt de schade volledig vergoed."
TEXT_D = "Inbraakschade wordt geheel gedekt door de polis."

# Corpus for TF-IDF training (simulating policy conditions)
CORPUS = [
    "De verzekerde som is het maximum bedrag dat wordt uitgekeerd.",
    "Inboedel omvat alle roerende zaken in de woning.",
    "Diefstal met braak betekent dat er sporen van inbraak zijn.",
    "De polis dekt schade aan huisraad en inboedel.",
    "Het verzekerd bedrag wordt jaarlijks aangepast aan de index.",
]

def test_mode(mode: AnalysisMode):
    """Test a single mode and return similarity scores."""
    config = load_config()
    config.semantic.apply_mode(mode)
    
    # Get mode config
    mode_config = config.semantic.get_active_config()
    
    print(f"\n{'='*60}")
    print(f"🧪 Testing mode: {mode.value.upper()}")
    print(f"{'='*60}")
    print(f"  SpaCy model: {mode_config.spacy_model}")
    print(f"  Embedding model: {mode_config.embedding_model or '(disabled)'}")
    print(f"  Enable NLP: {mode_config.enable_nlp}")
    print(f"  Enable TF-IDF: {mode_config.enable_tfidf}")
    print(f"  Enable Synonyms: {mode_config.enable_synonyms}")
    print(f"  Enable Embeddings: {mode_config.enable_embeddings}")
    print(f"  Weights: RF={mode_config.weight_rapidfuzz:.0%}, "
          f"Lemma={mode_config.weight_lemmatized:.0%}, "
          f"TF-IDF={mode_config.weight_tfidf:.0%}, "
          f"Syn={mode_config.weight_synonyms:.0%}, "
          f"Emb={mode_config.weight_embeddings:.0%}")
    
    # Create TF-IDF service and train on corpus
    tfidf_service = DocumentSimilarityService(config)
    if tfidf_service.is_available and mode_config.enable_tfidf:
        tfidf_service.train_on_corpus(CORPUS)
        print(f"  TF-IDF trained: {tfidf_service.is_trained}")
    
    # Create hybrid service
    hybrid = HybridSimilarityService(
        config,
        tfidf_service=tfidf_service if mode_config.enable_tfidf else None,
        semantic_service=None,  # Skip embeddings for quick test
    )
    
    # Force service initialization
    hybrid._ensure_services_initialized()
    
    # Get service availability
    stats = hybrid.get_statistics()
    services = stats['services_available']
    print(f"\n  Services available:")
    for svc, available in services.items():
        status = "✅" if available else "❌"
        print(f"    {status} {svc}")
    
    # Test similarity
    print(f"\n  Similarity tests:")
    
    # Test 1: Similar meaning, different words
    score1 = hybrid.similarity(TEXT_A, TEXT_B)
    print(f"    Test 1 (similar meaning): {score1:.3f}")
    
    # Test 2: Different topic
    score2 = hybrid.similarity(TEXT_A, TEXT_C)
    print(f"    Test 2 (different topic): {score2:.3f}")
    
    # Test 3: Same topic, different words
    score3 = hybrid.similarity(TEXT_C, TEXT_D)
    print(f"    Test 3 (same topic, diff words): {score3:.3f}")
    
    # Get detailed breakdown for Test 1
    breakdown = hybrid.similarity_detailed(TEXT_A, TEXT_B)
    print(f"\n  Detailed breakdown for Test 1:")
    print(f"    RapidFuzz: {breakdown.rapidfuzz:.3f}")
    print(f"    Lemmatized: {breakdown.lemmatized:.3f}")
    print(f"    TF-IDF: {breakdown.tfidf:.3f}")
    print(f"    Synonyms: {breakdown.synonyms:.3f}")
    print(f"    Embeddings: {breakdown.embeddings:.3f}")
    print(f"    FINAL: {breakdown.final_score:.3f}")
    print(f"    Methods used: {breakdown.methods_used}")
    
    return {
        'mode': mode.value,
        'test1': score1,
        'test2': score2,
        'test3': score3,
        'breakdown': breakdown.to_dict()
    }

def main():
    print("🔬 Mode Comparison Test")
    print("=" * 60)
    
    results = {}
    
    for mode in [AnalysisMode.FAST, AnalysisMode.BALANCED, AnalysisMode.ACCURATE]:
        try:
            results[mode.value] = test_mode(mode)
        except Exception as e:
            print(f"\n❌ Error testing {mode.value}: {e}")
            import traceback
            traceback.print_exc()
    
    # Summary comparison
    print(f"\n{'='*60}")
    print("📊 SUMMARY COMPARISON")
    print(f"{'='*60}")
    print(f"\n{'Test':<30} {'FAST':>10} {'BALANCED':>10} {'ACCURATE':>10}")
    print("-" * 60)
    
    if results:
        for test_name in ['test1', 'test2', 'test3']:
            row = f"{test_name:<30}"
            for mode in ['fast', 'balanced', 'accurate']:
                if mode in results:
                    row += f" {results[mode][test_name]:>10.3f}"
                else:
                    row += f" {'N/A':>10}"
            print(row)
        
        # Check if all modes are identical
        fast = results.get('fast', {})
        balanced = results.get('balanced', {})
        accurate = results.get('accurate', {})
        
        all_identical = (
            fast.get('test1') == balanced.get('test1') == accurate.get('test1') and
            fast.get('test2') == balanced.get('test2') == accurate.get('test2') and
            fast.get('test3') == balanced.get('test3') == accurate.get('test3')
        )
        
        print(f"\n{'='*60}")
        if all_identical:
            print("⚠️  WARNING: All modes produced IDENTICAL results!")
            print("   This means the semantic features are NOT working correctly.")
        else:
            print("✅ SUCCESS: Modes produce DIFFERENT results as expected!")

if __name__ == "__main__":
    main()
