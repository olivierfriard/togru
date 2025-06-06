import sys
from flask import (
    Flask,
    request,
    render_template,
    redirect,
    url_for,
    flash,
    send_file,
    session,
)
from fpdf import FPDF
from functools import wraps
from io import BytesIO
from markupsafe import Markup
from requests_oauthlib import OAuth2Session
from sqlalchemy import create_engine, text
import pandas as pd
import json
import os
import qrcode
from datetime import datetime

APP_ROOT = "/togru"

app = Flask(__name__, static_url_path="/togru/static")
app.secret_key = "sldjhalsdasd2435"  # needed for flash messages

DATABASE_URL = "postgresql://togru_user@localhost:5432/togru"
engine = create_engine(DATABASE_URL)
# SESSION_PERMANENT = False

# Carico le credenziali dal JSON
try:
    with open("client_secret.json") as f:
        config = json.load(f)["web"]

    client_id = config["client_id"]
    client_secret = config["client_secret"]
    authorization_base_url = config["auth_uri"]
    token_url = config["token_uri"]
    redirect_uri = config["redirect_uris"][0]

    scope = [
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/userinfo.email",
    ]

    # solo per DEV
    if "127.0.0.1" in redirect_uri:
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

except Exception:
    raise

# Creazione tabella
with engine.connect() as conn:
    conn.execute(
        text("""
        CREATE TABLE IF NOT EXISTS inventario (
            id SERIAL PRIMARY KEY,
            descrizione_inventario TEXT,
            num_inventario TEXT,
            num_inventario_ateneo TEXT,
            data_carico TEXT,
            descrizione_bene TEXT,
            codice_sipi_torino TEXT,
            codice_sipi_grugliasco TEXT,
            destinazione TEXT,
            rosso_fase_alimentazione_privilegiata TEXT,
            valore_convenzionale TEXT,
            esercizio_bene_migrato TEXT,
            responsabile_laboratorio TEXT,
            denominazione_fornitore TEXT,
            anno_fabbricazione TEXT,
            numero_seriale TEXT,
            categoria_inventoriale TEXT,
            catalogazione_materiale_strumentazione TEXT,
            peso TEXT,
            dimensioni TEXT,
            ditta_costruttrice_fornitrice TEXT,
            note TEXT,
    deleted TIMESTAMP DEFAULT NULL
        )
    """)
    )
    conn.commit()

# load email of users
try:
    with open("email_tdr.txt", "r") as f_in:
        autorizzati = [x.strip() for x in f_in.readlines()]
except Exception:
    print("Problema di lettura su file email_tdr.txt")
    sys.exit(1)


def check_login(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "email" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated_function


@app.route(APP_ROOT + "/login")
def login():
    """Reindirizza l'utente alla schermata di autorizzazione di Google"""
    google = OAuth2Session(client_id, scope=scope, redirect_uri=redirect_uri)
    authorization_url, state = google.authorization_url(authorization_base_url)  # , access_type="offline", prompt="select_account")
    session["oauth_state"] = state
    """
    with open("login_log", "w") as f_out:
        print(f"{session.keys()=}\n", file=f_out)
    """
    return redirect(authorization_url)


@app.route(APP_ROOT + "/callback")
def callback():
    """Callback dopo il login Google"""
    """
    with open("callback_log", "w") as f_out:
        print(f"{session.keys()=}\n", file=f_out)
    """
    google = OAuth2Session(client_id, state=session["oauth_state"], redirect_uri=redirect_uri)
    token = google.fetch_token(token_url, client_secret=client_secret, authorization_response=request.url)

    session["oauth_token"] = token

    # Recupero dati utente
    response = google.get("https://www.googleapis.com/oauth2/v1/userinfo")
    userinfo = response.json()

    if userinfo["email"] not in autorizzati:
        flash(f"Spiacente {userinfo['name']}, non sei autorizzato ad accedere", "danger")
        return redirect(url_for("index"))

    session["name"] = userinfo["name"]
    session["email"] = userinfo["email"]

    return redirect(url_for("index"))


@app.route(APP_ROOT + "/logout")
def logout():
    """logout"""
    if "email" in session:
        del session["email"]
    if "name" in session:
        del session["name"]

    return redirect(url_for("index"))


# Visualizza home page
@app.route(APP_ROOT)
@app.route(APP_ROOT + "/")
def index():
    with engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT COUNT(*) AS n FROM inventario WHERE deleted IS NULL"  # GROUP BY responsabile_laboratorio,id ORDER BY responsabile_laboratorio DESC,id "
            )
        )
        n = result.fetchone()[0]
    return render_template("index.html", n_records=n)


