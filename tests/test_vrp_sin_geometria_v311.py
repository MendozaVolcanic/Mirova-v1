"""
V31.1: una pasada cuyo Dist.png ya es de una pasada POSTERIOR se guarda con su
VRP y SIN distancia ni clase.

Fenomeno: MIROVA mantiene una sola Dist.png por volcan y sensor. Si el OCR corre
cuando MIROVA ya proceso la pasada siguiente, la estrella (distancia y clase) es
de esa pasada siguiente, pero el VRP de la celda de Latest10NTI sigue siendo de
la pasada vieja. V31 botaba ese VRP; una pasada que la tabla latest.php se salta
y que no es la ultima se perdia siempre.

Caso testigo: Nevados de Chillan 2026-10-15 05:00 UTC, 22,13 MW en VIIRS375 y
14 MW en VIIRS750 (erupcion), con Dist.png de las 06:00:02. Las filas estan en
monitoreo_satelital/ocr_rechazos_cabecera.csv; el log de la corrida OCR
38731370807 dice "SKIP V31: Dist.png es de otra pasada".

Las dos preguntas del instrumento: si el codigo siguiera botando el VRP,
test_pasada_0500_se_guarda_sin_distancia falla; si guardara cualquier rechazo
(VRP 0, Dist anterior o ilegible, duplicados), fallan los tests de "no se guarda".
"""
import csv
import os
from datetime import datetime

import pandas as pd
import pytz

UTC = pytz.utc


def _utc(s):
    return UTC.localize(datetime.strptime(s, "%Y-%m-%d %H:%M:%S"))


PASADA = _utc("2026-10-15 05:00:00")
CAB_POSTERIOR = _utc("2026-10-15 06:00:02")


# ---------------------------------------------------------------------------
# La fila
# ---------------------------------------------------------------------------

def test_pasada_0500_se_guarda_sin_distancia():
    from scraper_ocr import fila_vrp_sin_geometria, COLUMNAS_OCR
    f = fila_vrp_sin_geometria("Nevados de Chillan", "VIIRS375", PASADA, 22.13,
                               CAB_POSTERIOR, zen=62, azi=-84)
    assert f is not None
    assert set(f) == set(COLUMNAS_OCR)
    # tipo propio: sin distancia no se sabe si esta dentro del radio, asi que no
    # es ALERTA_TERMICA_OCR (que si lo afirma)
    assert f["Tipo_Registro"] == "ALERTA_SIN_GEOMETRIA_OCR"
    assert f["VRP_MW"] == 22.13
    assert f["Distancia_km"] == ""                 # desconocida, nunca 0
    assert f["Clasificacion Mirova"] == "SIN_GEOMETRIA"
    assert f["Metodo_Validacion"] == "vrp_sin_geometria_propia"
    assert f["Fecha_Satelite_UTC"] == "2026-10-15 05:00:00"
    assert f["timestamp"] == int(PASADA.timestamp())
    assert f["Zenith_Sat_deg"] == "62"
    assert f["Requiere_Verificacion"] is True
    # Contrato del CSV con VRP Chile: ningun valor lleva coma.
    assert not any("," in str(v) for v in f.values())
    # La nota no debe parecer una distancia medida (VRP Chile la extrae con
    # el patron "-> X km" o "dist~X km").
    assert "->" not in f["Nota_Validacion"] and "→" not in f["Nota_Validacion"]


