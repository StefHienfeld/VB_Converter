#!/usr/bin/env python3
"""
Golden Set Export Script
========================

Exporteert clausules uit een bestaand Excel/CSV bestand voor handmatige labeling.
De expert kan deze clausules labelen om een Golden Evaluation Set te creëren.

Gebruik:
    python scripts/export_golden_set_candidates.py input.xlsx --output golden_candidates.csv --count 100

Output format:
    clausule_id, clausule_tekst, correct_advies, vertrouwen, toelichting_expert, categorie

De kolommen correct_advies, vertrouwen en toelichting_expert zijn leeg - deze
moet de domeinexpert invullen.
"""

import argparse
import pandas as pd
import random
import sys
from pathlib import Path

# Voeg project root toe aan path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# Mogelijke advies-waarden voor de Golden Set
VALID_ADVIEZEN = [
    "VERWIJDEREN",           # Mag weg, niet relevant
    "BEHOUDEN",              # Relevant, moet blijven
    "VERVANGEN",             # Moet vervangen worden door standaard tekst
    "HANDMATIG CHECKEN",     # Twijfelgeval, menselijke beoordeling nodig
]

# Vertrouwensniveaus
VALID_VERTROUWEN = ["Hoog", "Midden", "Laag"]


def detect_text_column(df: pd.DataFrame) -> str:
    """Detecteer de kolom met clausuletekst."""
    # Bekende kolomnamen voor tekst
    text_columns = [
        'Vrije_Teksten', 'vrije_teksten', 'Tekst', 'tekst', 'Text', 'text',
        'Clausule', 'clausule', 'Vrije Teksten', 'Clausule_Tekst',
        'simplified_text', 'raw_text', 'Vrije tekst', 'vrije tekst'
    ]

    for col in text_columns:
        if col in df.columns:
            return col

    # Fallback: zoek kolom met langste gemiddelde tekstlengte
    text_cols = df.select_dtypes(include=['object']).columns
    if len(text_cols) == 0:
        raise ValueError("Geen tekstkolommen gevonden in het bestand")

    avg_lengths = {col: df[col].astype(str).str.len().mean() for col in text_cols}
    return max(avg_lengths, key=avg_lengths.get)


def detect_advice_column(df: pd.DataFrame) -> str | None:
    """Detecteer de kolom met bestaand advies (optioneel)."""
    advice_columns = ['Advies', 'advies', 'Advice', 'advice', 'Actie', 'actie']

    for col in advice_columns:
        if col in df.columns:
            return col
    return None


