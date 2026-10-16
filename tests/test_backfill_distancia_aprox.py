"""
Tests de backfill_distancia_aprox.py: seis columnas Distancia_aprox_* al final
de registro_vrp_ocr.csv, leídas en la Dist.png de 1 a 25 días después de la
pasada (dist_serie.py).

Por qué: la distancia del OCR sale sólo de la estrella de Dist.png, y cuando la
imagen ya era de otra pasada la fila queda sin distancia (o con un 0 fijo antes
del 2026-06-13). La serie de tiempo del panel trae esa pasada dibujada en las
imágenes siguientes. Es un COMPLEMENTO: Distancia_km no se toca nunca.

Las imágenes se inyectan (fixture real de Chillán) para que la suite no baje
nada de la red.
"""
import csv
import hashlib
import os

import pandas as pd
import pytest

from conftest import FIXTURES

DIST_CHILLAN = os.path.join(FIXTURES, "dist", "chillan_viirs375_dist_20261015_140626.png")
TABLA_CHILLAN = os.path.join(FIXTURES, "dist", "tabla_chillan_viirs375_20260913_20261016.csv")
LM_CHILLAN = "2026-10-15T14:06:26+00:00"

CABECERA = ["timestamp", "Fecha_Satelite_UTC", "Volcan", "Sensor", "VRP_MW", "Distancia_km", "Tipo_Registro",
            "Version_OCR"]
FILAS = [
    # pasada de la tabla escondida: 2026-10-10 06:30 está en la fixture de la tabla
    ["1", "2026-10-02 06:00:00", "Nevados de Chillan", "VIIRS375", "0.5", "", "ALERTA_SIN_GEOMETRIA_OCR", "31.1"],
    ["2", "2026-10-03 05:30:00", "Nevados de Chillan", "VIIRS375", "1.2", "0.95", "ALERTA_TERMICA_OCR", "31.1"],
    ["3", "2026-10-15 05:00:00", "Nevados de Chillan", "VIIRS375", "22.13", "", "ALERTA_SIN_GEOMETRIA_OCR", "31.1"],
    ["4", "2026-10-03 05:30:00", "Nevados de Chillan", "VIIRS", "3.0", "1.10", "ALERTA_TERMICA_OCR", "31.1"],
    ["5", "2026-10-03 05:30:00", "Nevados de Chillan", "MODIS", "3.0", "0.0", "ALERTA_TERMICA_OCR", "31.1"],
    ["6", "2026-08-01 05:30:00", "Nevados de Chillan", "VIIRS375", "0.3", "0.0", "ALERTA_TERMICA_OCR", "31.1"],
]


def _md5(ruta):
    return hashlib.md5(open(ruta, "rb").read()).hexdigest()


