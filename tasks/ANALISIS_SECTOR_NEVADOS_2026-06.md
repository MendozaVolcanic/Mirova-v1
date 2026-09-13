# 🧭 Análisis de sector: cúmulo térmico de Nevados de Chillán (5-8 km)
**Fecha:** 2026-06-12 · **Fuente:** NASA FIRMS (VIIRS 375m S-NPP/NOAA-20/NOAA-21 + MODIS),
mapa interactivo con archivo · **Referencia cráter:** -36.868, -71.378 (centrado MIROVA).

## Contexto
El geofence de 5 km de Nevados descarta como FALSO_POSITIVO un cúmulo recurrente a
6.2-8.25 km (36 detecciones VRP>0 en MIROVA entre 18-ene y 01-jun-2026, picos 34-72 MW).
Pregunta: ¿es volcánico/geotermal (fuente fija) o no volcánico? El dato decisivo es la
POSICIÓN, que MIROVA no entrega. FIRMS sí (lat/lon por píxel).

## Posiciones medidas (FIRMS)

| Episodio | Fechas | Coordenadas (centroide) | Rumbo/dist desde cráter | FRP |
|---|---|---|---|---|
| Enero | 18-19 ene | **-36.873, -71.291/-71.303** | **E (~95°), ~7.4 km** | 82.2 y 20.9 MW (día, MODIS) |
| Abril | 14-15 abr | misma zona ENE, 3 sub-grupos dispersos ~2 km | ENE | hasta 44 MW (MIROVA) |
| Mayo-junio | 27 may-1 jun | **-36.840/-36.847, -71.295/-71.321** | **ENE (~67°), ~6.6 km** | día: 38.4, 19.1, 10.1 MW · noche: 0.6-1.5 MW (4 noches seguidas) |

Detalle mayo-jun (VIIRS/NOAA-21, hora local GMT-4): 28-may 14:49 (2.36 D); 29-may 02:10
(1.47 N); 30-may 01:53 (0.61 N) y 14:11 (10.09 D); 31-may 01:31 (4 píxeles, 0.83-0.88 N)
y 13:54 (19.13 + 38.36 D); 01-jun 01:14 (1.05 N).

## Observaciones diagnósticas

1. **No es una fuente fija**: el centroide de enero (-36.873, -71.30) está ~3.3 km al SSE
   del de mayo (-36.844, -71.31). Episodios distintos ocurren en puntos distintos del
   mismo corredor E-ENE. Una fuente geotermal/volcánica fija no se mueve.
2. **Terreno**: las detecciones caen sobre laderas VEGETADAS de un cajón cordillerano
   (imagen satelital), no sobre terreno volcánico desnudo ni campo fumarólico conocido
   (el sistema geotermal conocido del complejo está al NW, en Termas, no al E).
3. **Patrón día/noche**: dominancia diurna fuerte (27 de 36 det. MIROVA; FRP día 10-82 MW
   vs noche 0.6-3.1 MW). Las noches muestran combustión residual (smoldering) que decae.
4. **Estacionalidad de los episodios**: enero (plena temporada de incendios) y
   abril-mayo (temporada de quemas agrícolas/forestales en Ñuble antes de las lluvias).
5. **Multi-sensor** (VIIRS×2/3 + MODIS) → fenómeno de superficie real, no artefacto.

## Interpretación (a validar por Nicolás)
Todo el patrón (móvil entre episodios, sobre vegetación, diurno con rescoldo nocturno,
estacional) es consistente con **incendios/quemas de vegetación recurrentes en el
corredor de valles al E-ENE del complejo** (~6.5-8 km del cráter), y NO con actividad
volcánica o geotermal. La decisión de mantener el geofence de 5 km parece correcta;
estos eventos son legítimamente FALSO_POSITIVO.

## Implicancias operativas (opcionales)
- Mantener límite 5 km de Nevados (los 6.5-8 km E-ENE son quemas, no volcán). ✔ decisión ya tomada
- Si se quiere trazabilidad futura: guardar el thumbnail Latest10NTI como evidencia
  diagnóstica cuando Nevados tenga FALSO_POSITIVO en 5-9 km (hoy no se guarda nada).
- FIRMS como herramienta de verificación de sector ante cualquier cúmulo sospechoso
  (mapa: firms.modaps.eosdis.nasa.gov/map, funciona sin API key; con key de SERNAGEOMIN
  se puede automatizar por API).
