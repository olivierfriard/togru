import pandas as pd
from sqlalchemy import create_engine, text
import sys
import os

# Configurazione database
DB_URL = "postgresql://togru_user:password123@localhost:5432/togru"
engine = create_engine(DB_URL)

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


def upload_excel(file_path, user_email="cli_uploader"):
    if not os.path.exists(file_path):
        print(f"❌ File non trovato: {file_path}")
        return

    try:
        df = pd.read_excel(file_path)
        df.columns = df.columns.str.strip()

        for col in df.columns:
            df[col] = df[col].astype(str)

        df.fillna("", inplace=True)

        # Eventuale rinomina colonna "Peso"
        for col in df.columns:
            if col.startswith("Peso"):
                df.rename(columns={col: "Peso"}, inplace=True)
                break

        df.rename(columns=excel_to_db_fields, inplace=True)
        df.fillna("", inplace=True)

        # Controllo colonne mancanti
        expected_cols = list(excel_to_db_fields.values())
        missing_cols = [c for c in expected_cols if c not in df.columns]
        if missing_cols:
            print(f"❌ Mancano colonne nel file Excel: {missing_cols}")
            return

        # Record senza responsabile
        senza_responsabile = df[df["responsabile_laboratorio"] == ""]

        with engine.connect() as conn:
            conn.execute(
                text("SET LOCAL application_name = :user"),
                {"user": user_email},
            )

            for _, row in df.iterrows():
                sql = text("""
                    INSERT INTO inventario (
                        descrizione_inventario, num_inventario, num_inventario_ateneo, data_carico,
                        descrizione_bene, codice_sipi_torino, codice_sipi_grugliasco, destinazione,
                        rosso_fase_alimentazione_privilegiata, valore_convenzionale, esercizio_bene_migrato,
                        responsabile_laboratorio, denominazione_fornitore, anno_fabbricazione, numero_seriale,
                        categoria_inventoriale, catalogazione_materiale_strumentazione, peso, dimensioni,
                        ditta_costruttrice_fornitrice, note
                    ) VALUES (
                        :descrizione_inventario, :num_inventario, :num_inventario_ateneo, :data_carico,
                        :descrizione_bene, :codice_sipi_torino, :codice_sipi_grugliasco, :destinazione,
                        :rosso_fase_alimentazione_privilegiata, :valore_convenzionale, :esercizio_bene_migrato,
                        :responsabile_laboratorio, :denominazione_fornitore, :anno_fabbricazione, :numero_seriale,
                        :categoria_inventoriale, :catalogazione_materiale_strumentazione, :peso, :dimensioni,
                        :ditta_costruttrice_fornitrice, :note
                    )
                """)
                conn.execute(sql, row.to_dict())

            conn.commit()

        print("✅ File caricato e dati inseriti con successo!")

        if not senza_responsabile.empty:
            print(
                f"⚠️ {len(senza_responsabile)} beni senza responsabile di laboratorio:"
            )
            for _, row in senza_responsabile.iterrows():
                print(f"- {row['descrizione_bene']} (inv: {row['num_inventario']})")

    except Exception as e:
        print(f"❌ Errore nel caricamento del file: {e}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python upload_excel_cli.py <file_excel.xlsx>")
    else:
        upload_excel(sys.argv[1])
