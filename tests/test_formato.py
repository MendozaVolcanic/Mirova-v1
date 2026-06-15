"""Tests del detector de formato errático de MIROVA (#1)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scraper_ocr import formato_anomalo


def test_dimensiones_calibradas_ok():
    assert formato_anomalo(850, 600) is False   # estándar
    assert formato_anomalo(850, 596) is False   # variante conocida


def test_dimensiones_inesperadas_se_marcan():
    assert formato_anomalo(800, 600) is True     # ancho distinto
    assert formato_anomalo(850, 700) is True     # alto distinto
    assert formato_anomalo(1024, 768) is True    # formato totalmente distinto
    assert formato_anomalo(0, 0) is True
