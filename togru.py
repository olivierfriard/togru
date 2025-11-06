"""
Servizio To-Gru (inventario per traslocco)
"""

import json
import os
import subprocess
import uuid
from datetime import datetime
from functools import wraps
from io import BytesIO
from pathlib import Path

import pandas as pd
from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from markupsafe import Markup
from requests_oauthlib import OAuth2Session
from sqlalchemy import create_engine, text

# from werkzeug.utils import secure_filename

__version__ = "2025-09-26 09:46"

APP_ROOT = "/togru"

app = Flask(__name__, static_url_path="/togru/static")
app.secret_key = "sldjhalsdasd2435"  # needed for flash messages


DATABASE_URL = "postgresql://togru_user@localhost:5432/togru"
engine = create_engine(DATABASE_URL)

# Carico le credenziali dal JSON
try:
    with open("client_secret.json") as f:
        config: dict[str, str] = json.load(f)["web"]

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
    app.config["UPLOAD_FOLDER"] = "static/images"


except Exception:
    raise


BOOLEAN_FIELDS = [
    "microscopia",
    "catena_del_freddo",
    "alta_specialistica",
    "da_movimentare",
    "trasporto_in_autonomia",
    "da_disinventariare",
    "rosso_fase_alimentazione_privilegiata",
    "didattica",
    "collezione",
]

