import csv
import difflib
import re
import sys
import os
import time
import collections
from openpyxl import Workbook

# Increase CSV field size limit
csv.field_size_limit(sys.maxsize)

def simplify_text(text):
    if not text: return ""
    # Keep only alphanumeric chars to compare content, ignoring layout/punctuation
    return " ".join(re.sub(r'[^\w\s]', '', text.lower()).split())

def get_cluster_name(text):
    """
    Generates a short descriptive name for a cluster based on its content.
    """
    if not text: return "Onbekend"
    
    # Check for clause codes like 9NX3, VB1, etc.
    code_match = re.search(r'\b[A-Z0-9]{3,4}\b', text)
    code = code_match.group(0) if code_match else ""
    
    lower_text = text.lower()
    
    # Common themes
    if "terrorisme" in lower_text: return f"{code} Terrorisme Clausule"
    if "sanctie" in lower_text: return f"{code} Sanctiewetgeving"
    if "brandregres" in lower_text: return f"{code} Brandregres"
    if "molest" in lower_text: return f"{code} Molest Dekking"
    if "verzekerde hoedanigheid" in lower_text: return f"{code} Doelgroepomschrijving"
    if "eigen risico" in lower_text: return f"{code} Eigen Risico Bepaling"
    if "buitenland" in lower_text: return f"{code} Buitenland Dekking"
    if "premie" in lower_text and "naverrekening" in lower_text: return f"{code} Premie Naverrekening"
    if "rangorde" in lower_text: return f"{code} Rangorde Bepaling"
    
    # Fallback: First 5 words
    words = text.split()
    return " ".join(words[:5]) + "..."

def analyze_policy_text(text, conditions_text, frequency):
    """
    Advanced analysis logic.
    Returns: (Advice, Reasoning, Confidence, Reference)
    """
    simple_text = simplify_text(text)
    
    # 1. MULTI-CLAUSE DETECTION (The "Brei" Check)
    # If text contains multiple 3-4 letter codes or is very long, it's likely a container.
    # Pattern: Look for things like "9NX3" followed by text, then "9NY3"
    codes = re.findall(r'\b[0-9][A-Z]{2}[0-9]\b', text) # Matches 9NX3 format
    if len(set(codes)) > 1:
        return ("⚠️ SPLITSEN", f"Bevat {len(set(codes))} verschillende clausules ({', '.join(set(codes))}). Moet handmatig gesplitst worden.", "Hoog", "Diverse")
    
    if len(text) > 1000:
        return ("⚠️ SPLITSEN/CONTROLEREN", "Tekst is erg lang (>1000 tekens), bevat mogelijk meerdere onderwerpen.", "Midden", "-")

    # 2. RANGORDE (Hierarchy) - Special Case
    # Only remove if it's a pure hierarchy clause, NOT if it contains other content.
    if "rangorde" in simple_text and "strijd" in simple_text and len(simple_text) < 300:
        return ("VERWIJDEREN", "Standaard Rangorde bepaling (Art 9.1). Let op: alleen verwijderen als de tekst leeg is van andere clausules.", "Hoog", "Art 9.1")

    # 3. MOLEST (Deviation)
    if "molest" in simple_text:
        if "inclusief" in simple_text or "meeverzekerd" in simple_text:
            return ("BEHOUDEN (CLAUSULE)", "Afwijking: Voorwaarden sluiten Molest uit (Art 2.14), polis dekt het expliciet.", "Hoog", "Art 2.14")

    # 4. FREQUENCY CHECK -> STANDARDIZATION
    if frequency > 20:
        # If it's frequent but not matched to removal criteria
        return ("🛠️ STANDAARDISEREN", f"Komt vaak voor ({frequency}x). Maak hiervan een standaard clausulecode in het systeem.", "Hoog", "Nieuw")

    # 5. FRAUDE (Redundant)
    if ("fraude" in simple_text or "misleiding" in simple_text) and len(simple_text) < 400:
        return ("VERWIJDEREN", "Fraude is al uitgesloten in voorwaarden (Art 2.8/3.3).", "Hoog", "Art 2.8")

    # 6. GENERIC OVERLAP (Fuzzy)
    # Only trigger if REALLY high match
    # (This part would ideally use embeddings, simulating here with keywords)
    
    return ("HANDMATIG CHECKEN", "Geen automatische match. Beoordeel of dit maatwerk is.", "Laag", "-")


