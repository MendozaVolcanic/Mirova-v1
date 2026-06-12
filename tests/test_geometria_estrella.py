"""
Tests de comportamiento del análisis visual de Dist.png (sin Tesseract):
geometría medida, estrella v2 (verde/gris), header y validación end-to-end.

Las fixtures son imágenes REALES de MIROVA que cubren los casos descubiertos
en la auditoría empírica de jun-2026 (tasks/AUDITORIA_OCR_EMPIRICA_2026-06.md):
- estrella verde (anomalía activa)         · 850×600
- estrella GRIS (detección sub-umbral)     · variante 850×596
- sin estrella (última medición NaN)       · header NONE
- espina superior CLARA (variante render)  · 850×600
"""
import cv2
import io
import contextlib

import ocr_utils


def _cargar(fixture_path, nombre):
    img = cv2.imread(fixture_path(nombre))
    assert img is not None, f"fixture no carga: {nombre}"
    return img


# ---------- geometría medida ----------

def test_geometria_600(fixture_path):
    img = _cargar(fixture_path, "dist_estrella_verde_600.png")
    geom = ocr_utils.medir_geometria_panel(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
    assert geom == (110, 295)


def test_geometria_596(fixture_path):
    img = _cargar(fixture_path, "dist_estrella_gris_596.png")
    assert img.shape[0] == 596
    geom = ocr_utils.medir_geometria_panel(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
    assert geom == (109, 293)


def test_geometria_techo_claro(fixture_path):
    """La espina superior a veces se renderiza clara (gris ~227): debe detectarse igual."""
    img = _cargar(fixture_path, "dist_techo_claro_600.png")
    geom = ocr_utils.medir_geometria_panel(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
    assert geom == (110, 295)


def test_y_a_km_reproduce_calibraciones():
    """Con la geometría estándar, la conversión reproduce las calibraciones manuales."""
    geom = (110, 295)  # 7.4 px/km
    assert abs(ocr_utils.y_a_km(295, geom) - 0.0) < 0.01
    assert abs(ocr_utils.y_a_km(257, geom) - 5.14) < 0.1   # límite 5 km
    assert abs(ocr_utils.y_a_km(272, geom) - 3.11) < 0.1   # límite 3 km
    assert abs(ocr_utils.y_a_km(148, geom) - 19.86) < 0.2  # límite 20 km
    assert abs(ocr_utils.y_a_km(243, geom) - 7.03) < 0.1   # Tupungatito 7 km


# ---------- estrella v2 + header ----------

def test_estrella_verde(fixture_path):
    img = _cargar(fixture_path, "dist_estrella_verde_600.png")
    color, y = ocr_utils.detectar_estrella_v2(img, 1.0)
    assert color == "verde"
    assert 250 <= y <= 262  # ≈5.3 km
    assert ocr_utils.leer_header_anomalia(img, 1.0) == "activa"


def test_estrella_gris(fixture_path):
    """La gris (S~38) era invisible para el detector V16; v2 debe verla."""
    img = _cargar(fixture_path, "dist_estrella_gris_596.png")
    sy = img.shape[0] / 600.0
    color, y = ocr_utils.detectar_estrella_v2(img, sy)
    assert color == "gris"
    assert 282 <= y <= 294  # ≈0.7 km
    assert ocr_utils.leer_header_anomalia(img, sy) == "none"


def test_sin_estrella_no_es_error(fixture_path):
    img = _cargar(fixture_path, "dist_sin_estrella_600.png")
    color, y = ocr_utils.detectar_estrella_v2(img, 1.0)
    assert (color, y) == (None, None)
    assert ocr_utils.leer_header_anomalia(img, 1.0) == "none"


# ---------- validación end-to-end (FASE 2) ----------

def _validar(img, volcan):
    with contextlib.redirect_stdout(io.StringIO()):
        return ocr_utils.validar_con_estrella_verde(img, volcan)


def test_validar_verde_dentro_alta(fixture_path):
    img = _cargar(fixture_path, "dist_estrella_verde_600.png")
    conf, tipo, nota = _validar(img, "Tupungatito")
    assert (conf, tipo) == ("alta", "ALERTA_TERMICA_OCR")
    assert "geometría medida" in nota


def test_validar_gris_dentro_media(fixture_path):
    img = _cargar(fixture_path, "dist_estrella_gris_596.png")
    conf, tipo, nota = _validar(img, "Isluga")
    assert (conf, tipo) == ("media", "ALERTA_TERMICA_OCR")
    assert "sub-umbral" in nota


def test_validar_verde_fuera_del_limite_falso(fixture_path):
    """La estrella de Tupungatito (~5.3 km) está FUERA para un límite de 3 km."""
    img = _cargar(fixture_path, "dist_estrella_verde_600.png")
    conf, tipo, nota = _validar(img, "Lastarria")  # límite 3 km
    assert (conf, tipo) == ("baja", "FALSO_POSITIVO_OCR")


def test_validar_sin_estrella_devuelve_none(fixture_path):
    img = _cargar(fixture_path, "dist_sin_estrella_600.png")
    conf, tipo, nota = _validar(img, "Lascar")
    assert conf is None and tipo is None
    assert "header=NONE" in nota


# ---------- FASE 1: clasificación por grupo con geometría ----------

def _evento_con_grupo(y_absoluto, geometria=(110, 295)):
    return {
        "vrp_mw": 1.5,
        "geometria_panel": geometria,
        "grupo_pixeles": {"y_absoluto": y_absoluto, "area": 12},
    }


def test_fase1_grupo_dentro(fixture_path):
    # y=280 con geometría estándar ≈ 2.0 km -> dentro de 5 km
    with contextlib.redirect_stdout(io.StringIO()):
        r = ocr_utils.clasificar_confianza(_evento_con_grupo(280), None, "Lascar")
    assert r["tipo_registro"] == "ALERTA_TERMICA_OCR"
    assert r["guardar"] is True


def test_fase1_grupo_fuera(fixture_path):
    # y=200 ≈ 12.8 km -> fuera de 5 km
    with contextlib.redirect_stdout(io.StringIO()):
        r = ocr_utils.clasificar_confianza(_evento_con_grupo(200), None, "Lascar")
    assert r["tipo_registro"] == "FALSO_POSITIVO_OCR"
    assert r["guardar"] is False


def test_fase1_tupungatito_6_5km_dentro():
    """El caso del bug histórico: 6.5 km debe ser DENTRO para Tupungatito (7 km)."""
    y_6_5km = 295 - round(6.5 * 7.4)  # ≈247
    with contextlib.redirect_stdout(io.StringIO()):
        r = ocr_utils.clasificar_confianza(_evento_con_grupo(y_6_5km), None, "Tupungatito")
    assert r["tipo_registro"] == "ALERTA_TERMICA_OCR"


def test_paso0_duplicado_latest():
    ev = {"vrp_mw": 1.0, "en_latest_php": True, "distancia_latest": 3.2, "tipo_latest": "ALERTA_TERMICA"}
    with contextlib.redirect_stdout(io.StringIO()):
        r = ocr_utils.clasificar_confianza(ev, None, "Lascar")
    assert r["tipo_registro"] == "DUPLICADO_LATEST"
    assert r["guardar"] is False


def test_vrp_invalido():
    with contextlib.redirect_stdout(io.StringIO()):
        r = ocr_utils.clasificar_confianza({"vrp_mw": 0}, None, "Lascar")
    assert r["tipo_registro"] == "VRP_INVALIDO"
    assert r["guardar"] is False
