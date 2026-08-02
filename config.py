"""
config.py — parámetros que cambian según DÓNDE corre el sistema.

Motivo: el mismo código tiene que servir en dos entornos —GitHub Actions +
Pages (el actual) y una instalación local en OVDAS— sin mantener dos copias.
Dos copias divergen: ya nos pasó con los 11 volcanes definidos en 6 lugares
distintos (ver el encabezado de volcanes.py). Acá se centraliza lo único que
realmente difiere; la lógica de scraping, OCR y gráficos es idéntica.

Uso:
    # GitHub (por defecto, no hay que hacer nada)
    python visualizador.py

    # Local / OVDAS
    set MIROVA_ENTORNO=local      (Windows)
    export MIROVA_ENTORNO=local   (Linux)
    python visualizador.py

El valor por defecto ('github') reproduce EXACTAMENTE el comportamiento
anterior, así que activar este módulo no cambia nada en producción.
"""
import os

# 'github' = GitHub Actions + Pages (actual) | 'local' = instalación en OVDAS
ENTORNO = os.environ.get("MIROVA_ENTORNO", "github").strip().lower()
ES_LOCAL = ENTORNO == "local"

# ------------------------------------------------------------------
# Rutas (relativas a la raíz del proyecto: no usar rutas absolutas,
# es lo que hace que el sistema sea portable entre máquinas)
# ------------------------------------------------------------------
CARPETA_PRINCIPAL   = os.environ.get("MIROVA_CARPETA_DATOS", "monitoreo_satelital")
RUTA_IMAGENES_BASE  = os.path.join(CARPETA_PRINCIPAL, "imagenes_satelitales")
CARPETA_LINEAL      = os.path.join(CARPETA_PRINCIPAL, "v_html")
CARPETA_LOG         = os.path.join(CARPETA_PRINCIPAL, "v_html_log")

# ------------------------------------------------------------------
# Cómo se embebe Plotly en cada gráfico
#
#   'cdn'       -> <script src="https://cdn.plot.ly/...">  (73 KB por gráfico,
#                  REQUIERE INTERNET en la máquina que MIRA el dashboard)
#   'directory' -> usa un plotly.min.js (~4,5 MB) compartido, guardado junto a
#                  los HTML. Funciona sin internet y no duplica la librería.
#   True        -> inserta los 4,5 MB DENTRO de cada gráfico (x22). Evitar.
#
# En local se usa 'directory' para que los gráficos se vean aunque la máquina
# no tenga salida a internet (o la tenga filtrada). En GitHub se deja 'cdn'
# porque ahí sí hay internet y así el repositorio no engorda en cada ciclo.
# ------------------------------------------------------------------
PLOTLY_JS = os.environ.get("MIROVA_PLOTLY_JS") or ("directory" if ES_LOCAL else "cdn")

# ------------------------------------------------------------------
# Base del link "ver carpeta" de cada punto del gráfico.
#
# En GitHub apunta al repositorio (así se ve la evidencia sin descargar nada).
# En local apunta a la carpeta servida por el servidor web: tiene que ser una
# ruta RELATIVA porque el dashboard se sirve desde la raíz del proyecto.
# ------------------------------------------------------------------
_URL_GITHUB = ("https://github.com/MendozaVolcanic/Mirova-v1/tree/main/"
               "monitoreo_satelital/imagenes_satelitales")
_URL_LOCAL  = "monitoreo_satelital/imagenes_satelitales"

URL_BASE_IMAGENES = os.environ.get("MIROVA_URL_IMAGENES") or (_URL_LOCAL if ES_LOCAL else _URL_GITHUB)


def resumen():
    """Línea de diagnóstico para los logs: deja asentado con qué config corrió."""
    return (f"entorno={ENTORNO} plotly={PLOTLY_JS} "
            f"datos={CARPETA_PRINCIPAL} imagenes={URL_BASE_IMAGENES}")


if __name__ == "__main__":
    print(resumen())
