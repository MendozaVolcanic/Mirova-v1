"""Reparacion del mojibake de las notas del OCR (auditoria 2026-10-22, H-O8; S139 H203).

POR QUE: el commit manual ffc7a97d8b (2026-06-12) leyo registro_vrp_ocr.csv como cp1252 y lo
escribio como UTF-8: 647 notas quedaron con "pÃ­xeles" y "distâ‰ˆ" en vez de "píxeles" y "dist≈",
y el lector de VRP Chile no encuentra la distancia. Algunas notas mezclan la parte vieja corrupta
con texto agregado despues, limpio: hay que reparar tramo por tramo, no la nota entera.
"""
from reparar_mojibake import reparar_texto


def test_repara_tramos_corruptos():
    assert reparar_texto("Estrella en Y=282 (dentro lÃ­mite Y=257, distâ‰ˆ3.40 km)") == \
        "Estrella en Y=282 (dentro límite Y=257, dist≈3.40 km)"
    assert reparar_texto("Grupo pÃ­xeles rojos") == "Grupo píxeles rojos"


def test_nota_mixta_repara_solo_la_parte_vieja():
    mixta = "pÃ­xeles distâ‰ˆ1.2 km | RECLASIFICADO 2026-06-15: latest.php dice 22 km, dist≈22 km"
    assert reparar_texto(mixta) == \
        "píxeles dist≈1.2 km | RECLASIFICADO 2026-06-15: latest.php dice 22 km, dist≈22 km"


def test_texto_limpio_no_cambia():
    for t in ["Estrella en Y=282 (dentro límite, dist≈3.40 km)", "Volcán Chaitén ñ", "", "sin acentos"]:
        assert reparar_texto(t) == t


def test_es_idempotente():
    t = "pÃ­xeles distâ‰ˆ3.40 km"
    assert reparar_texto(reparar_texto(t)) == reparar_texto(t)


def test_valores_no_texto_pasan_igual():
    assert reparar_texto(None) is None
    assert reparar_texto(3.5) == 3.5
