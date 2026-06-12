"""Escala de intensidad única (MIROVA/Coppola) — bordes exactos."""
from volcanes import clasificacion_mirova


def test_escala_coppola_bordes():
    assert clasificacion_mirova(0.5) == "Muy Bajo"
    assert clasificacion_mirova(0.999) == "Muy Bajo"
    assert clasificacion_mirova(1.0) == "Bajo"
    assert clasificacion_mirova(9.99) == "Bajo"
    assert clasificacion_mirova(10.0) == "Moderado"
    assert clasificacion_mirova(99.9) == "Moderado"
    assert clasificacion_mirova(100.0) == "Alto"
    assert clasificacion_mirova(999.9) == "Alto"
    assert clasificacion_mirova(1000.0) == "Muy Alto"


def test_escala_casos_nulos():
    assert clasificacion_mirova(0) == "NULO"
    assert clasificacion_mirova(-1) == "NULO"
    assert clasificacion_mirova(None) == "NULO"
    assert clasificacion_mirova(5.0, es_alerta=False) == "NULO"


def test_misma_etiqueta_que_formula_historica_scraper():
    """La función central debe reproducir la fórmula que usaba scraper.py."""
    def vieja(vrp, alerta=True):
        if not alerta or vrp <= 0:
            return "NULO"
        v = vrp * 1e6
        if v < 1e6: return "Muy Bajo"
        if v < 1e7: return "Bajo"
        if v < 1e8: return "Moderado"
        if v < 1e9: return "Alto"
        return "Muy Alto"

    import numpy as np
    for v in np.linspace(0.001, 1500, 500):
        assert clasificacion_mirova(float(v)) == vieja(float(v)), v