# Visualizza record
@app.route(APP_ROOT + "/tutti")
def tutti():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT * FROM inventario WHERE deleted IS NULL ORDER BY responsabile_laboratorio, descrizione_bene "))
        records = result.fetchall()
    return render_template("tutti_record.html", records=records, query_string="tutti")


@app.route(APP_ROOT + "/view/<int:record_id>")
@app.route(APP_ROOT + "/view/<int:record_id>/")
@app.route(APP_ROOT + "/view/<int:record_id>/<query_string>")
@check_login
def view(record_id: int, query_string: str = ""):
    with engine.connect() as conn:
        sql = text("""SELECT id, descrizione_bene, responsabile_laboratorio,
                      num_inventario, num_inventario_ateneo, data_carico,
                     codice_sipi_torino, codice_sipi_grugliasco, destinazione,
                     rosso_fase_alimentazione_privilegiata, valore_convenzionale, esercizio_bene_migrato,
                     denominazione_fornitore, anno_fabbricazione, numero_seriale,
                     categoria_inventoriale, catalogazione_materiale_strumentazione, peso, dimensioni,
                    ditta_costruttrice_fornitrice, note 
                    FROM inventario 
                    WHERE id = :id""")
        result = conn.execute(sql, {"id": record_id}).fetchone()
        if not result:
            return f"Bene con ID {record_id} non trovato", 404

        record_dict = dict(result._mapping)  # ✅ questo funziona sicuro

    return render_template("view.html", record=record_dict, query_string=query_string)


# Aggiungi record
@app.route(APP_ROOT + "/aggiungi", methods=["GET", "POST"])
@check_login
def aggiungi():
    if request.method == "GET":
        return render_template("aggiungi.html")

    if request.method == "POST":
        data = request.form
        query = text("""
            INSERT INTO inventario (
                 num_inventario, num_inventario_ateneo, data_carico,
                descrizione_bene, codice_sipi_torino, codice_sipi_grugliasco, destinazione,
                rosso_fase_alimentazione_privilegiata, valore_convenzionale, esercizio_bene_migrato,
                responsabile_laboratorio, denominazione_fornitore, anno_fabbricazione, numero_seriale,
                categoria_inventoriale, catalogazione_materiale_strumentazione, peso, dimensioni,
                ditta_costruttrice_fornitrice, note
            ) VALUES (
                 :num_inventario, :num_inventario_ateneo, :data_carico,
                :descrizione_bene, :codice_sipi_torino, :codice_sipi_grugliasco, :destinazione,
                :rosso_fase_alimentazione_privilegiata, :valore_convenzionale, :esercizio_bene_migrato,
                :responsabile_laboratorio, :denominazione_fornitore, :anno_fabbricazione, :numero_seriale,
                :categoria_inventoriale, :catalogazione_materiale_strumentazione, :peso, :dimensioni,
                :ditta_costruttrice_fornitrice, :note
            )
        """)
        with engine.connect() as conn:
            conn.execute(text("SET LOCAL application_name = :user"), {"user": session["email"]})
            conn.execute(query, data)
            conn.commit()
        return redirect(url_for("index"))


