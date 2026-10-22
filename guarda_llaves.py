"""
guarda_llaves.py: un CSV de datos no puede perder llaves ni traerlas repetidas al empujarse.

POR QUE (auditoria 2026-10-22, H-T1): la mezcla de texto del bucle de push dejo, en un solo
commit, cientos de filas perdidas y miles duplicadas, y el workflow termino en verde. Esta guarda
corre justo antes del push: compara el CSV que se va a empujar con el de la rama remota por la
llave (timestamp, Volcan, Sensor). Una llave que estaba y ya no esta, o una llave repetida, deja
la corrida en rojo y no se empuja nada. Filas nuevas y otro orden estan permitidos.

Uso:
  python guarda_llaves.py <csv> --ref origin/main      (la version anterior sale de git)
  python guarda_llaves.py <csv> --anterior <archivo>   (para pruebas)
Una ruta que no existe en la ref (archivo nuevo) solo se revisa por repetidas.
"""
import argparse
import csv
import io
import os
import subprocess
import sys
from collections import Counter


def _llave(fila):
    ts = (fila.get('timestamp') or '').strip()
    try:
        ts = str(int(float(ts)))
    except ValueError:
        pass
    return (ts, (fila.get('Volcan') or '').strip(), (fila.get('Sensor') or '').strip())


def _llaves(texto):
    return [_llave(f) for f in csv.DictReader(io.StringIO(texto))]


def revisar(texto_anterior, texto_nuevo):
    """Devuelve la lista de problemas (vacia si el CSV nuevo se puede empujar)."""
    nuevas = _llaves(texto_nuevo or '')
    problemas = []
    if not nuevas:
        return ['el CSV nuevo no tiene filas']
    repetidas = sum(c - 1 for c in Counter(nuevas).values() if c > 1)
    if repetidas:
        problemas.append(f'llaves repetidas {repetidas}')
    if texto_anterior is not None:
        perdidas = set(_llaves(texto_anterior)) - set(nuevas)
        if perdidas:
            ejemplo = sorted(perdidas)[:3]
            problemas.append(f'llaves perdidas {len(perdidas)} (ejemplo {ejemplo})')
    return problemas


def _desde_git(ref, ruta):
    rel = os.path.relpath(ruta).replace(os.sep, '/')
    r = subprocess.run(['git', 'show', f'{ref}:{rel}'], capture_output=True)
    if r.returncode != 0:
        return None  # la ruta no existe en la ref: archivo nuevo
    return r.stdout.decode('utf-8')


def main(argv=None):
    ap = argparse.ArgumentParser(description='Guarda de llaves antes del push')
    ap.add_argument('csv')
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--ref', help='ref de git con la version anterior (por ejemplo origin/main)')
    g.add_argument('--anterior', help='archivo con la version anterior')
    a = ap.parse_args(argv)
    anterior = (_desde_git(a.ref, a.csv) if a.ref
                else open(a.anterior, encoding='utf-8').read())
    nuevo = open(a.csv, encoding='utf-8').read() if os.path.exists(a.csv) else ''
    problemas = revisar(anterior, nuevo)
    if problemas:
        for p in problemas:
            print(f'::error title=Guarda de llaves ({a.csv})::{p}')
        return 1
    print(f'Guarda de llaves OK: {a.csv}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
