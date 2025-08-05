import os
from datetime import date
from supabase import create_client

SUPABASE_URL   = os.getenv("SUPABASE_URL")
SUPABASE_KEY   = os.getenv("SUPABASE_KEY")
BUCKET_NAME    = os.getenv("SUPABASE_BUCKET", "docs")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------- SUBIR ----------
def subir_pdf_y_metadatos(pdf_path: str,
                          codigo_verificador: str,
                          documento: str,
                          fecha_vigencia: date):
    # 1) Subir archivo al bucket
    obj_name = f"{codigo_verificador}.pdf"
    supabase.storage.from_(BUCKET_NAME).upload(obj_name, pdf_path)

    # 2) Insertar fila en la tabla
    supabase.table("documentos").insert({
        "codigo_verificador": codigo_verificador,
        "documento": documento,
        "fecha_vigencia": fecha_vigencia,
        "archivo_pdf": obj_name,
    }).execute()

# ---------- LISTAR ----------
def obtener_registros_supabase():
    res = supabase.table("documentos") \
                  .select("*") \
                  .order("id") \
                  .execute()
    filas = res.data or []
    return [(f["id"], f["codigo_verificador"], f["documento"],
             f["fecha_vigencia"], f["archivo_pdf"]) for f in filas]

# ---------- BORRAR ----------
def borrar_registro_supabase(registro_id: int, archivo_pdf: str):
    # 1) Borra el archivo del bucket
    supabase.storage.from_(BUCKET_NAME).remove([archivo_pdf])
    # 2) Borra la fila
    supabase.table("documentos").delete() \
            .eq("id", registro_id).execute()

# ---------- LIMPIAR VENCIDOS ----------
def eliminar_pdfs_expirados():
    hoy = date.today().isoformat()
    vencidos = supabase.table("documentos") \
                       .select("*") \
                       .lt("fecha_vigencia", hoy) \
                       .execute().data or []
    for fila in vencidos:
        borrar_registro_supabase(fila["id"], fila["archivo_pdf"])