# Creazione tabella
with engine.connect() as conn:
    _ = conn.execute(
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
            didattica boolean default false,
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


def check_login(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "email" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated_function


def check_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        with engine.connect() as conn:
            if "email" not in session:
                return redirect(url_for("index"))
            if session.get("admin", False):
                return f(*args, **kwargs)
            else:
                return redirect(url_for("index"))

    return decorated_function


# Aggiungi record
@app.route(APP_ROOT + "/aggiungi", methods=["GET", "POST"])
@app.route(APP_ROOT + "/aggiungi/", methods=["GET", "POST"])
@app.route(APP_ROOT + "/aggiungi/<query_string>", methods=["GET", "POST"])
@check_login
def aggiungi(query_string: str = ""):
    """
    aggiungi bene all'inventario
    """
    if request.method == "GET":
        with engine.connect() as conn:
            responsabili = conn.execute(
                text(
                    "SELECT DISTINCT responsabile_laboratorio FROM inventario WHERE deleted IS NULL ORDER BY responsabile_laboratorio"
                )
            ).fetchall()

        search_responsabile = "None"
        if query_string:
            search_responsabile = query_string.split("=")[1].replace("+", " ")
            print(f"{search_responsabile=}")

        return render_template(
            "aggiungi.html",
            responsabili=responsabili,
            boolean_fields=BOOLEAN_FIELDS,
            query_string=query_string,
            search_responsabile=search_responsabile,
        )

    if request.method == "POST":
        data = dict(request.form)

        # modify values for boolean fields
        for field in BOOLEAN_FIELDS:
            value = request.form.get(field)
            data[field] = value == "true"

        # check for new responsabile
        if data["responsabile_laboratorio"] == "altro":
            data["responsabile_laboratorio"] = data["nuovo_responsabile_laboratorio"]

        query = text("""
            INSERT INTO inventario (
            quantita,
                 num_inventario, num_inventario_ateneo, data_carico,
                descrizione_bene, codice_sipi_torino, codice_sipi_grugliasco, destinazione,
                microscopia, catena_del_freddo, alta_specialistica, da_movimentare, trasporto_in_autonomia, da_disinventariare,
                rosso_fase_alimentazione_privilegiata,
                didattica, valore_convenzionale, esercizio_bene_migrato,
                responsabile_laboratorio, denominazione_fornitore, anno_fabbricazione, numero_seriale,
                categoria_inventoriale, catalogazione_materiale_strumentazione, peso, dimensioni,
                ditta_costruttrice_fornitrice, note, collezione
            ) VALUES (
                :quantita, :num_inventario, :num_inventario_ateneo, :data_carico,
                :descrizione_bene, :codice_sipi_torino, :codice_sipi_grugliasco, :destinazione,
                :microscopia, :catena_del_freddo, :alta_specialistica, :da_movimentare, :trasporto_in_autonomia, :da_disinventariare,
                :rosso_fase_alimentazione_privilegiata, :didattica, :valore_convenzionale, :esercizio_bene_migrato,
                :responsabile_laboratorio, :denominazione_fornitore, :anno_fabbricazione, :numero_seriale,
                :categoria_inventoriale, :catalogazione_materiale_strumentazione, :peso, :dimensioni,
                :ditta_costruttrice_fornitrice, :note, :collezione
            )
            RETURNING id
        """)
        with engine.connect() as conn:
            _ = conn.execute(
                text("SET LOCAL application_name = :user"), {"user": session["email"]}
            )
            new_id = conn.execute(query, data).fetchone()[0]
            conn.commit()

            # foto
            foto = request.files.get("foto")
            if foto and foto.filename != "":
                foto.save(
                    Path(app.config["UPLOAD_FOLDER"])
                    / Path(str(new_id) + "_1").with_suffix(Path(foto.filename).suffix)
                )

        if query_string:
            return redirect(APP_ROOT + f"/search?{query_string}")
        else:
            return redirect(url_for("index"))


@app.route(f"{APP_ROOT}/aggiungi_user", methods=["GET", "POST"])
@check_login
@check_admin
def aggiungi_user():
    """
    add a user
    """
    if request.method == "GET":
        with engine.connect() as conn:
            users = conn.execute(
                text(
                    "SELECT email, INITCAP(REPLACE(REPLACE(email, '@unito.it', ''), '.', ' ')) AS name FROM users ORDER by email"
                )
            ).fetchall()

        return render_template("aggiungi_user.html", users=users)

    if request.method == "POST":
        email = request.form.get("email")
        with engine.connect() as conn:
            # text if user already present
            sql = text("SELECT COUNT(*) FROM users WHERE email = :email")
            if conn.execute(sql, {"email": email}).scalar():
                flash(Markup(f"L'utente <b>{email}</b> è già abilitato"), "warning")
                return redirect(url_for("aggiungi_user"))
            # insert new user
            sql = text("INSERT INTO users (email, admin) VALUES (:email, :admin)")
            _ = conn.execute(sql, {"email": email, "admin": False})
            conn.commit()

        flash(Markup(f"L'utente <b>{email}</b> è stato aggiunto"), "success")
        return redirect(url_for("aggiungi_user"))


@app.route(APP_ROOT + "/attivita_utenti", methods=["GET"])
@check_login
@check_admin
def attivita_utenti():
    """
    returns list of active users
    """
    with engine.connect() as conn:
        sql = text(
            (
                #                "SELECT executed_by AS email,"
                #                "INITCAP(REPLACE(REPLACE(executed_by, '@unito.it', ''), '.', ' ')) AS user, "
                #                "MAX(executed_at) AS last_operation, "
                #                "COUNT(*) AS num_operations "
                #                "FROM inventario_audit "
                #                "WHERE executed_by like '%@%' "
                #                "GROUP BY executed_by "
                #                "ORDER BY last_operation DESC"
                "SELECT "
                "    DATE(executed_at) AS day, "
                "    executed_by AS user, "
                "    COUNT(*) AS num_operations "
                "FROM inventario_audit "
                "GROUP BY day, executed_by "
                "ORDER BY day DESC, executed_by; "
            )
        )
        audits = conn.execute(sql).fetchall()

    return render_template("attivita_utenti.html", audit_records=audits)


@app.route(APP_ROOT + "/attivita_utente/<email>", methods=["GET"])
@check_login
@check_admin
def attivita_utente(email: str):
    """
    returns user activity
    """
    with engine.connect() as conn:
        sql = text(
            (
                "SELECT descrizione_bene, operation_type, record_id, executed_at "
                "FROM inventario_audit LEFT JOIN inventario ON inventario_audit.record_id = inventario.id "
                "WHERE executed_by = :email "
                "ORDER BY executed_at DESC"
            )
        )
        attivita = conn.execute(sql, {"email": email}).fetchall()

    return render_template("attivita_utente.html", attivita=attivita, email=email)


@app.route(APP_ROOT + "/callback")
def callback():
    """
    Callback dopo il login Google
    """
    google = OAuth2Session(
        client_id, state=session["oauth_state"], redirect_uri=redirect_uri
    )
    token = google.fetch_token(
        token_url, client_secret=client_secret, authorization_response=request.url
    )

    session["oauth_token"] = token

    # Recupero dati utente
    response = google.get("https://www.googleapis.com/oauth2/v1/userinfo")
    userinfo = response.json()

    with engine.connect() as conn:
        n_user = conn.execute(
            text("SELECT COUNT(*) FROM users WHERE email = :email"),
            {"email": userinfo["email"]},
        ).scalar()
        if not n_user:
            flash(
                f"Spiacente {userinfo['name']}, non sei autorizzato ad accedere",
                "danger",
            )
            return redirect(url_for("index"))

    session["name"] = userinfo["name"]
    session["email"] = userinfo["email"]
    session["admin"] = False

    # check if admin
    with engine.connect() as conn:
        if "email" in session:
            n = conn.execute(
                text(
                    "SELECT COUNT(*) FROM users WHERE admin = TRUE and email = :email"
                ),
                {"email": session["email"]},
            ).scalar()
            if n:
                session["admin"] = True

    return redirect(url_for("index"))


@app.route(APP_ROOT + "/collezioni")
def collezioni():
    """
    visualizza le collezioni
    """
    return redirect(f"{APP_ROOT}/search?collezione=true")


@app.route(APP_ROOT + "/etichetta", methods=["POST"])
@app.route(APP_ROOT + "/etichetta/<int:record_id>", methods=["GET"])
@check_login
def etichetta(record_id: str = ""):
    """
    Stampa etichetta da incollare sul bene
    require typst (https://github.com/typst/typst)
    """

    record_ids = request.form.getlist("record_ids")

    if not record_ids:
        record_list = [record_id]
    else:
        record_list = record_ids

    typst_content = label(record_list)
    if "Error in record list" in typst_content:
        flash("Un errore è avvenuto", "danger")
        return redirect(request.referrer)

    if len(record_list) > 50:
        flash("Troppi beni selezionati per la stampa (<50)", "danger")
        return redirect(request.referrer)

    if not record_id:
        record_id = str(uuid.uuid4())

    temp_typst_path: str = ""
    temp_pdf_path: str = ""

    try:
        temp_typst_path = f"/tmp/label_{record_id}.typst"
        with open(temp_typst_path, "w") as f_out:
            _ = f_out.write(typst_content)

        temp_pdf_path = f"/tmp/label_{record_id}.pdf"

        _ = subprocess.run(
            ["/usr/bin/typst", "compile", temp_typst_path, temp_pdf_path]
        )

        # send file to client
        return send_file(
            temp_pdf_path,
            mimetype="application/pdf",
            as_attachment=False,
            download_name=f"etichetta_{record_id}.pdf",
        )

    finally:
        # Delete temp files
        if Path(temp_typst_path).exists():
            Path(temp_typst_path).unlink()
        if Path(temp_pdf_path).exists():
            Path(temp_pdf_path).unlink()


@app.route(APP_ROOT + "/delete_foto/<img_id>")
@check_login
def delete_foto(img_id: str):
    """
    cancella foto
    """
    record_id = img_id.split("_")[0]
    if (Path(app.config["UPLOAD_FOLDER"]) / img_id).exists():
        (Path(app.config["UPLOAD_FOLDER"]) / img_id).unlink()
        # record
        with engine.connect() as conn:
            conn.execute(
                text(
                    f"INSERT INTO inventario_audit (operation_type, record_id, executed_by) VALUES ('DELETED FOTO {img_id}', :record_id, :executed_by)"
                ),
                {"record_id": record_id, "executed_by": session["email"]},
            )
            conn.commit()

    return redirect(f"/togru/modifica/{record_id}")


@app.route(APP_ROOT + "/delete/<int:record_id>", methods=["POST"])
@app.route(APP_ROOT + "/delete/<int:record_id>/", methods=["POST"])
@app.route(APP_ROOT + "/delete/<int:record_id>/<path:query_string>", methods=["POST"])
@check_login
def delete_record(record_id: int, query_string: str = ""):
    """
    delete record
    """
    with engine.connect() as conn:
        _ = conn.execute(
            text("SET LOCAL application_name = :user"), {"user": session["email"]}
        )
        sql = text(
            "UPDATE inventario SET deleted = :deleted_time WHERE id = :record_id"
        )
        _ = conn.execute(
            sql, {"deleted_time": datetime.utcnow(), "record_id": record_id}
        )
        conn.commit()

    flash(f"Record {record_id} eliminato", "success")

    if query_string == "view":
        return redirect(APP_ROOT + "/tutti")
    else:
        return redirect(APP_ROOT + f"/search?{query_string}")


@app.route(APP_ROOT + "/delete_user/<email>")
@check_login
@check_admin
def delete_user(email: str):
    """
    remove user
    """
    with engine.connect() as conn:
        # check if email in DB
        n_users = conn.execute(
            text("SELECT COUNT(*) FROM users WHERE email = :email"), {"email": email}
        ).scalar()
        if not n_users:
            flash(f"Utente {email} non trovato", "danger")
            return redirect(url_for("aggiungi_user"))

        # delete user
        _ = conn.execute(
            text("DELETE FROM users WHERE email = :email"), {"email": email}
        )
        conn.commit()
        flash(Markup(f"L'utente <b>{email}</b> è stato cancellato"), "success")

        return redirect(url_for("aggiungi_user"))


# Modifica record - form
@app.route(f"{APP_ROOT}/duplica/<int:record_id>", methods=["GET", "POST"])
@app.route(APP_ROOT + "/duplica/<int:record_id>/", methods=["GET", "POST"])
@app.route(
    APP_ROOT + "/duplica/<int:record_id>/<path:query_string>", methods=["GET", "POST"]
)
@check_login
def duplica(record_id: int, query_string: str = ""):
    """
    duplica un bene
    """
    if request.method == "GET":
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    (
                        "SELECT id, descrizione_bene, responsabile_laboratorio FROM inventario WHERE id = :id"
                    )
                ),
                {"id": record_id},
            )
            record = result.fetchone()

        return render_template(
            "duplica_bene.html",
            record_id=record_id,
            record=record,
            query_string=query_string,
        )

    if request.method == "POST":
        copy_number = int(request.form.get("numero_copie"))
        with engine.connect() as conn:
            for i in range(1, copy_number + 1):
                sql = text(
                    (
                        "INSERT INTO inventario ( "
                        "  num_inventario, "
                        "  num_inventario_ateneo, "
                        "  data_carico, "
                        "  descrizione_bene, "
                        "  codice_sipi_torino, "
                        "  codice_sipi_grugliasco, "
                        "  destinazione, "
                        "  rosso_fase_alimentazione_privilegiata, "
                        "  valore_convenzionale, "
                        "  esercizio_bene_migrato, "
                        "  responsabile_laboratorio, "
                        "  denominazione_fornitore, "
                        "  anno_fabbricazione, "
                        "  numero_seriale, "
                        "  categoria_inventoriale, "
                        "  catalogazione_materiale_strumentazione, "
                        "  peso, "
                        "  dimensioni, "
                        "  ditta_costruttrice_fornitrice, "
                        "  note, "
                        "  deleted, "
                        "  microscopia, "
                        "  catena_del_freddo, "
                        "  alta_specialistica, "
                        "  da_movimentare, "
                        "  trasporto_in_autonomia, "
                        "  da_disinventariare, "
                        "  didattica, "
                        "  collezione "
                        ") "
                        "SELECT "
                        "  num_inventario, "
                        "  num_inventario_ateneo, "
                        "  data_carico, "
                        f"  CONCAT(descrizione_bene, ' #', {i + 1}) , "
                        "  codice_sipi_torino, "
                        "  codice_sipi_grugliasco, "
                        "  destinazione, "
                        "  rosso_fase_alimentazione_privilegiata, "
                        "  valore_convenzionale, "
                        "  esercizio_bene_migrato, "
                        "  responsabile_laboratorio, "
                        "  denominazione_fornitore, "
                        "  anno_fabbricazione, "
                        "  numero_seriale, "
                        "  categoria_inventoriale, "
                        "  catalogazione_materiale_strumentazione, "
                        "  peso, "
                        "  dimensioni, "
                        "  ditta_costruttrice_fornitrice, "
                        "  note, "
                        "  deleted, "
                        "  microscopia, "
                        "  catena_del_freddo, "
                        "  alta_specialistica, "
                        "  da_movimentare, "
                        "  trasporto_in_autonomia, "
                        "  da_disinventariare, "
                        "  didattica, "
                        "  collezione "
                        "FROM inventario "
                        "WHERE id = :record_id "
                    )
                )
                _ = conn.execute(sql, {"record_id": record_id})
                conn.commit()

        flash("Bene duplicato con successo!", "success")

        return redirect(url_for("search") + "?" + query_string)


