#!/usr/bin/env python3
"""
Standalone test script for debugging custom instructions matching.

Usage:
    python test_custom_instructions.py
"""
import sys
import os

# Add project to path
sys.path.insert(0, os.path.dirname(__file__))

from hienfeld.services.custom_instructions_service import CustomInstructionsService
from hienfeld.services.similarity_service import RapidFuzzSimilarityService
from hienfeld.logging_config import setup_logging

# Setup logging to see all debug output
setup_logging()

def test_basic_matching():
    """Test basic contains matching with simple examples."""
    print("\n" + "=" * 80)
    print("TEST 1: Basic Contains Matching")
    print("=" * 80)
    
    # Initialize service
    fuzzy_service = RapidFuzzSimilarityService(threshold=0.65)
    service = CustomInstructionsService(
        fuzzy_service=fuzzy_service,
        semantic_service=None,
        hybrid_service=None
    )
    
    # Test case 1: Simple TSV format (like UI generates)
    print("\n--- Test Case 1: TSV Format ---")
    instructions_tsv = "medeverzekerde\tVullen in partijenkaart"
    print(f"Instructions (TSV): {repr(instructions_tsv)}")
    
    count = service.load_instructions(instructions_tsv)
    print(f"Loaded {count} instructions")
    
    # Test text (from user's screenshot)
    test_text = "VB1 # Als medeverzekerde is aangetekend mw. M. Kersloot-Lakemond."
    print(f"\nTest text: {test_text}")
    
    match = service.find_match(test_text)
    
    if match:
        print(f"✅ MATCH FOUND!")
        print(f"   Action: {match.instruction.action}")
        print(f"   Score: {match.score}")
        print(f"   Search text: {match.instruction.search_text}")
    else:
        print(f"❌ NO MATCH")
        print(f"   Expected: 'medeverzekerde' should be found in text")
        
        # Debug: manual check
        needle = "medeverzekerde".casefold()
        haystack = test_text.casefold()
        print(f"\n   Debug:")
        print(f"   Needle: '{needle}'")
        print(f"   Haystack: '{haystack}'")
        print(f"   Needle in haystack: {needle in haystack}")


def test_arrow_format():
    """Test arrow format (backwards compatibility)."""
    print("\n" + "=" * 80)
    print("TEST 2: Arrow Format (Backwards Compatible)")
    print("=" * 80)
    
    fuzzy_service = RapidFuzzSimilarityService(threshold=0.65)
    service = CustomInstructionsService(
        fuzzy_service=fuzzy_service,
        semantic_service=None,
        hybrid_service=None
    )
    
    instructions_arrow = """medeverzekerde
→ Vullen in partijenkaart"""
    
    print(f"Instructions (Arrow): {repr(instructions_arrow)}")
    
    count = service.load_instructions(instructions_arrow)
    print(f"Loaded {count} instructions")
    
    test_text = "VB1 # Als medeverzekerde is aangetekend mw. M. Kersloot-Lakemond."
    print(f"\nTest text: {test_text}")
    
    match = service.find_match(test_text)
    
    if match:
        print(f"✅ MATCH FOUND!")
        print(f"   Action: {match.instruction.action}")
        print(f"   Score: {match.score}")
    else:
        print(f"❌ NO MATCH")


def test_multiple_instructions():
    """Test multiple instructions at once."""
    print("\n" + "=" * 80)
    print("TEST 3: Multiple Instructions")
    print("=" * 80)
    
    fuzzy_service = RapidFuzzSimilarityService(threshold=0.65)
    service = CustomInstructionsService(
        fuzzy_service=fuzzy_service,
        semantic_service=None,
        hybrid_service=None
    )
    
    instructions = """medeverzekerde\tVullen in partijenkaart
sanctieclausule\tVerwijderen - mag weg
eigenrisico\tBehouden - belangrijk"""
    
    print(f"Instructions (3 rows):")
    for line in instructions.split('\n'):
        print(f"  {line}")
    
    count = service.load_instructions(instructions)
    print(f"\nLoaded {count} instructions")
    
    # Test multiple texts
    test_cases = [
        ("VB1 # Als medeverzekerde is aangetekend...", "Vullen in partijenkaart"),
        ("Deze sanctieclausule is verouderd.", "Verwijderen - mag weg"),
        ("Het eigenrisico bedraagt € 500.", "Behouden - belangrijk"),
        ("Dit is een normale clausule.", None),
    ]
    
    print("\nTesting multiple clauses:")
    for text, expected_action in test_cases:
        print(f"\n  Text: {text[:60]}...")
        match = service.find_match(text)
        if match:
            print(f"    ✅ Matched: {match.instruction.action}")
            if expected_action and match.instruction.action != expected_action:
                print(f"    ⚠️  Expected: {expected_action}")
        else:
            print(f"    ❌ No match")
            if expected_action:
                print(f"    ⚠️  Expected: {expected_action}")


def test_edge_cases():
    """Test edge cases and potential issues."""
    print("\n" + "=" * 80)
    print("TEST 4: Edge Cases")
    print("=" * 80)
    
    fuzzy_service = RapidFuzzSimilarityService(threshold=0.65)
    
    # Test case 1: Empty instructions
    print("\n--- Case 1: Empty Instructions ---")
    service1 = CustomInstructionsService(fuzzy_service=fuzzy_service)
    count1 = service1.load_instructions("")
    print(f"Empty string: Loaded {count1} instructions (expected: 0)")
    
    # Test case 2: Whitespace variations
    print("\n--- Case 2: Whitespace Variations ---")
    service2 = CustomInstructionsService(fuzzy_service=fuzzy_service)
    instructions2 = "  medeverzekerde  \t  Vullen in partijenkaart  "
    count2 = service2.load_instructions(instructions2)
    print(f"With whitespace: Loaded {count2} instructions")
    
    test_text = "Als medeverzekerde geldt..."
    match2 = service2.find_match(test_text)
    print(f"Match result: {'✅ Found' if match2 else '❌ Not found'}")
    
    # Test case 3: Case sensitivity
    print("\n--- Case 3: Case Sensitivity ---")
    service3 = CustomInstructionsService(fuzzy_service=fuzzy_service)
    instructions3 = "MEDEVERZEKERDE\tVullen in partijenkaart"
    count3 = service3.load_instructions(instructions3)
    
    test_text_lower = "als medeverzekerde is aangetekend"
    match3 = service3.find_match(test_text_lower)
    print(f"UPPERCASE instruction, lowercase text: {'✅ Found' if match3 else '❌ Not found'}")


if __name__ == "__main__":
    print("\n🧪 CUSTOM INSTRUCTIONS MATCHING TEST SUITE")
    print("=" * 80)
    
    try:
        test_basic_matching()
        test_arrow_format()
        test_multiple_instructions()
        test_edge_cases()
        
        print("\n" + "=" * 80)
        print("✅ ALL TESTS COMPLETED")
        print("=" * 80)
        print("\nCheck the output above to see if matching works correctly.")
        print("If you see '❌ NO MATCH' where you expect a match, there's a bug.")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