def test_distancia_vacia_sobrevive_el_ida_y_vuelta_de_pandas(tmp_path):
    """El scraper relee y reescribe el CSV con pandas en cada corrida: la celda
    vacia tiene que seguir vacia, no convertirse en 0."""
    from scraper_ocr import fila_vrp_sin_geometria, COLUMNAS_OCR
    f = fila_vrp_sin_geometria("Nevados de Chillan", "VIIRS375", PASADA, 22.13, CAB_POSTERIOR)
    otra = dict(f, timestamp=1, Distancia_km=1.08, Fecha_Satelite_UTC="2026-10-14 13:05:00")
    ruta = tmp_path / "ocr.csv"
    pd.DataFrame([otra, f])[COLUMNAS_OCR].to_csv(ruta, index=False)
    df = pd.read_csv(ruta)
    df[COLUMNAS_OCR].sort_values("timestamp", ascending=False).to_csv(ruta, index=False)
    with open(ruta, newline="", encoding="utf-8") as fh:
        filas = {r["Fecha_Satelite_UTC"]: r for r in csv.DictReader(fh)}
    assert filas["2026-10-15 05:00:00"]["Distancia_km"] == ""
    assert filas["2026-10-14 13:05:00"]["Distancia_km"] == "1.08"


def test_vrp_cero_no_se_guarda():
    from scraper_ocr import fila_vrp_sin_geometria
    assert fila_vrp_sin_geometria("Nevados de Chillan", "VIIRS375", PASADA, 0.0, CAB_POSTERIOR) is None
    assert fila_vrp_sin_geometria("Nevados de Chillan", "VIIRS375", PASADA, "", CAB_POSTERIOR) is None


def test_dist_anterior_ilegible_o_misma_pasada_no_se_guarda():
    from scraper_ocr import fila_vrp_sin_geometria
    anterior = _utc("2026-10-15 04:00:00")
    assert fila_vrp_sin_geometria("Nevados de Chillan", "VIIRS375", PASADA, 22.13, anterior) is None
    assert fila_vrp_sin_geometria("Nevados de Chillan", "VIIRS375", PASADA, 22.13, None) is None
    # dentro de la tolerancia de V31 la fila normal ya se crea con su geometria
    assert fila_vrp_sin_geometria("Nevados de Chillan", "VIIRS375", PASADA, 22.13,
                                  _utc("2026-10-15 05:01:30")) is None


def test_viirs750_entero_lleva_nota_de_truncado_sin_coma():
    from scraper_ocr import fila_vrp_sin_geometria
    f = fila_vrp_sin_geometria("Nevados de Chillan", "VIIRS", PASADA, 14.0, CAB_POSTERIOR)
    assert "real entre 14 y 15 MW" in f["Nota_Validacion"]
    assert "," not in f["Nota_Validacion"]


# ---------------------------------------------------------------------------
# Backfill desde ocr_rechazos_cabecera.csv
# ---------------------------------------------------------------------------

COLS_RECH = ["fecha_proceso_utc", "volcan", "sensor", "fecha_pasada_utc", "vrp_mw_celda",
             "zen_deg", "azi_deg", "cabecera_dist_utc", "cabecera_latest_utc", "motivo"]