def run_pipeline_xlsx(input_csv, conditions_file, output_xlsx):
    print("--- Starting Analysis Pipeline 2.0 ---")
    
    # Load conditions
    conditions_text = ""
    if conditions_file:
         with open(conditions_file, 'r', encoding='utf-8', errors='ignore') as f:
            conditions_text = simplify_text(f.read())
    
    # Read Input
    rows = []
    try:
        with open(input_csv, 'r', encoding='utf-8', errors='ignore') as f:
            # Smart Sniffer
            sample = f.read(4096)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample)
                delimiter = dialect.delimiter
            except:
                delimiter = ';' # Default fallback
            
            reader = csv.DictReader(f, delimiter=delimiter)
            
            # Clean headers
            reader.fieldnames = [f.strip().replace('\ufeff', '') for f in reader.fieldnames]
            
            for row in reader:
                rows.append(row)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    total_rows = len(rows)
    print(f"Total rows to process: {total_rows}")

    # --- STEP 1: FAST CLUSTERING (LEADER APPROACH) ---
    print("Step 1: Clustering...")
    
    # Sort by length for better grouping
    # Note: We sort a copy for clustering logic, but map back to original rows
    # For simplicity in this script, we just process list in order
    
    clusters = [] # List of { 'leader_text': str, 'id': str, 'count': int, 'name': str }
    cluster_map = {} # text -> cluster_id
    
    # Pre-calculate clean text for speed
    for row in rows:
        row['clean_text'] = simplify_text(row.get('Tekst', ''))
    
    # Sort rows by length (descending) ensures long texts become leaders first
    # This helps avoiding small subsets matching first
    rows.sort(key=lambda x: len(x['clean_text']), reverse=True)
    
    counter = 1
    
    for i, row in enumerate(rows):
        txt = row['clean_text']
        if not txt or len(txt) < 10:
            row['Cluster_ID'] = 'NVT'
            continue
            
        # Check if we already mapped this exact text
        if txt in cluster_map:
            row['Cluster_ID'] = cluster_map[txt]
            # Increment count for leader
            for c in clusters:
                if c['id'] == cluster_map[txt]:
                    c['count'] += 1
                    break
            continue
            
        # Fuzzy match against Leaders
        found = False
        # Optimization: Check only clusters with similar length (+/- 20%)
        # Since we sorted by length, we only look back at recent clusters
        # But wait, sorted descending means we look at LONGER clusters. 
        # Actually for "Leader" algo, order doesn't matter strictly, but length sorting helps.
        
        # Limit comparison to last 100 clusters for speed
        for c in clusters[-100:]:
             # Quick length filter
             if abs(len(c['leader_text']) - len(txt)) / len(c['leader_text']) > 0.2:
                 continue
                 
             ratio = difflib.SequenceMatcher(None, c['leader_text'], txt).ratio()
             if ratio > 0.85: # 85% similarity
                 row['Cluster_ID'] = c['id']
                 c['count'] += 1
                 cluster_map[txt] = c['id'] # Cache exact text to this cluster
                 found = True
                 break
        
        if not found:
            cid = f"CL-{counter:04d}"
            c_name = get_cluster_name(row.get('Tekst', ''))
            clusters.append({
                'leader_text': txt, 
                'original_text': row.get('Tekst', ''),
                'id': cid, 
                'count': 1,
                'name': c_name
            })
            row['Cluster_ID'] = cid
            cluster_map[txt] = cid
            counter += 1
            
        if i % 2000 == 0: print(f"Processed {i} rows...")

    # --- STEP 2: ANALYZE LEADERS ---
    print("Step 2: Analyzing...")
    
    analysis_results = {}
    
    for c in clusters:
        adv, reason, conf, ref = analyze_policy_text(c['original_text'], conditions_text, c['count'])
        analysis_results[c['id']] = {
            'Cluster_Naam': c['name'],
            'Frequentie': c['count'],
            'Advies': adv,
            'Reden': reason,
            'Vertrouwen': conf,
            'Artikel': ref
        }

    # --- STEP 3: EXPORT ---
    print("Step 3: Exporting...")
    
    # Enrich rows
    for row in rows:
        cid = row.get('Cluster_ID')
        if cid and cid in analysis_results:
            res = analysis_results[cid]
            row['Cluster_Naam'] = res['Cluster_Naam']
            row['Cluster_Frequentie'] = res['Frequentie']
            row['Advies'] = res['Advies']
            row['Reden'] = res['Reden']
            row['Vertrouwen'] = res['Vertrouwen']
            row['Ref_Artikel'] = res['Artikel']
        else:
            row['Cluster_Naam'] = ''
            row['Cluster_Frequentie'] = ''
            row['Advies'] = ''
            row['Reden'] = ''
            row['Vertrouwen'] = ''
            row['Ref_Artikel'] = ''
        
        del row['clean_text'] # Cleanup

    # Sort by Cluster ID
    rows.sort(key=lambda x: x.get('Cluster_ID', 'Z'))

    wb = Workbook()
    ws = wb.active
    ws.title = "Hienfeld Analyse"
    
    # Output Headers
    headers = ['Cluster_ID', 'Cluster_Naam', 'Cluster_Frequentie', 'Advies', 'Vertrouwen', 'Reden', 'Ref_Artikel', 'Actie_Collega'] + list(reader.fieldnames)
    
    # Make headers bold/blue later if needed, for now just data
    ws.append(headers)
    
    for row in rows:
        ws.append([row.get(h, '') for h in headers])
        
    wb.save(output_xlsx)
    print("Done!")

if __name__ == "__main__":
    run_pipeline_xlsx("Vrije teksten.csv", "nieuwe_voorwaarden_text.txt", "Verrijkte_Polis_Analyse_v2.xlsx")