def sample_clauses(
    df: pd.DataFrame,
    text_column: str,
    advice_column: str | None,
    count: int,
    include_edge_cases: bool = True
) -> pd.DataFrame:
    """
    Sample clausules met stratificatie op advies indien beschikbaar.

    Args:
        df: Input DataFrame
        text_column: Kolom met clausuletekst
        advice_column: Optionele kolom met bestaand advies
        count: Aantal clausules om te exporteren
        include_edge_cases: Voeg extra edge cases toe (korte/lange teksten)

    Returns:
        DataFrame met gesamplede clausules
    """
    # Filter lege teksten
    df = df[df[text_column].notna() & (df[text_column].str.strip() != '')]

    if len(df) < count:
        print(f"⚠️  Bestand bevat slechts {len(df)} niet-lege clausules, "
              f"exporteer alle {len(df)}")
        count = len(df)

    sampled_indices = []

    # Stratified sampling op advies indien beschikbaar
    if advice_column and advice_column in df.columns:
        advice_groups = df.groupby(advice_column)
        per_group = max(count // len(advice_groups), 5)

        for advice, group in advice_groups:
            n = min(per_group, len(group))
            sampled_indices.extend(group.sample(n=n).index.tolist())

        print(f"📊 Stratified sample: {len(sampled_indices)} clausules "
              f"verdeeld over {len(advice_groups)} advies-categorieën")
    else:
        # Random sample
        sampled_indices = df.sample(n=min(count, len(df))).index.tolist()

    # Voeg edge cases toe
    if include_edge_cases:
        # Korte teksten (< 50 karakters)
        short_texts = df[df[text_column].str.len() < 50]
        if len(short_texts) > 0:
            n_short = min(5, len(short_texts))
            short_indices = short_texts.sample(n=n_short).index.tolist()
            sampled_indices.extend(short_indices)
            print(f"➕ {n_short} korte teksten toegevoegd (edge cases)")

        # Lange teksten (> 500 karakters)
        long_texts = df[df[text_column].str.len() > 500]
        if len(long_texts) > 0:
            n_long = min(5, len(long_texts))
            long_indices = long_texts.sample(n=n_long).index.tolist()
            sampled_indices.extend(long_indices)
            print(f"➕ {n_long} lange teksten toegevoegd (edge cases)")

    # Deduplicate en limit
    sampled_indices = list(set(sampled_indices))[:count]

    return df.loc[sampled_indices]


def create_golden_set_template(
    df: pd.DataFrame,
    text_column: str,
    output_path: Path
) -> None:
    """
    Creëer Golden Set template CSV voor handmatige labeling.

    Args:
        df: DataFrame met gesamplede clausules
        text_column: Kolom met clausuletekst
        output_path: Output bestandspad
    """
    # Bouw output DataFrame
    output_data = []

    for idx, (row_idx, row) in enumerate(df.iterrows(), start=1):
        output_data.append({
            'clausule_id': f'GS-{idx:03d}',
            'clausule_tekst': row[text_column].strip(),
            'correct_advies': '',  # In te vullen door expert
            'vertrouwen': '',      # In te vullen door expert
            'toelichting_expert': '',  # In te vullen door expert
            'categorie': '',       # Optioneel
        })

    output_df = pd.DataFrame(output_data)

    # Exporteer als CSV
    output_df.to_csv(output_path, index=False, encoding='utf-8-sig')

    print(f"\n✅ Golden Set template geëxporteerd naar: {output_path}")
    print(f"   {len(output_df)} clausules klaar voor labeling")
    print(f"\n📝 Instructies voor de expert:")
    print(f"   1. Open het CSV bestand in Excel")
    print(f"   2. Vul per rij de kolom 'correct_advies' in met een van:")
    print(f"      - VERWIJDEREN (clausule mag weg)")
    print(f"      - BEHOUDEN (clausule moet blijven)")
    print(f"      - VERVANGEN (moet vervangen door standaard)")
    print(f"      - HANDMATIG CHECKEN (twijfelgeval)")
    print(f"   3. Vul 'vertrouwen' in: Hoog / Midden / Laag")
    print(f"   4. Voeg een korte toelichting toe (optioneel maar waardevol)")
    print(f"   5. Sla op als CSV of Excel")


def main():
    parser = argparse.ArgumentParser(
        description='Exporteer clausules voor Golden Set labeling',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Voorbeelden:
  python scripts/export_golden_set_candidates.py data/polissen.xlsx
  python scripts/export_golden_set_candidates.py data/polissen.xlsx --count 75 --output mijn_golden_set.csv
  python scripts/export_golden_set_candidates.py analyse_resultaat.xlsx --text-column "Vrije Teksten"
        """
    )

    parser.add_argument(
        'input_file',
        type=Path,
        help='Input Excel of CSV bestand met clausules'
    )

    parser.add_argument(
        '--output', '-o',
        type=Path,
        default=None,
        help='Output bestandspad (default: golden_set_candidates.csv)'
    )

    parser.add_argument(
        '--count', '-n',
        type=int,
        default=100,
        help='Aantal clausules om te exporteren (default: 100)'
    )

    parser.add_argument(
        '--text-column', '-t',
        type=str,
        default=None,
        help='Naam van de tekstkolom (auto-detect indien niet opgegeven)'
    )

    parser.add_argument(
        '--no-edge-cases',
        action='store_true',
        help='Geen extra korte/lange teksten toevoegen'
    )

    parser.add_argument(
        '--seed',
        type=int,
        default=42,
        help='Random seed voor reproduceerbaarheid (default: 42)'
    )

    args = parser.parse_args()

    # Valideer input
    if not args.input_file.exists():
        print(f"❌ Bestand niet gevonden: {args.input_file}")
        sys.exit(1)

    # Set random seed
    random.seed(args.seed)

    # Lees input bestand
    print(f"📖 Lezen: {args.input_file}")

    if args.input_file.suffix.lower() in ['.xlsx', '.xls']:
        df = pd.read_excel(args.input_file)
    elif args.input_file.suffix.lower() == '.csv':
        # Probeer verschillende encodings
        for encoding in ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']:
            try:
                df = pd.read_csv(args.input_file, encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            print(f"❌ Kon bestand niet lezen met bekende encodings")
            sys.exit(1)
    else:
        print(f"❌ Onbekend bestandstype: {args.input_file.suffix}")
        sys.exit(1)

    print(f"   {len(df)} rijen gevonden, {len(df.columns)} kolommen")

    # Detecteer kolommen
    text_column = args.text_column or detect_text_column(df)
    advice_column = detect_advice_column(df)

    print(f"   Tekstkolom: {text_column}")
    if advice_column:
        print(f"   Advieskolom: {advice_column}")

    # Sample clausules
    sampled = sample_clauses(
        df,
        text_column=text_column,
        advice_column=advice_column,
        count=args.count,
        include_edge_cases=not args.no_edge_cases
    )

    # Bepaal output pad
    output_path = args.output or Path('golden_set_candidates.csv')

    # Exporteer
    create_golden_set_template(sampled, text_column, output_path)


if __name__ == '__main__':
    main()