# Modifica record - form
@app.route(APP_ROOT + "/modifica/<int:record_id>")
@app.route(APP_ROOT + "/modifica/<int:record_id>/")
@app.route(APP_ROOT + "/modifica/<int:record_id>/<query_string>")
@check_login
def modifica(record_id, query_string: str = ""):
    with engine.connect() as conn:
        result = conn.execute(text("SELECT * FROM inventario WHERE id = :id"), {"id": record_id})
        record = result.fetchone()
    return render_template("modifica.html", record=record, query_string=query_string)


# Modifica record - salvataggio
@app.route(APP_ROOT + "/salva_modifiche/<int:record_id>", methods=["POST"])
@check_login
def salva_modifiche(record_id):
    data = request.form
    query = text("""
        UPDATE inventario SET
            num_inventario = :num_inventario,
            num_inventario_ateneo = :num_inventario_ateneo,
            data_carico = :data_carico,
            descrizione_bene = :descrizione_bene,
            codice_sipi_torino = :codice_sipi_torino,
            codice_sipi_grugliasco = :codice_sipi_grugliasco,
            destinazione = :destinazione,
            rosso_fase_alimentazione_privilegiata = :rosso_fase_alimentazione_privilegiata,
            valore_convenzionale = :valore_convenzionale,
            esercizio_bene_migrato = :esercizio_bene_migrato,
            responsabile_laboratorio = :responsabile_laboratorio,
            denominazione_fornitore = :denominazione_fornitore,
            anno_fabbricazione = :anno_fabbricazione,
            numero_seriale = :numero_seriale,
            categoria_inventoriale = :categoria_inventoriale,
            catalogazione_materiale_strumentazione = :catalogazione_materiale_strumentazione,
            peso = :peso,
            dimensioni = :dimensioni,
            ditta_costruttrice_fornitrice = :ditta_costruttrice_fornitrice,
            note = :note
        WHERE id = :id
    """)
    with engine.connect() as conn:
        conn.execute(text("SET LOCAL application_name = :user"), {"user": session["email"]})
        conn.execute(query, {**data, "id": record_id})
        conn.commit()

    query_string = request.form.get("query_string", "")
    if query_string == "tutti":
        return redirect(APP_ROOT + "/tutti")
    elif query_string:
        return redirect(APP_ROOT + f"/search?{query_string}")
    else:
        return redirect(url_for("index"))


@app.route(APP_ROOT + "/modifica_multipla", methods=["POST"])
@check_login
def modifica_multipla():
    campo = request.form.get("campo")
    nuovo_valore = request.form.get("nuovo_valore")
    record_ids = request.form.getlist("record_ids")
    query_string = request.form.get("query_string", "")

    if (
        nuovo_valore
        and record_ids
        and campo
        in (
            "responsabile_laboratorio",
            "codice_sipi_torino",
            "codice_sipi_grugliasco",
            "destinazione",
            "note",
        )
    ):
        for rid in record_ids:
            print(f"{campo=}")
            print(f"{nuovo_valore=}")
            print(f"{rid=}")
            print("==")

            query = text(f"UPDATE inventario SET {campo} = :nuovo_valore WHERE id = :id")
            with engine.connect() as conn:
                conn.execute(
                    text("SET LOCAL application_name = :user"),
                    {"user": session["email"]},
                )
                conn.execute(query, {"id": rid, "nuovo_valore": nuovo_valore})
                conn.commit()

    return redirect(url_for("search") + "?" + query_string)


