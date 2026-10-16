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


def test_el_scraper_ocr_no_borra_las_columnas_al_guardar():
    """scraper_ocr.py reescribe el CSV con reindex de sus columnas: sin esto,
    cada corrida con eventos nuevos borraba las seis columnas y el backfill
    tenía que recalcular la historia entera. Las filas nuevas las trae vacías y
    el backfill (que corre después en el mismo workflow) las llena."""
    import backfill_distancia_aprox as B
    import scraper_ocr
    assert scraper_ocr.COLUMNAS_GUARDADO[-len(B.COLUMNAS):] == B.COLUMNAS
    assert scraper_ocr.COLUMNAS_GUARDADO[:len(scraper_ocr.COLUMNAS_OCR)] == scraper_ocr.COLUMNAS_OCR


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
