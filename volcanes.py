"""
volcanes.py — FUENTE ÚNICA DE VERDAD de la red de vigilancia.

Antes, los 11 volcanes estaban definidos en 6 lugares con 4 formatos distintos
(scraper.py, scraper_ocr.py, ocr_utils.py ×2, visualizador.py, index.html), lo
que causaba "drift" de nombres y límites (ej: Peteroa→PlanchonPeteroa,
Tupungatito 5 vs 7 km). Ahora cada volcán se define UNA sola vez acá y todos los
módulos derivan sus estructuras desde este archivo.

Campos por volcán (clave = ID numérico de MIROVA):
  nombre        : nombre canónico usado en los CSV (NO cambiar: rompe históricos)
  id_mirova     : componente de la URL de imágenes en mirovaweb.it
  display       : nombre lindo para el dashboard (con tildes)
  region        : región administrativa de Chile
  limite_km     : radio de geofencing del cráter (validado por OVDAS)
  y_limite_px   : línea de límite en píxeles sobre el panel "Last Month" de
                  Dist.png (850×600). Geometría verificada empíricamente
                  (auditoría 2026-06-11): eje 0 km en y=295, 25 km en y=110
                  → 7.4 px/km → y_limite = 295 - 7.4*limite_km
  y_eje_x_px    : fila del eje X (dist=0 km) = 295 (medido en 33/33 imágenes)
  alias         : nombres alternativos que pueden aparecer en datos/lookups

Sin dependencias pesadas: este módulo es Python puro e importable en cualquier lado.
"""

VOLCANES = {
    # ===== ZONA NORTE =====
    "355030": dict(nombre="Isluga", id_mirova="Isluga", display="Isluga",
                   region="Tarapacá", limite_km=5.0, y_limite_px=257, y_eje_x_px=295, alias=[]),
    "355100": dict(nombre="Lascar", id_mirova="Lascar", display="Láscar",
                   region="Antofagasta", limite_km=5.0, y_limite_px=257, y_eje_x_px=295, alias=[]),
    "355120": dict(nombre="Lastarria", id_mirova="Lastarria", display="Lastarria",
                   region="Antofagasta", limite_km=3.0, y_limite_px=272, y_eje_x_px=295, alias=[]),
    # ===== ZONA CENTRO =====
    # Tupungatito: y_limite corregido 257→243 (auditoría 2026-06-11). El valor 257
    # equivalía a 5.1 km; con 7 km el límite cae en y = 295 - 7.4*7 ≈ 243.
    "357010": dict(nombre="Tupungatito", id_mirova="Tupungatito", display="Tupungatito",
                   region="Metropolitana", limite_km=7.0, y_limite_px=243, y_eje_x_px=295, alias=[]),
    "357040": dict(nombre="PlanchonPeteroa", id_mirova="PlanchonPeteroa", display="Planchón-Peteroa",
                   region="Maule", limite_km=3.0, y_limite_px=272, y_eje_x_px=295, alias=["Peteroa"]),
    "357070": dict(nombre="Nevados de Chillan", id_mirova="ChillanNevadosde", display="Nevados de Chillán",
                   region="Ñuble", limite_km=5.0, y_limite_px=257, y_eje_x_px=295, alias=["ChillanNevadosde"]),
    # ===== ZONA SUR =====
    "357090": dict(nombre="Copahue", id_mirova="Copahue", display="Copahue",
                   region="Biobío", limite_km=4.0, y_limite_px=266, y_eje_x_px=295, alias=[]),
    "357110": dict(nombre="Llaima", id_mirova="Llaima", display="Llaima",
                   region="Araucanía", limite_km=5.0, y_limite_px=257, y_eje_x_px=295, alias=[]),
    "357120": dict(nombre="Villarrica", id_mirova="Villarrica", display="Villarrica",
                   region="Araucanía", limite_km=5.0, y_limite_px=257, y_eje_x_px=295, alias=[]),
    "357150": dict(nombre="Puyehue-Cordon Caulle", id_mirova="PuyehueCordonCaulle", display="Puyehue-Cordón Caulle",
                   region="Los Ríos", limite_km=20.0, y_limite_px=148, y_eje_x_px=295, alias=["PuyehueCordonCaulle"]),
    # ===== ZONA AUSTRAL =====
    "358041": dict(nombre="Chaiten", id_mirova="Chaiten", display="Chaitén",
                   region="Los Lagos", limite_km=5.0, y_limite_px=257, y_eje_x_px=295, alias=[]),
}


def archivo_volcan(nombre):
    """Nombre de archivo (CSV/HTML) a partir del nombre canónico."""
    return nombre.replace(' ', '_').replace('-', '_')


def clasificacion_mirova(vrp_mw, es_alerta=True):
    """
    Clasificación de intensidad ÚNICA del sistema (escala logarítmica de MIROVA,
    Coppola et al. 2016): Muy Bajo <1 MW, Bajo <10, Moderado <100, Alto <1000,
    Muy Alto >=1000. Antes scraper.py y scraper_ocr.py usaban escalas distintas
    y un mismo evento recibía etiquetas diferentes según la fuente (unificado
    2026-06, decisión: escala Coppola).
    """
    if not es_alerta or vrp_mw is None or vrp_mw <= 0:
        return "NULO"
    if vrp_mw < 1:
        return "Muy Bajo"
    if vrp_mw < 10:
        return "Bajo"
    if vrp_mw < 100:
        return "Moderado"
    if vrp_mw < 1000:
        return "Alto"
    return "Muy Alto"


# ============================================================
# ESTRUCTURAS DERIVADAS (compatibilidad con el código existente)
# ============================================================

# Para scraper.py y scraper_ocr.py: dict por ID numérico.
VOLCANES_CONFIG = {
    vid: {"nombre": v["nombre"], "id_mirova": v["id_mirova"], "limite_km": v["limite_km"]}
    for vid, v in VOLCANES.items()
}

# Para ocr_utils.py: dict por NOMBRE (incluye alias), coordenadas de geofencing.
LIMITES_Y_COORDENADAS = {}
for _v in VOLCANES.values():
    _entry = {"Y_LIMITE_PX": _v["y_limite_px"], "Y_EJE_X_PX": _v["y_eje_x_px"], "LIMITE_KM": _v["limite_km"]}
    LIMITES_Y_COORDENADAS[_v["nombre"]] = _entry
    for _a in _v["alias"]:
        LIMITES_Y_COORDENADAS[_a] = _entry

# Para visualizador.py: lista ordenada de nombres canónicos.
LISTA_VOLCANES = [v["nombre"] for v in VOLCANES.values()]

# Para index.html (vía volcanes.js generado por el visualizador).
DASHBOARD = [
    {"n": v["display"], "r": v["region"], "file": archivo_volcan(v["nombre"])}
    for v in VOLCANES.values()
]