@app.route(APP_ROOT + "/upload_excel", methods=["GET", "POST"])
@check_login
def upload_excel():
    if request.method == "POST":
        file = request.files.get("file")
        if not file:
            flash("Nessun file caricato", "danger")
            return redirect(request.url)

        try:
            df = pd.read_excel(file)
            df.columns = df.columns.str.strip()

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

            for col in df.columns:
                if col.startswith("Peso"):
                    df.rename(columns={col: "Peso"}, inplace=True)
                    break  # Se vuoi rinominare solo la prima colonna che matcha

            df.rename(columns=excel_to_db_fields, inplace=True)
            df.fillna("", inplace=True)

            """
            # Trasforma num_inventario in intero dove possibile
            df["num_inventario"] = (
                pd.to_numeric(df["num_inventario"], errors="coerce")
                .fillna(0)
                .astype(int)
            )
            """

            # Controllo duplicati su num_inventario solo se diverso da NaN e stringa vuota
            """
            mask_validi = (df["num_inventario"].notna()) & (df["num_inventario"] != "")
            duplicati = df.loc[mask_validi, "num_inventario"].duplicated(keep=False)

            if duplicati.any():
                num_duplicati = duplicati.sum()
                inv_duplicati = df.loc[
                    duplicati.index[duplicati], ["num_inventario", "descrizione_bene"]
                ]
                elenco = "<br>".join(
                    f"{row['descrizione_bene']} (inv: {row['num_inventario']})"
                    for _, row in inv_duplicati.iterrows()
                )
                flash(
                    Markup(
                        f"<b>Nessun dato caricato</b> perché sono stati trovati <b>{num_duplicati} beni con numero di inventario duplicato nel file</b>:<br><br>{elenco}"
                    ),
                    "danger",
                )

                return redirect(request.url)
            """

            expected_cols = list(excel_to_db_fields.values())
            missing_cols = [c for c in expected_cols if c not in df.columns]
            if missing_cols:
                flash(f"Mancano colonne nel file Excel: {missing_cols}", "danger")
                return redirect(request.url)

            # record senza responsabile
            senza_responsabile = df[df["responsabile_laboratorio"] == ""]

            with engine.connect() as conn:
                conn.execute(
                    text("SET LOCAL application_name = :user"),
                    {"user": session["email"]},
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

            flash("File caricato e dati inseriti con successo!", "success")

            # se ci sono record senza responsabile -> flash di report sintetico
            count_senza_responsabile = len(senza_responsabile)

            if count_senza_responsabile > 0:
                # Prepariamo una lista di stringhe tipo "num_inventario (descrizione_bene)"
                dettagli = [f"{row['descrizione_bene']} (inv: {row['num_inventario']})" for _, row in senza_responsabile.iterrows()]
                inventari = "<br>".join(dettagli)
                flash(
                    Markup(f"<b>{count_senza_responsabile} beni senza responsabile di laboratorio</b>:<br>{inventari}"),
                    "warning",
                )

            return redirect(url_for("index"))

        except Exception as e:
            raise
            flash(f"Errore nel caricamento del file: {e}", "danger")
            return redirect(request.url)

    return render_template("upload_excel.html")


@app.route(APP_ROOT + "/search", methods=["GET"])
@check_login
def search():
    # Lista di tutti i campi su cui cercare
    fields = [
        # "descrizione_inventario",
        "descrizione_bene",
        "responsabile_laboratorio",
        "num_inventario",
        "num_inventario_ateneo",
        "data_carico",
        "codice_sipi_torino",
        "codice_sipi_grugliasco",
        "destinazione",
        "rosso_fase_alimentazione_privilegiata",
        # "valore_convenzionale",
        # "esercizio_bene_migrato",
        "denominazione_fornitore",
        "anno_fabbricazione",
        "numero_seriale",
        "categoria_inventoriale",
        "catalogazione_materiale_strumentazione",
        # "peso",
        # "dimensioni",
        "ditta_costruttrice_fornitrice",
        "note",
    ]

    query_string = request.query_string.decode("utf-8")

    # Controlla se almeno un parametro di ricerca è presente e non vuoto
    has_filter = any(request.args.get(field, "").strip() for field in fields)

    if not has_filter:
        # Nessun filtro: non eseguire query, ritorna lista vuota o messaggio
        records = []
        keys = fields  # se vuoi colonne vuote per tabella nel template
    else:
        query = "SELECT * FROM inventario WHERE deleted IS NULL "
        params = {}

        for field in fields:
            value = request.args.get(field, "").strip()
            if value:
                # add senza responsabile
                if field == "responsabile_laboratorio" and value == "SENZA":
                    query += f" AND ({field} = '' OR {field} IS NULL)"
                # add senza Codice SIPI Torino
                if field == "codice_sipi_torino" and value == "SENZA":
                    query += f" AND ({field} = '' OR {field} IS NULL)"

                else:
                    # Per testo, ricerca con ILIKE e wildcard %
                    query += f" AND {field} ILIKE :{field}"
                    params[field] = f"%{value}%"

        query += " ORDER BY id DESC"

        sql = text(query)
        with engine.connect() as conn:
            result = conn.execute(sql, params)
            records = result.fetchall()
            keys = result.keys()

    # Se viene richiesta esportazione Excel e ci sono risultati
    if request.args.get("export", "").lower() == "xlsx" and records:
        df = pd.DataFrame(records, columns=keys)
        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="Risultati")
        output.seek(0)

        return send_file(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="risultati_ricerca.xlsx",
        )

    return render_template(
        "search.html",
        records=records,
        request_args=request.args,
        fields=fields,
        query_string=query_string,
    )


