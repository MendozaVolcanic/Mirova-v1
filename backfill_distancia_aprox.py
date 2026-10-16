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
import urllib.error
import urllib.request

import pandas as pd

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import dist_serie as D
from dist_aprox_columnas import COLUMNAS, fmt_km

RAIZ = os.path.dirname(os.path.abspath(__file__))
CARPETA = os.path.join(RAIZ, 'monitoreo_satelital')
CSV_CONS = os.path.join(CARPETA, 'registro_vrp_consolidado.csv')
CSV_OCR = os.path.join(CARPETA, 'registro_vrp_ocr.csv')
RAW = 'https://raw.githubusercontent.com/MendozaVolcanic/mirova-tif-archive/main/'
CACHE = os.environ.get('MIROVA_DIST_CACHE', os.path.join(os.path.expanduser('~'), '.cache', 'mirova_dist'))
SENSOR_CONTROLADO = 'VIIRS375'
DIAS_CACHE = 30          # una PNG que no se usa hace mas de 30 dias se borra de la cache


def _bajar(url, intentos=5):
    """Baja un archivo por raw. 429 y 5xx (y fallas de red) se reintentan con espera: Retry-After si viene (tope
    60 s), si no 2, 4, 8 ... s. Un 4xx distinto de 429 (404: no existe) no se reintenta."""
    for i in range(intentos):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if (e.code != 429 and e.code < 500) or i == intentos - 1:
                raise
            ra = e.headers.get('Retry-After') if e.headers else None
            time.sleep(min(60, int(ra)) if ra and str(ra).isdigit() else 2 ** (i + 1))
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if i == intentos - 1:
                raise
            time.sleep(2 ** (i + 1))


def indice_remoto():
    """index_png.csv de mirova-tif-archive, solo las Dist.png VIIRS 375."""
    d = pd.read_csv(io.BytesIO(_bajar(RAW + 'index_png.csv')))
    return d[(d.kind == 'Dist') & (d.sensor == SENSOR_CONTROLADO)]


def obtener_png(png_path, md5):
    """Ruta local de la PNG (cache por md5). Un archivo bajado cuyo md5 no calza con el indice no se usa. Una PNG de
    la cache se toca al usarla, para que la poda no la borre."""
    os.makedirs(CACHE, exist_ok=True)
    ruta = os.path.join(CACHE, f'{md5}.png')
    if os.path.exists(ruta):
        os.utime(ruta, None)
        return ruta
    datos = _bajar(RAW + png_path)
    if hashlib.md5(datos).hexdigest() != md5:
        raise ValueError(f'md5 distinto al del indice: {png_path}')
    with open(ruta + '.tmp', 'wb') as f:
        f.write(datos)
    os.replace(ruta + '.tmp', ruta)
    return ruta


def podar_cache(carpeta=CACHE, dias=DIAS_CACHE):
    """Borra las PNG de la cache sin uso hace mas de `dias` (por fecha de modificacion; obtener_png la toca al
    usarla) y los calados de esas imagenes. Devuelve cuantas PNG borro."""
    if not os.path.isdir(carpeta):
        return 0
    limite = time.time() - dias * 86400
    n = 0
    for nombre in os.listdir(carpeta):
        ruta = os.path.join(carpeta, nombre)
        if nombre.endswith('.png') and os.path.getmtime(ruta) < limite:
            os.remove(ruta)
            n += 1
    ruta_cal = os.path.join(carpeta, 'calados.json')
    if n and os.path.exists(ruta_cal):
        try:
            with open(ruta_cal, encoding='utf-8') as f:
                cal = json.load(f)
            vivos = {k: v for k, v in cal.items() if os.path.exists(os.path.join(carpeta, k.split(':')[0] + '.png'))}
            with open(ruta_cal + '.tmp', 'w', encoding='utf-8') as f:
                json.dump(vivos, f, sort_keys=True)
            os.replace(ruta_cal + '.tmp', ruta_cal)
        except (OSError, ValueError):
            pass
    return n


def _vacia(metodo, pareos='', imagen=''):
    return {'Distancia_aprox_km': '', 'Distancia_aprox_min_km': '', 'Distancia_aprox_max_km': '',
            'Distancia_aprox_metodo': metodo, 'Distancia_aprox_pareos': str(pareos), 'Distancia_aprox_imagen': imagen}


