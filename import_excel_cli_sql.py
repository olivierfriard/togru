"""
Load content of an XLSX file and create SQL queries to load data into togru PostgreSQL DB
"""

import pandas as pd
import sys
import os

# Mappatura colonne Excel → DB
excel_to_db_fields = {
    "Descrizione Inventario": "descrizione_inventario",
    "Numero inventario": "num_inventario",
    "Num inventario Ateneo": "num_inventario_ateneo",
    "Data carico": "data_carico",
    "Descrizione bene": "descrizione_bene",
    "Codice Sipi Torino": "codice_sipi_torino",
    "Codice Sipi Grugliasco": "codice_sipi_grugliasco",
    "Destinazione (colori legenda)": "destinazione",
    "Rosso fase_alimentazione privilegiata": "rosso_fase_alimentazione_privilegiata",
    "Valore convenzionale": "valore_convenzionale",
    "Esercizio bene migrato": "esercizio_bene_migrato",
    "Responsabile di Laboratorio": "responsabile_laboratorio",
    "Denominazione Fornitore": "denominazione_fornitore",
    "Anno fabbricazione": "anno_fabbricazione",
    "Numero seriale": "numero_seriale",
    "Categoria inventariale": "categoria_inventoriale",
    "Catalogazione del materiale/strumentazione": "catalogazione_materiale_strumentazione",
    "Peso": "peso",
    "Dimensioni (Altezza e larghezza/lunghezza espressi in cm)": "dimensioni",
    "Ditta costruttrice/Fornitrice": "ditta_costruttrice_fornitrice",
    "Note": "note",
}


def upload_excel_generate_sql(file_path):
    if not os.path.exists(file_path):
        print(f"❌ File non trovato: {file_path}", file=sys.stderr)
        return

    try:
        df = pd.read_excel(file_path)
        df.columns = df.columns.str.strip()
        df.fillna("", inplace=True)

        for col in df.columns:
            df[col] = df[col].astype(str)

        # Eventuale rinomina colonna "Peso"
        for col in df.columns:
            if col.startswith("Peso"):
                df.rename(columns={col: "Peso"}, inplace=True)
                break

        df.rename(columns=excel_to_db_fields, inplace=True)

        # Controllo colonne mancanti
        expected_cols = list(excel_to_db_fields.values())
        missing_cols = [c for c in expected_cols if c not in df.columns]
        if missing_cols:
            print(f"❌ Mancano colonne nel file Excel: {missing_cols}", file=sys.stderr)
            return

        # Generazione stringhe SQL
        for _, row in df.iterrows():
            values = []
            for col in expected_cols:
                val = row[col].replace("'", "''")  # escape apici singoli
                values.append(f"'{val}'")
            sql = f"""INSERT INTO inventario (    {", ".join(expected_cols)}) VALUES (    {", ".join(values)});"""
            print(sql)

        print("✅ SQL generato con successo!", file=sys.stderr)

    except Exception as e:
        print(f"❌ Errore nella generazione SQL: {e}", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python generate_sql_from_excel.py <file_excel.xlsx>", file=sys.stderr)
    else:
        upload_excel_generate_sql(sys.argv[1])
