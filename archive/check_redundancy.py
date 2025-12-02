import csv
import difflib
import re
import sys
import os

# Increase CSV field size limit
csv.field_size_limit(sys.maxsize)

def versimpel_tekst(tekst):
    # Remove non-alphanumeric (keep spaces), lower case
    return " ".join(re.sub(r'[^\w\s]', '', tekst.lower()).split())

def load_conditions_text(file_path):
    print(f"Reading conditions from {file_path}...")
    with open(file_path, 'r', encoding='utf-8') as f:
        return versimpel_tekst(f.read())

def analyze_redundancy(clusters_file, conditions_text, output_file, similarity_threshold=0.75):
    print("Analyzing clusters against new conditions...")
    
    results = []
    
    with open(clusters_file, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.DictReader(f, delimiter=';')
        
        processed = 0
        for row in reader:
            processed += 1
            if processed % 100 == 0:
                print(f"Processed {processed} clusters...")
                
            cluster_text = row['Hoofd Tekst']
            simple_cluster = versimpel_tekst(cluster_text)
            
            # Check if significant parts of the cluster text appear in the conditions
            # Since conditions are large, we check if chunks of the cluster text appear
            
            # Strategy 1: Direct substring match of cleaned text (if cluster is short)
            if len(simple_cluster) < 50:
                if simple_cluster in conditions_text:
                    results.append({
                        'cluster': cluster_text,
                        'count': row['Aantal'],
                        'reason': "Direct match (short text)",
                        'confidence': "High"
                    })
                    continue
            
            # Strategy 2: Split into sentences/phrases and check coverage
            # Ideally we would use embeddings/LLM here, but for MVP pure Python:
            # check if >80% of the 5-word sequences in the cluster exist in conditions
            
            words = simple_cluster.split()
            if len(words) < 5: continue
            
            matched_chunks = 0
            total_chunks = 0
            chunk_size = 5
            
            for i in range(len(words) - chunk_size + 1):
                chunk = " ".join(words[i:i+chunk_size])
                total_chunks += 1
                if chunk in conditions_text:
                    matched_chunks += 1
            
            if total_chunks > 0:
                coverage = matched_chunks / total_chunks
                if coverage > 0.6: # If 60% of 5-gram phrases are found
                    results.append({
                        'cluster': cluster_text,
                        'count': row['Aantal'],
                        'reason': f"Content overlap: {int(coverage*100)}%",
                        'confidence': "Medium" if coverage < 0.8 else "High"
                    })

    # Sort by confidence then count
    results.sort(key=lambda x: (x['confidence'], int(x['count'])), reverse=True)
    
    print(f"Found {len(results)} candidates for removal.")
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(['Frequentie', 'Vrije Tekst', 'Reden (Match %)', 'Vertrouwen'])
        for r in results:
            writer.writerow([r['count'], r['cluster'], r['reason'], r['confidence']])
            
    print(f"Report written to {output_file}")

if __name__ == "__main__":
    clusters_csv = "Vrije_teksten_geclusterd.csv"
    conditions_txt = "nieuwe_voorwaarden_text.txt"
    output_report = "Redundantie_Analyse_Rapport.csv"
    
    if os.path.exists(clusters_csv) and os.path.exists(conditions_txt):
        conditions_content = load_conditions_text(conditions_txt)
        analyze_redundancy(clusters_csv, conditions_content, output_report)
    else:
        print("Missing input files.")

