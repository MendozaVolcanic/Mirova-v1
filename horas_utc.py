"""
horas_utc.py: horas de proceso del scraper en UTC, junto a las de Chile.

POR QUE
-------
Los dos registros (registro_vrp_consolidado.csv y registro_vrp_ocr.csv) guardan
tres horas en HORA DE CHILE y SIN desfase: Fecha_Captura_Chile,
Fecha_Proceso_GitHub y Ultima_Actualizacion. Las tres salen de
America/Santiago (scraper.py, scraper_ocr.py), no de un -3 o -4 fijo, y estan
bien convertidas (auditoria VRP Chile, docs/audit_s151/horas_mirova/INFORME.md).
Pero un texto local sin desfase no siempre se puede volver a UTC: cuando Chile
vuelve a UTC-4 en abril, la hora 23:00 a 23:59 ocurre dos veces, y esa hora
queda ambigua para siempre. Ademas el nombre Fecha_Proceso_GitHub hace pensar
que es el reloj de GitHub (UTC), y esta en hora de Chile.

Por eso se AGREGAN dos columnas en UTC, en formato ISO con Z
(2026-10-15T10:20:58Z), escritas desde el MISMO instante que la hora de Chile:
  - Fecha_Proceso_UTC        = Fecha_Proceso_GitHub en UTC
  - Ultima_Actualizacion_UTC = Ultima_Actualizacion en UTC
La hora del satelite ya esta en UTC (Fecha_Satelite_UTC) y no se duplica.
No se renombra ni se borra ninguna columna: los consumidores leen por nombre.

Para la historia, convertir_local_cl() pasa la hora de Chile a UTC con
zoneinfo('America/Santiago'). Si la hora es AMBIGUA (repetida en el cambio de
abril) o INEXISTENTE (saltada en el cambio de septiembre), devuelve vacio: no se
adivina cual de las dos fue.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytz

SANTIAGO = ZoneInfo('America/Santiago')
FORMATO_LOCAL = "%Y-%m-%d %H:%M:%S"
FORMATO_UTC = "%Y-%m-%dT%H:%M:%SZ"

COL_PROCESO_UTC = "Fecha_Proceso_UTC"
COL_ULTIMA_UTC = "Ultima_Actualizacion_UTC"
# columna UTC nueva -> columna local (hora de Chile) de la que se rellena
COLUMNAS_UTC = {
    COL_PROCESO_UTC: "Fecha_Proceso_GitHub",
    COL_ULTIMA_UTC: "Ultima_Actualizacion",
}


def ahora_cl_y_utc(instante=None):
    """Hora de Chile (texto de siempre, sin desfase) y hora UTC ISO con Z, las dos
    del MISMO instante. La hora de Chile se arma igual que antes (pytz), para que
    las columnas viejas no cambien de forma."""
    if instante is None:
        instante = datetime.now(pytz.utc)
    elif instante.tzinfo is None:
        instante = instante.replace(tzinfo=timezone.utc)
    cl = instante.astimezone(pytz.timezone('America/Santiago')).strftime(FORMATO_LOCAL)
    utc = instante.astimezone(timezone.utc).strftime(FORMATO_UTC)
    return cl, utc


def convertir_local_cl(texto):
    """Hora de Chile sin desfase -> (texto UTC ISO con Z, motivo).

    motivo: 'ok', 'vacia', 'ilegible', 'ambigua' (la hora ocurrio dos veces) o
    'inexistente' (la hora no existio). Fuera de 'ok' el texto UTC es ''."""
    if texto is None:
        return "", "vacia"
    s = str(texto).strip()
    if not s or s.lower() == "nan":
        return "", "vacia"
    try:
        local = datetime.strptime(s[:19], FORMATO_LOCAL)
    except ValueError:
        return "", "ilegible"
    a = local.replace(tzinfo=SANTIAGO, fold=0)
    b = local.replace(tzinfo=SANTIAGO, fold=1)
    if a.utcoffset() != b.utcoffset():
        # Las dos lecturas difieren: o la hora se repitio (ambigua) o no existio
        # (en el hueco, ida y vuelta no devuelve la misma hora local).
        vuelta = a.astimezone(timezone.utc).astimezone(SANTIAGO).replace(tzinfo=None)
        return "", ("ambigua" if vuelta == local else "inexistente")
    return a.astimezone(timezone.utc).strftime(FORMATO_UTC), "ok"


def rellenar_filas(cabecera, filas):
    """Agrega las columnas UTC al final de la cabecera (si faltan) y rellena las
    celdas UTC VACIAS desde su columna local. No toca ninguna otra celda ni una
    celda UTC que ya tenga valor (la escribio el scraper con el instante exacto).
    Idempotente: una segunda pasada no cambia nada.

    Devuelve (cabecera_nueva, conteo) con conteo[col_utc][motivo] = n filas que
    estaban vacias y se intentaron rellenar ('ok' = rellenadas)."""
    cabecera = list(cabecera)
    for col in COLUMNAS_UTC:
        if col not in cabecera:
            cabecera.append(col)
    conteo = {col: {} for col in COLUMNAS_UTC}
    for fila in filas:
        for col_utc, col_local in COLUMNAS_UTC.items():
            actual = fila.get(col_utc)
            if actual is not None and str(actual).strip() != "":
                continue
            valor, motivo = convertir_local_cl(fila.get(col_local))
            fila[col_utc] = valor
            conteo[col_utc][motivo] = conteo[col_utc].get(motivo, 0) + 1
    return cabecera, conteo
