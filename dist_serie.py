# -*- coding: utf-8 -*-
"""Lector del panel "Last Month" de Dist.png de MIROVA (850 x 600 o 850 x 596).

Que dibuja MIROVA ahi: una serie de tiempo de la distancia maxima ("Max Distance") de cada pasada con anomalia, un
marcador por pasada sobre un tallo vertical: circulo rojo (< 5 km), cuadrado negro (> 5 km); la pasada de la
cabecera "Last Update" lleva una estrella amarilla si la anomalia esta activa, y una linea punteada vertical marca
el momento del grafico. Eje y 0 a 25 km (lo de mas de 25 km no se dibuja en este panel).

Lee: geometria (techo 25 km, eje 0 km como ocr_utils V29; marcas semanales del eje x), marcadores (plantillas de
anillo y cuadrado, x afinado al tallo), estrella y linea punteada. La fecha de la primera marca semanal y el
desfase horario se resuelven fuera (calibrar).

Origen: portado de experiments/_s151_distancia_ocr/scripts/dist_png.py del repo VRP-chile (estudio y verificador
limpio del 2026-10-15). Unico cambio: la correlacion usa OpenCV (ya en requirements) en vez de scipy; el test
tests/test_dist_serie.py comprueba que da lo mismo."""
import cv2
import numpy as np
import pandas as pd
from PIL import Image


def _ring(r_in=2.4, r_out=4.1, n=9):
    c = (n - 1) / 2.0
    yy, xx = np.mgrid[0:n, 0:n]
    d = np.hypot(yy - c, xx - c)
    return (d >= r_in) & (d <= r_out)


def _square(w, h):
    t = np.zeros((h + 2, w + 2), bool)
    t[1, 1:w + 1] = t[h, 1:w + 1] = True
    t[1:h + 1, 1] = t[1:h + 1, w] = True
    return t


RING = _ring()
SQUARES = [_square(6, 7), _square(7, 7), _square(6, 6)]