@app.route(APP_ROOT + "/search_resp")
@check_login
def search_resp():
    with engine.connect() as conn:
        result = conn.execute(
            text(
                """( SELECT DISTINCT ON (LOWER(responsabile_laboratorio)) responsabile_laboratorio from inventario WHERE responsabile_laboratorio != '') ORDER by LOWER(responsabile_laboratorio)"""
            )
        )
        resp = result.fetchall()

    return render_template(
        "search_responsabile.html",
        resp=resp,
    )


@app.route(APP_ROOT + "/search_sipi_torino")
@check_login
def search_sipi_torino():
    with engine.connect() as conn:
        result = conn.execute(
            text("""( SELECT DISTINCT codice_sipi_torino FROM inventario WHERE codice_sipi_torino != '') ORDER BY codice_sipi_torino""")
        )
        sipi_list = result.fetchall()

    return render_template(
        "search_sipi_torino.html",
        sipi_list=sipi_list,
    )


@app.route(APP_ROOT + "/delete/<int:record_id>", methods=["POST"])
@app.route(APP_ROOT + "/delete/<int:record_id>/", methods=["POST"])
@app.route(APP_ROOT + "/delete/<int:record_id>/<query_string>", methods=["POST"])
@check_login
def delete_record(record_id, query_string: str = ""):
    """
    delete record
    """
    with engine.connect() as conn:
        conn.execute(text("SET LOCAL application_name = :user"), {"user": session["email"]})
        sql = text("UPDATE inventario SET deleted = :deleted_time WHERE id = :record_id")
        conn.execute(sql, {"deleted_time": datetime.utcnow(), "record_id": record_id})
        conn.commit()

    flash(f"Record {record_id} eliminato", "success")

    if query_string == "view":
        return redirect(APP_ROOT + "/tutti")
    else:
        return redirect(APP_ROOT + f"/search?{query_string}")


@app.route(APP_ROOT + "/view_qrcode/<int:record_id>")
def view_qrcode(record_id: int):
    with engine.connect() as conn:
        sql = text("""SELECT id, descrizione_bene, responsabile_laboratorio,
                      num_inventario, num_inventario_ateneo, data_carico,
                     codice_sipi_torino, codice_sipi_grugliasco, destinazione,
                     rosso_fase_alimentazione_privilegiata, valore_convenzionale, esercizio_bene_migrato,
                     denominazione_fornitore, anno_fabbricazione, numero_seriale,
                     categoria_inventoriale, catalogazione_materiale_strumentazione, peso, dimensioni,
                    ditta_costruttrice_fornitrice, note 
                    FROM inventario 
                    WHERE id = :id""")
        result = conn.execute(sql, {"id": record_id}).fetchone()
        if not result:
            return f"Bene con ID {record_id} non trovato", 404

        record_dict = dict(result._mapping)  # ✅ questo funziona sicuro

    return render_template("view.html", record=record_dict, query_string="")


