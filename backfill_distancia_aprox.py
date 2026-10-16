"""
backfill_distancia_aprox.py: agrega a registro_vrp_ocr.csv la distancia de cada
pasada VIIRS 375 leida en la serie de tiempo de Dist.png (seis columnas
Distancia_aprox_*, al final de la cabecera).

POR QUE
-------
El OCR lee la distancia solo de la estrella de Dist.png, que es la pasada de la
cabecera "Last Update". Cuando la imagen ya era de otra pasada la fila queda sin
distancia (ALERTA_SIN_GEOMETRIA_OCR) o, antes del 2026-06-13, con un 0 fijo. Pero
el panel "Last Month" es una serie de tiempo de unos 30 dias: la pasada sigue
dibujada en las imagenes que vienen despues, a la altura de su distancia. Este
script la lee ahi (dist_serie.py; estudio y verificador en VRP-chile,
experiments/_s151_distancia_ocr/).

Es un COMPLEMENTO, no una correccion: Distancia_km no se toca nunca. En las filas
sin distancia es el dato que falta; en las que tienen distancia del OCR es una
segunda lectura. Si la columna trae un marcador a la cifra del OCR y otro
lejano, la fila queda ambigua (dist_serie.con_cifra_ocr).

QUE HACE
--------
- Solo VIIRS 375 (el unico sensor con control). VIIRS 750 y MODIS: metodo
  "sin_control" y el resto vacio.
- Imagen: la Dist.png mas reciente de 1 a 25 dias despues de la pasada, del
  archivo de mirova-tif-archive (index_png.csv y cada PNG por
  raw.githubusercontent.com, archivo por archivo, NUNCA clone). Cache local en
  ~/.cache/mirova_dist/ (o MIROVA_DIST_CACHE), nunca en el repo. Se verifica el md5.
- Calado del eje de tiempo y eliminacion solo con la tabla latest.php
  (registro_vrp_consolidado.csv), nunca con distancias del OCR.
- Lee y escribe con el modulo csv: las columnas viejas quedan byte a byte
  iguales. Fin de linea LF. Si no hay nada que cambiar, no escribe.
- Idempotente. Con --dias N recalcula solo las filas de los ultimos N dias y las
  que nunca se calcularon (metodo vacio); las demas quedan como estan.

USO
---
    python backfill_distancia_aprox.py                    # todo el CSV
    python backfill_distancia_aprox.py --dias 26          # como en el cron
    python backfill_distancia_aprox.py --dry-run
"""
import argparse
import csv
import hashlib
import io
import json
import os
import sys
import time
import urllib.request

import pandas as pd

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import dist_serie as D

RAIZ = os.path.dirname(os.path.abspath(__file__))
CARPETA = os.path.join(RAIZ, 'monitoreo_satelital')
CSV_CONS = os.path.join(CARPETA, 'registro_vrp_consolidado.csv')
CSV_OCR = os.path.join(CARPETA, 'registro_vrp_ocr.csv')
RAW = 'https://raw.githubusercontent.com/MendozaVolcanic/mirova-tif-archive/main/'
CACHE = os.environ.get('MIROVA_DIST_CACHE', os.path.join(os.path.expanduser('~'), '.cache', 'mirova_dist'))

COLUMNAS = ['Distancia_aprox_km', 'Distancia_aprox_min_km', 'Distancia_aprox_max_km',
            'Distancia_aprox_metodo', 'Distancia_aprox_pareos', 'Distancia_aprox_imagen']
# scraper_ocr.COLUMNAS_DIST_APROX repite esta lista (el scraper no depende de este script); un test exige que sean iguales.
SENSOR_CONTROLADO = 'VIIRS375'


def _bajar(url, intentos=3):
    for i in range(intentos):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return r.read()
        except Exception:
            if i == intentos - 1:
                raise
            time.sleep(2 * (i + 1))


def indice_remoto():
    """index_png.csv de mirova-tif-archive, solo las Dist.png VIIRS 375."""
    d = pd.read_csv(io.BytesIO(_bajar(RAW + 'index_png.csv')))
    return d[(d.kind == 'Dist') & (d.sensor == SENSOR_CONTROLADO)]


