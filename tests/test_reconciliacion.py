"""Tests del sweep de reconciliación OCR <-> latest.php (reconciliar_latest.py)."""
import os
import sys
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from reconciliar_latest import reconciliar

COLS_OCR = ["timestamp", "Volcan", "Sensor", "VRP_MW", "Distancia_km",
            "Tipo_Registro", "Confianza_Validacion", "Requiere_Verificacion",
            "Editado", "Nota_Validacion"]


def _ocr(ts, volcan, sensor, tipo, dist=0.0, nota="ok"):
    return dict(timestamp=ts, Volcan=volcan, Sensor=sensor, VRP_MW=2.0,
                Distancia_km=dist, Tipo_Registro=tipo, Confianza_Validacion="alta",
                Requiere_Verificacion=False, Editado="NO", Nota_Validacion=nota)


def _cons(ts, volcan, sensor, tipo, dist):
    return dict(timestamp=ts, Volcan=volcan, Sensor=sensor, VRP_MW=2.0,
                Distancia_km=dist, Tipo_Registro=tipo)


def test_reclasifica_contradiccion_exacta():
    ocr = pd.DataFrame([_ocr(100, "Lascar", "VIIRS375", "ALERTA_TERMICA_OCR")])
    cons = pd.DataFrame([_cons(100, "Lascar", "VIIRS375", "FALSO_POSITIVO", 29.6)])
    out, n = reconciliar(ocr, cons, marca="2026-06-15")
    assert n == 1
    r = out.iloc[0]
    assert r.Tipo_Registro == "FALSO_POSITIVO_OCR"
    assert r.Confianza_Validacion == "baja"
    assert r.Distancia_km == 29.6
    assert r.Editado == "AUTO"
    assert "RECONCILIADO" in r.Nota_Validacion


def test_no_toca_si_latest_es_alerta():
    # latest.php confirma DENTRO -> el OCR estaba bien, no se toca
    ocr = pd.DataFrame([_ocr(100, "Lascar", "VIIRS375", "ALERTA_TERMICA_OCR")])
    cons = pd.DataFrame([_cons(100, "Lascar", "VIIRS375", "ALERTA_TERMICA", 1.2)])
    out, n = reconciliar(ocr, cons)
    assert n == 0
    assert out.iloc[0].Tipo_Registro == "ALERTA_TERMICA_OCR"


def test_no_toca_sin_par_en_latest():
    # evento solo-imagen (no está en latest.php) -> no hay con qué contradecir
    ocr = pd.DataFrame([_ocr(100, "Lascar", "VIIRS375", "ALERTA_TERMICA_OCR")])
    cons = pd.DataFrame([_cons(999, "Lascar", "VIIRS375", "FALSO_POSITIVO", 30.0)])
    out, n = reconciliar(ocr, cons)
    assert n == 0


def test_no_toca_otro_sensor():
    # mismo ts/volcán pero OTRO sensor en latest.php -> no es la misma medición
    ocr = pd.DataFrame([_ocr(100, "Isluga", "VIIRS", "ALERTA_TERMICA_OCR")])
    cons = pd.DataFrame([_cons(100, "Isluga", "VIIRS375", "FALSO_POSITIVO", 20.0)])
    out, n = reconciliar(ocr, cons)
    assert n == 0  # cruce EXACTO por sensor; el cross-sensor queda para revisión manual


def test_idempotente():
    ocr = pd.DataFrame([_ocr(100, "Lascar", "VIIRS375", "ALERTA_TERMICA_OCR")])
    cons = pd.DataFrame([_cons(100, "Lascar", "VIIRS375", "FALSO_POSITIVO", 29.6)])
    out, n1 = reconciliar(ocr, cons, marca="2026-06-15")
    out, n2 = reconciliar(out, cons, marca="2026-06-16")
    assert n1 == 1 and n2 == 0  # segunda pasada no re-modifica
    assert out.iloc[0].Nota_Validacion.count("RECONCILIADO") == 1  # sin nota duplicada