def _escribir(ruta, cols, filas):
    # LF, como el CSV real del repo (lo escribe pandas en Linux)
    with open(ruta, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows(filas)


def _rech(volcan, sensor, pasada, vrp, cab, zen="62"):
    return {"fecha_proceso_utc": "2026-10-15 09:31:00", "volcan": volcan, "sensor": sensor,
            "fecha_pasada_utc": pasada, "vrp_mw_celda": vrp, "zen_deg": zen, "azi_deg": "-84",
            "cabecera_dist_utc": cab, "cabecera_latest_utc": cab,
            "motivo": "Dist.png es de otra pasada (POSTERIOR: ...)"}


def _armar(tmp_path):
    from scraper_ocr import COLUMNAS_OCR
    rech, ocr, cons = tmp_path / "rech.csv", tmp_path / "ocr.csv", tmp_path / "cons.csv"
    _escribir(rech, COLS_RECH, [
        _rech("Nevados de Chillan", "VIIRS375", "2026-10-15 05:00:00", "22.13", "2026-10-15 06:00:02"),
        _rech("Nevados de Chillan", "VIIRS", "2026-10-15 05:00:00", "14.0", "2026-10-15 06:00:02"),
        _rech("Isluga", "VIIRS375", "2026-10-14 05:12:00", "0", "2026-10-14 05:30:01"),      # VRP 0
        _rech("Lascar", "VIIRS375", "2026-10-14 05:12:00", "0.5", "2026-10-14 04:30:01"),    # anterior
        _rech("Lascar", "MODIS", "2026-10-14 06:00:00", "0.9", ""),                            # ilegible
        _rech("Chaiten", "VIIRS", "2026-10-11 04:36:00", "1.0", "2026-10-11 05:36:02"),      # ya en la tabla
    ])
    existente = {c: "" for c in COLUMNAS_OCR}
    # misma pasada (mismo minuto, otros segundos) ya en el OCR: no se duplica
    existente.update({"timestamp": "1792040441", "Fecha_Satelite_UTC": "2026-10-15 05:00:41",
                      "Volcan": "Nevados de Chillan", "Sensor": "VIIRS", "VRP_MW": "14.0",
                      "Distancia_km": "0.9", "Tipo_Registro": "ALERTA_TERMICA_OCR",
                      "Nota_Validacion": "Estrella verde en Y=287 -> 0.9 km"})
    _escribir(ocr, COLUMNAS_OCR, [existente])
    _escribir(cons, ["timestamp", "Fecha_Satelite_UTC", "Volcan", "Sensor", "VRP_MW", "Distancia_km",
                     "Tipo_Registro"],
              [{"timestamp": "1", "Fecha_Satelite_UTC": "2026-10-11 04:36:00", "Volcan": "Chaiten",
                "Sensor": "VIIRS", "VRP_MW": "1.0", "Distancia_km": "2.0", "Tipo_Registro": "ALERTA_TERMICA"}])
    return rech, ocr, cons


def test_backfill_agrega_solo_lo_que_corresponde_sin_duplicar(tmp_path):
    import backfill_vrp_sin_geometria_v31 as bf
    rech, ocr, cons = _armar(tmp_path)
    antes = ocr.read_bytes()
    nuevas, descartes = bf.filas_a_agregar(str(rech), str(ocr), str(cons))
    assert [(f["Volcan"], f["Sensor"], f["Fecha_Satelite_UTC"], f["VRP_MW"]) for f in nuevas] == [
        ("Nevados de Chillan", "VIIRS375", "2026-10-15 05:00:00", 22.13)]
    assert descartes["ya_existe"] == 2               # VIIRS 05:00 en el OCR y Chaiten en la tabla
    assert descartes["no_posterior_o_vrp_no_positivo"] == 3
    bf.agregar(nuevas, str(ocr))
    # las filas existentes no se tocan: el archivo nuevo empieza con el viejo
    assert ocr.read_bytes().startswith(antes)
    with open(ocr, newline="", encoding="utf-8") as fh:
        filas = list(csv.DictReader(fh))
    assert len(filas) == 2
    nueva = filas[-1]
    assert nueva["Distancia_km"] == "" and nueva["VRP_MW"] == "22.13"
    assert nueva["Tipo_Registro"] == "ALERTA_SIN_GEOMETRIA_OCR"
    assert nueva["Metodo_Validacion"] == "vrp_sin_geometria_propia"
    assert "backfill" in nueva["Nota_Validacion"]
    # fin de linea: el archivo es LF y lo agregado tambien (sin CRLF mezclado)
    assert b"\r\n" not in ocr.read_bytes()
    # idempotente
    nuevas2, _ = bf.filas_a_agregar(str(rech), str(ocr), str(cons))
    assert nuevas2 == []
    # el log de rechazos no se modifica
    assert sum(1 for _ in open(rech, encoding="utf-8")) == 7


# ---------------------------------------------------------------------------
# Consumidores dentro de Mirova-v1: la distancia vacia no rompe ni se lee como 0
# ---------------------------------------------------------------------------

def test_maestro_publica_la_fila_con_distancia_vacia(tmp_path, monkeypatch):
    from scraper_ocr import fila_vrp_sin_geometria, COLUMNAS_OCR
    import merger_maestro
    monkeypatch.chdir(tmp_path)
    os.makedirs("monitoreo_satelital")
    f = fila_vrp_sin_geometria("Nevados de Chillan", "VIIRS375", PASADA, 22.13, CAB_POSTERIOR)
    pd.DataFrame([f])[COLUMNAS_OCR].to_csv(merger_maestro.DB_OCR, index=False)
    merger_maestro.merge()
    with open(merger_maestro.DB_PUBLICABLE, newline="", encoding="utf-8") as fh:
        filas = list(csv.DictReader(fh))
    assert len(filas) == 1
    assert filas[0]["VRP_MW"] == "22.13"
    assert filas[0]["Distancia_km"] == ""
    assert filas[0]["Tipo_Registro"] == "ALERTA_SIN_GEOMETRIA_OCR"


def test_reconciliacion_del_tipo_sin_geometria(tmp_path):
    """Caso Isluga 2026-10-14: la pasada de las 05:12 (0,08 MW) queda sin geometria;
    la de las 05:30 figura en la tabla como FALSO_POSITIVO a 9,07 km. Un FP de OTRA
    pasada no la reclasifica (no se sabe si es el mismo foco): sigue en su estrato.
    Si la tabla trae ESA MISMA pasada como FP, la tabla conoce la distancia y gana."""
    from scraper_ocr import fila_vrp_sin_geometria, COLUMNAS_OCR
    import reconciliar_latest
    f = fila_vrp_sin_geometria("Isluga", "VIIRS375", _utc("2026-10-14 05:12:00"), 0.08,
                               _utc("2026-10-14 05:30:01"))
    fp_0530 = {"timestamp": int(_utc("2026-10-14 05:30:01").timestamp()), "Volcan": "Isluga",
               "Sensor": "VIIRS375", "Distancia_km": 9.07, "Tipo_Registro": "FALSO_POSITIVO"}
    # como en produccion: el OCR se lee desde el CSV (la celda vacia llega como NaN)
    ruta = tmp_path / "ocr.csv"
    pd.DataFrame([f])[COLUMNAS_OCR].to_csv(ruta, index=False)
    df_ocr = pd.read_csv(ruta)
    df_ocr, n = reconciliar_latest.reconciliar(df_ocr, pd.DataFrame([fp_0530]))
    assert n == 0 and df_ocr.iloc[0]["Tipo_Registro"] == "ALERTA_SIN_GEOMETRIA_OCR"
    misma = dict(fp_0530, timestamp=f["timestamp"])
    df_ocr, n = reconciliar_latest.reconciliar(df_ocr, pd.DataFrame([misma]))
    assert n == 1 and df_ocr.iloc[0]["Tipo_Registro"] == "FALSO_POSITIVO_OCR"
    assert df_ocr.iloc[0]["Distancia_km"] == 9.07


def test_grafico_muestra_distancia_desconocida_y_no_nan():
    import visualizador
    df = pd.DataFrame({
        "timestamp": ["1792040400", "1791983100"],
        "Fecha_Satelite_UTC": ["2026-10-15 05:00:00", "2026-10-14 13:05:00"],
        "VRP_MW": [22.13, 6.0],
        "Sensor": ["VIIRS375", "MODIS"],
        "Distancia_km": [float("nan"), 1.08],
        "Tipo_Registro": ["ALERTA_SIN_GEOMETRIA_OCR", "ALERTA_TERMICA_OCR"],
        "Clasificacion Mirova": ["SIN_GEOMETRIA", "Bajo"],
        "Confianza_Validacion": ["media", "alta"],
        "Ruta Foto": ["No descargada - la imagen de MIROVA ya era de otra pasada", "No descargada"],
    })
    fig = visualizador.crear_grafico(df, "Nevados de Chillan")
    textos = " ".join(t for tr in fig.data for t in (tr.text or []) if isinstance(t, str))
    assert "Dist: desconocida (la imagen de MIROVA era de otra pasada)" in textos
    assert "nan km" not in textos
    assert "Dist: 1.1 km" in textos
    assert visualizador.texto_distancia({"Distancia_km": 0.0}) == "Dist: 0.0 km"
