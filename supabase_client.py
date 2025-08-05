# supabase_client.py
# -----------------------------------------------------------
# Utilidades para trabajar con Supabase
#   • Bucket  "docs"         → almacena PDFs
#   • Tabla   "documentos"   → guarda metadatos
# -----------------------------------------------------------

import os
from datetime import date
from supabase import create_client, Client

SUPABASE_URL  = os.getenv("SUPABASE_URL")
SUPABASE_KEY  = os.getenv("SUPABASE_KEY")          # service-role o anon (según tus políticas)
BUCKET_NAME   = os.getenv("SUPABASE_BUCKET", "docs")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ------------------------------------------------------------------
# SUBIR PDF + METADATOS
# ------------------------------------------------------------------
def subir_pdf_y_metadatos(
    filename: str,
    contenido: bytes,
    codigo_verificador: str,
    documento: str,
    fecha_vigencia: str | date,
):
    """
    1) Sube el PDF al bucket.
    2) Inserta la fila en la tabla documentos.
    """

    # 1) Subir archivo
    supabase.storage.from_(BUCKET_NAME).upload(
        path=filename,
        file=contenido,
        file_options={"content-type": "application/pdf"},
    )

    # 2) Insertar metadatos
    supabase.table("documentos").insert(
        {
            "codigo_verificador": codigo_verificador,
            "documento": documento,
            "fecha_vigencia": str(fecha_vigencia),
            "archivo_pdf": filename,
        }
    ).execute()


# ------------------------------------------------------------------
# LISTAR / FILTRAR REGISTROS
# ------------------------------------------------------------------
def obtener_registros_supabase(filtros: dict | None = None, limitar: int | None = None):
    """
    Devuelve una lista de tuplas:
    (id, codigo_verificador, documento, fecha_vigencia, archivo_pdf)

    • filtros: dict opcional {columna: valor} para .eq()
    • limitar: int opcional para .limit()
    """
    q = supabase.table("documentos").select("*").order("id")
    if filtros:
        for campo, valor in filtros.items():
            q = q.eq(campo, valor)
    if limitar:
        q = q.limit(limitar)

    data = q.execute().data or []
    return [
        (
            f["id"],
            f["codigo_verificador"],
            f["documento"],
            f["fecha_vigencia"],
            f["archivo_pdf"],
        )
        for f in data
    ]


# ------------------------------------------------------------------
# BORRAR REGISTRO + ARCHIVO
# ------------------------------------------------------------------
def borrar_registro_supabase(registro_id: int, archivo_pdf: str):
    """Elimina el PDF del bucket y la fila asociada de la tabla."""
    supabase.storage.from_(BUCKET_NAME).remove([archivo_pdf])
    supabase.table("documentos").delete().eq("id", registro_id).execute()


# ------------------------------------------------------------------
# LIMPIAR PDFs VENCIDOS
# ------------------------------------------------------------------
def eliminar_pdfs_expirados():
    """Borra todos los PDFs cuya fecha_vigencia sea anterior a hoy."""
    hoy = date.today().isoformat()
    vencidos = (
        supabase.table("documentos")
        .select("*")
        .lt("fecha_vigencia", hoy)
        .execute()
        .data
        or []
    )
    for fila in vencidos:
        borrar_registro_supabase(fila["id"], fila["archivo_pdf"])


# ------------------------------------------------------------------
# URL FIRMADA TEMPORAL (para bucket privado)
# ------------------------------------------------------------------
def generar_url_firmada(archivo_pdf: str, segundos: int = 60) -> str:
    """
    Devuelve una URL firmada válida durante `segundos`.
    Si tu bucket es público podrías usar directamente la URL pública,
    pero la firma funciona para ambos casos.
    """
    res = supabase.storage.from_(BUCKET_NAME).create_signed_url(
        path=archivo_pdf, expires_in=segundos
    )
    return res["signedURL"]