def _score(mask, tpl):
    # filter2D correlaciona (no invierte el nucleo). correlate2d mode="same" equivale al ancla ((w-1)//2, (h-1)//2):
    # en plantillas de lado par el ancla por defecto de OpenCV (w//2) corre el pico un pixel (medido 2026-10-15).
    # Borde en cero, como el relleno de scipy.
    h, w = tpl.shape
    out = cv2.filter2D(mask.astype(np.float64), cv2.CV_64F, tpl.astype(np.float64),
                       anchor=((w - 1) // 2, (h - 1) // 2), borderType=cv2.BORDER_CONSTANT)
    return out / tpl.sum()


def _picos(score, umbral, sep=3):
    # Un marcador cuadrado da el mismo puntaje en una meseta de pixeles vecinos; sin redondear, el empate lo decide el
    # ruido de punto flotante (1e-16) y cambia con la libreria (contra el lector del estudio, el numero de marcadores
    # cambiaba en 118 de 449 imagenes). Se redondea, se ordena estable y el pico se mueve al CENTRO de la meseta
    # (pixeles con el mismo puntaje a +-sep), que es el centro del marcador y por lo tanto su distancia.
    # Re-control del estudio con este lector (vuelta 65 del loop, 2026-10-15; VRP-chile
    # experiments/_s151_distancia_ocr/recontrol/): dibujadas 98,6 % (estudio 98,5), error del caso unico mediana
    # 0,07 km y p90 0,64 (estudio 0,08 y 0,64), decisiones cerca/lejos erradas 41 de 1.353 (estudio 40).
    score = np.round(score, 9)
    ys, xs = np.nonzero(score >= umbral)
    orden = np.argsort(-score[ys, xs], kind="stable")
    tomados = []
    for i in orden:
        y, x = ys[i], xs[i]
        if all(abs(y - a) > sep or abs(x - b) > sep for a, b, _ in tomados):
            s = score[y, x]
            y0, x0 = max(0, y - sep), max(0, x - sep)
            py, px = np.nonzero(score[y0:y + sep + 1, x0:x + sep + 1] == s)
            tomados.append((int(round(y0 + py.mean())), int(round(x0 + px.mean())), float(s)))
    return tomados


def _grupos(f, gap=2):
    if not f:
        return []
    g = [[f[0]]]
    for y in f[1:]:
        (g[-1].append(y) if y - g[-1][-1] <= gap else g.append([y]))
    return [float(np.mean(x)) for x in g]


def geometria(gray):
    h = gray.shape[0]; sy = h / 600.0
    def filas(y0, y1, u):
        v = gray[y0:y1, 300:790] < u
        return [y0 + i for i, c in enumerate(v.sum(1)) if c >= 0.93 * v.shape[1]]
    fe = filas(int(240 * sy), int(340 * sy), 170)
    if not fe:
        return None
    eje = _grupos(fe)[-1]
    cand = [t for t in _grupos(filas(int(70 * sy), int(eje - 150 * sy), 235)) if 160 * sy < eje - t < 210 * sy]
    if not cand:
        return None
    techo = min(cand, key=lambda t: abs((eje - t) - 185 * sy))
    y0, y1 = int(techo + 4), int(eje - 4)
    cols = []
    for x in range(240, 830):
        v = gray[y0:y1, x]
        if (v < 236).mean() > 0.9 and 170 < np.median(v) < 233:
            cols.append(x)
    gx = _grupos(cols)
    mejor = []
    for i in range(len(gx)):
        seq = [gx[i]]
        for x in gx[i + 1:]:
            if abs((x - seq[-1]) - 106.5) < 4:
                seq.append(x)
        if len(seq) > len(mejor):
            mejor = seq
    if len(mejor) < 3:
        return None
    ppd = float(np.median(np.diff(mejor))) / 7.0
    return {"techo": techo, "eje": eje, "ticks": mejor, "ppd": ppd}


def leer(path):
    a = np.asarray(Image.open(path).convert("RGB")).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    gray = a.mean(2)
    geo = geometria(gray)
    if geo is None:
        return None
    t0, ej = int(geo["techo"]) - 6, int(geo["eje"]) + 4
    x0, x1 = int(geo["ticks"][0]) - 4, int(geo["ticks"][-1]) + 4
    sub = (slice(t0, ej), slice(x0, x1))
    roj = ((r - (g + b) / 2) > 70)[sub]
    neutro = (np.abs(r - b) < 12) & (np.abs(r - g) < 12)      # la punteada es azulada (134,134,148): queda fuera
    osc = ((gray < 175) & neutro)[sub]
    osc[int(geo["eje"]) - t0 - 2:, :] = False                 # el eje 0 km es oscuro: no es marcador
    ama = ((r > 200) & (g > 200) & (b < 110))[sub]
    km = lambda y: (geo["eje"] - y) * 25.0 / (geo["eje"] - geo["techo"])
    ye = int(geo["eje"]) - t0 - 2

    def afinar(mask, y, x, mitad):
        y_a = y + mitad + 1
        if ye - y_a >= 3:
            vent = mask[y_a:ye, max(0, x - 5):x + 6]
            cols = vent.sum(0)
            if cols.max() >= 0.8 * vent.shape[0]:
                return max(0, x - 5) + int(np.argmax(cols))
        w = mask[max(0, y - mitad):y + mitad + 1, max(0, x - mitad):x + mitad + 1]
        ys_, xs_ = np.nonzero(w)
        return max(0, x - mitad) + xs_.mean() if len(xs_) else x

    marc = []
    for (y, x, s) in _picos(_score(roj, RING), 0.55):
        marc.append({"tipo": "circulo", "x": afinar(roj, y, x, 4) + x0, "y": y + t0, "km": km(y + t0), "score": s})
    sq = np.max([_score(osc, T) for T in SQUARES], axis=0)
    for (y, x, s) in _picos(sq, 0.65):
        marc.append({"tipo": "cuadrado", "x": afinar(osc, y, x, 4) + x0, "y": y + t0, "km": km(y + t0), "score": s})
    estrella = None
    if ama.sum() > 20:
        ys, xs = np.nonzero(ama)
        estrella = {"tipo": "estrella", "x": xs.mean() + x0, "y": ys.mean() + t0, "km": km(ys.mean() + t0)}
    pun = ((b - r >= 8) & (b - r <= 25) & (gray > 110) & (gray < 200))[int(geo["techo"]) + 3:int(geo["eje"]) - 3, x0:x1]
    frac = pun.mean(0)
    xp = int(np.argmax(frac))
    punteada = float(xp + x0) if frac[xp] > 0.25 else None
    return {"geo": geo, "marcadores": marc, "estrella": estrella, "punteada": punteada}


# ---------------------------------------------------------------- eje de tiempo
# El eje x no trae fechas legibles: hay que calarlo. La fecha de la primera marca semanal (L) y el desfase horario
# del dibujo se eligen por imagen, maximizando cuantos marcadores calzan con pasadas conocidas a +-TOL_T dias y
# +-TOL_KM km. Portado de control_dist.py del estudio (calibrar_imagen, marcadores_t, pareos).
TOL_T, TOL_KM = 0.12, 0.6


def marcadores_t(lectura, L, desfase):
    """Marcadores (y la estrella) con su hora: L + (x - primera marca) / px por dia + desfase."""
    g = lectura["geo"]
    ms = list(lectura["marcadores"]) + ([lectura["estrella"]] if lectura["estrella"] else [])
    return [dict(m, t=L + pd.Timedelta(days=(m["x"] - g["ticks"][0]) / g["ppd"] + desfase)) for m in ms]


def solo_tabla(conocidas):
    """Cambio 1 del verificador limpio: sólo filas de la tabla latest.php. Las distancias del OCR discrepan mas de
    2 km en ~24 % de las pasadas del 2026-06-13 al 10-08, asi que no calan ni eliminan."""
    return conocidas[~conocidas.Tipo_Registro.astype(str).str.endswith("_OCR")]


def tabla(df, sensor):
    """Pasadas conocidas de un sensor: filas de la tabla latest.php (no _OCR, cambio 1) con VRP > 0 y Distancia_km.
    MIROVA solo dibuja pasadas con anomalia; las RUTINA traen Distancia_km = 0 y calzarian con cualquier marcador del
    crater. Agrega t (Fecha_Satelite_UTC) y vol (nombre de MIROVA, el del indice de PNG)."""
    d = solo_tabla(df)
    d = d[(d.Sensor == sensor) & (pd.to_numeric(d.VRP_MW, errors="coerce") > 0)
          & pd.to_numeric(d.Distancia_km, errors="coerce").notna()].copy()
    d["Distancia_km"] = pd.to_numeric(d.Distancia_km)
    d["t"] = pd.to_datetime(d.Fecha_Satelite_UTC, errors="coerce")
    d["vol"] = d.Volcan.map(_id_mirova_o_none)
    malas = d.t.isna() | d.vol.isna()
    if malas.any():
        # una fila de la tabla con volcan desconocido o fecha ilegible no puede tumbar el calado de los demas
        print(f"aviso: {int(malas.sum())} filas de la tabla sin volcan conocido o sin fecha legible: se ignoran")
    return d[~malas].sort_values(["vol", "t"])


def _id_mirova_o_none(volcan):
    try:
        return id_mirova(volcan)
    except KeyError:
        return None


def id_mirova(volcan):
    """Nombre de MIROVA (el de mirova-tif-archive) para el nombre del CSV o un alias; un volcan desconocido es error."""
    from volcanes import VOLCANES
    for v in VOLCANES.values():
        if volcan == v["nombre"] or volcan == v["id_mirova"] or volcan in v["alias"]:
            return v["id_mirova"]
    raise KeyError(volcan)


def pareos(ms, ref):
    """Cuantos marcadores calzan con alguna pasada de ref (columnas t y Distancia_km). Sobre 25,3 km no hay dibujo."""
    n = 0
    for m in ms:
        dt = (ref.t - m["t"]).dt.total_seconds().abs() / 86400
        dk = (ref.Distancia_km.where(ref.Distancia_km <= 25.3, 999) - m["km"]).abs()
        n += int(((dt <= TOL_T) & (dk <= TOL_KM)).any())
    return n


def calibrar(lectura, lm, conocidas):
    """Cala el eje de tiempo de una imagen escrita en lm (UTC, sin zona). Candidatos: L = dia de lm - 31, -30 o
    -29 dias; desfase de -0,30 a +0,78 d cada 0,02. Condicion fisica: ningun marcador despues de lm + 2 h. Desempate:
    el marcador mas a la derecha mas cerca de lm. Devuelve {"pareos", "L", "desfase"} o None si no hay marcadores.
    (En el estudio el desfase mediano por mes fue +0,48 a +0,53 d; 7 de 429 imagenes calan en el borde, >= +0,76.)"""
    ref = solo_tabla(conocidas)
    g = lectura["geo"]
    ms = list(lectura["marcadores"]) + ([lectura["estrella"]] if lectura["estrella"] else [])
    if not ms:
        return None
    xmax = max(m["x"] for m in ms)
    mejor = None
    for k in (-31, -30, -29):
        L = lm.normalize() + pd.Timedelta(days=k)
        for off in np.arange(-0.30, 0.80, 0.02):
            tmax = L + pd.Timedelta(days=(xmax - g["ticks"][0]) / g["ppd"] + off)
            if tmax > lm + pd.Timedelta(hours=2):
                continue
            n = pareos(marcadores_t(lectura, L, off), ref)
            cand = (n, -abs((lm - tmax).total_seconds()), L, round(float(off), 2))
            if mejor is None or cand[:2] > mejor[:2]:
                mejor = cand
    if mejor is None:
        return None
    return {"pareos": mejor[0], "L": mejor[2], "desfase": mejor[3]}


# ---------------------------------------------------------------- umbral de calado debil (cambio 3)
# Con pocos pareos el eje de tiempo puede quedar corrido y la columna de la noche ser otra. PAREOS_MINIMOS NO se eligio:
# es el menor umbral u cuya banda marginal (calados de u a u+3 pareos, los mas debiles que admite) yerra no mas que el
# error global del control. Dos controles con este lector y los cambios 1 y 2 del verificador, sobre muestras de
# imagenes casi disjuntas (17 en comun): el del PR (331 imagenes de la muestra del estudio) y el del verificador limpio
# del PR #25 (400 imagenes de la cache del backfill). Juntos en tests/fixtures/dist/control_juntas.csv (una pasada en
# la misma imagen cuenta una vez). scripts/umbral_pareos.py, 2026-10-16:
#   control: 2919 pasadas, decididas 2362, erradas 80 (3,39 %)   [PR 38 de 1240 (3,1 %); verificador 42 de 1122 (3,7 %)]
#    u | banda [u, u+4): decididas, erradas (error) | quedan fuera (pareos < u): decididas, erradas
#    1 |   47   2 (4,3 %) |    2   2
#    2 |   84   4 (4,8 %) |    4   2
#    3 |  123   5 (4,1 %) |    9   2
#    4 |  148   6 (4,1 %) |   26   2
#    5 |  133   4 (3,0 %) |   49   4      <- PAREOS_MINIMOS
#    6 |  106   2 (1,9 %) |   88   6
#    8 |  112   2 (1,8 %) |  174   8
#   12 |  140   2 (1,4 %) |  286  10
#   20 |  173   4 (2,3 %) |  646  15
# Lectura: los calados de 1 a 7 pareos yerran algo mas que el global (4,1 a 4,8 %); desde 5 la banda cae bajo el
# global y ya no vuelve a superarlo hasta 20 (el error que queda esta en las imagenes de 20 a 40 pareos, volcanes con
# muchas pasadas por noche: es de atribucion, no de calado). El valor depende de la banda y descansa en pocos errores
# (6 de 148 en la de 4): con banda de 5 o 6 tambien da 5, con 2 o 3 da 1. La version anterior (4) medía el error
# acumulado de lo admitido, que por construccion acepta el piso de la busqueda (verificador del PR #25, §3).
# Con el umbral: 76 erradas de 2313 decididas (3,3 %); en ALERTA, 37 de 1493 crater leidas lejanas (2,5 %), ninguna
# ALERTA lejana en el control. Calados en el borde de la busqueda (desfase >= +0,76 d): 6 de 140 errados (4,3 %)
# contra 3,3 % del resto, Fisher p = 0,47; con el umbral, 4 de 138. No se justifica tratar el borde aparte.
PAREOS_MINIMOS = 5


# ---------------------------------------------------------------- eleccion de la imagen
# Cambio 2 del verificador: solo imagenes de 1 a 25 dias despues de la pasada (el rango que el control cubrio; con
# menos de 1 dia la columna todavia puede recibir pasadas de la misma noche). Se elige la MAS RECIENTE del rango, la
# que recomienda el informe §7 (el verificador midio el mismo error que con la primera).
MIN_DIAS, MAX_DIAS = 1.0, 25.0


def imagen_para(t, indice, min_dias=MIN_DIAS, max_dias=MAX_DIAS):
    """Fila del indice (columnas last_modified_utc, md5, png_path; ya filtrado por volcan, sensor y tipo Dist) de la
    imagen a usar para la pasada t, o None (pendiente). Un md5 repetido cuenta por su PRIMERA aparicion: MIROVA a veces
    vuelve a servir una imagen vieja bajo una hora nueva (A106 de VRP-chile), y su contenido es el de la primera."""
    if indice is None or len(indice) == 0:
        return None
    d = indice.copy()
    d["lm"] = pd.to_datetime(d.last_modified_utc, utc=True).dt.tz_localize(None)
    d = d.sort_values("lm").drop_duplicates("md5", keep="first")
    t = pd.Timestamp(t)
    ok = d[(d.lm >= t + pd.Timedelta(days=min_dias)) & (d.lm <= t + pd.Timedelta(days=max_dias))]
    return None if ok.empty else ok.iloc[-1]


# ---------------------------------------------------------------- eliminacion
# Las pasadas de una noche (04:30 a 07:00 UTC) caen en la misma columna del panel, a menos de 2 px: no se separan por
# la hora, solo por la altura. La distancia de una pasada P sale de los marcadores de su columna menos los que explican
# las otras pasadas de esa noche cuya distancia se conoce por la TABLA. Portado de control_dist.py (eliminar, otras_de).
W = 0.15        # semiancho de la columna de una noche (dias)


def otras_de(t, conocidas):
    """Pasadas de la tabla de la misma noche que t (hasta W + 0,05 d), sin la propia (a menos de 3 min).
    `conocidas` ya filtrada por volcan y sensor; las filas OCR se descartan aqui (cambio 1)."""
    ref = solo_tabla(conocidas)
    dd = (ref.t - pd.Timestamp(t)).dt.total_seconds().abs()
    return ref[(dd / 86400 <= W + 0.05) & (dd > 180)]


def eliminar(t, ms, otras):
    """Distancia de la pasada t por eliminacion en su columna. ms: marcadores con hora (marcadores_t).
    Devuelve {"clase", "km", "kmin", "kmax", "n_col"}; clase unico (un solo marcador sin explicar: km puntual),
    ambiguo (varios: intervalo), solapado (todos explicados: la pasada esta tapada o a mas de 25 km; intervalo de la
    columna) o sin_marcador (columna vacia: posible a mas de 25 km)."""
    t = pd.Timestamp(t)
    col = [m for m in ms if abs((m["t"] - t).total_seconds()) / 86400 <= W]
    if not col:
        return {"clase": "sin_marcador", "km": None, "kmin": None, "kmax": None, "n_col": 0}
    restantes = list(col)
    for _, k in otras.iterrows():
        if not restantes:
            break
        if k.Distancia_km > 25.3:          # el panel llega a 25 km: sobre eso no se dibuja
            continue
        dk = [abs(m["km"] - min(k.Distancia_km, 25)) for m in restantes]
        i = int(np.argmin(dk))
        if dk[i] <= TOL_KM:
            restantes.pop(i)
    kms = [m["km"] for m in col]
    extra = {"n_col": len(col), "col_kmin": min(kms), "col_kmax": max(kms)}
    if len(restantes) == 1:
        km = restantes[0]["km"]
        # el marcador elegido, para detectar si otra fila de la misma noche reclama el mismo (backfill)
        return {"clase": "unico", "km": km, "kmin": km, "kmax": km,
                "marcador": (round(float(restantes[0]["x"]), 3), round(float(restantes[0]["km"]), 3)), **extra}
    if not restantes:
        return {"clase": "solapado", "km": None, "kmin": min(kms), "kmax": max(kms), **extra}
    kr = [m["km"] for m in restantes]
    return {"clase": "ambiguo", "km": None, "kmin": min(kr), "kmax": max(kr), **extra}


# ---------------------------------------------------------------- decision cerca o lejos
# Portado de decision.py del estudio. La decision NO se escribe en el CSV: queda como funcion para quien lo consuma,
# porque depende del limite de alerta, que es de cada volcan y puede cambiar.
MARGEN_KM = TOL_KM      # margen a cada lado del limite: la tolerancia de lectura del control (0,6 km)


def limite_km(volcan):
    """Limite de alerta del volcan (volcanes.py, por nombre del CSV o por id de MIROVA). Un volcan desconocido es un
    error: no se adivina un limite."""
    from volcanes import LIMITES_Y_COORDENADAS
    return float(LIMITES_Y_COORDENADAS[volcan]["LIMITE_KM"])


def decidir(clase, km, kmin, kmax, volcan):
    """cerca (todo el intervalo bajo limite - 0,6 km), lejos (todo sobre limite + 0,6), indecidible (cruza la franja),
    "posible >25 km" (sin_marcador: el panel no dibuja sobre 25 km; nunca cerca) o None (sin lectura: pendiente,
    calado_debil, sin_control). En el caso unico el intervalo es el punto."""
    if clase == "sin_marcador":
        return "posible >25 km"
    if clase not in ("unico", "ambiguo", "solapado"):
        return None
    lo, hi = (km, km) if clase == "unico" else (kmin, kmax)
    u = limite_km(volcan)
    if hi < u - MARGEN_KM:
        return "cerca"
    if lo > u + MARGEN_KM:
        return "lejos"
    return "indecidible"


def con_cifra_ocr(t, ms, res, ocr_km):
    """Si la fila trae una distancia medida por el OCR (> 0; en el OCR el 0 es «no medida») y su columna tiene un
    marcador a esa cifra (+-0,6 km) que la eliminacion dejo fuera, el resultado pasa a ambiguo con el intervalo que
    incluye ese marcador. Por que: con una columna de dos marcadores, uno a la cifra del OCR y otro lejano, la serie
    no sabe cual es de esta pasada; en las pasadas OCR que tambien estan en la tabla dijo «lejos» en 5 de 9 cuya
    verdad era crater (VRP-chile, medicion del 2026-10-16). La serie es una segunda lectura, no una correccion."""
    try:
        o = float(ocr_km)
    except (TypeError, ValueError):
        return res
    if not o > 0 or res["clase"] not in ("unico", "ambiguo", "solapado"):
        return res
    o = min(o, 25.0)
    t = pd.Timestamp(t)
    en_cifra = [m["km"] for m in ms
                if abs((m["t"] - t).total_seconds()) / 86400 <= W and abs(m["km"] - o) <= TOL_KM]
    if not en_cifra or res["kmin"] - TOL_KM <= o <= res["kmax"] + TOL_KM:
        return res
    kmin, kmax = min([res["kmin"]] + en_cifra), max([res["kmax"]] + en_cifra)
    return dict(res, clase="ambiguo", km=None, kmin=kmin, kmax=kmax)
