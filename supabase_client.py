from supabase import create_client

SUPABASE_URL = "https://bajjvhjkkbqaxhhvodox.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJhamp2aGpra2JxYXhoaHZvZG94Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTM4MzIxODUsImV4cCI6MjA2OTQwODE4NX0.DrzB6gfv7VCXN74ZVqHnmJOwHPWEvsvbv2z7-tgD9JY"  # (tu clave está bien)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def subir_pdf_a_supabase(nombre_archivo, contenido_binario):
    response = supabase.storage.from_('docs').upload(
        path=nombre_archivo,
        file=contenido_binario,
        file_options={"content-type": "application/pdf"}  # ← sin "upsert"
    )
    return response
    
def eliminar_pdf_supabase(nombre_archivo):
    response = supabase.storage.from_('docs').remove([nombre_archivo])
    return response
    
def obtener_registros_supabase():
    """
    Devuelve una lista de tuplas con el mismo orden que usa la plantilla:
    (id, codigo_verificador, documento, fecha_vigencia, archivo_pdf)
    """
    resp = supabase.table("documentos").select("*").order("id", desc=False).execute()
    filas = resp.data or []
    return [
        (
            f["id"],
            f["codigo_verificador"],
            f["documento"],
            f["fecha_vigencia"],
            f["archivo_pdf"],
        )
        for f in filas
    ]