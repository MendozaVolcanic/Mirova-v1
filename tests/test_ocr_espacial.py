"""
Tests del extractor espacial de Latest10NTI (requieren binario Tesseract).
Fixtures reales: grilla MODIS toda-NaN y grilla VIIRS375 con un valor.
"""
import io
import contextlib

from conftest import requiere_tesseract

import ocr_utils


@requiere_tesseract
def test_extrae_10_celdas_modis_nan(fixture_path):
    ev = ocr_utils.extraer_eventos_espacial(fixture_path("latest10nti_modis_nan.png"))
    assert len(ev) == 10
    assert all(e["vrp_mw"] == 0.0 for e in ev)  # todos NaN -> 0.0


@requiere_tesseract
def test_extrae_10_celdas_viirs(fixture_path):
    ev = ocr_utils.extraer_eventos_espacial(fixture_path("latest10nti_viirs375.png"))
    assert len(ev) == 10
    assert sum(1 for e in ev if e["vrp_mw"] > 0) == 1  # un solo VRP>0 en esta imagen


@requiere_tesseract
def test_wrapper_ordena_descendente(fixture_path):
    with contextlib.redirect_stdout(io.StringIO()):
        ev = ocr_utils.extraer_eventos_latest10nti(fixture_path("latest10nti_viirs375.png"))
    ts = [e["timestamp"] for e in ev]
    assert ts == sorted(ts, reverse=True)  # requisito de la asociación V26
    assert len(ev) == 10


def test_normalizador_ruido_tesseract():
    """Ruido conocido del benchmark: 'J/un' y año pegado a la hora."""
    assert "Jun" in ocr_utils._normalizar_texto_ocr("10-J/un-2026")
    assert "2026 07:" in ocr_utils._normalizar_texto_ocr("202607:25:00")