@pytest.fixture
def entorno(tmp_path):
    ocr = tmp_path / "registro_vrp_ocr.csv"
    with open(ocr, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\r\n")      # CRLF de entrada: la salida debe quedar en LF
        w.writerow(CABECERA)
        w.writerows(FILAS)
    t = pd.read_csv(TABLA_CHILLAN)
    t["Clasificacion Mirova"] = ""
    cons = tmp_path / "registro_vrp_consolidado.csv"
    t.to_csv(cons, index=False)
    idx = pd.DataFrame([dict(captured_at_utc=LM_CHILLAN, volcano="ChillanNevadosde", sensor="VIIRS375", kind="Dist",
                             last_modified_utc=LM_CHILLAN, md5=_md5(DIST_CHILLAN), size_bytes=1,
                             png_path="data/png/ChillanNevadosde/20261015_140626_VIIRS375_Dist.png")])
    return dict(ocr=str(ocr), cons=str(cons), indice=idx, obtener=lambda png_path, md5: DIST_CHILLAN)


def _correr(e, **kw):
    import backfill_distancia_aprox as B
    return B.rellenar(e["ocr"], e["cons"], e["indice"], e["obtener"], **kw)


def _leer(ruta):
    with open(ruta, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_distancia_km_queda_byte_a_byte_igual(entorno):
    antes = [f["Distancia_km"] for f in _leer(entorno["ocr"])]
    _correr(entorno)
    assert [f["Distancia_km"] for f in _leer(entorno["ocr"])] == antes
    # y ninguna columna vieja cambia
    for f, orig in zip(_leer(entorno["ocr"]), FILAS):
        assert [f[c] for c in CABECERA] == orig


def test_seis_columnas_al_final_y_sin_control_fuera_de_viirs375(entorno):
    import backfill_distancia_aprox as B
    _correr(entorno)
    with open(entorno["ocr"], encoding="utf-8") as f:
        cab = f.readline().strip().split(",")
    assert cab == CABECERA + B.COLUMNAS
    filas = _leer(entorno["ocr"])
    for f in filas[3:5]:                      # VIIRS 750 y MODIS
        assert f["Distancia_aprox_metodo"] == "sin_control"
        assert all(f[c] == "" for c in B.COLUMNAS if c != "Distancia_aprox_metodo")


def test_se_llenan_tambien_las_filas_con_distancia_ocr(entorno):
    """Cambio 6 del verificador: la fila 2 trae Distancia_km = 0,95 medida por
    el OCR y también recibe su lectura de la serie (segunda lectura)."""
    _correr(entorno)
    f = _leer(entorno["ocr"])[1]
    assert f["Distancia_aprox_metodo"] in ("unico", "ambiguo", "solapado", "sin_marcador")
    assert f["Distancia_aprox_imagen"].endswith("_VIIRS375_Dist.png")
    assert int(f["Distancia_aprox_pareos"]) >= 30


def test_pendiente_sin_imagen_de_1_a_25_dias(entorno):
    """La pasada del 10-15 05:00 sólo tiene la imagen del mismo día (0,4 d) y la
    del 08-01 queda a más de 25 días: las dos quedan pendientes, sin valor."""
    _correr(entorno)
    filas = _leer(entorno["ocr"])
    for f in (filas[2], filas[5]):
        assert f["Distancia_aprox_metodo"] == "pendiente"
        assert f["Distancia_aprox_km"] == f["Distancia_aprox_min_km"] == f["Distancia_aprox_imagen"] == ""


def test_unico_lleva_el_valor_y_el_intervalo_igual(entorno):
    _correr(entorno)
    for f in _leer(entorno["ocr"]):
        m = f["Distancia_aprox_metodo"]
        if m == "unico":
            assert f["Distancia_aprox_km"] == f["Distancia_aprox_min_km"] == f["Distancia_aprox_max_km"] != ""
        elif m in ("ambiguo", "solapado"):
            assert f["Distancia_aprox_km"] == "" and float(f["Distancia_aprox_min_km"]) <= float(f["Distancia_aprox_max_km"])


def test_calado_debil_no_escribe_valor(entorno, monkeypatch):
    import dist_serie as D
    monkeypatch.setattr(D, "PAREOS_MINIMOS", 1000)
    _correr(entorno)
    f = _leer(entorno["ocr"])[0]
    assert f["Distancia_aprox_metodo"] == "calado_debil"
    assert f["Distancia_aprox_km"] == f["Distancia_aprox_min_km"] == f["Distancia_aprox_max_km"] == ""
    assert int(f["Distancia_aprox_pareos"]) >= 30          # el calado se guarda igual (trazabilidad)


def test_idempotente_y_en_lf(entorno):
    _correr(entorno)
    uno = open(entorno["ocr"], "rb").read()
    assert b"\r\n" not in uno
    _correr(entorno)
    assert open(entorno["ocr"], "rb").read() == uno


def test_ventana_solo_recalcula_lo_reciente_y_lo_nunca_calculado(entorno):
    """En el cron: filas de los últimos N días y filas sin método. Una fila vieja
    ya calculada no se toca aunque hoy diera otra cosa."""
    _correr(entorno)
    filas = _leer(entorno["ocr"])
    filas[1]["Distancia_aprox_metodo"] = "marca_de_prueba"
    with open(entorno["ocr"], "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(filas)
    _correr(entorno, dias=2, ahora=pd.Timestamp("2026-10-16 12:00:00"))
    assert _leer(entorno["ocr"])[1]["Distancia_aprox_metodo"] == "marca_de_prueba"


def test_calado_guardado_no_se_recalcula_y_cambia_si_cambia_la_tabla(entorno, tmp_path, monkeypatch):
    """El calado es lo caro (unos segundos por imagen) y el cron corre cada
    hora: se guarda por md5 de la imagen y por las pasadas de la tabla que caen
    en su panel. Con la misma tabla no se recalcula; si llega una pasada nueva
    a esa ventana, sí."""
    import dist_serie as D
    cache = str(tmp_path / "calados.json")
    _correr(entorno, cache_calados=cache)
    uno = open(entorno["ocr"], "rb").read()
    calibrar = D.calibrar
    llamadas = []
    monkeypatch.setattr(D, "calibrar", lambda *a, **k: llamadas.append(1) or calibrar(*a, **k))
    os.remove(entorno["ocr"])
    with open(entorno["ocr"], "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(CABECERA)
        w.writerows(FILAS)
    _correr(entorno, cache_calados=cache)
    assert llamadas == []
    assert open(entorno["ocr"], "rb").read() == uno
    t = pd.read_csv(entorno["cons"])
    t.loc[len(t)] = t.iloc[-1]
    t.loc[len(t) - 1, "Fecha_Satelite_UTC"] = "2026-10-01 05:00:00"
    t.to_csv(entorno["cons"], index=False)
    _correr(entorno, cache_calados=cache)
    assert llamadas == [1]


def test_presupuesto_de_tiempo_guarda_lo_hecho_y_la_proxima_sigue(entorno):
    """La primera corrida del cron llena la historia entera (decenas de minutos).
    Con un presupuesto, se detiene, escribe lo calculado y deja el resto con el
    método vacío; la corrida siguiente lo retoma. Nada a medias: una fila o se
    calcula entera o no se toca."""
    import backfill_distancia_aprox as B
    _correr(entorno, limite_s=0)
    filas = _leer(entorno["ocr"])
    assert list(filas[0].keys())[-len(B.COLUMNAS):] == B.COLUMNAS
    assert all(f["Distancia_aprox_metodo"] == "" for f in filas)
    _correr(entorno, dias=1, ahora=pd.Timestamp("2026-10-16 12:00:00"))
    assert all(f["Distancia_aprox_metodo"] != "" for f in _leer(entorno["ocr"]))


# ---------------------------------------------------------------- arreglos del verificador (PR #25)
def test_el_scraper_ocr_conserva_las_columnas_al_guardar(tmp_path):
    """scraper_ocr.py reescribe el CSV con pandas: si vuelve a reindexar solo con
    sus columnas, cada corrida con eventos nuevos borra las seis y el backfill
    tiene que rehacer la historia. Se prueba el guardado de verdad, no la lista."""
    import scraper_ocr
    import dist_aprox_columnas as C
    viejo = {c: "" for c in scraper_ocr.COLUMNAS_OCR}
    viejo.update({"timestamp": 1, "Volcan": "Isluga", "Sensor": "VIIRS375", "Distancia_aprox_km": 0.54,
                  "Distancia_aprox_min_km": 0.54, "Distancia_aprox_max_km": 0.54, "Distancia_aprox_metodo": "unico",
                  "Distancia_aprox_pareos": 39, "Distancia_aprox_imagen": "data/png/Isluga/x.png"})
    nuevo = {c: "" for c in scraper_ocr.COLUMNAS_OCR}
    nuevo.update({"timestamp": 2, "Volcan": "Isluga", "Sensor": "VIIRS375"})
    ruta = tmp_path / "ocr.csv"
    scraper_ocr.guardar_ocr(pd.DataFrame([viejo]), [nuevo], str(ruta))
    f = _leer(ruta)
    assert list(f[0].keys())[-len(C.COLUMNAS):] == C.COLUMNAS
    vieja = next(x for x in f if x["timestamp"] == "1")
    assert (vieja["Distancia_aprox_metodo"], vieja["Distancia_aprox_pareos"], vieja["Distancia_aprox_km"]) \
        == ("unico", "39", "0.54")
    assert next(x for x in f if x["timestamp"] == "2")["Distancia_aprox_metodo"] == ""


def test_ida_y_vuelta_por_pandas_no_cambia_las_columnas(entorno):
    """scraper_ocr.py y reconciliar_latest.py reescriben el CSV con pandas: los
    pareos no pueden volver como 11.0 ni los km cambiar de forma (24.80 a 24.8)."""
    import dist_aprox_columnas as C
    _correr(entorno)
    antes = _leer(entorno["ocr"])
    C.escribir_ocr(pd.read_csv(entorno["ocr"]), entorno["ocr"])
    despues = _leer(entorno["ocr"])
    assert [[f[c] for c in C.COLUMNAS] for f in despues] == [[f[c] for c in C.COLUMNAS] for f in antes]
    assert not any(f["Distancia_aprox_pareos"].endswith(".0") for f in despues)


def _sintetico(monkeypatch, tmp_path, filas_ocr, tabla, marcadores_km_t):
    """Una imagen falsa con marcadores dados (km, hora): sin red ni PNG, para
    probar la lógica de calcular() fila por fila."""
    import dist_serie as D
    L = pd.Timestamp("2026-10-01")
    lectura = {"geo": {"ticks": [0.0], "ppd": 1.0},
               "marcadores": [{"tipo": "circulo", "x": (pd.Timestamp(t) - L).total_seconds() / 86400, "y": 0, "km": km}
                              for km, t in marcadores_km_t],
               "estrella": None}
    monkeypatch.setattr(D, "leer", lambda ruta: lectura)
    monkeypatch.setattr(D, "calibrar", lambda x, lm, ref: {"pareos": 30, "L": L, "desfase": 0.0})
    ocr = tmp_path / "ocr.csv"
    with open(ocr, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(CABECERA)
        w.writerows(filas_ocr)
    cons = tmp_path / "cons.csv"
    pd.DataFrame(tabla, columns=["Fecha_Satelite_UTC", "Volcan", "Sensor", "VRP_MW", "Distancia_km", "Tipo_Registro"]
                 ).to_csv(cons, index=False)
    idx = pd.DataFrame([dict(volcano="Lastarria", sensor="VIIRS375", kind="Dist",
                             last_modified_utc="2026-10-12T05:00:00+00:00", md5="m1",
                             png_path="data/png/Lastarria/x.png")])
    return dict(ocr=str(ocr), cons=str(cons), indice=idx, obtener=lambda png_path, md5: "no_se_lee")


def test_cifra_ocr_mas_lejano_queda_ambiguo_en_el_csv(monkeypatch, tmp_path):
    """La llamada a con_cifra_ocr en el backfill: la tabla explica el marcador a
    0,95 km con otra pasada de la noche, la eliminación se queda con el de 16,5,
    pero la fila trae 0,95 medido por el OCR: queda ambiguo, no lejos."""
    e = _sintetico(monkeypatch, tmp_path,
                   [["1", "2026-10-05 05:30:00", "Lastarria", "VIIRS375", "1.0", "0.95", "ALERTA_TERMICA_OCR", "31"]],
                   [("2026-10-05 06:10:00", "Lastarria", "VIIRS375", 0.8, 0.95, "ALERTA_TERMICA")],
                   [(0.95, "2026-10-05 06:10"), (16.5, "2026-10-05 05:30")])
    _correr(e)
    f = _leer(e["ocr"])[0]
    assert (f["Distancia_aprox_metodo"], f["Distancia_aprox_km"], f["Distancia_aprox_min_km"],
            f["Distancia_aprox_max_km"]) == ("ambiguo", "", "0.95", "16.5")


def test_marcador_reclamado_por_dos_filas_no_es_unico(monkeypatch, tmp_path):
    """Dos filas OCR de la misma noche se quedan con el mismo marcador (las
    vecinas solo OCR no se descuentan). Ninguna puede ser unico: el marcador es
    de una sola de ellas, y la otra puede estar tapada o a más de 25 km. Las dos
    quedan ambiguo con el intervalo de su columna (Lastarria 2026-06-28, verificador)."""
    e = _sintetico(monkeypatch, tmp_path,
                   [["1", "2026-10-05 05:36:00", "Lastarria", "VIIRS375", "1.0", "", "ALERTA_SIN_GEOMETRIA_OCR", "31"],
                    ["2", "2026-10-05 05:54:00", "Lastarria", "VIIRS375", "1.0", "", "ALERTA_SIN_GEOMETRIA_OCR", "31"]],
                   [("2026-10-05 06:20:00", "Lastarria", "VIIRS375", 0.8, 2.70, "ALERTA_TERMICA")],
                   [(2.70, "2026-10-05 06:20"), (15.56, "2026-10-05 05:45")])
    _correr(e)
    for f in _leer(e["ocr"]):
        assert (f["Distancia_aprox_metodo"], f["Distancia_aprox_km"], f["Distancia_aprox_min_km"],
                f["Distancia_aprox_max_km"]) == ("ambiguo", "", "2.7", "15.56")


def test_error_por_fila_no_aborta_y_avisa(monkeypatch, tmp_path, capsys):
    """Un volcán desconocido, una fecha ilegible o una PNG que no baja quedan
    como error_lectura en su fila; las demás se calculan, el CSV se escribe y
    sale un ::warning:: con el conteo (el paso no queda verde en silencio)."""
    filas = [["1", "2026-10-05 05:30:00", "Lastarria", "VIIRS375", "1.0", "", "ALERTA_SIN_GEOMETRIA_OCR", "31"],
             ["2", "2026-10-05 05:30:00", "Volcan Nuevo", "VIIRS375", "1.0", "", "ALERTA_SIN_GEOMETRIA_OCR", "31"],
             ["3", "basura", "Lastarria", "VIIRS375", "1.0", "", "ALERTA_SIN_GEOMETRIA_OCR", "31"],
             ["4", "2026-10-06 05:30:00", "Lastarria", "VIIRS375", "1.0", "", "ALERTA_SIN_GEOMETRIA_OCR", "31"]]
    e = _sintetico(monkeypatch, tmp_path, filas, [], [(1.0, "2026-10-05 05:30")])
    e["indice"] = pd.concat([e["indice"], e["indice"].assign(md5="m2", last_modified_utc="2026-10-30T12:00:00+00:00")])

    def obtener(png_path, md5):
        if md5 == "m2":
            raise OSError("HTTP Error 404")
        return "no_se_lee"
    e["obtener"] = obtener
    _correr(e)
    f = _leer(e["ocr"])
    assert f[0]["Distancia_aprox_metodo"] == "unico"
    assert [x["Distancia_aprox_metodo"] for x in f[1:]] == ["error_lectura"] * 3
    assert "::warning" in capsys.readouterr().out


def test_error_lectura_se_reintenta_aunque_sea_vieja(monkeypatch, tmp_path):
    """Un error transitorio no puede quedar pegado: fuera de la ventana del cron
    la fila con error_lectura se vuelve a calcular."""
    e = _sintetico(monkeypatch, tmp_path,
                   [["1", "2026-10-05 05:30:00", "Lastarria", "VIIRS375", "1.0", "", "ALERTA_SIN_GEOMETRIA_OCR", "31"]],
                   [], [(1.0, "2026-10-05 05:30")])
    falla = {"si": True}

    def obtener(png_path, md5):
        if falla["si"]:
            raise OSError("HTTP Error 429")
        return "no_se_lee"
    e["obtener"] = obtener
    _correr(e)
    assert _leer(e["ocr"])[0]["Distancia_aprox_metodo"] == "error_lectura"
    falla["si"] = False
    _correr(e, dias=1, ahora=pd.Timestamp("2026-12-01"))
    assert _leer(e["ocr"])[0]["Distancia_aprox_metodo"] == "unico"


def test_429_reintenta_con_espera_y_404_no(monkeypatch):
    import urllib.error
    import backfill_distancia_aprox as B
    esperas, llamadas = [], []

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"ok"

    def fake(url, timeout=60):
        llamadas.append(url)
        if len(llamadas) <= 2:
            raise urllib.error.HTTPError(url, 429, "Too Many Requests", {"Retry-After": "3"}, None)
        return Resp()
    monkeypatch.setattr(B.urllib.request, "urlopen", fake)
    monkeypatch.setattr(B.time, "sleep", esperas.append)
    assert B._bajar("u") == b"ok"
    assert esperas == [3, 3]
    llamadas.clear()

    def no_existe(url, timeout=60):
        llamadas.append(url)
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
    monkeypatch.setattr(B.urllib.request, "urlopen", no_existe)
    with pytest.raises(urllib.error.HTTPError):
        B._bajar("u")
    assert len(llamadas) == 1


def test_poda_de_la_cache_de_imagenes(tmp_path):
    """La caché de PNG no crece sin fin: se borra lo que no se usa hace más de
    30 días. Una PNG usada se toca al usarla (obtener_png)."""
    import time as _t
    import backfill_distancia_aprox as B
    vieja, nueva = tmp_path / "a.png", tmp_path / "b.png"
    vieja.write_bytes(b"x")
    nueva.write_bytes(b"y")
    hace = _t.time() - 31 * 86400
    os.utime(vieja, (hace, hace))
    assert B.podar_cache(str(tmp_path), dias=30) == 1
    assert not vieja.exists() and nueva.exists()


def test_tmp_en_gitignore():
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assert "*.tmp" in open(os.path.join(raiz, ".gitignore"), encoding="utf-8").read().split()