class Lector:
    """Lee y cala cada imagen una sola vez (por md5) con la tabla de su volcan. El calado (lo caro, unos segundos por
    imagen) se guarda en cache_calados (JSON) con una clave que incluye el md5 y las pasadas de la tabla que caen en
    el panel de la imagen: si llega una pasada nueva a esa ventana, se recalcula; si no, se reusa. Si una imagen no
    se puede bajar o leer, el error queda guardado para esa imagen en esta corrida (no se reintenta fila por fila)."""

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

    def _leer(self, img, vol):
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
        return x, cb

    def __call__(self, img, vol):
        if img.md5 not in self.cache:
            try:
                self.cache[img.md5] = self._leer(img, vol)
            except Exception as e:      # red, md5, PNG ilegible: error de ESA imagen, no de la corrida
                self.cache[img.md5] = e
        r = self.cache[img.md5]
        if isinstance(r, Exception):
            raise r
        return r

    def guardar(self):
        if self.ruta_calados:
            os.makedirs(os.path.dirname(os.path.abspath(self.ruta_calados)), exist_ok=True)
            with open(self.ruta_calados + '.tmp', 'w', encoding='utf-8') as f:
                json.dump(self.calados, f, sort_keys=True)
            os.replace(self.ruta_calados + '.tmp', self.ruta_calados)


def calcular(fila, tabla, indice, lector):
    """Las seis columnas para una fila del CSV OCR, y lo que hace falta para la revision entre filas (imagen, marcador
    elegido, intervalo de la columna). Puede lanzar excepcion: rellenar() la convierte en error_lectura."""
    if fila.get('Sensor') != SENSOR_CONTROLADO:
        return _vacia('sin_control'), None
    vol = D.id_mirova(fila['Volcan'])
    t = pd.Timestamp(fila['Fecha_Satelite_UTC'])
    img = D.imagen_para(t, indice[indice.volcano == vol])
    if img is None:
        return _vacia('pendiente'), None
    x, cb = lector(img, vol)
    pareos = 0 if cb is None else cb['pareos']
    if x is None or cb is None or pareos < D.PAREOS_MINIMOS:
        # sin geometria o sin marcadores cuenta como calado nulo: no hay lectura en la que confiar
        return _vacia('calado_debil', pareos, img.png_path), None
    ms = D.marcadores_t(x, cb['L'], cb['desfase'])
    r = D.eliminar(t, ms, D.otras_de(t, tabla[tabla.vol == vol]))
    # Distancia_km > 0 es una cifra medida (en el OCR el 0 es "no medida"; las sin geometria la traen vacia)
    r = D.con_cifra_ocr(t, ms, r, fila.get('Distancia_km'))
    cols = {'Distancia_aprox_km': fmt_km(r['km']) if r['clase'] == 'unico' else '',
            'Distancia_aprox_min_km': fmt_km(r['kmin']), 'Distancia_aprox_max_km': fmt_km(r['kmax']),
            'Distancia_aprox_metodo': r['clase'], 'Distancia_aprox_pareos': str(pareos),
            'Distancia_aprox_imagen': img.png_path}
    extra = None
    if r['clase'] == 'unico':
        extra = {'marcador': (img.md5,) + tuple(r['marcador']), 'col': (r['col_kmin'], r['col_kmax'])}
    return cols, extra


def marcadores_compartidos(resultados):
    """Si dos filas se quedan con el MISMO marcador de la misma imagen, ninguna puede ser unico: el marcador es de una
    sola, y la otra puede estar tapada o a mas de 25 km. Pasa con vecinas de la misma noche que la tabla no
    trae (las solo OCR no se descuentan). Las dos quedan ambiguo con el intervalo de su columna. Devuelve cuantas."""
    por_marcador = {}
    for f, cols, extra in resultados:
        if extra is not None and cols['Distancia_aprox_metodo'] == 'unico':
            por_marcador.setdefault(extra['marcador'], []).append((cols, extra))
    n = 0
    for grupo in por_marcador.values():
        if len(grupo) > 1:
            for cols, extra in grupo:
                cols.update({'Distancia_aprox_metodo': 'ambiguo', 'Distancia_aprox_km': '',
                             'Distancia_aprox_min_km': fmt_km(extra['col'][0]),
                             'Distancia_aprox_max_km': fmt_km(extra['col'][1])})
                n += 1
    return n


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


