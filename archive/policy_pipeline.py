import csv
import difflib
import re
import sys
import os
import time

# Increase CSV field size limit
csv.field_size_limit(sys.maxsize)

def simplify_text(text):
    # Remove non-alphanumeric (keep spaces), lower case
    if not text: return ""
    return " ".join(re.sub(r'[^\w\s]', '', text.lower()).split())

def load_conditions_text(file_path):
    print(f"Reading conditions from {file_path}...")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return simplify_text(f.read())
    except Exception as e:
        print(f"Error reading conditions: {e}")
        return ""

def get_semantic_advice(text, conditions_text):
    """
    Simulates semantic analysis by checking keywords and context.
    Returns: (Advice, Reasoning, Confidence, Reference)
    """
    simple_text = simplify_text(text)
    
    # 1. Check for Rangorde (Hierarchy)
    if "strijd" in simple_text and "voorwaarden" in simple_text and "gaan" in simple_text and "voor" in simple_text:
        return ("VERWIJDEREN", "Dubbelop: Rangorde is geregeld in Art 9.1", "Hoog", "Art 9.1")
        
    # 2. Check for Molest (War/Unrest) - CRITICAL: Conditions EXCLUDE it, Policy INCLUDES it
    if "molest" in simple_text:
        if "inclusief" in simple_text or "meeverzekerd" in simple_text:
            return ("BEHOUDEN (CLAUSULE)", "Afwijking: Voorwaarden sluiten Molest uit (Art 2.14), polis dekt het.", "Hoog", "Art 2.14")
        return ("CHECK", "Molest genoemd, check of het dekking of uitsluiting betreft", "Midden", "Art 2.14")

    # 3. Check for Terrorisme (NHT)
    if "terrorisme" in simple_text and "clausule" in simple_text:
        return ("VERWIJDEREN", "Standaard NHT tekst staat in Bijlage voorwaarden", "Hoog", "Bijlage")
        
    # 4. Check for Fraude
    if "fraude" in simple_text or "misleiding" in simple_text:
        return ("VERWIJDEREN", "Fraude is al uitgesloten in voorwaarden", "Hoog", "Art 2.8")

    # 5. Check for Premiebetaling
    if "premie" in simple_text and "betalen" in simple_text and "30 dagen" in simple_text:
        return ("VERWIJDEREN", "Betalingstermijn is standaard geregeld", "Hoog", "Art 5.1")
    
    # 6. Check for Inzage / Personeelszaken
    if "inzage" in simple_text and "personeelszaken" in simple_text:
        return ("VERWIJDEREN", "Interne instructie, geen dekkingsvoorwaarde", "Hoog", "-")
        
    # 7. Check for 12 months duration
    if "duur" in simple_text and "12 maanden" in simple_text:
        return ("VERWIJDEREN", "Contractduur hoort in systeemveld, niet als vrije tekst", "Hoog", "Art 8.1")

    # 8. General Redundancy Check (Fuzzy Match)
    # Check if significant chunks of text appear in conditions
    words = simple_text.split()
    if len(words) > 10:
        matched_chunks = 0
        total_chunks = 0
        chunk_size = 6
        for i in range(len(words) - chunk_size + 1):
            chunk = " ".join(words[i:i+chunk_size])
            total_chunks += 1
            if chunk in conditions_text:
                matched_chunks += 1
        
        if total_chunks > 0:
            coverage = matched_chunks / total_chunks
            if coverage > 0.6:
                return ("VERWIJDEREN", f"Tekst komt voor {int(coverage*100)}% overeen met voorwaarden", "Midden", "Diverse")

    return ("HANDMATIG CHECKEN", "Geen automatische match gevonden", "Laag", "-")