def obtener_png(png_path, md5):
    """Ruta local de la PNG (cache por md5). Un archivo bajado cuyo md5 no calza con el indice no se usa."""
    os.makedirs(CACHE, exist_ok=True)
    ruta = os.path.join(CACHE, f'{md5}.png')
    if not os.path.exists(ruta):
        datos = _bajar(RAW + png_path)
        if hashlib.md5(datos).hexdigest() != md5:
            raise ValueError(f'md5 distinto al del indice: {png_path}')
        with open(ruta + '.tmp', 'wb') as f:
            f.write(datos)
        os.replace(ruta + '.tmp', ruta)
    return ruta


def _fmt(v):
    return '' if v is None else f'{float(v):.2f}'


def _vacia(metodo, pareos='', imagen=''):
    return {'Distancia_aprox_km': '', 'Distancia_aprox_min_km': '', 'Distancia_aprox_max_km': '',
            'Distancia_aprox_metodo': metodo, 'Distancia_aprox_pareos': str(pareos), 'Distancia_aprox_imagen': imagen}


class Lector:
    """Lee y cala cada imagen una sola vez (por md5) con la tabla de su volcan. El calado (lo caro, unos segundos por
    imagen) se guarda en cache_calados (JSON) con una clave que incluye el md5 y las pasadas de la tabla que caen en
    el panel de la imagen: si llega una pasada nueva a esa ventana, se recalcula; si no, se reusa."""

    def __init__(self, tabla, obtener, cache_calados=None):
        self.tabla, self.obtener, self.cache = tabla, obtener, {}
        self.ruta_calados, self.calados = cache_calados, {}
        if cache_calados and os.path.exists(cache_calados):
            try:
                with open(cache_calados, encoding='utf-8') as f:
                    self.calados = json.load(f)
            except (OSError, ValueError):
                self.calados = {}

    def _clave(self, md5, vol, lm):
        t = self.tabla[(self.tabla.vol == vol) & (self.tabla.t >= lm - pd.Timedelta(days=33))
                       & (self.tabla.t <= lm + pd.Timedelta(days=1))]
        firma = ';'.join(f'{a.isoformat()}|{b!r}|{c}' for a, b, c in zip(t.t, t.Distancia_km, t.Tipo_Registro))
        return md5 + ':' + hashlib.sha1(firma.encode()).hexdigest()

    def __call__(self, img, vol):
        if img.md5 not in self.cache:
            x = D.leer(self.obtener(img.png_path, img.md5))
            lm = pd.Timestamp(img.last_modified_utc)
            lm = lm.tz_convert(None) if lm.tzinfo else lm
            cb = None
            if x is not None:
                clave = self._clave(img.md5, vol, lm)
                if clave in self.calados:
                    g = self.calados[clave]
                    cb = None if g is None else {'pareos': g['pareos'], 'L': pd.Timestamp(g['L']), 'desfase': g['desfase']}
                else:
                    cb = D.calibrar(x, lm, self.tabla[self.tabla.vol == vol])
                    self.calados[clave] = None if cb is None else {
                        'pareos': int(cb['pareos']), 'L': cb['L'].isoformat(), 'desfase': float(cb['desfase'])}
            self.cache[img.md5] = (x, cb)
        return self.cache[img.md5]

    def guardar(self):
        if self.ruta_calados:
            os.makedirs(os.path.dirname(os.path.abspath(self.ruta_calados)), exist_ok=True)
            with open(self.ruta_calados + '.tmp', 'w', encoding='utf-8') as f:
                json.dump(self.calados, f, sort_keys=True)
            os.replace(self.ruta_calados + '.tmp', self.ruta_calados)


def calcular(fila, tabla, indice, lector):
    """Las seis columnas para una fila del CSV OCR."""
    if fila.get('Sensor') != SENSOR_CONTROLADO:
        return _vacia('sin_control')
    vol = D.id_mirova(fila['Volcan'])
    t = pd.Timestamp(fila['Fecha_Satelite_UTC'])
    img = D.imagen_para(t, indice[indice.volcano == vol])
    if img is None:
        return _vacia('pendiente')
    x, cb = lector(img, vol)
    pareos = 0 if cb is None else cb['pareos']
    if x is None or cb is None or pareos < D.PAREOS_MINIMOS:
        # sin geometria o sin marcadores cuenta como calado nulo: no hay lectura en la que confiar
        return _vacia('calado_debil', pareos, img.png_path)
    ms = D.marcadores_t(x, cb['L'], cb['desfase'])
    tv = tabla[tabla.vol == vol]
    r = D.eliminar(t, ms, D.otras_de(t, tv))
    if fila.get('Tipo_Registro') != 'ALERTA_SIN_GEOMETRIA_OCR':
        r = D.con_cifra_ocr(t, ms, r, fila.get('Distancia_km'))
    return {'Distancia_aprox_km': _fmt(r['km']) if r['clase'] == 'unico' else '',
            'Distancia_aprox_min_km': _fmt(r['kmin']), 'Distancia_aprox_max_km': _fmt(r['kmax']),
            'Distancia_aprox_metodo': r['clase'], 'Distancia_aprox_pareos': str(pareos),
            'Distancia_aprox_imagen': img.png_path}


