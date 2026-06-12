"""
Test de equivalencia (golden master): garantiza que las estructuras DERIVADAS
de volcanes.py son IDÉNTICAS al estado esperado. Si este test pasa, no hubo
cambios accidentales de configuración.

Los valores GOLDEN_* parten del estado previo al refactor (scraper.py,
ocr_utils.py, index.html, visualizador.py) con DOS cambios intencionales de
calibración (auditoría empírica 2026-06-11, ver tasks/AUDITORIA_OCR_EMPIRICA):
  1. Tupungatito Y_LIMITE_PX 257 → 243  (257 equivalía a 5.1 km; 7 km ≈ y=243)
  2. Y_EJE_X_PX 335 → 295 en todos      (el eje 0 km real está en y=295)

Ejecutar:  python tests/test_volcanes_equivalencia.py   (o: pytest tests/)
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from volcanes import VOLCANES_CONFIG, LIMITES_Y_COORDENADAS, LISTA_VOLCANES, DASHBOARD

# ---- GOLDEN: scraper.py::VOLCANES_CONFIG (estado previo) ----
GOLDEN_VOLCANES_CONFIG = {
    "355100": {"nombre": "Lascar", "id_mirova": "Lascar", "limite_km": 5.0},
    "355120": {"nombre": "Lastarria", "id_mirova": "Lastarria", "limite_km": 3.0},
    "355030": {"nombre": "Isluga", "id_mirova": "Isluga", "limite_km": 5.0},
    "357120": {"nombre": "Villarrica", "id_mirova": "Villarrica", "limite_km": 5.0},
    "357110": {"nombre": "Llaima", "id_mirova": "Llaima", "limite_km": 5.0},
    "357070": {"nombre": "Nevados de Chillan", "id_mirova": "ChillanNevadosde", "limite_km": 5.0},
    "357090": {"nombre": "Copahue", "id_mirova": "Copahue", "limite_km": 4.0},
    "357150": {"nombre": "Puyehue-Cordon Caulle", "id_mirova": "PuyehueCordonCaulle", "limite_km": 20.0},
    "358041": {"nombre": "Chaiten", "id_mirova": "Chaiten", "limite_km": 5.0},
    "357040": {"nombre": "PlanchonPeteroa", "id_mirova": "PlanchonPeteroa", "limite_km": 3.0},
    "357010": {"nombre": "Tupungatito", "id_mirova": "Tupungatito", "limite_km": 7.0},
}

# ---- GOLDEN: ocr_utils.py::LIMITES_Y_COORDENADAS (estado previo, 14 claves) ----
GOLDEN_LIMITES = {
    'Lastarria': {'Y_LIMITE_PX': 272, 'Y_EJE_X_PX': 295, 'LIMITE_KM': 3.0},
    'PlanchonPeteroa': {'Y_LIMITE_PX': 272, 'Y_EJE_X_PX': 295, 'LIMITE_KM': 3.0},
    'Peteroa': {'Y_LIMITE_PX': 272, 'Y_EJE_X_PX': 295, 'LIMITE_KM': 3.0},
    'Copahue': {'Y_LIMITE_PX': 266, 'Y_EJE_X_PX': 295, 'LIMITE_KM': 4.0},
    'Lascar': {'Y_LIMITE_PX': 257, 'Y_EJE_X_PX': 295, 'LIMITE_KM': 5.0},
    'Isluga': {'Y_LIMITE_PX': 257, 'Y_EJE_X_PX': 295, 'LIMITE_KM': 5.0},
    'Nevados de Chillan': {'Y_LIMITE_PX': 257, 'Y_EJE_X_PX': 295, 'LIMITE_KM': 5.0},
    'ChillanNevadosde': {'Y_LIMITE_PX': 257, 'Y_EJE_X_PX': 295, 'LIMITE_KM': 5.0},
    'Llaima': {'Y_LIMITE_PX': 257, 'Y_EJE_X_PX': 295, 'LIMITE_KM': 5.0},
    'Villarrica': {'Y_LIMITE_PX': 257, 'Y_EJE_X_PX': 295, 'LIMITE_KM': 5.0},
    'Chaiten': {'Y_LIMITE_PX': 257, 'Y_EJE_X_PX': 295, 'LIMITE_KM': 5.0},
    'Puyehue-Cordon Caulle': {'Y_LIMITE_PX': 148, 'Y_EJE_X_PX': 295, 'LIMITE_KM': 20.0},
    'PuyehueCordonCaulle': {'Y_LIMITE_PX': 148, 'Y_EJE_X_PX': 295, 'LIMITE_KM': 20.0},
    'Tupungatito': {'Y_LIMITE_PX': 243, 'Y_EJE_X_PX': 295, 'LIMITE_KM': 7.0},  # corregido 2026-06
}

# ---- GOLDEN: visualizador.py::VOLCANES (mismos 11 nombres) ----
GOLDEN_LISTA = ["Tupungatito", "Isluga", "Lascar", "Lastarria", "PlanchonPeteroa",
                "Nevados de Chillan", "Copahue", "Llaima", "Villarrica",
                "Puyehue-Cordon Caulle", "Chaiten"]

# ---- GOLDEN: index.html::volcanes (file stems que NO deben cambiar) ----
GOLDEN_FILES = {"Isluga", "Lascar", "Lastarria", "Tupungatito", "PlanchonPeteroa",
                "Nevados_de_Chillan", "Copahue", "Llaima", "Villarrica",
                "Puyehue_Cordon_Caulle", "Chaiten"}


def _check(nombre, ok):
    print(f"   {'✅' if ok else '❌'} {nombre}")
    return ok


def main():
    print("="*70)
    print("TEST DE EQUIVALENCIA — volcanes.py vs estado previo (golden)")
    print("="*70)
    results = []

    print("\n1) VOLCANES_CONFIG (scraper) idéntico al golden:")
    results.append(_check("VOLCANES_CONFIG", VOLCANES_CONFIG == GOLDEN_VOLCANES_CONFIG))

    print("\n2) LIMITES_Y_COORDENADAS (ocr_utils) idéntico al golden:")
    results.append(_check("LIMITES_Y_COORDENADAS", LIMITES_Y_COORDENADAS == GOLDEN_LIMITES))

    print("\n3) LISTA_VOLCANES tiene los mismos 11 nombres (orden no importa):")
    results.append(_check("set(LISTA_VOLCANES)", set(LISTA_VOLCANES) == set(GOLDEN_LISTA)))
    results.append(_check("len == 11", len(LISTA_VOLCANES) == 11))

    print("\n4) DASHBOARD: file stems preservados (no rompe iframes/CSV):")
    files_nuevos = {d["file"] for d in DASHBOARD}
    results.append(_check("file stems", files_nuevos == GOLDEN_FILES))
    results.append(_check("11 tarjetas", len(DASHBOARD) == 11))

    print("\n" + "="*70)
    if all(results):
        print("✅ TODO EQUIVALENTE — el refactor no cambia el comportamiento.")
        return 0
    else:
        print("❌ HAY DIFERENCIAS — NO continuar con el refactor.")
        # mostrar diffs útiles
        if VOLCANES_CONFIG != GOLDEN_VOLCANES_CONFIG:
            for k in set(VOLCANES_CONFIG) | set(GOLDEN_VOLCANES_CONFIG):
                if VOLCANES_CONFIG.get(k) != GOLDEN_VOLCANES_CONFIG.get(k):
                    print(f"   CONFIG[{k}]: nuevo={VOLCANES_CONFIG.get(k)} golden={GOLDEN_VOLCANES_CONFIG.get(k)}")
        if LIMITES_Y_COORDENADAS != GOLDEN_LIMITES:
            for k in set(LIMITES_Y_COORDENADAS) | set(GOLDEN_LIMITES):
                if LIMITES_Y_COORDENADAS.get(k) != GOLDEN_LIMITES.get(k):
                    print(f"   LIMITES[{k}]: nuevo={LIMITES_Y_COORDENADAS.get(k)} golden={GOLDEN_LIMITES.get(k)}")
        return 1


def test_equivalencia_golden_master():
    """Wrapper pytest: las estructuras derivadas == golden."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
