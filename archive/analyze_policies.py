import csv
import difflib
import sys
import os
import re

# Try to import pypdf, if not available we might need to install it
try:
    from pypdf import PdfReader
except ImportError:
    print("pypdf not found. Please run: pip install pypdf")
    # We will continue with just CSV processing if PDF fails
    PdfReader = None

def versimpel_tekst(tekst):
    # Remove non-alphanumeric (keep spaces), lower case
    # This helps with fuzzy matching
    return " ".join(re.sub(r'[^\w\s]', '', tekst.lower()).split())

def extract_pdf_text(pdf_path, output_txt_path):
    if not PdfReader:
        print(f"Skipping PDF extraction for {pdf_path} (pypdf missing)")
        return ""
    
    print(f"Extracting text from {pdf_path}...")
    try:
        reader = PdfReader(pdf_path)
        full_text = []
        for page in reader.pages:
            full_text.append(page.extract_text())
        
        text_content = "\n".join(full_text)
        
        with open(output_txt_path, 'w', encoding='utf-8') as f:
            f.write(text_content)
        
        print(f"Saved text to {output_txt_path}")
        return text_content
    except Exception as e:
        print(f"Error reading PDF: {e}")
        return ""

def cluster_teksten(input_file, output_file, drempelwaarde=0.85):
    print(f"Reading {input_file}...")
    
    # Step 1: Exact Grouping (Deduplication)
    # key: simplified_text, value: { 'original': text, 'count': int, 'polissen': [] }
    exact_groups = {}
    
    try:
        with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
            # Force semi-colon delimiter
            reader = csv.DictReader(f, delimiter=';')
            
            total_rows = 0
            for row in reader:
                total_rows += 1
                if 'Tekst' not in row:
                    # Try to find key that looks like Tekst (sometimes BOM or whitespace issues)
                    keys = list(row.keys())
                    found = False
                    for k in keys:
                        if k and 'Tekst' in k:
                            tekst = row[k]
                            found = True
                            break
                    if not found:
                        if total_rows < 5: print(f"Skipping row {total_rows}, keys found: {keys}")
                        continue
                else:
                    tekst = row['Tekst']
                
                if not tekst or len(tekst.strip()) < 5: 
                    continue
                
                # Use simplified text as key for exact grouping (ignoring case/punctuation)
                simple_key = versimpel_tekst(tekst)
                
                if simple_key in exact_groups:
                    exact_groups[simple_key]['count'] += 1
                    if len(exact_groups[simple_key]['polissen']) < 5:
                        exact_groups[simple_key]['polissen'].append(row.get('Polisnummer', ''))
                else:
                    exact_groups[simple_key] = {
                        'original': tekst,
                        'count': 1,
                        'polissen': [row.get('Polisnummer', '')]
                    }
                    
        print(f"Total rows processed: {total_rows}")
        print(f"Unique exact texts found: {len(exact_groups)}")
        
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    # Step 2: Fuzzy Clustering of the unique groups
    # This reduces N^2 complexity significantly
    clusters = []
    unique_keys = list(exact_groups.keys())
    
    print("Starting fuzzy clustering...")
    
    # Sort by length to optimize (compare similar lengths first)
    # Although for O(N^2) it doesn't matter much, but we can skip very different lengths
    unique_keys.sort(key=len, reverse=True)
    
    processed_keys = set()
    
    for i, key in enumerate(unique_keys):
        if key in processed_keys:
            continue
            
        if i % 100 == 0:
            print(f"Clustering progress: {i}/{len(unique_keys)}")
            
        # Create new cluster
        current_cluster = {
            'main_text': exact_groups[key]['original'],
            'total_count': exact_groups[key]['count'],
            'variations': [exact_groups[key]['original']],
            'polissen': exact_groups[key]['polissen']
        }
        processed_keys.add(key)
        
        # Compare with remaining keys
        # Optimization: only compare with next N items or use a quicker filter?
        # For MVP, we'll do a simplified check: 
        # If we have < 2000 unique groups, O(N^2) is 4M ops, might take a bit but okay.
        # If > 5000, it might be slow.
        
        for other_key in unique_keys[i+1:]:
            if other_key in processed_keys:
                continue
            
            # Optimization: Length difference check
            if abs(len(key) - len(other_key)) / max(len(key), 1) > (1 - drempelwaarde):
                continue
                
            ratio = difflib.SequenceMatcher(None, key, other_key).ratio()
            if ratio > drempelwaarde:
                # Merge into current cluster
                current_cluster['total_count'] += exact_groups[other_key]['count']
                if exact_groups[other_key]['original'] not in current_cluster['variations']:
                    current_cluster['variations'].append(exact_groups[other_key]['original'])
                current_cluster['polissen'].extend(exact_groups[other_key]['polissen'])
                processed_keys.add(other_key)
        
        clusters.append(current_cluster)

    # Sort clusters by frequency
    clusters.sort(key=lambda x: x['total_count'], reverse=True)
    
    print(f"Final number of clusters: {len(clusters)}")
    
    # Write to output
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(['Aantal', 'Hoofd Tekst', 'Variaties', 'Voorbeeld Polissen'])
        
        for c in clusters:
            variations_str = " | ".join(c['variations'][:3]) # limit variations column
            if len(c['variations']) > 3:
                variations_str += "..."
                
            polissen_str = ", ".join(list(set(c['polissen']))[:5])
            
            writer.writerow([
                c['total_count'],
                c['main_text'],
                variations_str,
                polissen_str
            ])
    print(f"Results written to {output_file}")

if __name__ == "__main__":
    # 1. Extract PDF Text (New Conditions)
    pdf_file = "Hienfeld algemene voorwaarden Renaissance FA001REN25.pdf"
    txt_file = "nieuwe_voorwaarden_text.txt"
    if os.path.exists(pdf_file):
        extract_pdf_text(pdf_file, txt_file)
    else:
        print(f"PDF file {pdf_file} not found.")

    # 2. Cluster CSV
    csv_file = "Vrije teksten.csv"
    output_csv = "Vrije_teksten_geclusterd.csv"
    if os.path.exists(csv_file):
        cluster_teksten(csv_file, output_csv)
    else:
        print(f"CSV file {csv_file} not found.")

