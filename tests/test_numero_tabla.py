"""Tests de la lectura de numeros de latest.php (issue #19: VRP con coma de miles)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scraper import numero_tabla


def test_numero_simple():
    assert numero_tabla("0.18") == 0.18
    assert numero_tabla(" 12.5 ") == 12.5


def test_coma_de_miles_del_issue_19():
    assert numero_tabla("1,234.5") == 1234.5
    assert numero_tabla("2,178.53") == 2178.53
    assert numero_tabla("1,357") == 1357.0
    assert numero_tabla("12,345,678.9") == 12345678.9


def test_coma_decimal_no_se_lee_como_miles():
    with pytest.raises(ValueError):
        numero_tabla("0,5")
    with pytest.raises(ValueError):
        numero_tabla("1,23")


def test_texto_basura_falla():
    with pytest.raises(ValueError):
        numero_tabla("NaN MW")
