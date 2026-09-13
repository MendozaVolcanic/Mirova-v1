"""
backfill_geometria_v30.py: puebla las 4 columnas V30 en las filas historicas.

POR QUE
-------
V30 empezo a leer de Latest10NTI la geometria de observacion (angulo cenital y
azimut del satelite) y el nivel que declara el banner de MIROVA. Eso vale para
lo que se scrapee de aqui en adelante, pero el historico (824 filas desde enero)
quedo con esas columnas vacias. Las imagenes ya estan guardadas: no hace falta
volver a MIROVA, solo releer lo que ya tenemos en disco.

El angulo cenital importa porque condiciona cuanta atmosfera atraviesa la
observacion y el tamano efectivo del pixel: una anomalia de 2 MW vista a 65
grados no es fisicamente comparable con una vista a 10. Sin esa columna, la
serie historica de VRP mezcla observaciones que no son equivalentes entre si.

IDEMPOTENCIA (requisito duro: esto puede correrse dos veces)
------------------------------------------------------------
- NUNCA agrega ni elimina filas. Solo rellena celdas que estan VACIAS.
- Si un campo ya trae valor (del scraper V30 o de una corrida anterior) no se
  toca. La segunda corrida es un no-op salvo por imagenes nuevas.
- El OCR se cachea por imagen en disco, asi que reprocesar es barato.

CONTRATO DEL CSV (lo consume VRP Chile, que parte por split(",") sin comillas)
------------------------------------------------------------------------------
- Las columnas nuevas van AL FINAL y en el orden de COLUMNAS_OCR. No se
  renombra, reordena ni elimina ninguna existente.
- Ningun valor escrito lleva coma.
- Vacio se escribe como cadena vacia, nunca 'None' ni 'nan'.
- Todas las filas terminan con el mismo numero de campos.

USO
---
    python backfill_geometria_v30.py --dry-run
    python backfill_geometria_v30.py
    python backfill_geometria_v30.py --imagenes-extra RUTA [--sanear-comas]
"""
import argparse
import csv
import json
import os
import re
import sys

# El CSV y las notas llevan acentos; en consola Windows (cp1252) eso revienta.
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import cv2
import pytesseract

import ocr_utils
from scraper_ocr import COLUMNAS_OCR

# Columnas que este script puede poblar (las 4 de V30, todas al final).
CAMPOS_V30 = ['Zenith_Sat_deg', 'Azimut_Sat_deg', 'Nivel_Anomalia_MIROVA',
              'Confianza_Geometria']

RAIZ = os.path.dirname(os.path.abspath(__file__))
CSV_OCR = os.path.join(RAIZ, 'monitoreo_satelital', 'registro_vrp_ocr.csv')
CACHE = os.path.join(RAIZ, '_audit', 'cache_ocr_geometria_v30.json')

# En GitHub Actions tesseract viene en el PATH. En Windows normalmente no, y
# pytesseract falla con TesseractNotFoundError aunque este instalado.
_TESS_WIN = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
if os.name == 'nt' and os.path.exists(_TESS_WIN):
    pytesseract.pytesseract.tesseract_cmd = _TESS_WIN


def _limpiar(valor):
    """Un valor apto para este CSV: sin coma, sin salto, y '' en vez de None/nan."""
    if valor is None:
        return ''
    s = str(valor).strip()
    if s.lower() in ('none', 'nan', 'nat'):
        return ''
    # La coma rompe el split ingenuo del frontend de VRP Chile.
    return s.replace(',', ';').replace('\n', ' ').replace('\r', ' ')


def ruta_latest(ruta_foto):
    """'Ruta Foto' apunta al _VRP.png del evento; su hermana _Latest.png es la
    Latest10NTI de esa misma pasada (mismo directorio y mismo prefijo horario)."""
    if not ruta_foto:
        return None
    rel = ruta_foto.replace('\\', '/')
    rel = re.sub(r'^.*?imagenes_satelitales/', '', rel)
    if not rel.lower().endswith('.png'):
        return None
    return re.sub(r'_(VRP|logVRP|Dist|Latest)\.png$', '_Latest.png', rel)


def localizar(rel, raices):
    for r in raices:
        p = os.path.join(r, *rel.split('/'))
        if os.path.exists(p):
            return p
    return None


def clave_cache(path):
    """Volcan/fecha/archivo. El basename SOLO no sirve como clave: el mismo
    'HH-MM-SS_Volcan_Sensor_Latest.png' se repite en distintas carpetas de fecha
    (misma hora del dia, mismo volcan, mismo sensor) y el cache devolveria las
    celdas de OTRO dia."""
    partes = os.path.abspath(path).replace('\\', '/').split('/')
    return '/'.join(partes[-3:])