def _toca(f, desde):
    """En el cron: filas de la ventana, las nunca calculadas y las que quedaron con error (para que un error
    transitorio no quede pegado)."""
    if desde is None or f.get('Distancia_aprox_metodo') in (None, '', 'error_lectura'):
        return True
    try:
        return pd.Timestamp(f['Fecha_Satelite_UTC']) >= desde
    except (ValueError, TypeError):
        return True


def rellenar(ruta_ocr, ruta_cons, indice, obtener, dias=None, ahora=None, dry_run=False, cache_calados=None,
             limite_s=None):
    """Rellena el CSV OCR. Devuelve (conteo por metodo de las filas recalculadas, escribio). Un error en una fila
    (volcan desconocido, fecha ilegible, PNG que no baja o no se lee) queda como error_lectura en esa fila, y al final
    sale un ::warning:: de GitHub Actions con el conteo."""
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
    conteo, errores, resultados = {}, [], []
    t0 = time.monotonic()
    for f in filas:
        if not _toca(f, desde):
            continue
        if limite_s is not None and time.monotonic() - t0 >= limite_s:
            conteo['sin_tiempo'] = conteo.get('sin_tiempo', 0) + 1     # queda para la proxima corrida
            continue
        try:
            cols, extra = calcular(f, tabla, indice, lector)
        except Exception as e:
            cols, extra = _vacia('error_lectura'), None
            errores.append(f"{f.get('Volcan')} {f.get('Sensor')} {f.get('Fecha_Satelite_UTC')}: "
                           f"{type(e).__name__} {str(e)[:120]}")
        resultados.append((f, cols, extra))
    compartidos = marcadores_compartidos(resultados)
    cambia = cabecera_nueva != cabecera
    for f, cols, _ in resultados:
        conteo[cols['Distancia_aprox_metodo']] = conteo.get(cols['Distancia_aprox_metodo'], 0) + 1
        if any(f.get(c, '') != v for c, v in cols.items()):
            f.update(cols)
            cambia = True
    if cambia and not dry_run:
        escribir_csv(ruta_ocr, cabecera_nueva, filas)
    if not dry_run:
        lector.guardar()
    if compartidos:
        print(f'   {compartidos} filas con un marcador reclamado por otra fila de la misma imagen: ambiguo')
    if errores:
        print(f'::warning title=Distancia aproximada::{len(errores)} filas con error_lectura '
              f'(se reintentan en la proxima corrida). Primera: {errores[0]}')
        for e in errores[:20]:
            print(f'   error_lectura: {e}')
    return conteo, cambia and not dry_run


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument('--ocr', default=CSV_OCR)
    ap.add_argument('--consolidado', default=CSV_CONS)
    ap.add_argument('--dias', type=float, default=None,
                    help='solo filas de los ultimos N dias, las nunca calculadas y las con error (cron)')
    ap.add_argument('--max-minutos', type=float, default=None,
                    help='presupuesto: al agotarse escribe lo calculado; lo demas queda para la proxima corrida')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args(argv)
    t0 = time.time()
    podadas = podar_cache()
    conteo, escribio = rellenar(a.ocr, a.consolidado, indice_remoto(), obtener_png, dias=a.dias, dry_run=a.dry_run,
                               cache_calados=os.path.join(CACHE, 'calados.json'),
                               limite_s=None if a.max_minutos is None else a.max_minutos * 60)
    print(f'{os.path.relpath(a.ocr, RAIZ)}: filas recalculadas {sum(conteo.values())} {conteo}; PNG podadas {podadas}')
    if conteo.get('sin_tiempo'):
        print(f"::notice title=Distancia aproximada::{conteo['sin_tiempo']} filas quedaron para la proxima corrida "
              f"(presupuesto de {a.max_minutos} min)")
    print(f'   {"escrito" if escribio else "sin cambios" if not a.dry_run else "(dry-run)"} en {time.time() - t0:.0f} s')
    return 0


if __name__ == '__main__':
    sys.exit(main())
