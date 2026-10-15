"""
Issue #23: columnas Fecha_Proceso_UTC y Ultima_Actualizacion_UTC.

Fenomeno: las horas de proceso del scraper se guardaban solo en hora de Chile y
sin desfase. Cuando Chile vuelve a UTC-4 (2026-04-05 03:00 UTC), la hora 23:00 a
23:59 del 2026-04-04 ocurre dos veces, y ese texto ya no se puede pasar a UTC sin
adivinar. Ademas Fecha_Proceso_GitHub suena a reloj de GitHub (UTC) y no lo es.

Las dos preguntas del instrumento:
- si el scraper o el OCR no escribieran las columnas UTC, o las escribieran desde
  otro instante que la hora de Chile, fallan los tests de "fila nueva";
- si el relleno adivinara la hora ambigua, convirtiera con un desfase fijo,
  tocara otras celdas, cambiara el fin de linea o no fuera idempotente, fallan
  los tests de relleno.
"""
import csv
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytz

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UTC = pytz.utc


def _utc(s):
    return UTC.localize(datetime.strptime(s, "%Y-%m-%d %H:%M:%S"))


def _reloj(modulo, monkeypatch, ahora):
    """Fija datetime.now() del modulo en el instante `ahora` (UTC)."""
    class _DT(datetime):
        @classmethod
        def now(cls, tz=None):
            return ahora.astimezone(tz) if tz else ahora.replace(tzinfo=None)
    monkeypatch.setattr(modulo, "datetime", _DT)


# ---------------------------------------------------------------------------
# Conversion de la historia
# ---------------------------------------------------------------------------

def test_relleno_verano_utc_menos_3():
    from horas_utc import convertir_local_cl
    assert convertir_local_cl("2026-01-15 12:00:00") == ("2026-01-15T15:00:00Z", "ok")
    # el ejemplo del informe: Chillan VIIRS 750, proceso 07:20:58 hora de Chile
    assert convertir_local_cl("2026-10-15 07:20:58") == ("2026-10-15T10:20:58Z", "ok")


def test_relleno_invierno_utc_menos_4():
    from horas_utc import convertir_local_cl
    assert convertir_local_cl("2026-07-15 12:00:00") == ("2026-07-15T16:00:00Z", "ok")
    # justo despues del cambio de abril (23:00 del 04 ya paso dos veces; 00:00 del 05 es -4)
    assert convertir_local_cl("2026-04-05 00:00:00") == ("2026-04-05T04:00:00Z", "ok")


def test_hora_ambigua_queda_vacia():
    from horas_utc import convertir_local_cl
    # 2026-04-04 23:30 ocurrio dos veces (02:30 UTC con -3 y 03:30 UTC con -4)
    assert convertir_local_cl("2026-04-04 23:30:00") == ("", "ambigua")
    assert convertir_local_cl("2026-04-04 23:00:00") == ("", "ambigua")
    assert convertir_local_cl("2026-04-04 23:59:59") == ("", "ambigua")
    assert convertir_local_cl("2026-04-04 22:59:59") == ("2026-04-05T01:59:59Z", "ok")


def test_hora_inexistente_y_vacia_quedan_vacias():
    from horas_utc import convertir_local_cl
    # 2026-09-06 a las 00:00 local Chile salta a la 01:00: 00:30 no existio
    assert convertir_local_cl("2026-09-06 00:30:00") == ("", "inexistente")
    assert convertir_local_cl("") == ("", "vacia")
    assert convertir_local_cl(None) == ("", "vacia")
    assert convertir_local_cl(float("nan")) == ("", "vacia")
    assert convertir_local_cl("ayer") == ("", "ilegible")


def test_conversion_inversa_coincide_con_la_escritura_hora_a_hora():
    """La hora de Chile se escribe con pytz y se rellena con zoneinfo: las dos
    bases de zonas deben coincidir en todo 2024 a 2027, salvo la hora ambigua."""
    from horas_utc import ahora_cl_y_utc, convertir_local_cl
    t = datetime(2024, 1, 1, tzinfo=timezone.utc)
    fin = datetime(2028, 1, 1, tzinfo=timezone.utc)
    ambiguas = 0
    while t < fin:
        cl, utc = ahora_cl_y_utc(t)
        vuelta, motivo = convertir_local_cl(cl)
        if motivo == "ambigua":
            ambiguas += 1
        else:
            assert (vuelta, motivo) == (utc, "ok"), (t, cl)
        t += timedelta(minutes=30)
    # una hora repetida por año (abril), vista por los dos lados = 2 h = 4 medias horas
    assert ambiguas == 4 * 4


# ---------------------------------------------------------------------------
# Filas nuevas: las dos columnas UTC, del mismo instante que la hora de Chile
# ---------------------------------------------------------------------------

