# -*- coding: utf-8 -*-
"""Control de la distancia aproximada (dist_serie.py) contra la tabla latest.php, con el lector PORTADO.

Por que: el umbral de calado debil (dist_serie.PAREOS_MINIMOS) tiene que salir del instrumento que va a produccion,
no del lector del estudio. Este script repite el control del estudio (VRP-chile experiments/_s151_distancia_ocr,
INFORME §4) con dist_serie y con los cambios del verificador: calado y eliminacion SOLO con la tabla (cambio 1) y la
imagen MAS RECIENTE de 1 a 25 dias (cambio 2).

Para cada pasada VIIRS 375 de la tabla con VRP > 0 y distancia publicada que tenga imagen en la muestra: se lee su
columna en la imagen, se descuentan las otras pasadas de la tabla de esa noche (no ella misma), se decide cerca o
lejos con el limite del volcan y se compara con la distancia publicada. Escribe una fila por pasada con el numero de
pareos y el desfase del calado de la imagen usada, que es lo que necesita scripts/umbral_pareos.py.

El calado de cada imagen usa todas las pasadas de la tabla del volcan, incluida la de control (como el backfill:
para una fila OCR la imagen se cala con la tabla entera). El verificador midio que sacar la noche de control del
calado no cambia el error de la decision (VERIFICADOR §1, variante B).

Uso: python scripts/control_distancia_aprox.py <consolidado.csv> <muestra.csv> <salida.csv>
     muestra.csv: columnas volcano, last_modified_utc, md5, archivo (ruta de la Dist.png VIIRS 375, tal cual o junto
     a muestra.csv)."""
import os
import sys
import time

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import dist_serie as D  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def main(cons, muestra, salida):
    c = pd.read_csv(cons)
    tab = D.tabla(c, "VIIRS375")
    mu = pd.read_csv(muestra).rename(columns={"archivo": "png_path"})
    base = os.path.dirname(os.path.abspath(muestra))
    t0 = time.time()
    cache = {}

    def lectura_y_calado(fila, vol):
        p = fila.png_path
        if p not in cache:
            ruta = p if os.path.exists(p) else os.path.join(base, os.path.basename(p.replace("\\", "/")))
            x = D.leer(ruta)
            cb = None if x is None else D.calibrar(x, pd.Timestamp(fila.last_modified_utc).tz_convert(None),
                                                   tab[tab.vol == vol])
            cache[p] = (x, cb)
        return cache[p]

    out = []
    for r in tab.itertuples():
        img = D.imagen_para(r.t, mu[mu.volcano == r.vol])
        if img is None:
            continue
        x, cb = lectura_y_calado(img, r.vol)
        base_fila = dict(vol=r.vol, t=r.t, tipo=r.Tipo_Registro, dist=r.Distancia_km,
                         real="cerca" if r.Distancia_km <= D.limite_km(r.vol) else "lejos",
                         imagen=os.path.basename(img.png_path),
                         dias_img=(pd.Timestamp(img.last_modified_utc).tz_convert(None) - r.t).total_seconds() / 86400)
        if x is None or cb is None:
            out.append(dict(base_fila, clase="sin_lectura", pareos=0))
            continue
        ms = D.marcadores_t(x, cb["L"], cb["desfase"])
        e = D.eliminar(r.t, ms, D.otras_de(r.t, tab[tab.vol == r.vol]))
        out.append(dict(base_fila, clase=e["clase"], km=e["km"], kmin=e["kmin"], kmax=e["kmax"], n_col=e["n_col"],
                        pareos=cb["pareos"], desfase=cb["desfase"],
                        dec=D.decidir(e["clase"], e["km"], e["kmin"], e["kmax"], r.vol)))
    X = pd.DataFrame(out)
    X.to_csv(salida, index=False, lineterminator="\n", float_format="%.4f")
    print(f"imagenes leidas {len(cache)}, pasadas de control {len(X)}, {time.time() - t0:.0f} s")
    d = X[X.dec.isin(["cerca", "lejos"])]
    print(f"decididas {len(d)} de {len(X)}; erradas {(d.dec != d.real).sum()} ({100 * (d.dec != d.real).mean():.1f} %)")


if __name__ == "__main__":
    main(*sys.argv[1:4])