def eventos_de_imagen(path, cache):
    """OCR de una Latest10NTI -> {timestamp: {zen, azi, nivel, vrp}}. Cacheado."""
    clave = clave_cache(path)
    if clave in cache:
        return {int(k): v for k, v in cache[clave].items()}
    try:
        eventos = ocr_utils.extraer_eventos_latest10nti(path)
    except Exception as e:
        print('   ERROR OCR %s: %s' % (clave, e))
        eventos = []
    d = {}
    for ev in eventos:
        d[int(ev['timestamp'])] = {
            'zen': ev.get('zen'),
            'azi': ev.get('azi'),
            'nivel': ev.get('nivel_mirova', ''),
            'vrp': ev.get('vrp_mw'),
        }
    cache[clave] = d
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', default=CSV_OCR)
    ap.add_argument('--dry-run', action='store_true',
                    help='calcula y reporta, pero no escribe el CSV')
    ap.add_argument('--imagenes-extra', action='append', default=[],
                    help='raiz adicional donde buscar las Latest (repetible)')
    ap.add_argument('--sanear-comas', action='store_true',
                    help='ademas, reemplaza , por ; en Nota_Validacion (filas ya existentes)')
    args = ap.parse_args()

    raices = [os.path.join(RAIZ, 'monitoreo_satelital', 'imagenes_satelitales')]
    raices += [os.path.abspath(x) for x in args.imagenes_extra]

    with open(args.csv, encoding='utf-8', newline='') as f:
        lector = csv.DictReader(f)
        cabecera = list(lector.fieldnames)
        filas = list(lector)
    n_filas_inicial = len(filas)

    # Las columnas V30 se AGREGAN al final si aun no estan. Nunca se reordena
    # ni se renombra lo que ya existe: VRP Chile lee este CSV por posicion.
    salida = list(cabecera)
    for c in CAMPOS_V30:
        if c not in salida:
            salida.append(c)
    orden_esperado = [c for c in COLUMNAS_OCR if c in salida]
    if [c for c in salida if c in COLUMNAS_OCR] != orden_esperado:
        sys.exit('ABORTA: el orden de columnas no coincide con COLUMNAS_OCR')

    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    cache = json.load(open(CACHE, encoding='utf-8')) if os.path.exists(CACHE) else {}

    est = {'ya_poblada': 0, 'sin_ruta': 0, 'sin_imagen': 0, 'sin_match': 0,
           'poblada': 0, 'ocr_vacio': 0, 'vrp_discrepa': 0, 'sin_cambio': 0}
    llenados = {c: 0 for c in CAMPOS_V30}
    imgs_vistas = set()

    for i, fila in enumerate(filas, 1):
        for c in CAMPOS_V30:
            fila.setdefault(c, '')
            if fila[c] is None:
                fila[c] = ''

        # IDEMPOTENCIA: si ya hay geometria, esta fila no se toca jamas.
        if _limpiar(fila.get('Zenith_Sat_deg')) or _limpiar(fila.get('Azimut_Sat_deg')) \
                or _limpiar(fila.get('Confianza_Geometria')):
            est['ya_poblada'] += 1
            continue

        rel = ruta_latest(fila.get('Ruta Foto'))
        if not rel:
            est['sin_ruta'] += 1
            continue
        path = localizar(rel, raices)
        if not path:
            est['sin_imagen'] += 1
            continue

        if path not in imgs_vistas:
            imgs_vistas.add(path)
            if len(imgs_vistas) % 25 == 0:
                print('   ... %d imagenes OCR / fila %d de %d' % (len(imgs_vistas), i, len(filas)))
        celdas = eventos_de_imagen(path, cache)
        if not celdas:
            est['ocr_vacio'] += 1
            continue

        try:
            ts = int(float(fila['timestamp']))
        except (ValueError, TypeError, KeyError):
            est['sin_match'] += 1
            continue
        celda = celdas.get(ts)
        if celda is None:
            est['sin_match'] += 1
            continue

        # Control de integridad: la celda emparejada por timestamp deberia traer
        # el mismo VRP que la fila. Si no, el emparejamiento es sospechoso y se
        # prefiere no escribir geometria antes que escribirla en la fila errada.
        try:
            vrp_fila = float(fila.get('VRP_MW') or 0)
            if celda['vrp'] is not None and abs(float(celda['vrp']) - vrp_fila) > 0.051:
                est['vrp_discrepa'] += 1
                continue
        except (ValueError, TypeError):
            pass

        zen, azi = celda['zen'], celda['azi']
        nuevos = {
            'Zenith_Sat_deg': '' if zen is None else str(int(zen)),
            'Azimut_Sat_deg': '' if azi is None else str(int(azi)),
            'Nivel_Anomalia_MIROVA': celda.get('nivel') or '',
            'Confianza_Geometria': ('alta' if (zen is not None and azi is not None)
                                    else 'parcial' if (zen is not None or azi is not None)
                                    else ''),
        }
        if not any(nuevos.values()):
            est['sin_match'] += 1
            continue
        escritos = 0
        for c in CAMPOS_V30:
            v = _limpiar(nuevos[c])
            if v and not _limpiar(fila[c]):   # solo rellena vacios
                fila[c] = v
                llenados[c] += 1
                escritos += 1
        # Una fila cuyo unico campo legible era el nivel del banner ya lo tiene de
        # una corrida previa: se releyo, no se escribio nada. No es "poblada ahora".
        est['poblada' if escritos else 'sin_cambio'] += 1

    # Saneo global: garantiza el contrato del CSV en TODA celda que se escriba.
    saneadas = 0
    for fila in filas:
        for c in salida:
            v = fila.get(c)
            limpio = _limpiar(v)
            if c == 'Nota_Validacion' and not args.sanear_comas:
                # Se deja como esta salvo que se pida explicitamente; tocarla
                # modifica datos historicos y es una decision aparte.
                limpio = '' if v is None else str(v)
            if limpio != (v if v is not None else ''):
                saneadas += 1
            fila[c] = limpio

    assert len(filas) == n_filas_inicial, 'el backfill no puede cambiar el numero de filas'

    if not args.dry_run:
        json.dump(cache, open(CACHE, 'w', encoding='utf-8'))
        tmp = args.csv + '.tmp'
        with open(tmp, 'w', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=salida, extrasaction='ignore',
                               lineterminator='\n')
            w.writeheader()
            w.writerows(filas)
        os.replace(tmp, args.csv)

    print('\n' + '=' * 68)
    print('BACKFILL V30: geometria de observacion%s' % (' (DRY RUN)' if args.dry_run else ''))
    print('=' * 68)
    print('filas en el CSV        : %d (sin cambios: el backfill no agrega ni borra)' % len(filas))
    print('imagenes Latest leidas : %d' % len(imgs_vistas))
    print('\nque paso con cada fila:')
    print('  poblada ahora        : %4d' % est['poblada'])
    print('  ya venia poblada     : %4d  <- intacta (idempotencia)' % est['ya_poblada'])
    print('  releida, sin cambio  : %4d  <- idempotencia' % est['sin_cambio'])
    print('  sin imagen en disco  : %4d' % est['sin_imagen'])
    print('  sin match de celda   : %4d' % est['sin_match'])
    print('  OCR sin eventos      : %4d' % est['ocr_vacio'])
    print('  VRP discrepa (omitida): %3d' % est['vrp_discrepa'])
    print('  sin Ruta Foto        : %4d' % est['sin_ruta'])

    print('\nTOTAL de filas con cada campo poblado (estado final del CSV):')
    for c in CAMPOS_V30:
        n = sum(1 for f in filas if f.get(c))
        print('  %-24s %4d / %d  (%.1f%%)   [+%d en esta corrida]'
              % (c, n, len(filas), 100.0 * n / len(filas), llenados[c]))

    conf = {}
    for f in filas:
        conf[f.get('Confianza_Geometria') or '(vacio)'] = conf.get(f.get('Confianza_Geometria') or '(vacio)', 0) + 1
    print('\nConfianza_Geometria:', ', '.join('%s=%d' % kv for kv in sorted(conf.items())))
    niv = {}
    for f in filas:
        if f.get('Nivel_Anomalia_MIROVA'):
            niv[f['Nivel_Anomalia_MIROVA']] = niv.get(f['Nivel_Anomalia_MIROVA'], 0) + 1
    print('Nivel_Anomalia_MIROVA:', ', '.join('%s=%d' % kv for kv in sorted(niv.items())) or '(ninguno)')

    con_coma = sum(1 for f in filas for c in salida if ',' in (f.get(c) or ''))
    print('\ncontrato del CSV: columnas=%d, celdas con coma=%d, celdas saneadas=%d'
          % (len(salida), con_coma, saneadas))


if __name__ == '__main__':
    main()
