# -*- coding: utf-8 -*-
"""Umbral de calado debil (dist_serie.PAREOS_MINIMOS), medido contra el control del lector portado.

Por que: el eje de tiempo de Dist.png no trae fechas y se cala contando cuantos marcadores calzan con pasadas de la
tabla ("pareos"). Con pocos pareos el calado puede quedar corrido y la columna de la noche ser la de otra noche.

La regla (no se elige el numero): el umbral es el menor u cuyo error no supera el error global del control, donde
"el error de u" es el de los calados que ese umbral admite en el margen, los de u a u+3 pareos (banda de 4, la
misma de las tablas del verificador: "4 a 7", "8 a 11"). La version anterior media el error ACUMULADO de todo lo
que pasa el umbral, que esta dominado por los calados fuertes y es casi igual al global por construccion: aceptaba
siempre el piso de la busqueda (verificador del PR #25, §3). La busqueda parte en 1, no en 4.

Entrada: una o mas salidas de scripts/control_distancia_aprox.py (columnas vol, t, md5, pareos, desfase, dec, real).
Una misma pasada leida en la misma imagen en dos controles cuenta una vez.

Uso: python scripts/umbral_pareos.py tests/fixtures/dist/control_juntas.csv [otro_control.csv ...]"""
import sys

import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ANCHO = 4                         # banda de pareos que admite el umbral en el margen
BORDE = 0.76                      # la busqueda del desfase llega a +0,78 d: +0,76 y +0,78 son el borde


def juntar(rutas):
    X = pd.concat([pd.read_csv(r) for r in rutas], ignore_index=True)
    if "md5" in X.columns:
        X = X.drop_duplicates(["vol", "t", "md5"])
    return X


def tasas(x):
    d = x[x.dec.isin(["cerca", "lejos"])]
    mal = int((d.dec != d.real).sum())
    return len(x), len(d), mal, (mal / len(d) if len(d) else float("nan"))


def banda(X, u, ancho=ANCHO):
    return X[(X.pareos >= u) & (X.pareos < u + ancho)]


def umbral(X, ancho=ANCHO, hasta=20):
    """Menor u (1 a hasta) cuya banda [u, u+ancho) yerra no mas que el global de X. None si ninguno."""
    techo = tasas(X)[3]
    for u in range(1, hasta + 1):
        _, nd, _, e = tasas(banda(X, u, ancho))
        if nd and e <= techo:
            return u
    return None


def main(rutas):
    X = juntar(rutas)
    n, nd, mal, e = tasas(X)
    print(f"control: {n} pasadas, decididas {nd} ({100 * nd / n:.1f} %), erradas {mal} ({100 * e:.2f} %)")
    if "muestra" in X.columns:
        for m, g in X.groupby("muestra"):
            n_, nd_, m_, e_ = tasas(g)
            print(f"   muestra {m}: {n_} pasadas, {nd_} decididas, {m_} erradas ({100 * e_:.1f} %)")
    print(f"\n u | banda [u, u+{ANCHO}): decididas, erradas (error) | quedan fuera (pareos < u): decididas, erradas")
    for u in range(1, 21):
        _, nb, mb, eb = tasas(banda(X, u))
        _, nf, mf, _ = tasas(X[X.pareos < u])
        print(f"{u:2d} | {nb:4d} {mb:3d} ({100 * eb:4.1f} %) | {nf:4d} {mf:3d}")
    print(f"\nPAREOS_MINIMOS = {umbral(X)}  (banda de {ANCHO}; con banda 2, 3, 5 y 6: "
          + ", ".join(str(umbral(X, a)) for a in (2, 3, 5, 6)) + ")")
    for nombre, x in (("borde (desfase >= +0,76 d)", X[X.desfase >= BORDE]), ("resto", X[X.desfase < BORDE])):
        n_, nd_, m_, e_ = tasas(x)
        print(f"{nombre}: pasadas {n_}, decididas {nd_}, erradas {m_}" + (f" ({100 * e_:.1f} %)" if nd_ else ""))


if __name__ == "__main__":
    main(sys.argv[1:])
