"""
backfill_horas_utc.py: rellena Fecha_Proceso_UTC y Ultima_Actualizacion_UTC en
la historia de registro_vrp_consolidado.csv y registro_vrp_ocr.csv (issue #23).

POR QUE
-------
Las horas de proceso se guardaban solo en hora de Chile y sin desfase (ver
horas_utc.py). Desde este cambio el scraper y el OCR escriben ademas la hora UTC
del mismo instante. Las filas viejas no la tienen: este script la calcula desde
la columna de Chile con zoneinfo('America/Santiago').

QUE HACE
--------
- Agrega las dos columnas al FINAL de la cabecera si faltan.
- Rellena solo celdas UTC VACIAS. No toca ninguna otra celda, ni una celda UTC
  que ya tenga valor (la escribio el scraper con el instante exacto).
- Hora ambigua (la hora 23:00 a 23:59 del 2026-04-04 ocurrio dos veces, al
  volver Chile a UTC-4) o inexistente (la que se salta en septiembre): queda
  VACIA. No se adivina. Se informan las filas por pantalla.
- Hora de Chile vacia (las 104 filas de enero de 2026 anteriores a la columna
  Fecha_Proceso_GitHub): la UTC queda vacia.
- Lee y escribe con el modulo csv, sin pasar por pandas, para que el resto de
  las celdas quede byte a byte igual. Fin de linea LF, como lo escribe pandas
  en el runner Linux. Si no hay nada que cambiar, no escribe.
- Idempotente: la segunda corrida no cambia nada.

Corre dentro de los workflows que ya escriben cada CSV (main.yml para el
consolidado, ocr_workflow.yml para el OCR), y no como commit de datos en el PR,
porque los dos CSV se reescriben cada 5 y cada 30 minutos y un commit de datos
chocaria con los scrapers (mismo criterio que el PR #22).

USO
---
    python backfill_horas_utc.py --dry-run
    python backfill_horas_utc.py                         # los dos CSV
    python backfill_horas_utc.py monitoreo_satelital/registro_vrp_ocr.csv
"""
import argparse
import csv
import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from horas_utc import COLUMNAS_UTC, convertir_local_cl, rellenar_filas

RAIZ = os.path.dirname(os.path.abspath(__file__))
CARPETA = os.path.join(RAIZ, 'monitoreo_satelital')
CSV_CONS = os.path.join(CARPETA, 'registro_vrp_consolidado.csv')
CSV_OCR = os.path.join(CARPETA, 'registro_vrp_ocr.csv')


def leer(ruta):
    with open(ruta, newline='', encoding='utf-8') as f:
        lector = csv.DictReader(f)
        filas = list(lector)
        return list(lector.fieldnames or []), filas


def escribir(ruta, cabecera, filas):
    tmp = ruta + '.tmp'
    with open(tmp, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=cabecera, lineterminator='\n',
                           extrasaction='raise', restval='')
        w.writeheader()
        for fila in filas:
            w.writerow({c: ('' if fila.get(c) is None else fila.get(c)) for c in cabecera})
    os.replace(tmp, ruta)


def rellenar_archivo(ruta, dry_run=False):
    """Rellena un CSV. Devuelve (conteo, filas_no_convertibles, escribio)."""
    if not os.path.exists(ruta):
        print(f"(no existe {ruta}: nada que rellenar)")
        return {}, [], False
    cabecera, filas = leer(ruta)
    if None in cabecera or any(None in f for f in filas):
        # Una fila con mas campos que la cabecera: el archivo esta roto (por
        # ejemplo un rebase que mezclo dos cabeceras). Mejor fallar fuerte que
        # escribir encima.
        raise SystemExit(f"ERROR: {ruta} tiene filas con mas campos que la cabecera")
    cabecera_nueva, conteo = rellenar_filas(cabecera, filas)
    no_convertibles = []
    for f in filas:
        for col_utc, col_local in COLUMNAS_UTC.items():
            if f.get(col_utc):
                continue
            _, motivo = convertir_local_cl(f.get(col_local))
            if motivo in ('ambigua', 'inexistente', 'ilegible'):
                no_convertibles.append((col_local, f.get(col_local), motivo,
                                        f.get('Volcan'), f.get('Sensor'),
                                        f.get('Fecha_Satelite_UTC')))
    rellenadas = sum(c.get('ok', 0) for c in conteo.values())
    cambia = cabecera_nueva != cabecera or rellenadas > 0
    if cambia and not dry_run:
        escribir(ruta, cabecera_nueva, filas)
    return conteo, no_convertibles, cambia and not dry_run


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument('rutas', nargs='*', help='CSV a rellenar (por defecto los dos registros)')
    ap.add_argument('--dry-run', action='store_true', help='solo informar, no escribir')
    a = ap.parse_args(argv)
    for ruta in (a.rutas or [CSV_CONS, CSV_OCR]):
        conteo, no_conv, escribio = rellenar_archivo(ruta, dry_run=a.dry_run)
        print(f"{os.path.relpath(ruta, RAIZ)}:")
        for col, c in conteo.items():
            print(f"   {col}: rellenadas {c.get('ok', 0)} | vacias por ambigua {c.get('ambigua', 0)}"
                  f" | inexistente {c.get('inexistente', 0)} | ilegible {c.get('ilegible', 0)}"
                  f" | sin hora de Chile {c.get('vacia', 0)}")
        # El detalle de las que quedan vacias solo cuando se escribe o en dry-run:
        # el workflow corre cada 5 minutos y la lista no cambia de una vez a otra.
        if escribio or a.dry_run:
            for col_local, valor, motivo, volcan, sensor, fsat in no_conv:
                print(f"   - {motivo}: {col_local}={valor} | {volcan} | {sensor} | pasada {fsat} UTC")
        print(f"   {'escrito' if escribio else 'sin cambios' if not a.dry_run else '(dry-run)'}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