# Visualizza home page
@app.route(APP_ROOT)
@app.route(APP_ROOT + "/")
def index():
    with engine.connect() as conn:
        n_beni = conn.execute(
            text("SELECT COUNT(*) FROM inventario WHERE deleted IS NULL")
        ).scalar()

        n_beni_da_movimentare = conn.execute(
            text(
                "SELECT COUNT(*) FROM inventario WHERE deleted IS NULL AND da_movimentare AND not trasporto_in_autonomia"
            )
        ).scalar()

        n_beni_non_conforme = conn.execute(
            text(
                (
                    "SELECT COUNT(*) FROM inventario WHERE deleted IS NULL AND not collezione AND da_movimentare AND not trasporto_in_autonomia "
                    r"AND (peso !~ '^-?[0-9]+(\.[0-9]+)?$' OR dimensioni !~ '^[0-9]+x[0-9]+x[0-9]+$')"
                )
            )
        ).scalar()

        n_beni_da_movimentare_in_autonomia = conn.execute(
            text(
                "SELECT COUNT(*) FROM inventario WHERE deleted IS NULL AND da_movimentare AND trasporto_in_autonomia"
            )
        ).scalar()

        alta_specialistica = conn.execute(
            text(
                "SELECT COUNT(*) FROM inventario WHERE deleted IS NULL AND da_movimentare  AND alta_specialistica"
            )
        ).scalar()

        microscopia = conn.execute(
            text(
                "SELECT COUNT(*) FROM inventario WHERE deleted IS NULL AND da_movimentare  AND microscopia"
            )
        ).scalar()

        microscopia_non_alta = conn.execute(
            text(
                "SELECT COUNT(*) FROM inventario WHERE deleted IS NULL AND da_movimentare  AND microscopia AND not alta_specialistica"
            )
        ).scalar()

        catena_freddo = conn.execute(
            text(
                "SELECT COUNT(*) FROM inventario WHERE deleted IS NULL AND da_movimentare AND catena_del_freddo"
            )
        ).scalar()

        n_beni_senza_responsabile = conn.execute(
            text(
                "SELECT COUNT(*) FROM inventario WHERE deleted IS NULL AND (responsabile_laboratorio = '' OR responsabile_laboratorio IS NULL)"
            )
        ).scalar()

    return render_template(
        "index.html",
        n_records=n_beni,
        n_beni_senza_responsabile=n_beni_senza_responsabile,
        n_beni_da_movimentare=n_beni_da_movimentare,
        n_beni_da_movimentare_in_autonomia=n_beni_da_movimentare_in_autonomia,
        n_beni_non_conforme=n_beni_non_conforme,
        alta_specialistica=alta_specialistica,
        microscopia=microscopia,
        microscopia_non_alta=microscopia_non_alta,
        catena_freddo=catena_freddo,
    )