def leer_csv(ruta):
    with open(ruta, newline='', encoding='utf-8') as f:
        lector = csv.DictReader(f)
        filas = list(lector)
        return list(lector.fieldnames or []), filas


def escribir_csv(ruta, cabecera, filas):
    tmp = ruta + '.tmp'
    with open(tmp, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=cabecera, lineterminator='\n', extrasaction='raise', restval='')
        w.writeheader()
        for fila in filas:
            w.writerow({c: ('' if fila.get(c) is None else fila.get(c)) for c in cabecera})
    os.replace(tmp, ruta)


def rellenar(ruta_ocr, ruta_cons, indice, obtener, dias=None, ahora=None, dry_run=False, cache_calados=None,
             limite_s=None):
    """Rellena el CSV OCR. Devuelve (conteo por metodo de las filas recalculadas, escribio)."""
    cabecera, filas = leer_csv(ruta_ocr)
    if None in cabecera or any(None in f for f in filas):
        raise SystemExit(f'ERROR: {ruta_ocr} tiene filas con mas campos que la cabecera')
    cabecera_nueva = cabecera + [c for c in COLUMNAS if c not in cabecera]
    tabla = D.tabla(pd.read_csv(ruta_cons), SENSOR_CONTROLADO)
    lector = Lector(tabla, obtener, cache_calados)
    desde = None
    if dias is not None:
        desde = (pd.Timestamp.now(tz='UTC').tz_convert(None) if ahora is None else pd.Timestamp(ahora)) \
            - pd.Timedelta(days=dias)
    conteo, cambia = {}, cabecera_nueva != cabecera
    t0 = time.monotonic()
    for f in filas:
        if limite_s is not None and time.monotonic() - t0 >= limite_s:
            conteo['sin_tiempo'] = conteo.get('sin_tiempo', 0) + 1     # queda para la proxima corrida
            continue
        if desde is not None and f.get('Distancia_aprox_metodo') and \
                pd.Timestamp(f['Fecha_Satelite_UTC']) < desde:
            continue
        nuevo = calcular(f, tabla, indice, lector)
        conteo[nuevo['Distancia_aprox_metodo']] = conteo.get(nuevo['Distancia_aprox_metodo'], 0) + 1
        if any(f.get(c, '') != v for c, v in nuevo.items()):
            f.update(nuevo)
            cambia = True
    if cambia and not dry_run:
        escribir_csv(ruta_ocr, cabecera_nueva, filas)
    if not dry_run:
        lector.guardar()
    return conteo, cambia and not dry_run


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument('--ocr', default=CSV_OCR)
    ap.add_argument('--consolidado', default=CSV_CONS)
    ap.add_argument('--dias', type=float, default=None,
                    help='solo filas de los ultimos N dias y las nunca calculadas (cron)')
    ap.add_argument('--max-minutos', type=float, default=None,
                    help='presupuesto: al agotarse escribe lo calculado; lo demas queda para la proxima corrida')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args(argv)
    t0 = time.time()
    conteo, escribio = rellenar(a.ocr, a.consolidado, indice_remoto(), obtener_png, dias=a.dias, dry_run=a.dry_run,
                               cache_calados=os.path.join(CACHE, 'calados.json'),
                               limite_s=None if a.max_minutos is None else a.max_minutos * 60)
    print(f'{os.path.relpath(a.ocr, RAIZ)}: filas recalculadas {sum(conteo.values())} {conteo}')
    print(f'   {"escrito" if escribio else "sin cambios" if not a.dry_run else "(dry-run)"} en {time.time() - t0:.0f} s')
    return 0


if __name__ == '__main__':
    sys.exit(main())
