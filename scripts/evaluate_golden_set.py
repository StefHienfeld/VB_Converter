#!/usr/bin/env python3
"""
Golden Set Evaluatie Script
===========================

Vergelijkt de output van de VB Converter met de Golden Set om
de accuracy en andere metrics te berekenen.

Gebruik:
    python scripts/evaluate_golden_set.py golden_set.csv analyse_output.xlsx

Output:
    - Overall accuracy
    - Precision/Recall per advies-categorie
    - Confusion matrix
    - Lijst met fouten voor analyse
"""

import argparse
import pandas as pd
import sys
from pathlib import Path
from collections import defaultdict

# Voeg project root toe aan path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# Mapping van tool-output naar Golden Set categorieën
ADVICE_MAPPING = {
    # Directe matches
    'VERWIJDEREN': 'VERWIJDEREN',
    'BEHOUDEN': 'BEHOUDEN',
    'BEHOUDEN (CLAUSULE)': 'BEHOUDEN',
    'BEHOUDEN (MAATWERK)': 'BEHOUDEN',
    'HANDMATIG CHECKEN': 'HANDMATIG CHECKEN',
    'VERVANGEN': 'VERVANGEN',

    # Standaardiseren = Vervangen
    '🛠️ STANDAARDISEREN': 'VERVANGEN',
    'STANDAARDISEREN': 'VERVANGEN',

    # Admin codes -> Verwijderen of Handmatig
    '📅 VERWIJDEREN (VERLOPEN)': 'VERWIJDEREN',
    '🧹 OPSCHONEN': 'HANDMATIG CHECKEN',
    '📝 AANVULLEN': 'HANDMATIG CHECKEN',
    '⚪ LEEG': 'VERWIJDEREN',
    '❌ ONLEESBAAR': 'HANDMATIG CHECKEN',

    # Frequentie/consistentie -> afhankelijk van context
    '📊 FREQUENTIE INFO': 'HANDMATIG CHECKEN',
    '🔄 CONSISTENTIE CHECK': 'HANDMATIG CHECKEN',
    '✨ UNIEK': 'HANDMATIG CHECKEN',
}


def normalize_advice(advice: str) -> str:
    """Normaliseer advies naar Golden Set categorieën."""
    if pd.isna(advice):
        return 'ONBEKEND'

    advice = str(advice).strip().upper()

    # Directe mapping
    for key, value in ADVICE_MAPPING.items():
        if key.upper() in advice or advice in key.upper():
            return value

    # Fallback patronen
    if 'VERWIJDER' in advice:
        return 'VERWIJDEREN'
    if 'BEHOUD' in advice:
        return 'BEHOUDEN'
    if 'VERVANG' in advice or 'STANDAARD' in advice:
        return 'VERVANGEN'
    if 'CHECK' in advice or 'HANDMATIG' in advice:
        return 'HANDMATIG CHECKEN'

    return 'ONBEKEND'


def load_golden_set(path: Path) -> pd.DataFrame:
    """Laad en valideer Golden Set."""
    if path.suffix.lower() == '.csv':
        df = pd.read_csv(path, encoding='utf-8-sig')
    else:
        df = pd.read_excel(path)

    required_cols = ['clausule_id', 'clausule_tekst', 'correct_advies']
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Ontbrekende kolommen in Golden Set: {missing}")

    # Filter niet-gelabelde rijen
    df = df[df['correct_advies'].notna() & (df['correct_advies'].str.strip() != '')]

    print(f"📋 Golden Set: {len(df)} gelabelde clausules")
    return df


def load_analysis_output(path: Path) -> pd.DataFrame:
    """Laad analyse output."""
    if path.suffix.lower() == '.csv':
        df = pd.read_csv(path, encoding='utf-8-sig')
    else:
        df = pd.read_excel(path)

    print(f"📊 Analyse output: {len(df)} rijen")
    return df