@app.route(APP_ROOT + "/storico/<int:record_id>", methods=["GET"])
@check_login
def storico(record_id):
    with engine.connect() as conn:
        sql = text("SELECT * FROM inventario_audit WHERE record_id = :id ORDER BY executed_at DESC")
        audits = conn.execute(sql, {"id": record_id}).fetchall()
        if not audits:
            return f"Bene con ID {record_id} non trovato", 404

    return render_template("storico.html", audits=audits, record_id=record_id)


@app.route(APP_ROOT + "/storico_utente", methods=["GET"])
@app.route(APP_ROOT + "/storico_utente/", methods=["GET"])
@app.route(APP_ROOT + "/storico_utente/<email>", methods=["GET"])
@check_login
def storico_utente(email: str = ""):
    if not email:
        return "utente non trovato"
    with engine.connect() as conn:
        sql = text(
            """
SELECT 
    *
FROM inventario_audit a
INNER JOIN inventario i ON a.record_id = i.id
WHERE a.executed_by = :email
ORDER BY a.executed_at DESC;
            """
        )
        audits = conn.execute(sql, {"email": email}).fetchall()
        if not audits:
            return f"utente {email} non trovato/a", 404

    return render_template("storico_utente.html", audit_records=audits, username=email)


@app.route(APP_ROOT + "/etichetta/<int:record_id>", methods=["GET"])
@check_login
def etichetta(record_id):
    """
    Stampa etichetta da incollare sul bene
    """
    with engine.connect() as conn:
        sql = text("""SELECT * FROM inventario WHERE id = :id""")
        result = conn.execute(sql, {"id": record_id}).fetchone()
        if not result:
            return f"Bene con ID {record_id} non trovato", 404

        record_dict = dict(result._mapping)

    # Créer le QR code en mémoire
    qr_data = f"http://penelope.unito.it/togru/view_qrcode/{record_id}"
    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(qr_data)
    qr.make(fit=True)

    img_qr = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    # Save QR code in a BytesIO buffer
    qr_buffer = BytesIO()
    img_qr.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)

    # Save QR in a temporary file
    temp_qr_path = f"temp_{record_id}.png"
    img_qr.save(temp_qr_path)

    try:
        font_size = 12
        # Créer le PDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=font_size)
        h = font_size * 0.7
        pdf.cell(
            0,
            h,
            txt=f"{record_dict['descrizione_bene']}",
            ln=True,
            align="L",
        )
        pdf.cell(
            200,
            h,
            txt=f"Responsabile laboratorio: {record_dict['responsabile_laboratorio']}",
            ln=True,
            align="L",
        )
        pdf.cell(
            200,
            h,
            txt=f"Inventario: {record_dict['num_inventario']}  Ateneo: {record_dict['num_inventario_ateneo']}",
            ln=True,
            align="L",
        )
        pdf.cell(
            200,
            h,
            txt=f"Codice SIPI TORINO: {record_dict['codice_sipi_torino']}  GRUGLIASCO: {record_dict['codice_sipi_grugliasco']}",
            ln=True,
            align="L",
        )
        if record_dict["destinazione"]:
            pdf.cell(
                200,
                h,
                txt=f"Destinazione: {record_dict['destinazione']}",
                ln=True,
                align="L",
            )
        if record_dict["note"]:
            pdf.cell(200, h, txt=f"Destinazione: {record_dict['note']}", ln=True, align="L")

        pdf.cell(200, h, txt=f"TO-GRU id: {record_dict['id']}", ln=True, align="L")

        # Ajouter une image si tu veux
        pdf.image(temp_qr_path, x=5, y=50, w=50)

        # Sauvegarder le PDF dans un buffer mémoire
        pdf_buffer = BytesIO()
        pdf.output(pdf_buffer)
        pdf_buffer.seek(0)

        # Retourner le fichier au navigateur
        return send_file(
            pdf_buffer,
            mimetype="application/pdf",
            as_attachment=False,
            download_name=f"document_{record_id}.pdf",
        )

    finally:
        # Supprimer le fichier QR temporaire
        if os.path.exists(temp_qr_path):
            os.remove(temp_qr_path)


if __name__ == "__main__":
    app.run(debug=True)
