# 🔬 Auditoría empírica del pipeline OCR — Mirova-v1
**Fecha:** 2026-06-11 · **Método:** análisis de 66 imágenes vivas (11 volcanes × 3 sensores × Dist+Latest10NTI) + 543 imágenes históricas del repo + CSV OCR vivo (644 reg) + exploración del sitio MIROVA.
**Material de trabajo:** carpeta `_audit/live/` (66 imágenes de referencia, útiles como fixtures de tests).

---

## A. Semántica de los gráficos MIROVA (decodificada)

1. **La estrella SIEMPRE marca la última medición**, y su **color codifica el estado**:
   - 🟢 **Verde** RGB≈(4,222,5), saturación ~250 → anomalía térmica ACTIVA (header "Thermal anomaly: VERY LOW/LOW/...", caja verde).
   - ⚪ **Gris/plateada** saturación media ~38 → última medición con VRP=0/NaN (header "NONE").
   - **Ausencia de estrella verde NO es error**: 30/33 imágenes vivas no la tienen porque no hay anomalía activa.
   - Ejemplo de estrella gris confirmado: `Isluga/2026-03-11/06-36-01_Isluga_VIIRS375_Dist.png`.

2. **MIROVA ya clasifica por color según el límite DEL VOLCÁN**: la leyenda del panel "Last Year" es `>Xkm / <Xkm` donde X = límite específico (5 para Láscar, 7 para Tupungatito). **Tallos/círculos rojos = dentro del límite; negros = fuera.** El rojo es la clasificación de MIROVA, no solo "color de alerta".

3. **Header "Thermal anomaly: <estado>"** en todas las imágenes (caja verde cuando activa) → señal gratuita aún no explotada.

4. **Geometría del panel "Last Month"** (en 850×600): eje 0 km en **y=295**, techo 25 km en **y=110** → escala **7.4 px/km**, uniforme en las 33 imágenes vivas (verificado por detección de espinas). Eje X: gráfico ~x280–810 (~35 días → ~15.1 px/día; el ROI de 18 px ≈ 1.2 días ✓).

## B. Bugs de calibración CONFIRMADOS

| # | Bug | Evidencia | Impacto |
|---|---|---|---|
| **B1** | **Tupungatito `Y_LIMITE_PX=257` ≡ 5.1 km, no 7 km.** Correcto: **~243** (295−7.4×7) | Recta ajustada con las otras 4 calibraciones reproduce 272/266/257/148 al píxel; 7 km→243 | Eventos entre 5.1–7 km → FALSO_POSITIVO erróneo. La estrella de HOY (11-jun, y≈255 ≈5.4 km, VERY LOW) se clasifica mal |
| **B2** | **`Y_EJE_X_PX=335` mal; el eje real es 295** | Espina medida en y=295 (33/33) | Las distancias de las notas están infladas ~2× (ej: Y=283 reporta 3.33 km, real ≈1.6 km). NO afecta la clasificación dentro/fuera |
| **B3** | **Dos tamaños de imagen coexisten: 850×600 (504 hist.) y 850×596 (39 hist., intermitente, 85% VIIRS375)** | Ene–Mar 2026, eje en y=293 (no 295) | Corrimiento de ~2 px en los límites con calibración absoluta; riesgo mayor si MIROVA cambia más |
| **B4** | **Detector de estrella ciego a la GRIS** (exige S≥80; la gris tiene S~38) | Isluga 11-Mar y otros | FASE 2 no valida cuando estado=NONE. Relevante: las notas del CSV muestran que **FASE 2 (estrella) domina las validaciones guardadas** |
| **B5** | **Emparejamiento fecha↔VRP por orden** (`extraer_eventos_latest10nti`): si Tesseract pierde UNA fecha pero lee su VRP, **todos los pares siguientes quedan corridos** | Diseño V11 (riesgo latente) | Eventos con timestamp/VRP cruzados. Mejor: emparejar por posición espacial (grilla 2×5) |

## C. Sobre el sitio MIROVA (exploración completa)

- **No existe fuente estructurada** más allá de `latest.php`: las páginas `volcanoDetails_*.php` solo embeben los mismos PNG; no hay endpoints JSON/tabla (probados: dashboard, timeseries, map, scheda). **El OCR sigue siendo necesario** para recuperar eventos que latest.php rota.
- Existen secciones por sensor adicionales: `volcanoDetails_MSI.php` (Sentinel-2), `OLI` (Landsat), `SWIR`, `MIR` → posible fuente futura de evidencia (conexión con proyecto VRP Chile).
- `Latest10NTI` trae **ZEN y AZI** por medición → el azimut está disponible por OCR para análisis de sector (ej. cúmulo de Nevados a ~7 km).
- Layout de Latest10NTI **uniforme entre sensores** (MODIS = VIIRS): grilla 2×5, fechas `DD-Mon-YYYY HH:MM:SS`, `VRP =X MW`/`NaN`.

## D. Señales del CSV OCR vivo (644 registros)

- `Color_Punto_Dist`: "mixto" en 595/644 → la clasificación global de ROI casi nunca es informativa (los métodos por grupo/estrella son los que deciden).
- Métodos mezclados de versiones viejas (v17–v26) conviven en el CSV (esperable).
- Las distancias en notas (~2×) son consecuencia de B2.

## E. Mejoras propuestas (orden sugerido)

1. **Fix inmediato B1+B2** en `volcanes.py`: Tupungatito 243; `y_eje_x_px` 295 (todos). Recupera eventos 5.1–7 km YA.
2. **Item #4 reforzado (calibración auto-adaptativa)**: en vez de px fijos, detectar el eje (espina continua, algoritmo ya probado en esta auditoría) y mapear `y(km) = y_eje − 7.4·(600/alto)·km`... o directamente `y(km) = y_eje_detectado − (y_eje−y_techo)/25·km`. Absorbe 596/600 y futuros cambios; si la detección falla → warning y fallback a calibración fija.
3. **Detector de estrella v2**: verde (actual) **+ gris** (blob brillante baja saturación, tamaño de marcador, en zona de panel). Reportar color como estado de anomalía.
4. **Leer el header "Thermal anomaly"** (color de la caja) como señal adicional de contexto.
5. **Emparejamiento espacial** fecha↔VRP en Latest10NTI (por celdas de la grilla 2×5 con `pytesseract.image_to_data`), eliminando el riesgo de corrimiento.
6. **Extraer AZI** en el OCR → análisis de sector (pendiente Nevados).
7. (Futuro) Explorar `MSI/OLI` de MIROVA como evidencia adicional Sentinel-2/Landsat.
