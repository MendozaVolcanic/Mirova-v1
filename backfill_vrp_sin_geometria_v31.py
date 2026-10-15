"""
backfill_vrp_sin_geometria_v31.py: pasa a registro_vrp_ocr.csv las pasadas que
V31 dejo solo en ocr_rechazos_cabecera.csv porque Dist.png era POSTERIOR.

POR QUE
-------
MIROVA mantiene una sola imagen Dist.png por volcan y sensor, y la reemplaza en
cada pasada. Cuando el OCR corre despues de que MIROVA ya proceso otra pasada,
la estrella de Dist.png (distancia y clase) es de esa otra pasada. V31 no copio
esa geometria, y eso sigue siendo correcto. Pero tambien botaba el VRP, que si
es de la pasada vieja: sale de su propia celda en Latest10NTI. Una pasada que la
tabla latest.php se salta y que no es la ultima nunca tendra su propia Dist.png,
asi que se perdia para siempre. Caso: Nevados de Chillan 2026-10-15 05:00 UTC,
22,13 MW en VIIRS375 y 14 MW en VIIRS750, en erupcion.

V31.1 (scraper_ocr.fila_vrp_sin_geometria) guarda esas pasadas desde ahora.
Este script hace lo mismo con las que ya estan en el log de rechazos.

QUE HACE
--------
- Lee monitoreo_satelital/ocr_rechazos_cabecera.csv. Toma solo las filas cuya
  Dist.png es POSTERIOR a la pasada (fuera de la tolerancia de V31) y cuyo VRP
  de celda es mayor que 0. Las demas causas de rechazo no se tocan.
- Arma cada fila con la MISMA funcion que usa el scraper (fila_vrp_sin_geometria):
  ALERTA_TERMICA_OCR, Distancia_km vacia, clase SIN_GEOMETRIA, metodo
  vrp_sin_geometria_propia.
- No duplica: si la pasada ya existe (misma clave volcan, sensor y minuto UTC)
  en registro_vrp_ocr.csv, o en registro_vrp_consolidado.csv (la tabla manda),
  no se agrega.
- Agrega al FINAL del CSV sin reescribir las filas existentes (el scraper lo
  reordena en su proxima corrida). El log de rechazos no se modifica.
- Idempotente: la segunda corrida agrega 0.

USO
---
    python backfill_vrp_sin_geometria_v31.py --dry-run
    python backfill_vrp_sin_geometria_v31.py
"""
import argparse
import csv
import os
import sys
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import pytz

from scraper_ocr import fila_vrp_sin_geometria

RAIZ = os.path.dirname(os.path.abspath(__file__))
CARPETA = os.path.join(RAIZ, 'monitoreo_satelital')
CSV_RECHAZOS = os.path.join(CARPETA, 'ocr_rechazos_cabecera.csv')
CSV_OCR = os.path.join(CARPETA, 'registro_vrp_ocr.csv')
CSV_CONS = os.path.join(CARPETA, 'registro_vrp_consolidado.csv')

UTC = pytz.utc
SANTIAGO = pytz.timezone('America/Santiago')


def _utc(s):
    s = (s or '').strip()
    if not s:
        return None
    try:
        return UTC.localize(datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S"))
    except ValueError:
        return None


def clave(volcan, sensor, fecha_utc):
    """Una pasada: volcan, sensor y hora al minuto (la tabla y el OCR difieren en segundos)."""
    return ((volcan or '').strip(), (sensor or '').strip(), (fecha_utc or '').strip()[:16])


def _claves_existentes(ruta):
    if not os.path.exists(ruta):
        return set()
    with open(ruta, newline='', encoding='utf-8') as f:
        return {clave(r.get('Volcan'), r.get('Sensor'), r.get('Fecha_Satelite_UTC'))
                for r in csv.DictReader(f)}


def filas_a_agregar(ruta_rechazos=CSV_RECHAZOS, ruta_ocr=CSV_OCR, ruta_cons=CSV_CONS):
    """Devuelve (filas nuevas, contador de motivos de descarte)."""
    ya = _claves_existentes(ruta_ocr) | _claves_existentes(ruta_cons)
    nuevas, descartes = [], {'no_posterior_o_vrp_no_positivo': 0, 'ya_existe': 0,
                             'repetida_en_log': 0}
    vistas = set()
    if not os.path.exists(ruta_rechazos):
        return nuevas, descartes
    with open(ruta_rechazos, newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            dt = _utc(r.get('fecha_pasada_utc'))
            cab = _utc(r.get('cabecera_dist_utc'))
            if dt is None:
                descartes['no_posterior_o_vrp_no_positivo'] += 1
                continue
            proc = _utc(r.get('fecha_proceso_utc'))
            ahora_cl = proc.astimezone(SANTIAGO).strftime("%Y-%m-%d %H:%M:%S") if proc else None
            fila = fila_vrp_sin_geometria(
                r.get('volcan'), r.get('sensor'), dt, r.get('vrp_mw_celda'), cab,
                zen=r.get('zen_deg'), azi=r.get('azi_deg'), ahora_cl=ahora_cl,
                origen='backfill')
            if fila is None:
                descartes['no_posterior_o_vrp_no_positivo'] += 1
                continue
            k = clave(fila['Volcan'], fila['Sensor'], fila['Fecha_Satelite_UTC'])
            if k in ya:
                descartes['ya_existe'] += 1
                continue
            if k in vistas:
                descartes['repetida_en_log'] += 1
                continue
            vistas.add(k)
            nuevas.append(fila)
    return nuevas, descartes


def agregar(filas, ruta_ocr=CSV_OCR):
    """Agrega al final sin tocar las filas existentes, con el encabezado del archivo."""
    if not filas:
        return
    with open(ruta_ocr, newline='', encoding='utf-8') as f:
        cabecera = next(csv.reader(f))
    # El archivo debe terminar en salto de linea antes de agregar.
    with open(ruta_ocr, 'rb') as f:
        f.seek(-1, os.SEEK_END)
        termina_bien = f.read(1) == b'\n'
    with open(ruta_ocr, 'a', newline='', encoding='utf-8') as f:
        if not termina_bien:
            f.write('\r\n')
        w = csv.DictWriter(f, fieldnames=cabecera, extrasaction='ignore')
        for fila in filas:
            w.writerow({c: ('' if fila.get(c) is None else fila.get(c, '')) for c in cabecera})


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument('--dry-run', action='store_true', help='solo informar, no escribir')
    a = ap.parse_args(argv)
    nuevas, descartes = filas_a_agregar()
    print(f"Filas a agregar a {os.path.relpath(CSV_OCR, RAIZ)}: {len(nuevas)}")
    for f in nuevas:
        print(f"   + {f['Fecha_Satelite_UTC']} | {f['Volcan']} | {f['Sensor']} | {f['VRP_MW']} MW")
    print(f"Descartadas: {descartes}")
    if a.dry_run:
        print("(dry-run: no se escribio nada)")
        return 0
    agregar(nuevas)
    print(f"Agregadas: {len(nuevas)}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
