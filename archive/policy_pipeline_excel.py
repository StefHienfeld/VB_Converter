import csv
import difflib
import re
import sys
import os
import time
from openpyxl import Workbook

# Increase CSV field size limit
csv.field_size_limit(sys.maxsize)

def simplify_text(text):
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

def run_pipeline_xlsx(input_csv, conditions_file, output_xlsx):
    print("--- Starting Excel Analysis Pipeline ---")
    
    conditions_text = load_conditions_text(conditions_file)
    
    rows = []
    print(f"Reading {input_csv}...")
    
    try:
        with open(input_csv, 'r', encoding='utf-8', errors='ignore') as f:
            # Sniff delimiter
            sample = f.read(2048)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample)
                delimiter = dialect.delimiter
            except:
                delimiter = ';'
            
            reader = csv.DictReader(f, delimiter=delimiter)
            fieldnames = reader.fieldnames
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
    
    for row in rows:
        row['clean_text'] = simplify_text(row.get('Tekst', ''))
        row['Cluster_ID'] = ''
        row['Advies_Actie'] = ''
        row['Redenering_AI'] = ''
        row['Vertrouwen'] = ''
        row['Ref_Artikel'] = ''
        row['Actie_Collega'] = ''

    # Sort rows by text length for efficiency
    rows.sort(key=lambda x: len(x['clean_text']), reverse=True)
    
    clusters = []
    cluster_counter = 1
    exact_map = {}
    processed_count = 0
    
    # Increased coverage: check last 200 clusters instead of 50
    # For MVP, we rely on exact match + recent fuzzy match.
    
    for row in rows:
        txt = row['clean_text']
        if not txt or len(txt) < 5:
            row['Cluster_ID'] = 'NVT' # Te kort / leeg
            continue
            
        if txt in exact_map:
            row['Cluster_ID'] = exact_map[txt]
        else:
            found_cluster = False
            # Heuristic: Only check against clusters of similar length
            # In this loop, we are sorted by length descending, so we compare with slightly longer previous clusters
            
            for cluster in clusters[-200:]: 
                # Quick length check: if diff > 20%, skip (SequenceMatcher is slow)
                l1 = len(cluster['leader_text'])
                l2 = len(txt)
                if abs(l1 - l2) / l1 > 0.2: continue

                ratio = difflib.SequenceMatcher(None, cluster['leader_text'], txt).ratio()
                if ratio > 0.90:
                    row['Cluster_ID'] = cluster['id']
                    found_cluster = True
                    break
            
            if not found_cluster:
                cid = f"CL-{cluster_counter:04d}"
                cluster_counter += 1
                clusters.append({ 'leader_text': txt, 'id': cid })
                row['Cluster_ID'] = cid
                exact_map[txt] = cid
        
        processed_count += 1
        if processed_count % 2000 == 0:
            print(f"Clustered {processed_count} rows...")

    # --- STEP 2: ANALYSIS ---
    print("Step 2: Analyzing clusters...")
    
    cluster_advice_map = {}
    for cluster in clusters:
        advice, reason, confidence, ref = get_semantic_advice(cluster['leader_text'], conditions_text)
        cluster_advice_map[cluster['id']] = {
            'advies': advice,
            'reden': reason,
            'vertrouwen': confidence,
            'ref': ref
        }
        
    for row in rows:
        cid = row['Cluster_ID']
        if cid in cluster_advice_map:
            advice_data = cluster_advice_map[cid]
            row['Advies_Actie'] = advice_data['advies']
            row['Redenering_AI'] = advice_data['reden']
            row['Vertrouwen'] = advice_data['vertrouwen']
            row['Ref_Artikel'] = advice_data['ref']
            
        del row['clean_text'] # Cleanup

    # --- STEP 3: EXCEL OUTPUT ---
    print("Step 3: Creating Excel file...")
    
    rows.sort(key=lambda x: x['Cluster_ID'])
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Polis Analyse"
    
    # Headers
    headers = ['Cluster_ID', 'Advies_Actie', 'Vertrouwen', 'Redenering_AI', 'Ref_Artikel', 'Actie_Collega'] + clean_fieldnames
    ws.append(headers)
    
    for i, row in enumerate(rows):
        # Create list of values in correct order
        row_values = []
        for h in headers:
            row_values.append(row.get(h, ''))
        ws.append(row_values)
        
        if i % 5000 == 0:
             print(f"Writing row {i} to Excel...")
            
    wb.save(output_xlsx)
    print(f"Successfully saved {output_xlsx}")

if __name__ == "__main__":
    run_pipeline_xlsx("Vrije teksten.csv", "nieuwe_voorwaarden_text.txt", "Verrijkte_Polis_Analyse.xlsx")