class _Resp:
    def __init__(self, texto):
        self.text = texto
        self.status_code = 200
        self.content = b""


def _tabla_latest(filas):
    tr = "".join(f"<tr><td>{f}</td><td>{i}</td><td>x</td><td>{v}</td><td>{d}</td><td>{s}</td></tr>"
                 for f, i, v, d, s in filas)
    return f"<html><table><tbody>{tr}</tbody></table></html>"


def _preparar_scraper(monkeypatch, tmp_path, ahora, filas_latest):
    import scraper
    _reloj(scraper, monkeypatch, ahora)
    monkeypatch.setattr(scraper, "CARPETA_PRINCIPAL", str(tmp_path))
    monkeypatch.setattr(scraper, "DB_MASTER", str(tmp_path / "cons.csv"))
    monkeypatch.setattr(scraper, "DB_POSITIVOS", str(tmp_path / "pos.csv"))
    monkeypatch.setattr(scraper, "ARCHIVO_BITACORA", str(tmp_path / "bitacora.txt"))

    class _Sesion:
        def get(self, url, headers=None, timeout=None):
            return _Resp(_tabla_latest(filas_latest))
    monkeypatch.setattr(scraper.requests, "Session", _Sesion)
    return scraper


def test_scraper_fila_nueva_trae_las_dos_columnas_utc(tmp_path, monkeypatch):
    scraper = _preparar_scraper(monkeypatch, tmp_path, _utc("2026-01-15 15:00:00"),
                                [("15-Jan-2026 07:35:00", "355100", "0.0", "0.0", "MODIS")])
    scraper.procesar()
    df = pd.read_csv(tmp_path / "cons.csv", dtype=str, keep_default_na=False)
    assert list(df.columns)[-2:] == ["Fecha_Proceso_UTC", "Ultima_Actualizacion_UTC"]
    f = df.iloc[0]
    assert f["Fecha_Proceso_GitHub"] == "2026-01-15 12:00:00"     # hora de Chile, como siempre
    assert f["Fecha_Proceso_UTC"] == "2026-01-15T15:00:00Z"
    assert f["Ultima_Actualizacion"] == "2026-01-15 12:00:00"
    assert f["Ultima_Actualizacion_UTC"] == "2026-01-15T15:00:00Z"


def test_scraper_sobre_csv_viejo_conserva_proceso_y_actualiza_ultima(tmp_path, monkeypatch):
    """CSV con la cabecera vieja (13 columnas). La fila que sigue en latest.php
    conserva su Fecha_Proceso_GitHub; su UTC queda vacia para el relleno (no se
    inventa un instante que no se vio) y Ultima_Actualizacion_UTC es la de ahora.
    Una fila con Fecha_Proceso_UTC ya escrita la conserva."""
    from scraper import COLUMNAS_ESTANDAR
    viejas = [c for c in COLUMNAS_ESTANDAR if not c.endswith("_UTC") or c == "Fecha_Satelite_UTC"]
    ts = int(_utc("2026-07-15 07:35:00").timestamp())
    pd.DataFrame([{"timestamp": ts, "Fecha_Satelite_UTC": "2026-07-15 07:35:00",
                   "Fecha_Captura_Chile": "2026-07-15 03:35:00", "Volcan": "Lascar",
                   "Sensor": "MODIS", "VRP_MW": 0.0, "Distancia_km": 0.0, "Tipo_Registro": "RUTINA",
                   "Clasificacion Mirova": "NULO", "Ruta Foto": "No descargada",
                   "Fecha_Proceso_GitHub": "2026-07-15 06:00:00",
                   "Ultima_Actualizacion": "2026-07-15 06:00:00", "Editado": "NO"}])[viejas] \
        .to_csv(tmp_path / "cons.csv", index=False)
    scraper = _preparar_scraper(monkeypatch, tmp_path, _utc("2026-07-15 11:00:00"),
                                [("15-Jul-2026 07:35:00", "355100", "0.0", "0.0", "MODIS")])
    scraper.procesar()
    df = pd.read_csv(tmp_path / "cons.csv", dtype=str, keep_default_na=False)
    f = df.iloc[0]
    assert f["Fecha_Proceso_GitHub"] == "2026-07-15 06:00:00"
    assert f["Fecha_Proceso_UTC"] == ""
    assert f["Ultima_Actualizacion"] == "2026-07-15 07:00:00"
    assert f["Ultima_Actualizacion_UTC"] == "2026-07-15T11:00:00Z"

    # segunda corrida, ya con la columna escrita: se conserva
    df.loc[0, "Fecha_Proceso_UTC"] = "2026-07-15T10:00:00Z"
    df.to_csv(tmp_path / "cons.csv", index=False)
    _reloj(scraper, monkeypatch, _utc("2026-07-15 11:05:00"))
    scraper.procesar()
    f = pd.read_csv(tmp_path / "cons.csv", dtype=str, keep_default_na=False).iloc[0]
    assert f["Fecha_Proceso_UTC"] == "2026-07-15T10:00:00Z"
    assert f["Ultima_Actualizacion_UTC"] == "2026-07-15T11:05:00Z"


