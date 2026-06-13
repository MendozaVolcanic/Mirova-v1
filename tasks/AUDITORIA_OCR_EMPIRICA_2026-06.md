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

---

## F. Benchmark de OCR (2026-06-11, Tesseract 5.4.0 local, 33 Latest10NTI vivas)

| Método | Pares fecha↔VRP extraídos | Inmune a desalineamiento |
|---|---|---|
| Actual (página completa, emparejado por orden) | 329/330 | ❌ (si pierde 1 fecha, corre todos los pares siguientes) |
| Por celdas v1 (cortes fijos) | 246/330 | ✅ (fallo: coordenadas de corte) |
| Por celdas v2 (posicional `image_to_data`) | 316/330 | ✅ (fallo: ruido "J/un", "202607:") |
| **Por celdas v3 (posicional + normalización)** | **330/330** | ✅ |

- v3 = OCR de las tiras de fecha/VRP con `image_to_data` (psm 6, upscale 3×), asignación
  de palabras a columnas por posición X (grilla 2×5 de 170 px), normalización de ruido
  (`J/un`→`Jun`, `202607:`→`2026 07:`), regex estricta. Escala con `h/600` → absorbe 850×596.
- Validación cruzada actual vs v3 hoy: **0 discrepancias** fecha↔VRP (no hay corrupción
  silenciosa activa en este momento; el riesgo del método actual es latente, no actual).
- Diseño recomendado: **v3 como extractor primario + método actual como fallback** si v3
  devuelve <10 pares; loguear cuando difieren.

---

## G. Semántica de la estrella RESUELTA con datos (2026-06-11, 543 hist + 33 vivas)

Cruce: posición de estrella vs `latest.php` en el timestamp exacto del "Last Update"
(leído por OCR de cada imagen). Detector gris corregido (umbral área ≥30, sin morfología).

**Conclusión (corrige la interpretación preliminar de §A.1):**
- La estrella (verde O gris) marca la **última medición CON detección (VRP>0)**;
  su posición Y es la **distancia de esa detección**. Error mediano: verde 0.06 km
  (n=446), gris 0.15 km (n=13) → la posición es confiable en ambos colores.
- El **color** replica el banner "Thermal anomaly" de MIROVA con consistencia 100%
  (451/451 verde⇔banner verde, 13/13 gris⇔banner NONE):
  - 🟢 verde: VRP ≥ ~0.05 MW (mín verde = 0.05, mediana 0.35, máx 4.6)
  - ⚪ gris: VRP 0.02–0.05 MW → **detección real pero sub-umbral** del banner
- **Sin estrella** = la última medición no detectó nada (NaN) — no es un fallo.
- Las 13 grises históricas estaban TODAS dentro del límite de su volcán: son
  detecciones débiles reales de fondo térmico (0.02–0.05 MW), exactamente la señal
  que la escala logarítmica del dashboard busca visibilizar.

**Diseño v2 derivado:** FASE 2 debe aceptar ambos colores. Verde → confianza alta
(sin cambio); gris → confianza media + nota "detección débil sub-umbral (~X MW)".
El header "Thermal anomaly" se lee como validación cruzada del color.

---

## H. V29 implementada y validada (2026-06-12)

**Geometría medida (reemplaza Y_LIMITE_PX como mecanismo primario):**
- `medir_geometria_panel()`: detecta espinas 25km/0km por imagen. El eje siempre
  se renderiza oscuro; el techo a veces claro (gris 227) — tercera variante de
  render descubierta. Detección final: **576/576 (100%)**.
- Clasificación dentro/fuera = `km_medidos <= limite_km + 0.15` (tolerancia ~1px).
  Fallback automático a Y_LIMITE_PX si la medición falla.

**Replay de validación (576 imágenes, nueva FASE 2 vs vieja):**
| Caso | n | Resultado |
|---|---|---|
| Verde dentro | 447 | idéntico (alta/ALERTA) ✅ |
| Verde fuera | 4 | idéntico (baja/FALSO) ✅ |
| **Gris (antes invisible)** | **13** | **ahora media/ALERTA con km medidos** 🆕 |
| Sin estrella | 112 | sin cambio |
| Discrepancias con lógica vieja | **0** | equivalencia exacta |

FASE 1 (grupos rojos) también usa km medidos vía `evento['geometria_panel']`.
Header "Thermal anomaly" se lee como validación cruzada del color de estrella.

---

## I. Verificación píxeles/ROI para TODOS los volcanes (2026-06-12)

