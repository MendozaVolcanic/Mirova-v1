"""
dist_aprox_columnas.py: las seis columnas Distancia_aprox_* de registro_vrp_ocr.csv
y como escribirlas sin que cambien de forma.

POR QUE: tres programas reescriben ese CSV. backfill_distancia_aprox.py lo hace con
el modulo csv; scraper_ocr.py y reconciliar_latest.py, con pandas. Pandas lee una
columna entera con huecos como float y la vuelve a escribir como 11.0, y la columna
de km sale sin el cero final. Para que la ida y vuelta no cambie nada, el backfill
escribe los km como los escribiria pandas (repr del float redondeado a 2) y los
escritores con pandas pasan por escribir_ocr, que deja los pareos como entero.
Modulo liviano (solo pandas): el scraper no depende del backfill.
"""
import pandas as pd

COLUMNAS = ['Distancia_aprox_km', 'Distancia_aprox_min_km', 'Distancia_aprox_max_km',
            'Distancia_aprox_metodo', 'Distancia_aprox_pareos', 'Distancia_aprox_imagen']
COLUMNAS_KM = COLUMNAS[:3]


def fmt_km(v):
    """Km como los escribe pandas: repr del float redondeado a 2 decimales ('' si no hay)."""
    return '' if v is None else repr(round(float(v), 2))


def normalizar(df):
    """Tipos estables para la ida y vuelta por pandas (solo si las columnas estan)."""
    df = df.copy()
    for c in COLUMNAS_KM:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').round(2)
    if 'Distancia_aprox_pareos' in df.columns:
        df['Distancia_aprox_pareos'] = pd.to_numeric(df['Distancia_aprox_pareos'], errors='coerce').round().astype('Int64')
    return df


def escribir_ocr(df, ruta):
    """Escribe registro_vrp_ocr.csv con pandas (LF) sin deformar las columnas Distancia_aprox_*."""
    normalizar(df).to_csv(ruta, index=False, lineterminator='\n')