def label(record_list: list) -> str:
    """
    create typst label for records
    """
    with engine.connect() as conn:
        ids = ",".join([str(x) for x in record_list])
        sql = text(f"SELECT * FROM inventario WHERE id in ({ids})")
        records = conn.execute(sql).mappings().all()
        if not records:
            return f"Error in record list {', '.join(record_list)}"

        label_header = (
            '#import "@preview/cades:0.3.0": qr-code\n'
            "\n"
            "#set page(margin: (top: 1cm, bottom: 1cm, x:1cm))\n"
            "\n"
            "#set text(\n"
            '  font: "Libertinus Serif",\n'
            "  size: 11pt,\n"
            ")\n"
        )

    out = [label_header]

    for record in records:
        out.append("#block(breakable: false)[")

        out.append(
            f"""#text(size: 12pt)[*`{record["descrizione_bene"].replace("`", "'") if record["descrizione_bene"] else " "}`*] """
        )

        out.append(
            f"""#text(size: 12pt)[*`{record["descrizione_bene"].replace("`", "'") if record["descrizione_bene"] else " "}`*]"""
        )
        out.append("")
        out.append("#grid(columns: (14cm, 5cm),")
        out.append("[")
        if record["responsabile_laboratorio"]:
            out.append(f"`Responsabile lab:` *`{record['responsabile_laboratorio']}`*")
        else:
            out.append("*`SENZA RESPONSABILE`*")
        out.append("")

        out.append("#grid(columns: (7cm, 7cm),")
        if record["num_inventario"]:
            out.append(f"[`Num inv:` *`{record['num_inventario']}`*],")
        else:
            out.append("[`Num inventario` *`ASSENTE`*],")
        out.append(f"[`TOGRU id:` *`{record['id']}`*],")
        out.append(")")
        out.append("")

        out.append("#grid(columns: (7cm, 7cm),")
        out.append("")
        out.append(
            f"""[`SIPI TO:` *`{record["codice_sipi_torino"] if record["codice_sipi_torino"] else "-"}`*],"""
        )
        out.append(
            f"""[`SIPI GRU:` *`{record["codice_sipi_grugliasco"] if record["codice_sipi_grugliasco"] else "-"}`*],"""
        )
        out.append(")")
        out.append("")
        out.append(
            f"""`{"DA MOVIMENTARE" if record["da_movimentare"] else "STRUMENTO/BENE DA NON MOVIMENTARE/DISMETTERE"}`"""
        )
        out.append("")
        out.append(
            f"""`{"DA DISINVENTARIARE" if record["da_disinventariare"] else ""}`"""
        )
        out.append("")
        out.append(
            f"""`{"TRASPORTO IN AUTONOMIA" if record["trasporto_in_autonomia"] else ""}`"""
        )
        out.append("")
        out.append(f"""`{record["destinazione"]}`""")
        out.append("")
        out.append("],")
        out.append("")
        out.append("[")
        out.append("")
        out.append("#grid( columns: (2.5cm, 2.5cm),")
        out.append("[")
        out.append("#rect(width: 2.3cm,height: 2.3cm,")
        out.append(f"""  fill: {"green" if record["da_movimentare"] else "red"},""")
        out.append("  stroke: 0.4cm+white,")
        out.append(")")
        out.append("],")
        out.append("[")
        out.append(
            f"""#qr-code("https://penelope.unito.it/togru/view_qrcode/{record["id"]}", width: 2.3cm)"""
        )
        out.append("]")
        out.append(")")
        out.append("]")
        out.append("")
        out.append(")")
        out.append("")
        out.append("#line(length: 100%)")
        out.append("")
        out.append("]")

    return "\n".join(out)


@app.route(APP_ROOT + "/login")
def login():
    """
    Reindirizza l'utente alla schermata di autorizzazione di Google
    """
    google = OAuth2Session(client_id, scope=scope, redirect_uri=redirect_uri)
    authorization_url, state = google.authorization_url(authorization_base_url)
    session["oauth_state"] = state
    return redirect(authorization_url)


@app.route(APP_ROOT + "/logout")
def logout():
    """logout"""
    if "email" in session:
        del session["email"]
    if "admin" in session:
        del session["admin"]

    if "name" in session:
        del session["name"]

    return redirect(url_for("index"))


@app.route(APP_ROOT + "/mappe", methods=["GET"])
@check_login
def mappe():
    return render_template("mappe.html")


