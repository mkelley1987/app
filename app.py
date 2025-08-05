from datetime import datetime, date
import os

from flask import (
    Flask,
    request,
    jsonify,
    render_template,
    redirect,
    url_for,
    flash,
)
from werkzeug.utils import secure_filename
from apscheduler.schedulers.background import BackgroundScheduler

# Funciones utilitarias centralizadas en supabase_client.py
from supabase_client import (
    subir_pdf_y_metadatos,
    obtener_registros_supabase,
    borrar_registro_supabase,
    eliminar_pdfs_expirados,
    generar_url_firmada,
    obtener_borrados_supabase,
)

# ------------------------------------------------------------------
# Configuración básica de Flask
# ------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "mi_secreto")

# ------------------------------------------------------------------
# Rutas públicas
# ------------------------------------------------------------------

@app.route("/")
def index():
    """Redirige al dashboard principal."""
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


# ------------------------------------------------------------------
# Generador de QR (solo interfaz; la lógica no cambia)
# ------------------------------------------------------------------
@app.route("/admin/generar-qr")
def generar_qr():
    return render_template("generar_qr.html")


# ------------------------------------------------------------------
# Formulario de subida manual (panel de admin)
# ------------------------------------------------------------------
@app.route("/admin/subir")
def subir_pdf_form():
    return render_template("subir_pdf.html")


# ------------------------------------------------------------------
# API – VALIDAR (consulta tabla documentos en Supabase)
# ------------------------------------------------------------------
@app.route("/api/validar", methods=["GET"])
def api_validar():
    codigo = request.args.get("codigoVerificador")
    documento = request.args.get("documento")
    fecha = request.args.get("fechaVigencia")

    if not all([codigo, documento, fecha]):
        return jsonify({"status": "error", "mensaje": "Parámetros faltantes"}), 400

    # Traemos solo la coincidencia exacta
    filas = obtener_registros_supabase(
        filtros={
            "codigo_verificador": codigo,
            "documento": documento,
            "fecha_vigencia": fecha,
        },
        limitar=1,
    )

    if filas:
        archivo_pdf = filas[0][4]  # ruta dentro del bucket
        url_descarga = generar_url_firmada(archivo_pdf, segundos=60)
        return jsonify({"status": "ok", "url": url_descarga})

    return jsonify({"status": "error", "mensaje": "Datos inválidos"}), 404


# ------------------------------------------------------------------
# API – SUBIR DESDE APPS DE TERCEROS
# ------------------------------------------------------------------
@app.route("/api/subir", methods=["POST"])
def api_subir_pdf():
    archivo = request.files.get("archivo")
    codigo = request.form.get("codigoVerificador")
    documento = request.form.get("documento")
    fecha = request.form.get("fechaVigencia")

    if not all([archivo, codigo, documento, fecha]):
        return jsonify({"status": "error", "mensaje": "Campos incompletos"}), 400

    # Nombre seguro → XXXXX.pdf
    filename = secure_filename(f"{codigo}.pdf")
    contenido = archivo.read()

    subir_pdf_y_metadatos(filename, contenido, codigo, documento, fecha)
    return jsonify({"status": "ok", "mensaje": "PDF subido exitosamente"})
    
    
@app.route("/descargar/<path:archivo_pdf>")
def descargar_pdf(archivo_pdf: str):
    """
    Devuelve una redirección (HTTP 302) a la URL real del archivo.
    • Si tu bucket es privado → genera URL firmada temporal.
    • Si es público → construye la URL pública directamente.
    """
    # 1) Si el bucket es PRIVADO (recomendado):
    url = generar_url_firmada(archivo_pdf, segundos=60)

    # ----------------------------------------------------
    # Si tu bucket “docs” es PÚBLICO y prefieres no firmar,
    # comenta la línea anterior y descomenta estas dos:
    # base = os.getenv("SUPABASE_URL")
    # url  = f"{base}/storage/v1/object/public/{BUCKET_NAME}/{archivo_pdf}"
    # -----------------------------------------------------------

    return redirect(url)

# ------------------------------------------------------------------
# Dashboard – Ver registros (tabla documentos)
# ------------------------------------------------------------------
@app.route("/admin/registros")
def ver_registros():
    registros = obtener_registros_supabase()  # todos los registros
    return render_template("registros.html", registros=registros)


# ------------------------------------------------------------------
# Dashboard – Eliminar un registro concreto
# ------------------------------------------------------------------
@app.route("/admin/eliminar/<int:registro_id>/<path:archivo_pdf>", methods=["POST"])
def eliminar_registro(registro_id: int, archivo_pdf: str):
    borrar_registro_supabase(registro_id, archivo_pdf)
    flash("Registro eliminado correctamente")
    return redirect(url_for("ver_registros"))


# ------------------------------------------------------------------
# Dashboard – Subir PDF desde formulario interno
# ------------------------------------------------------------------
@app.route("/admin/subir_pdf", methods=["POST"])
def subir_pdf_dashboard():
    archivo = request.files.get("archivo")
    codigo = request.form.get("codigoVerificador")
    documento = request.form.get("documento")
    fecha = request.form.get("fechaVigencia")

    if not all([archivo, codigo, documento, fecha]):
        flash("Todos los campos son obligatorios")
        return redirect(url_for("subir_pdf_form"))

    filename = secure_filename(f"{codigo}.pdf")
    contenido = archivo.read()

    subir_pdf_y_metadatos(filename, contenido, codigo, documento, fecha)
    flash("PDF subido y registrado correctamente")
    return redirect(url_for("ver_registros"))

@app.route("/admin/borrados")
def ver_borrados():
    registros = obtener_borrados_supabase()  # 50 últimos por defecto
    return render_template("borrados.html", registros=registros)

# ------------------------------------------------------------------
# Tareas programadas – limpieza de PDFs vencidos
# ------------------------------------------------------------------

def programar_limpieza_diaria():
    scheduler = BackgroundScheduler()
    scheduler.add_job(eliminar_pdfs_expirados, trigger="cron", hour=3, minute=0)
    scheduler.start()


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------
if __name__ == "__main__":
    # 1) Limpieza inicial
    eliminar_pdfs_expirados()

    # 2) Limpieza diaria automática
    programar_limpieza_diaria()

    # 3) Arrancar Flask
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)