def match_clauses(golden_df: pd.DataFrame, analysis_df: pd.DataFrame) -> pd.DataFrame:
    """
    Match Golden Set clausules met analyse output.

    Gebruikt fuzzy text matching om clausules te koppelen.
    """
    from rapidfuzz import fuzz

    # Detecteer tekstkolom in analyse output
    text_cols = ['Vrije_Teksten', 'Tekst', 'simplified_text', 'raw_text', 'text']
    text_col = None
    for col in text_cols:
        if col in analysis_df.columns:
            text_col = col
            break

    if text_col is None:
        # Fallback: langste tekstkolom
        text_cols = analysis_df.select_dtypes(include=['object']).columns
        if len(text_cols) == 0:
            raise ValueError("Geen tekstkolom gevonden in analyse output")
        text_col = max(text_cols, key=lambda c: analysis_df[c].astype(str).str.len().mean())

    # Detecteer advieskolom in analyse output
    advice_cols = ['Advies', 'advies', 'advice', 'Actie']
    advice_col = None
    for col in advice_cols:
        if col in analysis_df.columns:
            advice_col = col
            break

    if advice_col is None:
        raise ValueError("Geen advieskolom gevonden in analyse output")

    print(f"   Tekstkolom: {text_col}")
    print(f"   Advieskolom: {advice_col}")

    # Match clausules
    results = []
    unmatched = 0

    for _, golden_row in golden_df.iterrows():
        golden_text = str(golden_row['clausule_tekst']).strip()
        golden_advice = normalize_advice(golden_row['correct_advies'])

        # Zoek beste match in analyse output
        best_match = None
        best_score = 0

        for _, analysis_row in analysis_df.iterrows():
            analysis_text = str(analysis_row[text_col]).strip()
            score = fuzz.ratio(golden_text.lower(), analysis_text.lower())

            if score > best_score:
                best_score = score
                best_match = analysis_row

        if best_score >= 85:  # Match threshold
            predicted_advice = normalize_advice(best_match[advice_col])
            results.append({
                'clausule_id': golden_row['clausule_id'],
                'golden_advice': golden_advice,
                'predicted_advice': predicted_advice,
                'match_score': best_score,
                'correct': golden_advice == predicted_advice,
                'text_preview': golden_text[:80] + '...' if len(golden_text) > 80 else golden_text
            })
        else:
            unmatched += 1
            results.append({
                'clausule_id': golden_row['clausule_id'],
                'golden_advice': golden_advice,
                'predicted_advice': 'NIET GEVONDEN',
                'match_score': best_score,
                'correct': False,
                'text_preview': golden_text[:80] + '...' if len(golden_text) > 80 else golden_text
            })

    if unmatched > 0:
        print(f"⚠️  {unmatched} clausules niet gevonden in analyse output")

    return pd.DataFrame(results)


def calculate_metrics(results_df: pd.DataFrame) -> dict:
    """Bereken evaluatie metrics."""
    # Filter matched results
    matched = results_df[results_df['predicted_advice'] != 'NIET GEVONDEN']

    if len(matched) == 0:
        return {'error': 'Geen matches gevonden'}

    # Overall accuracy
    accuracy = matched['correct'].mean()

    # Per-categorie metrics
    categories = ['VERWIJDEREN', 'BEHOUDEN', 'VERVANGEN', 'HANDMATIG CHECKEN']
    per_category = {}

    for cat in categories:
        # True positives: correct voorspeld als deze categorie
        tp = len(matched[(matched['golden_advice'] == cat) & (matched['predicted_advice'] == cat)])
        # False positives: verkeerd voorspeld als deze categorie
        fp = len(matched[(matched['golden_advice'] != cat) & (matched['predicted_advice'] == cat)])
        # False negatives: had deze categorie moeten zijn maar was anders
        fn = len(matched[(matched['golden_advice'] == cat) & (matched['predicted_advice'] != cat)])

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

        per_category[cat] = {
            'precision': precision,
            'recall': recall,
            'f1': f1,
            'support': len(matched[matched['golden_advice'] == cat])
        }

    # Confusion matrix
    confusion = defaultdict(lambda: defaultdict(int))
    for _, row in matched.iterrows():
        confusion[row['golden_advice']][row['predicted_advice']] += 1

    return {
        'accuracy': accuracy,
        'total_evaluated': len(matched),
        'total_correct': matched['correct'].sum(),
        'per_category': per_category,
        'confusion_matrix': dict(confusion)
    }


