import os
import pandas as pd
import win32com.client as win32
from docx import Document
import re

def clean_text_for_excel(text):
    """
    Verwijdert karakters die niet toegestaan zijn in Excel cellen.
    Excel accepteert geen control characters behalve \t (tab) en \n (nieuwe regel).
    """
    if not text:
        return ""
    # Verwijder non-printable characters (behalve newline en tab)
    # De regex zoekt naar karakters in de range 0-31 (x00-x1f), behalve 9 (tab) en 10 (newline)
    cleaned = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
    return cleaned

def extract_text_from_doc(file_path, word_app):
    """Leest tekst uit oude .doc bestanden via de open Word instantie"""
    try:
        doc = word_app.Documents.Open(file_path)
        text = doc.Range().Text
        doc.Close(False) # Sluit zonder opslaan
        return text
    except Exception as e:
        print(f"Let op: Fout bij lezen .doc {os.path.basename(file_path)}: {e}")
        return ""

def extract_text_from_docx(file_path):
    """Leest tekst uit moderne .docx bestanden"""
    try:
        doc = Document(file_path)
        full_text = []
        for para in doc.paragraphs:
            full_text.append(para.text)
        return '\n'.join(full_text)
    except Exception as e:
        print(f"Let op: Fout bij lezen .docx {os.path.basename(file_path)}: {e}")
        return ""

def main():
    # --- INSTELLINGEN ---
    # Pas dit pad aan naar jouw map
    bron_map = r"Y:\Projecten\Data\VB tool\Clausules Renaissance"
    output_excel = "Clausulebibliotheek_Compleet.xlsx"
    
    data = []
    
    print(f"Start met inlezen van bestanden uit: {bron_map}")
    
    # Start Word instantie (alleen nodig als er .doc bestanden zijn)
    word_app = None
    try:
        word_app = win32.Dispatch("Word.Application")
        word_app.Visible = False
    except Exception as e:
        print("Kon Word niet starten. .doc bestanden worden mogelijk overgeslagen.")

    # Loop door de bestanden
    for filename in os.listdir(bron_map):
        if filename.startswith("~$"): 
            continue
            
        file_path = os.path.join(bron_map, filename)
        raw_text = ""
        
        naam_zonder_ext, extensie = os.path.splitext(filename)
        ext = extensie.lower()
        
        if ext == ".docx":
            raw_text = extract_text_from_docx(file_path)
        elif ext == ".doc":
            if word_app:
                raw_text = extract_text_from_doc(file_path, word_app)
        else:
            continue # Sla andere bestanden over
            
        # BELANGRIJK: Tekst opschonen voor Excel
        clean_text = clean_text_for_excel(raw_text.strip())
        
        if clean_text:
            data.append({
                "Code": naam_zonder_ext,
                "Tekst": clean_text,
                "Categorie": ""
            })
            print(f"✓ Verwerkt: {filename} ({len(clean_text)} tekens)")
        else:
            print(f"⚠ Leeg of onleesbaar: {filename}")

    # Sluit Word netjes af
    if word_app:
        try:
            word_app.Quit()
        except:
            pass

    print(f"\nGenereren van Excel bestand met {len(data)} regels...")

    # Opslaan naar Excel met de 'xlsxwriter' engine (die is stabieler voor grote teksten)
    try:
        df = pd.DataFrame(data)
        # Gebruik xlsxwriter engine expliciet
        writer = pd.ExcelWriter(output_excel, engine='xlsxwriter')
        df.to_excel(writer, index=False, sheet_name='Clausules')
        
        # Optioneel: Kolombreedte aanpassen voor leesbaarheid
        workbook  = writer.book
        worksheet = writer.sheets['Clausules']
        worksheet.set_column('A:A', 30) # Breedte kolom Code
        worksheet.set_column('B:B', 100) # Breedte kolom Tekst
        
        writer.close()
        print(f"✅ SUCCES! Bestand opgeslagen als: {output_excel}")
        
    except Exception as e:
        print(f"❌ FOUT bij opslaan Excel: {e}")
        # Fallback naar CSV als Excel echt niet lukt
        csv_file = output_excel.replace('.xlsx', '.csv')
        df.to_csv(csv_file, sep=';', index=False, encoding='utf-8-sig')
        print(f"   (Backup gemaakt als CSV: {csv_file})")

if __name__ == "__main__":
    main()