# Modifica record - form
@app.route(APP_ROOT + "/modifica/<int:record_id>")
@app.route(APP_ROOT + "/modifica/<int:record_id>/")
@app.route(APP_ROOT + "/modifica/<int:record_id>/<path:query_string>")
@check_login
def modifica(record_id: int, query_string: str = ""):
    """
    modifica un bene
    """
    with engine.connect() as conn:
        result = conn.execute(
            text(
                (
                    "SELECT id, quantita, descrizione_bene, responsabile_laboratorio, "
                    "num_inventario, num_inventario_ateneo, data_carico,"
                    "codice_sipi_torino, codice_sipi_grugliasco, destinazione,"
                    "CASE WHEN microscopia THEN 'SI' ELSE 'NO' END AS microscopia,"
                    "CASE WHEN catena_del_freddo THEN 'SI' ELSE 'NO' END AS catena_del_freddo,"
                    "CASE WHEN alta_specialistica THEN 'SI' ELSE 'NO' END AS alta_specialistica, "
                    "CASE WHEN da_movimentare THEN 'SI' ELSE 'NO' END AS da_movimentare,"
                    "CASE WHEN trasporto_in_autonomia THEN 'SI' ELSE 'NO' END AS trasporto_in_autonomia,"
                    "CASE WHEN da_disinventariare THEN 'SI' ELSE 'NO' END AS da_disinventariare,"
                    "CASE WHEN rosso_fase_alimentazione_privilegiata THEN 'SI' ELSE 'NO' END AS rosso_fase_alimentazione_privilegiata,"
                    "CASE WHEN didattica THEN 'SI' ELSE 'NO' END AS didattica,"
                    "CASE WHEN collezione THEN 'SI' ELSE 'NO' END AS collezione,"
                    "valore_convenzionale,"
                    "denominazione_fornitore, anno_fabbricazione, numero_seriale,"
                    "categoria_inventoriale, catalogazione_materiale_strumentazione, peso, dimensioni,"
                    "ditta_costruttrice_fornitrice, note, "
                    r"(collezione = false AND da_movimentare = true AND trasporto_in_autonomia = false AND peso !~ '^-?[0-9]+(\.[0-9]+)?$') AS peso_non_conforme, "  #
                    "(collezione = false AND da_movimentare = true AND trasporto_in_autonomia = false AND dimensioni !~ '^[0-9]+x[0-9]+x[0-9]+$') AS dimensioni_non_conforme "
                    "FROM inventario "
                    "WHERE id = :id"
                )
            ),
            {"id": record_id},
        )
        record = result.mappings().fetchone()

        responsabili = conn.execute(
            text(
                "SELECT DISTINCT responsabile_laboratorio FROM inventario WHERE deleted IS NULL ORDER BY responsabile_laboratorio"
            )
        ).fetchall()

        # check for images
        img_list = [
            x.name for x in list(Path(app.config["UPLOAD_FOLDER"]).glob("*_*.*"))
        ]

    return render_template(
        "modifica.html",
        record=record,
        query_string=query_string,
        responsabili=responsabili,
        img_list=img_list,
        boolean_fields=BOOLEAN_FIELDS,
        peso_non_conforme=record["peso_non_conforme"],
        dimensioni_non_conforme=record["dimensioni_non_conforme"],
    )


# Modifica record - salvataggio
@app.route(APP_ROOT + "/salva_modifiche/<int:record_id>", methods=["POST"])
@check_login
def salva_modifiche(record_id):
    data = dict(request.form)

    for field in BOOLEAN_FIELDS:
        value = request.form.get(field)
        data[field] = value == "true"

    # check for new responsabile
    if data["responsabile_laboratorio"] == "altro":
        data["responsabile_laboratorio"] = data["nuovo_responsabile_laboratorio"]

    query = text(
        (
            "UPDATE inventario SET "
            "    quantita = :quantita, "
            "    descrizione_bene = :descrizione_bene, "
            "    responsabile_laboratorio = :responsabile_laboratorio, "
            "    num_inventario = :num_inventario, "
            "    num_inventario_ateneo = :num_inventario_ateneo, "
            "    data_carico = :data_carico, "
            "    codice_sipi_torino = :codice_sipi_torino, "
            "    codice_sipi_grugliasco = :codice_sipi_grugliasco, "
            "    destinazione = :destinazione, "
            "    microscopia = :microscopia, "
            "    catena_del_freddo = :catena_del_freddo, "
            "    alta_specialistica = :alta_specialistica, "
            "    da_movimentare = :da_movimentare, "
            "    trasporto_in_autonomia = :trasporto_in_autonomia, "
            "    da_disinventariare = :da_disinventariare, "
            "    rosso_fase_alimentazione_privilegiata = :rosso_fase_alimentazione_privilegiata, "
            "    didattica = :didattica, "
            "    valore_convenzionale = :valore_convenzionale, "
            # "    esercizio_bene_migrato = :esercizio_bene_migrato, "
            "    denominazione_fornitore = :denominazione_fornitore, "
            "    anno_fabbricazione = :anno_fabbricazione, "
            "    numero_seriale = :numero_seriale, "
            "    categoria_inventoriale = :categoria_inventoriale, "
            "    catalogazione_materiale_strumentazione = :catalogazione_materiale_strumentazione, "
            "    peso = :peso, "
            "    dimensioni = :dimensioni, "
            "    ditta_costruttrice_fornitrice = :ditta_costruttrice_fornitrice, "
            "    note = :note, "
            "    collezione = :collezione "
            "WHERE id = :id "
        )
    )
    with engine.connect() as conn:
        conn.execute(
            text("SET LOCAL application_name = :user"), {"user": session["email"]}
        )
        conn.execute(query, {**data, "id": record_id})
        conn.commit()

    foto = request.files.get("foto")
    if foto and foto.filename != "":
        # filename = secure_filename(foto.filename)
        img_list = [
            x.stem
            for x in list(Path(app.config["UPLOAD_FOLDER"]).glob(f"{record_id}_*.*"))
        ]
        if not img_list:
            foto.save(
                Path(app.config["UPLOAD_FOLDER"])
                / Path(str(record_id) + "_1").with_suffix(Path(foto.filename).suffix)
            )
        else:
            img_id = max([int(x.split("_")[1]) for x in img_list]) + 1
            foto.save(
                Path(app.config["UPLOAD_FOLDER"])
                / Path(str(record_id) + f"_{img_id}").with_suffix(
                    Path(foto.filename).suffix
                )
            )

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

    if campo in (
        "da_movimentare",
        "trasporto_in_autonomia",
        "collezione",
    ) and nuovo_valore.upper() not in ("SI", "NO"):
        flash(
            Markup(
                f"Il valore per il campo <b>{campo.replace('_', ' ')}</b> deve essere <b>SI</b> o <b>NO</b>"
            ),
            "danger",
        )
        return redirect(url_for("search") + "?" + query_string)

    if (
        nuovo_valore
        and record_ids
        and campo
        in (
            "responsabile_laboratorio",
            "codice_sipi_torino",
            "codice_sipi_grugliasco",
            "da_movimentare",
            "trasporto_in_autonomia",
            "catena_del_freddo",
            "didattica",
            "collezione",
            "destinazione",
            "note",
        )
    ):
        # set boolean values
        if campo in (
            "da_movimentare",
            "trasporto_in_autonomia",
            "catena_del_freddo",
            "didattica",
            "collezione",
        ):
            nuovo_valore = nuovo_valore.upper() == "SI"

        with engine.connect() as conn:
            for rid in record_ids:
                query = text(
                    f"UPDATE inventario SET {campo} = :nuovo_valore WHERE id = :id"
                )

                conn.execute(
                    text("SET LOCAL application_name = :user"),
                    {"user": session["email"]},
                )
                conn.execute(query, {"id": rid, "nuovo_valore": nuovo_valore})
                conn.commit()

    return redirect(url_for("search") + "?" + query_string)


