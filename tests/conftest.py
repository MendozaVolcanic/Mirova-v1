"""Configuración compartida de la suite de tests."""
import os
import shutil
import sys

import pytest

# El repo raíz al path para importar los módulos del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def _configurar_tesseract():
    """Devuelve True si el binario de Tesseract está disponible."""
    if shutil.which("tesseract"):
        return True
    ruta_win = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(ruta_win):
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = ruta_win
        return True
    return False


TIENE_TESSERACT = _configurar_tesseract()

requiere_tesseract = pytest.mark.skipif(
    not TIENE_TESSERACT, reason="binario de Tesseract no disponible"
)


@pytest.fixture
def fixture_path():
    def _path(nombre):
        return os.path.join(FIXTURES, nombre)
    return _path