def test_ocr_fila_sin_geometria_trae_las_dos_columnas_utc():
    from scraper_ocr import fila_vrp_sin_geometria, COLUMNAS_OCR
    f = fila_vrp_sin_geometria("Nevados de Chillan", "VIIRS375", _utc("2026-10-15 05:00:00"),
                               22.13, _utc("2026-10-15 06:00:02"),
                               ahora_cl="2026-10-15 06:31:00",
                               ahora_utc="2026-10-15T09:31:00Z")
    assert {"Fecha_Proceso_UTC", "Ultima_Actualizacion_UTC"} <= set(COLUMNAS_OCR)
    assert f["Fecha_Proceso_UTC"] == f["Ultima_Actualizacion_UTC"] == "2026-10-15T09:31:00Z"
    # solo la hora de Chile (llamada antigua): la UTC sale de convertirla
    g = fila_vrp_sin_geometria("Nevados de Chillan", "VIIRS375", _utc("2026-10-15 05:00:00"),
                               22.13, _utc("2026-10-15 06:00:02"), ahora_cl="2026-10-15 06:31:00")
    assert g["Fecha_Proceso_UTC"] == "2026-10-15T09:31:00Z"
    # sin nada: las dos del mismo instante
    h = fila_vrp_sin_geometria("Nevados de Chillan", "VIIRS375", _utc("2026-10-15 05:00:00"),
                               22.13, _utc("2026-10-15 06:00:02"))
    from horas_utc import convertir_local_cl
    assert convertir_local_cl(h["Fecha_Proceso_GitHub"])[0] == h["Fecha_Proceso_UTC"]


# ---------------------------------------------------------------------------
# El relleno sobre un archivo
# ---------------------------------------------------------------------------

CABECERA_VIEJA = ["timestamp", "Fecha_Satelite_UTC", "Fecha_Captura_Chile", "Volcan", "Sensor",
                  "VRP_MW", "Distancia_km", "Tipo_Registro", "Clasificacion Mirova", "Ruta Foto",
                  "Fecha_Proceso_GitHub", "Ultima_Actualizacion", "Editado", "Nota_Validacion"]


def _fila(fsat, proc, ult, nota=""):
    return {"timestamp": "1", "Fecha_Satelite_UTC": fsat, "Fecha_Captura_Chile": "x",
            "Volcan": "Lascar", "Sensor": "VIIRS375", "VRP_MW": "0.25", "Distancia_km": "",
            "Tipo_Registro": "RUTINA", "Clasificacion Mirova": "NULO", "Ruta Foto": "No descargada",
            "Fecha_Proceso_GitHub": proc, "Ultima_Actualizacion": ult, "Editado": "NO",
            "Nota_Validacion": nota}


def _csv_viejo(ruta):
    filas = [
        _fila("2026-01-15 05:00:00", "2026-01-15 05:20:00", "2026-01-15 06:00:00",
              nota='Estrella "verde" en Y=287 -> 0.9 km | ok'),
        _fila("2026-07-15 05:00:00", "2026-07-15 05:20:00", "2026-07-15 06:00:00"),
        _fila("2026-04-05 02:30:00", "2026-04-04 23:40:00", "2026-04-04 23:50:00"),   # ambiguas
        _fila("2026-01-10 19:06:00", "", ""),                                         # enero sin columna
    ]
    # como lo escribe el scraper: pandas, LF
    pd.DataFrame(filas)[CABECERA_VIEJA].to_csv(ruta, index=False, lineterminator="\n")