'''
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

            print(df.columns)

            expected_cols = list(excel_to_db_fields.keys())
            missing_cols = [c for c in expected_cols if c not in df.columns]
            if missing_cols:
                flash(
                    Markup(
                        f"Mancano colonne nel file Excel:<br><b> {'<br>'.join(missing_cols)}</b>"
                    ),
                    "danger",
                )
                return redirect(request.url)

            # rename columns
            df.rename(columns=excel_to_db_fields, inplace=True)
            df.fillna("", inplace=True)

            # record senza responsabile
            senza_responsabile = df[df["responsabile_laboratorio"] == ""]

            #

            with engine.connect() as conn:
                conn.execute(
                    text("SET LOCAL application_name = :user"),
                    {"user": session["email"]},
                )
                for _, row in df.iterrows():
                    sql = text("""
                    INSERT INTO inventario (
                         num_inventario, num_inventario_ateneo, data_carico,
                        descrizione_bene, codice_sipi_torino, codice_sipi_grugliasco, destinazione,
                        rosso_fase_alimentazione_privilegiata, valore_convenzionale, esercizio_bene_migrato,
                        responsabile_laboratorio, denominazione_fornitore, anno_fabbricazione, numero_seriale,
                        catalogazione_materiale_strumentazione, peso, dimensioni,
                        ditta_costruttrice_fornitrice, note
                    ) VALUES (
                         :num_inventario, :num_inventario_ateneo, :data_carico,
                        :descrizione_bene, :codice_sipi_torino, :codice_sipi_grugliasco, :destinazione,
                        :rosso_fase_alimentazione_privilegiata, :valore_convenzionale, :esercizio_bene_migrato,
                        :responsabile_laboratorio, :denominazione_fornitore, :anno_fabbricazione, :numero_seriale,
                        :catalogazione_materiale_strumentazione, :peso, :dimensioni,
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
                dettagli = [
                    f"{row['descrizione_bene']} (inv: {row['num_inventario']})"
                    for _, row in senza_responsabile.iterrows()
                ]
                inventari = "<br>".join(dettagli)
                flash(
                    Markup(
                        f"<b>{count_senza_responsabile} beni senza responsabile di laboratorio</b>:<br>{inventari}"
                    ),
                    "warning",
                )

            return redirect(url_for("index"))

        except Exception as e:
            raise
            flash(f"Errore nel caricamento del file: {e}", "danger")
            return redirect(request.url)

    return render_template("upload_excel.html")
'''


