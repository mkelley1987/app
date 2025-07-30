from flask import Flask, request, jsonify, send_from_directory, render_template, redirect, url_for, flash
from werkzeug.utils import secure_filename
from supabase_client import subir_pdf_a_supabase
from supabase_client import eliminar_pdf_supabase
from apscheduler.schedulers.background import BackgroundScheduler
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
UPLOAD_FOLDER = 'pdfs'
DB_NAME = 'base.db'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = 'mi_secreto'

# Asegurar que exista la carpeta de PDFs
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Rutas principales
@app.route('/')
def index():
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/admin/generar-qr')
def generar_qr():
    return render_template('generar_qr.html')

@app.route('/admin/subir')
def subir_pdf_form():
    return render_template('subir_pdf.html')

# API para validar
@app.route('/api/validar', methods=['GET'])
def validar():
    codigo = request.args.get('codigoVerificador')
    documento = request.args.get('documento')
    fecha = request.args.get('fechaVigencia')

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT archivo_pdf FROM documentos WHERE codigo_verificador=? AND documento=? AND fecha_vigencia=?", (codigo, documento, fecha))
    resultado = cur.fetchone()
    conn.close()

    if resultado:
        return jsonify({"status": "ok", "archivo": resultado[0]})
    else:
        return jsonify({"status": "error", "mensaje": "Datos inválidos"}), 404

# API para subir PDF
@app.route('/api/subir', methods=['POST'])
def subir_pdf():
    archivo = request.files.get('archivo')
    codigo = request.form.get('codigoVerificador')
    documento = request.form.get('documento')
    fecha = request.form.get('fechaVigencia')

    if not archivo or not codigo or not documento or not fecha:
        return jsonify({"status": "error", "mensaje": "Campos incompletos"}), 400

    filename = secure_filename(f"{codigo}.pdf")
    ruta_pdf = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT INTO documentos (codigo_verificador, documento, fecha_vigencia, archivo_pdf) VALUES (?, ?, ?, ?)",
                (codigo, documento, fecha, filename))
    conn.commit()
    conn.close()

    return jsonify({"status": "ok", "mensaje": "PDF guardado exitosamente"})

# API para descargar PDF
@app.route('/api/pdf/<filename>', methods=['GET'])
def descargar_pdf(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

# Ver registros en el dashboard
@app.route('/admin/registros')
def ver_registros():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT * FROM documentos")
    registros = cur.fetchall()
    conn.close()
    return render_template('registros.html', registros=registros)
    
@app.route('/admin/borrados')
def ver_borrados():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT archivo_pdf, fecha_borrado FROM borrados ORDER BY fecha_borrado DESC LIMIT 50")
    registros_borrados = cur.fetchall()
    conn.close()
    return render_template('borrados.html', registros=registros_borrados)


# Eliminar registro desde el dashboard
@app.route('/admin/eliminar/<int:registro_id>', methods=['POST'])
def eliminar_registro(registro_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT archivo_pdf FROM documentos WHERE id=?", (registro_id,))
    resultado = cur.fetchone()

    if resultado:
        archivo = resultado[0]
        eliminar_pdf_supabase(archivo)  # ← eliminar de Supabase
        cur.execute("DELETE FROM documentos WHERE id=?", (registro_id,))
        conn.commit()

    conn.close()
    return redirect(url_for('ver_registros'))

# Subida de PDF desde dashboard
@app.route('/admin/subir_pdf', methods=['POST'])
def subir_pdf_dashboard():
    archivo = request.files.get('archivo')
    id_valor = request.form.get('id')
    codigo = request.form.get('codigoVerificador')
    documento = request.form.get('documento')
    fecha = request.form.get('fechaVigencia')

    if not archivo or not codigo or not documento or not fecha:
        flash("Todos los campos son obligatorios")
        return redirect(url_for('subir_pdf_form'))

    # Generar nombre del archivo
    filename = secure_filename(f"{codigo}.pdf")

    # Leer contenido del archivo
    contenido = archivo.read()

    # Subir a Supabase
    subir_pdf_a_supabase(filename, contenido)

    # Guardar en base de datos local (sólo el nombre del archivo, no su contenido)
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT INTO documentos (id, codigo_verificador, documento, fecha_vigencia, archivo_pdf) VALUES (?, ?, ?, ?, ?)",
                (id_valor, codigo, documento, fecha, filename))
    conn.commit()
    conn.close()

    flash("PDF subido y registrado")
    return redirect(url_for('ver_registros'))

def eliminar_pdfs_expirados():
    print("Verificando PDFs expirados...")
    hoy = datetime.now().date()
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id, archivo_pdf, fecha_vigencia FROM documentos")
    registros = cur.fetchall()

    for id_registro, archivo, fecha_vigencia in registros:
        try:
            fecha = datetime.strptime(fecha_vigencia, "%Y-%m-%d").date()
            if fecha < hoy:
                print(f"Eliminando vencido: {archivo}")
                eliminar_pdf_supabase(archivo)

                # Registrar en tabla de borrados
                cur.execute("INSERT INTO borrados (archivo_pdf, fecha_borrado) VALUES (?, ?)", (archivo, ahora))

                # Eliminar de la tabla principal
                cur.execute("DELETE FROM documentos WHERE id=?", (id_registro,))
        except ValueError:
            print(f"Formato inválido para: {fecha_vigencia}")

    conn.commit()
    conn.close()


# Iniciar servidor
if __name__ == '__main__':
    scheduler = BackgroundScheduler()
    scheduler.add_job(eliminar_pdfs_expirados, 'cron', hour=12, minute=0)  # todos los días a las 12:00 PM
    scheduler.start()
    
    app.run(debug=True)