def print_report(metrics: dict, results_df: pd.DataFrame) -> None:
    """Print evaluatie rapport."""
    print("\n" + "=" * 60)
    print("  GOLDEN SET EVALUATIE RAPPORT")
    print("=" * 60)

    if 'error' in metrics:
        print(f"\n❌ {metrics['error']}")
        return

    # Overall metrics
    print(f"\n📊 OVERALL METRICS")
    print(f"   Accuracy:  {metrics['accuracy']:.1%}")
    print(f"   Correct:   {metrics['total_correct']}/{metrics['total_evaluated']}")

    # Per-categorie metrics
    print(f"\n📋 PER CATEGORIE")
    print(f"   {'Categorie':<20} {'Precision':>10} {'Recall':>10} {'F1':>10} {'Support':>10}")
    print(f"   {'-' * 60}")

    for cat, m in metrics['per_category'].items():
        print(f"   {cat:<20} {m['precision']:>10.1%} {m['recall']:>10.1%} "
              f"{m['f1']:>10.2f} {m['support']:>10}")

    # Confusion matrix
    print(f"\n🔀 CONFUSION MATRIX")
    print(f"   (rij = werkelijk, kolom = voorspeld)")

    categories = ['VERWIJDEREN', 'BEHOUDEN', 'VERVANGEN', 'HANDMATIG CHECKEN']
    print(f"\n   {'':>20}", end='')
    for cat in categories:
        print(f" {cat[:8]:>8}", end='')
    print()

    for actual in categories:
        print(f"   {actual:<20}", end='')
        for predicted in categories:
            count = metrics['confusion_matrix'].get(actual, {}).get(predicted, 0)
            print(f" {count:>8}", end='')
        print()

    # Fouten lijst
    errors = results_df[~results_df['correct']]
    if len(errors) > 0:
        print(f"\n❌ FOUTEN ({len(errors)} stuks)")
        print(f"   {'ID':<10} {'Werkelijk':<20} {'Voorspeld':<20} {'Tekst'}")
        print(f"   {'-' * 80}")

        for _, row in errors.head(15).iterrows():
            print(f"   {row['clausule_id']:<10} {row['golden_advice']:<20} "
                  f"{row['predicted_advice']:<20} {row['text_preview'][:40]}")

        if len(errors) > 15:
            print(f"   ... en nog {len(errors) - 15} fouten")

    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description='Evalueer VB Converter tegen Golden Set',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Voorbeelden:
  python scripts/evaluate_golden_set.py golden_set.csv analyse_output.xlsx
  python scripts/evaluate_golden_set.py golden_set.csv analyse_output.xlsx --output rapport.csv
        """
    )

    parser.add_argument(
        'golden_set',
        type=Path,
        help='Golden Set bestand (CSV of Excel)'
    )

    parser.add_argument(
        'analysis_output',
        type=Path,
        help='Analyse output bestand (CSV of Excel)'
    )

    parser.add_argument(
        '--output', '-o',
        type=Path,
        default=None,
        help='Exporteer gedetailleerde resultaten naar CSV'
    )

    args = parser.parse_args()

    # Valideer input
    if not args.golden_set.exists():
        print(f"❌ Golden Set niet gevonden: {args.golden_set}")
        sys.exit(1)

    if not args.analysis_output.exists():
        print(f"❌ Analyse output niet gevonden: {args.analysis_output}")
        sys.exit(1)

    # Laad data
    golden_df = load_golden_set(args.golden_set)
    analysis_df = load_analysis_output(args.analysis_output)

    # Match clausules
    print("\n🔍 Matching clausules...")
    results_df = match_clauses(golden_df, analysis_df)

    # Bereken metrics
    metrics = calculate_metrics(results_df)

    # Print rapport
    print_report(metrics, results_df)

    # Exporteer indien gewenst
    if args.output:
        results_df.to_csv(args.output, index=False, encoding='utf-8-sig')
        print(f"\n💾 Gedetailleerde resultaten geëxporteerd naar: {args.output}")


if __name__ == '__main__':
    main()