@app.route(APP_ROOT + "/search", methods=["GET"])
@check_login
def search():
    # Lista di tutti i campi su cui cercare
    fields = [
        # "descrizione_inventario",
        "descrizione_bene",
        "responsabile_laboratorio",
        "collezione",
        "num_inventario",
        "num_inventario_ateneo",
        "data_carico",
        "codice_sipi_torino",
        "codice_sipi_grugliasco",
        "destinazione",
        "microscopia",
        "catena_del_freddo",
        "alta_specialistica",
        "da_movimentare",
        "trasporto_in_autonomia",
        "da_disinventariare",
        "rosso_fase_alimentazione_privilegiata",
        "didattica",
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

    n_beni_non_conformi: int = 0

    if not has_filter:
        # Nessun filtro: non eseguire query, ritorna lista vuota o messaggio
        records = []
        keys = fields
    else:
        query: str = (
            'SELECT id AS "ID", '
            'quantita as "Quantità", '
            'descrizione_bene AS "Descrizione bene", '
            'responsabile_laboratorio AS "Responsabile Laboratorio / Ufficio", '
            "da_movimentare, catena_del_freddo, trasporto_in_autonomia, microscopia, alta_specialistica, collezione, "
            'codice_sipi_torino AS "Codice SIPI Torino", '
            'codice_sipi_grugliasco AS "Codice SIPI Grugliasco", '
            'destinazione AS "Destinazione", '
            'note AS "Note", '
            r"(collezione = false AND da_movimentare = true AND trasporto_in_autonomia = false AND peso !~ '^-?[0-9]+(\.[0-9]+)?$')  AS peso_non_conforme, "
            "(collezione = false AND da_movimentare = true AND trasporto_in_autonomia = false AND dimensioni !~ '^[0-9]+x[0-9]+x[0-9]+$') AS dimensioni_non_conforme "
            "FROM inventario WHERE deleted IS NULL "
        )
        params: dict[str, str] = {}

        query_non_conforme: str = (
            "SELECT count(*) FROM inventario WHERE deleted IS NULL "
            r"AND ((collezione = false AND da_movimentare = true AND trasporto_in_autonomia = false AND peso !~ '^-?[0-9]+(\.[0-9]+)?$') "
            r"OR (collezione = false AND da_movimentare = true AND trasporto_in_autonomia = false AND dimensioni !~ '^[0-9]+x[0-9]+x[0-9]+$')) "
        )

        for field in fields:
            if field in BOOLEAN_FIELDS:
                if not request.args.get(field, ""):
                    continue
                value = request.args.get(field, "") == "true"
                query += f" AND {field} IS {value}"
                query_non_conforme += f" AND {field} IS {value}"
            else:
                value = request.args.get(field, "").strip()
                if value:
                    # add senza responsabile
                    if field == "responsabile_laboratorio":
                        if value == "SENZA":
                            query += f" AND ({field} = '' OR {field} IS NULL)"
                            query_non_conforme += (
                                f" AND ({field} = '' OR {field} IS NULL)"
                            )
                            continue
                        if "," in value:
                            subquery = ""
                            for resp in [x.strip() for x in value.split(",")]:
                                if subquery:
                                    subquery += " OR "
                                subquery += f"{field} ILIKE '%{resp}%' "
                            query += f" AND ({subquery})"
                            query_non_conforme += f" AND ({subquery})"
                            continue

                    if value == "SENZA":
                        # add senza Codice SIPI Torino
                        if field == "codice_sipi_torino":
                            query += f" AND ({field} = '' OR {field} IS NULL)"
                            query_non_conforme += (
                                f" AND ({field} = '' OR {field} IS NULL)"
                            )
                            continue
                        # add senza Codice SIPI Grugliasco
                        if field == "codice_sipi_grugliasco":
                            query += f" AND ({field} = '' OR {field} IS NULL)"
                            query_non_conforme += (
                                f" AND ({field} = '' OR {field} IS NULL)"
                            )
                            continue

                    # Per testo, ricerca con ILIKE e wildcard %
                    query += f" AND {field} ILIKE :{field}"
                    query_non_conforme += f" AND {field} ILIKE :{field}"
                    params[field] = f"%{value}%"

        query += " ORDER BY descrizione_bene ASC"

        # numero beni da fare movimentare con peso e/o dimensioni non conformi
        sql_non_conforme = text(query_non_conforme)
        with engine.connect() as conn:
            n_beni_non_conformi: int = conn.execute(sql_non_conforme, params).scalar()

        sql = text(query)
        with engine.connect() as conn:
            result = conn.execute(sql, params)
            records = result.fetchall()
            keys = result.keys()

    # Se viene richiesta esportazione Excel e ci sono risultati
    if request.args.get("export", "").lower() == "xlsx" and records:
        df = pd.DataFrame(records, columns=keys)
        df = df.drop(columns=["peso_non_conforme", "dimensioni_non_conforme"])
        df = df.replace({True: "SI", False: "NO"})
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
        boolean_fields=BOOLEAN_FIELDS,
        columns=keys,
        n_beni_non_conformi=n_beni_non_conformi,
    )


@app.route(APP_ROOT + "/search_resp")
@check_login
def search_resp():
    with engine.connect() as conn:
        result = conn.execute(
            text(
                (
                    "SELECT "
                    "   responsabile_laboratorio, "
                    "    COUNT(*) FILTER ( "
                    "        WHERE deleted IS NULL "
                    "          AND collezione = FALSE "
                    "          AND da_movimentare = TRUE "
                    "          AND trasporto_in_autonomia = FALSE "
                    "          AND ( "
                    r"              peso !~ '^-?[0-9]+(\.[0-9]+)?$' "
                    "              OR dimensioni !~ '^[0-9]+x[0-9]+x[0-9]+$' "
                    "          ) "
                    "    ) AS invalid_items_count "
                    "FROM inventario "
                    "WHERE responsabile_laboratorio <> '' "
                    "GROUP BY responsabile_laboratorio "
                    "ORDER BY responsabile_laboratorio "
                )
            )
        )
    return render_template(
        "search_responsabile.html",
        resp=result.fetchall(),
    )


# book2
@app.route(APP_ROOT + "/search_sipi_torino")
@check_login
def search_sipi_torino():
    with engine.connect() as conn:
        result = conn.execute(
            text(
                (
                    "SELECT codice_sipi_torino, "
                    "    COUNT(*) FILTER ( "
                    "        WHERE deleted IS NULL "
                    "          AND da_movimentare = TRUE "
                    "          AND trasporto_in_autonomia = FALSE "
                    "          AND ( "
                    r"              peso !~ '^-?[0-9]+(\.[0-9]+)?$' "
                    "              OR dimensioni !~ '^[0-9]+x[0-9]+x[0-9]+$' "
                    "          ) "
                    "    ) AS invalid_items_count "
                    "FROM inventario "
                    "WHERE codice_sipi_torino != '' "
                    "AND deleted IS NULL "
                    "GROUP BY codice_sipi_torino "
                    "ORDER BY codice_sipi_torino "
                )
            )
        )

    return render_template(
        "search_sipi_torino.html",
        sipi_list=result.fetchall(),
    )


@app.route(APP_ROOT + "/search_struttura")
@check_login
def search_struttura():
    return render_template(
        "search_struttura.html",
    )


@app.route(APP_ROOT + "/storico/<int:record_id>", methods=["GET"])
@check_login
def storico(record_id: int):
    with engine.connect() as conn:
        sql = text(
            "SELECT * FROM inventario_audit WHERE record_id = :id ORDER BY executed_at DESC"
        )
        audits = conn.execute(sql, {"id": record_id}).fetchall()

    return render_template("storico.html", audits=audits, record_id=record_id)


@app.route(APP_ROOT + "/storico_utente", methods=["GET"])
@app.route(APP_ROOT + "/storico_utente/", methods=["GET"])
@app.route(APP_ROOT + "/storico_utente/<email>", methods=["GET"])
@check_login
@check_admin
def storico_utente(email: str = ""):
    if not email:
        flash(f"Utente {email} non trovato", "danger")
        return render_template("storico_utente.html", audit_records=[], username=[])
    with engine.connect() as conn:
        sql = text(
            (
                "SELECT  "
                "    * "
                "FROM inventario_audit a "
                "INNER JOIN inventario i ON a.record_id = i.id "
                "WHERE a.executed_by = :email "
                "ORDER BY a.executed_at DESC "
            )
        )
        audits = conn.execute(sql, {"email": email}).fetchall()
        if not audits:
            flash(f"Utente {email} non trovato", "danger")

    return render_template("storico_utente.html", audit_records=audits, username=email)