**1. Límites km↔px contra la clasificación del propio MIROVA** (el rojo/negro de
los tallos usa el límite específico de cada volcán — ground truth):
- 9.455 marcadores ROJOS en 576 imágenes de los 12 volcanes → **0 fuera del límite**.
- Máximos rojos observados confirman cada calibración: Lastarria 2.97<3,
  PlanchonPeteroa 2.99<3, Copahue 3.38<4, Isluga 4.35<5, **Tupungatito 6.93<7**
  (confirma el fix 257→243), Puyehue 12.16<20.
- (Los "negros dentro del límite" de la primera pasada eran artefactos del script
  de validación —contornos de estrella, ticks—, no del pipeline productivo.)

**2. ROI temporal vs línea punteada del "ahora"**:
- Detector por transiciones (una punteada tiene 20–40 guiones; un tallo sólido 1–2).
- **576/576 imágenes: punteada en x=730–733.** El ROI fijo (x 716–734) cubre
  exactamente [≈1.2 días antes del ahora → ahora] en todos los volcanes/épocas.
- La alarma inicial (52 "outliers") era un falso positivo del primer detector
  (columnas de tallos altos). Verificado visualmente (Láscar 20-Feb: punteada en
  ~733 con la estrella encima, ROI correcto).

**Conclusión:** geometría, límites y ROI verificados para los 11 volcanes (12
configs con Peteroa legacy) contra 5 meses de imágenes. Mejora opcional de
blindaje: anclar el ROI a la punteada detectada (mismo patrón medido-primario /
fijo-fallback); prioridad baja dado 576/576 estable.

**Corrección importante sobre ZEN/AZI:** revisando los Latest10NTI, ZEN/AZI son
los ángulos de VISIÓN DEL SATÉLITE (geometría de la pasada), NO el azimut del
foco respecto al cráter. Para el análisis de sector de Nevados, la dirección
está en la POSICIÓN del píxel caliente dentro del thumbnail (escena centrada en
el volcán): un foco a ~7 km al NE aparece desplazado al NE del centro.

---

## J. Barrido de estado-ANOMALÍA: 580 imágenes Latest + cruce vs latest.php (2026-06-12)

**Método:** extractor espacial V28 sobre las 580 Latest10NTI guardadas en alertas
(5.746 lecturas de celda) cruzadas contra el consolidado (verdad terreno), más
taxonomía visual e hipótesis de oclusión del ROI.

### J1. El OCR lee BIEN — los "errores" eran del gráfico
- Tasa de coincidencia en celdas cruzables: **93.8%**, y de los 264 "VRP difiere",
  **262 siguen el patrón exacto de truncado a entero, TODOS VIIRS750/MODIS**.
- **Confirmado visualmente**: los paneles VIIRS750/MODIS muestran "VRP =1 MW"
  donde latest.php dice 1.05; "VRP =0 MW" donde dice 0.33. **MIROVA renderiza el
  VRP truncado a entero en esos sensores** (VIIRS375 sí muestra 2 decimales).
- Consecuencias: (a) eventos VIIRS750/MODIS de 0.01–0.99 MW aparecen como
  "VRP =0" → el OCR los trata como inválidos y LOS DESCARTA aunque la celda tenga
  borde verde (= detección real de MIROVA); (b) los valores 1.x guardados por OCR
  de esos sensores tienen precisión ±1 MW.
- Texto ROJO de las celdas en alerta: se lee sin problema (los rojos matchearon).
- Solo 2/5.746 lecturas fueron misreads reales (0.0 vs 1.0, MODIS).

### J2. Latest10NTI contiene mediciones que latest.php NO tiene
- 1.422 lecturas sin match en cobertura → deduplicadas: **666 mediciones únicas**
  (531 VIIRS375), de las cuales **213 con VRP>0**.
- Verificado visualmente (Chaitén 12-ene): los paneles muestran gránulos
  (06:06:00, 04:30:00, 18:42:00…) que latest.php nunca listó (tiene 06:30:01,
  04:48:01…). **MIROVA publica más gránulos por pasada en las imágenes que en la
  tabla** → esta es la justificación cuantificada del scraper OCR: ~213 eventos
  VRP>0 en 5 meses solo accesibles por imagen.

### J3. La estrella OCLUYE el ROI en estado de anomalía
- 448/448 estrellas verdes caen dentro del rango X del ROI (la estrella se dibuja
  sobre la línea punteada del "ahora", que el ROI cubre).
