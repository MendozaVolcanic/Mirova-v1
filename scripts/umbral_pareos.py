# -*- coding: utf-8 -*-
"""Umbral de calado debil (dist_serie.PAREOS_MINIMOS), medido contra el control del lector portado.

Por que: el eje de tiempo de Dist.png no trae fechas y se cala contando cuantos marcadores calzan con pasadas de la
tabla ("pareos"). Con pocos pareos el calado puede quedar corrido y la columna de la noche ser la de otra noche. El
umbral no se elige: es el menor numero de pareos desde el que el error de la decision cerca o lejos no supera el
error global del control.

Lee la salida de scripts/control_distancia_aprox.py (una fila por pasada de control: pareos, desfase, dec, real) y
para cada umbral de 4 a 20 imprime el error de la decision y la fraccion decidida de las pasadas que lo cumplen, y el
error de las que quedarian fuera. Ademas compara los calados en el borde de la busqueda (desfase >= +0,76 d) con el
resto.

Uso: python scripts/umbral_pareos.py tests/fixtures/dist/control_port.csv"""
import sys

import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ERROR_GLOBAL_ESTUDIO = 0.045      # INFORME §4 y VERIFICADOR §1 (56 de 1.246)
BORDE = 0.76                      # la busqueda del desfase llega a +0,78 d: +0,76 y +0,78 son el borde


def tasas(x):
    d = x[x.dec.isin(["cerca", "lejos"])]
    mal = int((d.dec != d.real).sum())
    return len(x), len(d), mal, (mal / len(d) if len(d) else float("nan"))


def umbral(X, techo):
    """Menor umbral u (4 a 20) cuyo error entre las pasadas con pareos >= u no supera techo. None si ninguno."""
    for u in range(4, 21):
        n, nd, mal, e = tasas(X[X.pareos >= u])
        if nd and e <= techo:
            return u
    return None


def main(ruta):
    X = pd.read_csv(ruta)
    n, nd, mal, e = tasas(X)
    print(f"control: {n} pasadas, decididas {nd} ({100 * nd / n:.1f} %), erradas {mal} ({100 * e:.1f} %)")
    print(f"pareos por imagen usada: min {X.pareos.min()}, p5 {X.pareos.quantile(.05):.0f}, mediana {X.pareos.median():.0f}")
    print("\numbral | pasadas >= u | decididas (frac de todas) | erradas (error) || quedan fuera: decididas, erradas")
    for u in range(4, 21):
        a, b = X[X.pareos >= u], X[X.pareos < u]
        n1, nd1, m1, e1 = tasas(a)
        n2, nd2, m2, e2 = tasas(b)
        print(f"  {u:3d}  | {n1:5d} | {nd1:5d} ({100 * nd1 / n:5.1f} %) | {m1:3d} ({100 * e1:4.1f} %) || {nd2:4d}, {m2:3d}"
              + (f" ({100 * e2:.1f} %)" if nd2 else ""))
    techo = min(e, ERROR_GLOBAL_ESTUDIO)
    print(f"\ntecho de error: min(global de este control {100 * e:.1f} %, global del estudio 4,5 %) = {100 * techo:.1f} %")
    print(f"PAREOS_MINIMOS = {umbral(X, techo)}")
    b = X[X.desfase >= BORDE]
    r = X[X.desfase < BORDE]
    for nombre, x in (("borde (desfase >= +0,76 d)", b), ("resto", r)):
        n_, nd_, m_, e_ = tasas(x)
        print(f"{nombre}: imagenes {x.imagen.nunique()}, pasadas {n_}, decididas {nd_}, erradas {m_}"
              + (f" ({100 * e_:.1f} %)" if nd_ else "") + f"; pareos mediana {x.pareos.median() if len(x) else float('nan')}")


if __name__ == "__main__":
    main(sys.argv[1])