def run_pipeline(input_csv, conditions_file, output_csv):
    print("--- Starting Policy Analysis Pipeline ---")
    
    # Load conditions
    conditions_text = load_conditions_text(conditions_file)
    
    # Store all rows to process
    rows = []
    print(f"Reading {input_csv}...")
    
    # Detect headers and read
    try:
        with open(input_csv, 'r', encoding='utf-8', errors='ignore') as f:
            # Sniff delimiter
            sample = f.read(2048)
            f.seek(0)
            sniffer = csv.Sniffer()
            try:
                dialect = sniffer.sniff(sample)
                delimiter = dialect.delimiter
            except:
                delimiter = ';'
            
            reader = csv.DictReader(f, delimiter=delimiter)
            fieldnames = reader.fieldnames
            
            # Sanitize fieldnames (remove BOM if present)
            clean_fieldnames = [f.strip().replace('\ufeff', '') for f in fieldnames]
            reader.fieldnames = clean_fieldnames
            
            for row in reader:
                rows.append(row)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    print(f"Total rows to process: {len(rows)}")

    # --- STEP 1: CLUSTERING ---
    print("Step 1: Clustering similar texts...")
    
    # We'll assign a Cluster ID to each row
    # Strategy: Sort by text length, then fuzzy match
    
    # Add new columns placeholder
    for row in rows:
        row['clean_text'] = simplify_text(row.get('Tekst', ''))
        row['Cluster_ID'] = ''
        row['Advies_Actie'] = ''
        row['Redenering_AI'] = ''
        row['Vertrouwen'] = ''
        row['Ref_Artikel'] = ''
        row['Actie_Collega'] = '' # Empty for user to fill
    
    # Sort rows by text to make clustering faster/easier
    rows.sort(key=lambda x: len(x['clean_text']), reverse=True)
    
    clusters = [] # List of { 'leader_text': str, 'id': int }
    cluster_counter = 1
    
    processed_count = 0
    
    # Optimization: Use a dictionary for exact matches first to speed up O(N^2)
    exact_map = {}
    
    for row in rows:
        txt = row['clean_text']
        if not txt or len(txt) < 5:
            row['Cluster_ID'] = 'IGNORE'
            continue
            
        if txt in exact_map:
            row['Cluster_ID'] = exact_map[txt]
        else:
            # Check fuzzy match against existing cluster leaders
            found_cluster = False
            # Only check last 100 clusters for performance in this MVP script
            # In production, use LSH or vector search
            for cluster in clusters[-50:]: 
                ratio = difflib.SequenceMatcher(None, cluster['leader_text'], txt).ratio()
                if ratio > 0.90: # Strict clustering
                    row['Cluster_ID'] = cluster['id']
                    found_cluster = True
                    break
            
            if not found_cluster:
                cid = f"CL-{cluster_counter:04d}"
                cluster_counter += 1
                clusters.append({ 'leader_text': txt, 'id': cid })
                row['Cluster_ID'] = cid
                exact_map[txt] = cid # Cache for exact match
        
        processed_count += 1
        if processed_count % 1000 == 0:
            print(f"Clustered {processed_count} rows...")

    # --- STEP 2: ANALYSIS ---
    print("Step 2: Analyzing clusters...")
    
    # Analyze each cluster leader once, apply to all members
    cluster_advice_map = {}
    
    for cluster in clusters:
        advice, reason, confidence, ref = get_semantic_advice(cluster['leader_text'], conditions_text)
        cluster_advice_map[cluster['id']] = {
            'advies': advice,
            'reden': reason,
            'vertrouwen': confidence,
            'ref': ref
        }
        
    # Apply advice to rows
    for row in rows:
        cid = row['Cluster_ID']
        if cid in cluster_advice_map:
            advice_data = cluster_advice_map[cid]
            row['Advies_Actie'] = advice_data['advies']
            row['Redenering_AI'] = advice_data['reden']
            row['Vertrouwen'] = advice_data['vertrouwen']
            row['Ref_Artikel'] = advice_data['ref']
            
        # Clean up temp column
        del row['clean_text']

    # --- STEP 3: OUTPUT ---
    print("Step 3: Writing results...")
    
    # Define output columns
    output_columns = ['Cluster_ID', 'Advies_Actie', 'Vertrouwen', 'Redenering_AI', 'Ref_Artikel', 'Actie_Collega'] + clean_fieldnames
    
    # Sort by Cluster ID so similar items are together
    rows.sort(key=lambda x: x['Cluster_ID'])
    
    try:
        with open(output_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=output_columns, delimiter=';', extrasaction='ignore')
            writer.writeheader()
            writer.writerows(rows)
            
        print(f"Successfully wrote {len(rows)} rows to {output_csv}")
        
    except Exception as e:
        print(f"Error writing output: {e}")

if __name__ == "__main__":
    run_pipeline("Vrije teksten.csv", "nieuwe_voorwaarden_text.txt", "Verrijkte_Polis_Analyse.csv")