- En **69/448 (15%)** la estrella tapa POR COMPLETO el círculo rojo del evento →
  cero píxeles rojos en ROI → FASE 1 ciega y todo recae en FASE 2 (consistente
  con que las notas del CSV estén dominadas por validación-por-estrella).
  Es una limitación DEL GRÁFICO, no de la lectura.

### J4. Otras variantes confirmadas en estado anomalía
- Cada celda con VRP>0 lleva: borde verde + fecha en ROJO + "VRP =X MW" en ROJO
  (múltiples celdas a la vez, no solo la última).
- La variante 850×596 también existe en Latest (36/580); V28 la absorbe (escala h/600).
- Carpetas de evidencia con nombres duplicados ('Nevados de Chillan' vs
  'Nevados_de_Chillan', 'Puyehue-Cordon Caulle' vs '_'): scraper y OCR normalizan
  distinto — pendiente unificar con archivo_volcan() de volcanes.py.

### J5. Mejoras candidatas derivadas
1. **Celdas "VRP =0" con borde verde (VIIRS750/MODIS)**: detectar el borde verde
   de la celda y, si VRP=0, guardar como detección "<1 MW (precisión del gráfico)"
   con confianza media en vez de descartar.
2. **Nota de precisión**: marcar eventos OCR de VIIRS750/MODIS como ±1 MW.
3. **ROI anclado a la línea punteada** (mitiga parcialmente la oclusión, baja prioridad).
4. Unificar normalización de carpetas de evidencia con volcanes.archivo_volcan().

---

## K. VERIFICACIÓN CIEGA del truncado VIIRS750/MODIS (2026-06-12)

Para validar §J1 sin depender del extractor propio: 6 imágenes Latest de Láscar
(2 VIIRS750, 2 MODIS, 2 VIIRS375) leídas por 6 agentes-visión independientes que
transcribieron el texto literal de cada panel SIN conocer la hipótesis. Luego
cruce de cada lectura contra latest.php (consolidado) en el mismo timestamp.

**Resultado (prueba):**
- VIIRS750/MODIS: **9/9** enteros == floor(valor real de latest.php).
  Ejemplos: php 3.39→"3", 2.53→"2", 1.03→"1", 0.27→"0", 0.62→"0".
- VIIRS375: **7/7** decimales == valor exacto de latest.php (0.74, 1.22, 2.55…).
- 2 detecciones reales (header VERY LOW/LOW) renderizadas como "VRP =0":
  VIIRS750 25-Feb (php 0.27) y MODIS 15-Feb (php 0.62). → truncado CONFIRMADO.

**Alcance HONESTO de la pérdida (cuantificado):**
- latest.php (scraper primario) ya captura CON decimales todo lo que está en su
  tabla; el truncado solo causa pérdida en granulos que viven SOLO en la imagen.
- Granulos solo-imagen en VIIRS750/MODIS (5 meses): **135**.
  - 24 leídos como entero >0 → capturados pero imprecisos (±1 MW) → aplica nota de precisión.
  - 111 leídos como 0/NaN → CANDIDATOS a detección sub-1 invisible (cota superior;
    parte serán NaN reales por nube — solo el borde verde de celda los distingue).
- Magnitud: ~decenas a ~100 detecciones DÉBILES (<1 MW) de fondo en 5 meses.
  No son alertas mayores perdidas; es completitud/precisión del fondo térmico.

**Conclusión:** truncado real y probado; rescate (borde-verde + nota ±1 MW)
recupera señal débil de fondo de magnitud modesta. Decisión de implementar = de Nicolás.

### K2. El rescate por "borde verde" NO es viable (refutado 2026-06-12)
Test de la regla sobre las 60 celdas etiquetadas a ciegas: **borde verde ⟺ valor
MOSTRADO > 0** → **60/60**. El borde verde sigue el MISMO valor truncado, no aporta
información extra. Confirmado en píxeles: la celda VIIRS750 de 0.27 MW real (img_1 p1,
header VERY LOW) muestra "VRP =0 MW" Y tiene 0 px verdes (borde gris). Idem MODIS 0.62.
→ Una detección sub-1 MW en VIIRS750/MODIS es **invisible** en Latest10NTI (ni número
ni borde). Solo recuperable por latest.php (que ya la tiene) o leyendo logVRP.png por
píxel (impreciso). **Implementado solo lo válido:** nota de precisión ±1 MW en eventos
VIIRS750/MODIS (V29.1). Rescate de los 111 image-only sub-1: NO se implementa (sin señal
visual que los distinga de NaN). Alternativa posible pero marginal: punto rojo del Dist.png
en ROI con texto=0 → diferida.