def test_backfill_rellena_deja_ambiguas_vacias_y_no_toca_lo_demas(tmp_path):
    import backfill_horas_utc as bf
    ruta = str(tmp_path / "cons.csv")
    _csv_viejo(ruta)
    antes = open(ruta, "rb").read().split(b"\n")
    conteo, no_conv, escribio = bf.rellenar_archivo(ruta)
    assert escribio
    assert conteo["Fecha_Proceso_UTC"] == {"ok": 2, "ambigua": 1, "vacia": 1}
    assert conteo["Ultima_Actualizacion_UTC"] == {"ok": 2, "ambigua": 1, "vacia": 1}
    assert len(no_conv) == 2 and {m for _, _, m, *_ in no_conv} == {"ambigua"}
    with open(ruta, newline="", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    assert [(r["Fecha_Proceso_UTC"], r["Ultima_Actualizacion_UTC"]) for r in filas] == [
        ("2026-01-15T08:20:00Z", "2026-01-15T09:00:00Z"),   # verano, -3
        ("2026-07-15T09:20:00Z", "2026-07-15T10:00:00Z"),   # invierno, -4
        ("", ""),                                           # hora repetida en abril
        ("", ""),                                           # sin hora de Chile
    ]
    # el resto de cada linea queda byte a byte igual, con las dos columnas al final
    despues = open(ruta, "rb").read().split(b"\n")
    assert despues[0] == antes[0] + b",Fecha_Proceso_UTC,Ultima_Actualizacion_UTC"
    for a, d, r in zip(antes[1:-1], despues[1:-1], filas):
        extra = f",{r['Fecha_Proceso_UTC']},{r['Ultima_Actualizacion_UTC']}".encode()
        assert d == a + extra


def test_backfill_dos_veces_no_cambia_nada(tmp_path):
    import backfill_horas_utc as bf
    ruta = str(tmp_path / "cons.csv")
    _csv_viejo(ruta)
    bf.rellenar_archivo(ruta)
    una = open(ruta, "rb").read()
    mtime = os.path.getmtime(ruta)
    _, _, escribio = bf.rellenar_archivo(ruta)
    assert not escribio
    assert open(ruta, "rb").read() == una
    assert os.path.getmtime(ruta) == mtime


def test_backfill_no_pisa_lo_que_escribio_el_scraper(tmp_path):
    import backfill_horas_utc as bf
    ruta = str(tmp_path / "cons.csv")
    f = _fila("2026-07-15 05:00:00", "2026-07-15 05:20:00", "2026-07-15 06:00:00")
    f["Fecha_Proceso_UTC"] = "2026-07-15T09:20:07Z"      # instante exacto del scraper
    f["Ultima_Actualizacion_UTC"] = ""
    pd.DataFrame([f]).to_csv(ruta, index=False, lineterminator="\n")
    bf.rellenar_archivo(ruta)
    r = next(csv.DictReader(open(ruta, newline="", encoding="utf-8")))
    assert r["Fecha_Proceso_UTC"] == "2026-07-15T09:20:07Z"
    assert r["Ultima_Actualizacion_UTC"] == "2026-07-15T10:00:00Z"


def test_backfill_deja_el_csv_en_lf(tmp_path):
    import backfill_horas_utc as bf
    ruta = str(tmp_path / "cons.csv")
    _csv_viejo(ruta)
    bf.rellenar_archivo(ruta)
    datos = open(ruta, "rb").read()
    assert b"\r" not in datos and datos.endswith(b"\n")


def test_backfill_falla_fuerte_si_una_fila_trae_mas_campos(tmp_path):
    import pytest
    import backfill_horas_utc as bf
    ruta = tmp_path / "cons.csv"
    ruta.write_bytes(b"a,b\n1,2,3,4\n")
    with pytest.raises(SystemExit):
        bf.rellenar_archivo(str(ruta))
    assert ruta.read_bytes() == b"a,b\n1,2,3,4\n"


# ---------------------------------------------------------------------------
# El hash del deploy no debe cambiar por las columnas UTC volatiles
# ---------------------------------------------------------------------------

def _hash_deploy(cwd):
    out = subprocess.run([sys.executable, os.path.join(RAIZ, "scripts", "deploy_hash.py")],
                         cwd=cwd, capture_output=True, text=True, check=True)
    return out.stdout.strip()


def test_deploy_hash_ignora_las_columnas_utc_volatiles(tmp_path):
    """registro_vrp_positivos.csv lleva todas las columnas del consolidado y
    Ultima_Actualizacion_UTC cambia en cada corrida: si el hash la mirara, el
    sitio se republicaria cada 5 minutos sin datos nuevos."""
    (tmp_path / "monitoreo_satelital").mkdir()
    pos = tmp_path / "monitoreo_satelital" / "registro_vrp_positivos.csv"
    cab = "timestamp,VRP_MW,Ultima_Actualizacion,Fecha_Proceso_UTC,Ultima_Actualizacion_UTC\n"
    pos.write_text(cab + "1,0.5,2026-10-15 07:00:00,2026-10-15T10:00:00Z,2026-10-15T10:00:00Z\n")
    h1 = _hash_deploy(tmp_path)
    pos.write_text(cab + "1,0.5,2026-10-15 07:05:00,2026-10-15T10:00:00Z,2026-10-15T10:05:00Z\n")
    assert _hash_deploy(tmp_path) == h1
    pos.write_text(cab + "1,0.6,2026-10-15 07:05:00,2026-10-15T10:00:00Z,2026-10-15T10:05:00Z\n")
    assert _hash_deploy(tmp_path) != h1
