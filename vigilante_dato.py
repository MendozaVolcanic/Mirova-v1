"""
vigilante_dato.py: falla en rojo si el consolidado dejo de actualizarse.

POR QUE (auditoria 2026-10-22, H-P1 y hallazgo 414): lo que habia vigilaba que el workflow
terminara, no que llegara dato: un scraper que no leia nada seguia en verde y la bitacora hacia
parecer vivo el repo. Ultima_Actualizacion_UTC la reescribe cada ciclo sano en las filas que
latest.php muestra, asi que su maximo se congela a los 5 min de una falla. Corre en un workflow
aparte (vigilante_dato.yml), fuera del pipeline que vigila: si el scraper no corre, esto si.

Umbral: 60 min. Medido en 60 dias de bitacora (2026-08-22 a 2026-10-22): 3 de 17.397 silencios
entre ciclos completos pasan de 60 min y ninguno de 90. Un archivo sin la columna o sin horas
legibles tambien es rojo: un vigilante ciego no puede dar verde.

Uso: python vigilante_dato.py [csv] [--umbral-min 60]
"""
import argparse
import csv
import io
import sys
from datetime import datetime, timezone

CSV_CONS = "monitoreo_satelital/registro_vrp_consolidado.csv"
COLUMNA = "Ultima_Actualizacion_UTC"


def evaluar(texto, ahora, umbral_min=60):
    """Devuelve (codigo, mensaje): 0 si el dato mas nuevo tiene menos de umbral_min minutos."""
    lector = csv.DictReader(io.StringIO(texto or ""))
    if not lector.fieldnames or COLUMNA not in lector.fieldnames:
        return 1, f"el consolidado no tiene la columna {COLUMNA}"
    horas = []
    for fila in lector:
        v = (fila.get(COLUMNA) or "").strip()
        if v:
            try:
                horas.append(datetime.fromisoformat(v.replace("Z", "+00:00")))
            except ValueError:
                pass
    if not horas:
        return 1, f"ninguna hora legible en {COLUMNA}"
    edad = (ahora - max(horas)).total_seconds() / 60
    if edad > umbral_min:
        return 1, f"el consolidado no se actualiza hace {edad:.0f} min (umbral {umbral_min})"
    return 0, f"dato fresco: ultima actualizacion hace {edad:.0f} min"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Vigilante de dato del consolidado")
    ap.add_argument("csv", nargs="?", default=CSV_CONS)
    ap.add_argument("--umbral-min", type=float, default=60)
    a = ap.parse_args(argv)
    try:
        texto = open(a.csv, encoding="utf-8").read()
    except OSError as e:
        texto = ""
        print(f"no se pudo leer {a.csv}: {e}")
    codigo, msj = evaluar(texto, datetime.now(timezone.utc), a.umbral_min)
    print(f"::error title=Vigilante de dato::{msj}" if codigo else msj)
    return codigo


if __name__ == "__main__":
    sys.exit(main())