# Visualizza record
@app.route(APP_ROOT + "/tutti")
@app.route(APP_ROOT + "/tutti/<mode>")
def tutti(mode: str = ""):
    """
    visualizza tutti i beni dell'inventario
    """
    with engine.connect() as conn:
        results = conn.execute(
            text(
                (
                    'SELECT id AS "ID", '
                    'quantita as "Quantità", '
                    'descrizione_bene AS "Descrizione bene", '
                    'responsabile_laboratorio AS "Responsabile Laboratorio / Ufficio", '
                    "da_movimentare, catena_del_freddo, trasporto_in_autonomia, microscopia, alta_specialistica, collezione, "
                    'codice_sipi_torino AS "Codice SIPI Torino", '
                    'codice_sipi_grugliasco AS "Codice SIPI Grugliasco", '
                    'destinazione AS "Destinazione", '
                    'note AS "Note", '
                    r"(collezione = false AND da_movimentare = true AND trasporto_in_autonomia = false AND peso !~ '^-?[0-9]+(\.[0-9]+)?$') AS peso_non_conforme, "  #
                    "(collezione = false AND da_movimentare = true AND trasporto_in_autonomia = false AND dimensioni !~ '^[0-9]+x[0-9]+x[0-9]+$') AS dimensioni_non_conforme "
                    "FROM inventario WHERE deleted IS NULL "
                    "ORDER BY responsabile_laboratorio, descrizione_bene, id "
                )
            )
        )
        records = results.fetchall()

        columns = results.keys()

    if mode == "spreadsheet":
        df = pd.DataFrame(records, columns=columns)
        df = df.drop(columns=["peso_non_conforme", "dimensioni_non_conforme"])
        df = df.replace({True: "SI", False: "NO"})
        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="Risultati")
        output.seek(0)

        return send_file(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="togru_tutti_beni.xlsx",
        )
    else:
        return render_template(
            "tutti_record.html",
            records=records,
            query_string="tutti",
            columns=columns,
        )


@app.route(APP_ROOT + "/version")
def version():
    """
    display version of service
    """

    return f"(c) Olivier Friard 2025<br>v. {__version__}"


@app.route(APP_ROOT + "/view/<int:record_id>")
@app.route(APP_ROOT + "/view/<int:record_id>/")
@app.route(APP_ROOT + "/view/<int:record_id>/<path:query_string>")
@check_login
def view(record_id: int, query_string: str = ""):
    """
    visualizza bene
    """
    with engine.connect() as conn:
        sql = text(
            (
                'SELECT id AS "ID", descrizione_bene AS "Descrizione bene", '
                "CASE WHEN collezione THEN 'SI' ELSE 'NO' END AS collezione,"
                """quantita AS "Quantità", """
                """responsabile_laboratorio AS "Responsabile del laboratorio/ufficio", """
                """num_inventario AS "Numero di inventario", num_inventario_ateneo, data_carico,"""
                """codice_sipi_torino AS "Codice SIPI Torino", codice_sipi_grugliasco AS "Codice SIPI Grugliasco", """
                "destinazione AS Destinazione,"
                "CASE WHEN microscopia THEN 'SI' ELSE 'NO' END AS microscopia,"
                """CASE WHEN catena_del_freddo THEN 'SI' ELSE 'NO' END AS "Rispettare la catena del freddo","""
                "CASE WHEN alta_specialistica THEN 'SI' ELSE 'NO' END AS alta_specialistica,                    "
                "CASE WHEN da_movimentare THEN 'SI' ELSE 'NO' END AS da_movimentare,"
                "CASE WHEN trasporto_in_autonomia THEN 'SI' ELSE 'NO' END AS trasporto_in_autonomia,"
                "CASE WHEN da_disinventariare THEN 'SI' ELSE 'NO' END AS da_disinventariare,"
                "CASE WHEN rosso_fase_alimentazione_privilegiata THEN 'SI' ELSE 'NO' END AS rosso_fase_alimentazione_privilegiata,"
                "CASE WHEN didattica THEN 'SI' ELSE 'NO' END AS didattica,"
                "valore_convenzionale,"
                "denominazione_fornitore, anno_fabbricazione, numero_seriale,"
                "categoria_inventoriale, catalogazione_materiale_strumentazione, peso, dimensioni,"
                "ditta_costruttrice_fornitrice, note, "
                r"(collezione = false AND da_movimentare = true AND trasporto_in_autonomia = false AND peso !~ '^-?[0-9]+(\.[0-9]+)?$') AS peso_non_conforme, "  #
                "(collezione = false AND da_movimentare = true AND trasporto_in_autonomia = false AND dimensioni !~ '^[0-9]+x[0-9]+x[0-9]+$') AS dimensioni_non_conforme "
                "FROM inventario "
                "WHERE id = :id"
            )
        )
        result = conn.execute(sql, {"id": record_id}).fetchone()
        if not result:
            return f"Bene con ID {record_id} non trovato", 404

        record_dict = dict(result._mapping)

        record_dict["note"] = Markup(record_dict["note"].replace("\r", "<br>"))

        # check for images
        img_list = [
            x.name for x in list(Path(app.config["UPLOAD_FOLDER"]).glob("*_*.*"))
        ]

    return render_template(
        "view.html", record=record_dict, query_string=query_string, img_list=img_list
    )


@app.route(APP_ROOT + "/view_qrcode/<int:record_id>")
def view_qrcode(record_id: int):
    with engine.connect() as conn:
        sql = text(("SELECT * FROM inventario WHERE id = :id "))
        result = conn.execute(sql, {"id": record_id}).fetchone()
        if not result:
            return f"Bene con ID {record_id} non trovato", 404

        record_dict = dict(result._mapping)

    return render_template("view.html", record=record_dict, query_string="")


if __name__ == "__main__":
    app.run(debug=True)
