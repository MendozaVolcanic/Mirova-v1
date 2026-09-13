# 🔬 Auditoría Técnica Profunda: Mirova-v1 (V5.0)
**Fecha:** 2026-06-10 · **Auditor:** Claude (Opus 4.8) · **Para:** Nicolás Mendoza (SERNAGEOMIN)
**Objetivo:** Entendimiento completo del sistema para planificar mejoras.

---

## 1. Qué es el sistema (en una frase)

Un **nodo de respaldo, archivo y visualización** que scrapea datos térmicos públicos de **MIROVA** (Univ. Turín, sensores MODIS/VIIRS de NASA) para 11 volcanes chilenos, los filtra por cercanía al cráter (geofencing), y los publica en un dashboard en GitHub Pages. No mide nada propio: depende 100% de MIROVA.

**Cadena de datos:**
```
                  cron externo cada 5 min                cron GitHub cada 1 h
                          │                                      │
                          ▼                                      ▼
  latest.php ──scraper.py──► registro_vrp_consolidado.csv   Latest10NTI.png + Dist.png
  (tabla HTML)                       │                       ──scraper_ocr.py──► registro_vrp_ocr.csv
                                     │                                      │
                                     └──────────► merger_maestro.py ◄───────┘
                                                       │
                                     registro_vrp_maestro_publicable.csv
                                     + registro_<Volcan>.csv (11)
                                                       │
                                            visualizador.py (Plotly)
                                       v_html/*.html  +  v_html_log/*.html
                                                       │
                                            index.html (GitHub Pages)
```

---

## 2. Inventario de módulos

| Archivo | Rol | Estado |
|---|---|---|
| `scraper.py` | Fuente primaria: parsea tabla `latest.php` (BeautifulSoup). Clasifica ALERTA/FALSO/RUTINA por distancia. Descarga evidencia si alerta. | OK, con deuda |
| `scraper_ocr.py` (V21) | Fuente secundaria: descarga imágenes, las pasa a `ocr_utils`, dedup contra latest.php. | OK, complejo |
| `ocr_utils.py` (V27) | **Cerebro**: OCR Tesseract + visión OpenCV (ROI temporal, grupos de píxeles rojos, estrella verde, geofencing en px). | OK, frágil (px hardcodeados) |
| `merger_maestro.py` (V17) | Fusiona consolidado + OCR, dedup, filtra a publicable, genera CSV por volcán. | OK, con bug menor |
| `visualizador.py` (V4.1) | Genera gráficos Plotly duales (lineal/log) de 30 días por volcán + `estado_sistema.json`. | OK |
| `index.html` | Dashboard: 11 tarjetas con iframes, toggle escala, semáforo, descarga CSV. | OK |
| `validar_sistema_v17.py` | Anti-regresión local: grep de constantes críticas. | OK |
| `diagnostico_github.py` | Smoke-test del entorno CI (imports, archivos). | OK, no usado en workflows |
| `.github/workflows/*` (4) | main (scraper), ocr_workflow, graficos_completo, validar_funcionalidades. | ✅ arreglados 2026-06-10 |

**Configuración clave (los 11 volcanes):**
- `VOLCANES_CONFIG` (en scraper.py y scraper_ocr.py): mapea ID numérico MIROVA → nombre + id_mirova + límite km.
- `LIMITES_Y_COORDENADAS` (ocr_utils.py): nombre → `Y_LIMITE_PX` (línea de límite en píxeles), `Y_EJE_X_PX=335`, `LIMITE_KM`.
- `ROI_CONFIG` (ocr_utils.py): ventana temporal en % (x: 84.24-86.35%, y: 18.17-49.33%) = "último día" del gráfico Dist.

---

## 3. Lógica del pipeline OCR (lo más sofisticado del sistema)

Por cada volcán × sensor (VIIRS375, VIIRS750, MODIS), cada hora:

1. **`extraer_eventos_latest10nti()`**: Tesseract con 3 configs de respaldo (psm 6/4/11). Regex extrae fechas y VRP (NaN→0). Empareja por orden → hasta 10 eventos.
2. **Filtro 24h (V18)**: descarta eventos > 24h.
3. **`obtener_contexto_latest()` (V27)**: busca en consolidado eventos ±10 min; los separa en **lejanos** (>límite → estrella verde / FALSO en latest.php) y **cercanos** (≤límite → ya en latest.php). Calibración cruzada.
4. **`analizar_puntos_distancia()`**: recorta ROI temporal, detecta **grupos de píxeles rojos** (`cv2.findContours`, umbral 3 px²), los asocia a eventos **por orden temporal** (V26), y marca duplicados con latest.php (±60 s).
5. **`clasificar_confianza()`, árbol de decisión:**
   - PASO 0: ¿en latest.php? → `DUPLICADO_LATEST`, no guardar.
   - VRP inválido → `VRP_INVALIDO`.
   - **FASE 1** (grupo rojo): `Y_grupo ≥ Y_LIMITE_PX` → `ALERTA_TERMICA_OCR` (conf. **alta** 🟢); si no → `FALSO_POSITIVO`.
   - **FASE 2** (estrella verde, V16): `detectar_centro_estrella_verde` con filtro de zona `[100:, 250:]`; dentro → alerta (conf. **media** 🟡).
   - **FASE 3** (píxeles negros): `ratio_negros > 0.70` → falso positivo.
6. **`verificar_evento_no_existe()`**: dedup final contra consolidado + ocr.

**Solo se guardan en `registro_vrp_ocr.csv` los `ALERTA_TERMICA_OCR`** (los FALSO_POSITIVO devuelven `guardar=False`). Por eso el OCR solo aporta eventos que latest.php *perdió*.

---

## 4. HALLAZGOS: Bugs, riesgos y deuda técnica (priorizados)

### 🔴 Críticos / funcionales

**H1: Geofence de Nevados de Chillán recorta actividad real (ya conocido, diferido).**
Límite 5 km descarta un cúmulo persistente a 6.2-7.95 km (picos 34-51 MW, mayo 2026). Congela OCR y dashboard de Nevados. Decisión actual: dejarlo. Si se retoma → cruzar azimut y evaluar ampliar a ~8 km en `scraper.py`, `ocr_utils.py` (recalibrar `Y_LIMITE_PX`) y README.

**H2: Drift de nombre histórico "Peteroa" → "PlanchonPeteroa" (datos huérfanos).**
Existen DOS identidades para el mismo volcán (357040):
- `registro_Peteroa.csv` con ~65 registros congelados en 2026-01-16 (nombre viejo).
- `registro_PlanchonPeteroa.csv` actualizado (nombre actual en `scraper.py`).
`LIMITES_Y_COORDENADAS` tiene ambas claves. El visualizador y el index.html solo usan "PlanchonPeteroa", así que los datos de "Peteroa" quedaron **huérfanos** (no se muestran ni se actualizan). Confirma que el drift de nombres ya ocurrió una vez, exactamente el riesgo que te preocupa. **Acción sugerida:** migrar/fusionar los 65 registros de Peteroa a PlanchonPeteroa, o documentar y archivar.

**H3: Calibración en píxeles absolutos asume imagen 850×600 (frágil).**
`Y_LIMITE_PX`, el filtro de estrella `mask_grafico[100:, 250:]` y la zona `250≤cy≤450` son **píxeles fijos**. Si MIROVA cambia el tamaño/layout de la imagen, todo el geofencing OCR se rompe **en silencio** (no hay assert de dimensiones). Inconsistencia: el ROI es robusto (%) pero el límite no. **Mejora de raíz:** expresar `Y_LIMITE_PX` como % de altura, o validar `img.shape == (600, 850)` y abortar/recalibrar si cambió.

### 🟠 Importantes / consistencia

**H4: Dos escalas de clasificación distintas para el mismo VRP.**
`scraper.py::obtener_clasificacion_mirova` usa umbrales en Watts (Muy Bajo <1 MW, Bajo <10, Moderado <100…), pero `scraper_ocr.py` usa otra escala (Muy Bajo <0.2, Bajo <1, Medio <5, Alto ≥5). Un mismo evento recibe etiqueta distinta según la fuente. **Unificar** en una sola función compartida.

**H5: Doc/código drift en README.**
- Tabla "Red de Vigilancia": Tupungatito dice **5.0 km / Y_LIMITE 257**, el código usa **7.0 km** (comentario V24).
- README dice "Respaldo en Calma: captura diaria VIIRS375 cuando VRP=0", pero `scraper.py::descargar_v104` solo descarga si `es_alerta_real` → **la captura de referencia diaria no está implementada**.
- Docstring de ocr_utils dice "14 volcanes"; son 11 (con claves alias).

**H6: `merger_maestro.py` nunca escribe el maestro completo.**
Calcula `DB_MAESTRO = registro_vrp_maestro.csv` pero solo guarda `_publicable`. El `registro_vrp_maestro.csv` no existe (confirmado: 404 en GitHub). El fallback del visualizador a ese archivo es **código muerto**. Limpiar o implementar.

### 🟡 Deuda técnica / resiliencia

**H7: `except:` desnudos en todo el código.** `scraper.py`, `scraper_ocr.py` usan `except:` que tragan TODO (incluido KeyboardInterrupt) y ocultan la causa. Cambiar a `except Exception as e:` con log. Choca con el principio "Resilience" del CLAUDE.md.

**H8: Dependencias sin fijar (`requirements.txt`).** Ya rompió una vez (Python 3.9). Ahora CI corre **pandas 3.0.3 / numpy 2.4.6**: pandas 3.0 trae *copy-on-write* por defecto, que puede afectar asignaciones sobre slices (p. ej. `visualizador.py:153` `df_sensor['VRP_Transformed'] = ...` sobre un slice). **Pinear versiones** (`pandas>=2.2,<3` o validar compatibilidad 3.0) para reproducibilidad.

**H9: Crecimiento ilimitado del repo.** `imagenes_satelitales/` se commitea a git (ya 2200+ archivos). El historial crecerá sin límite. Considerar Git LFS, retención (borrar evidencia > N meses) o almacenamiento externo. El dashboard linkea a `github.com/.../tree/...` para la evidencia, así que migrar requiere repensar esos enlaces.

**H10: `git add -A` en main.yml.** Commitea cualquier archivo suelto (p. ej. backups manuales como `registro_vrp_consolidado al 08042026.csv`). Usar `git add` selectivo como en graficos_completo.yml.

**H11: Referencia a `config_sentinel2.py` inexistente** en `validar_funcionalidades.yml` (paths trigger). Vestigio de una integración Sentinel-2 planeada/removida. Limpiar o retomar.

**H12: `ts = naive.timestamp()` depende de la TZ del sistema** (`scraper.py:145`). En GitHub (UTC) es correcto; si se corre localmente en Chile, los timestamps se desplazan 3-4 h. Latente. Forzar UTC explícito.

**H13: Sin tests automatizados.** La "validación" es grep de strings (frágil: pasa aunque la lógica esté rota mientras el texto exista). No hay pytest con imágenes de fixture. Oportunidad grande dado que ya tenés casos de prueba documentados (Lastarria 05:42+06:06, Tupungatito).

---

## 5. Fortalezas del diseño (a preservar)

- **Doble fuente con dedup** (latest.php + OCR) → robustez ante pérdidas.
- **Calibración cruzada V27** (usar latest.php para desambiguar la estrella verde) → idea elegante.
- **ROI temporal** (analizar solo el último día) → reduce falsos positivos de días viejos 99.4%.
- **Detección de grupos por clustering** → resuelve eventos superpuestos en la misma hora.
- **Separación auditoría/publicación** → conserva falsos positivos sin ensuciar el dashboard.
- **Anti-regresión en CI** → buena intención (aunque mejorable, ver H13).

---

## 6. Recomendaciones para "continuar con mejoras" (orden sugerido)

1. **Estabilizar primero (1-2 h):** pinear `requirements.txt` (H8), unificar clasificación VRP (H4), corregir README (H5), limpiar código muerto (H6, H11). Bajo riesgo, alta higiene.
2. **Robustez de calibración (medio):** convertir `Y_LIMITE_PX` a % + assert de dimensiones de imagen (H3). Esto blinda el sistema contra el próximo cambio de MIROVA, la dependencia más riesgosa del proyecto.
3. **Resolver drift de nombres (medio):** fusionar Peteroa/PlanchonPeteroa (H2) y crear un **único diccionario maestro de volcanes** (nombre canónico, alias, id_mirova, límite, Y_LIMITE) importado por todos los módulos, en vez de redefinir `VOLCANES_CONFIG` en 2 archivos. Esto previene futuros drifts.
4. **Tests (mayor, alto valor):** pytest con imágenes fixture de los casos documentados. Reemplaza el grep-validation por tests reales.
5. **Escalabilidad de almacenamiento (mayor):** estrategia para `imagenes_satelitales/` (H9).
6. **Node 24 actions (antes del 16-jun):** bump de `checkout@v4`, `configure-pages@v4`, `deploy-pages@v4`, `upload-artifact@v4`.

---

## 7. Apéndice: el "diccionario maestro" propuesto (refactor H3+H2+H4)

Hoy la config está duplicada en 3 lugares con formatos distintos. Un solo `volcanes.py`:
```python
VOLCANES = {
  "357040": {
    "canonico": "PlanchonPeteroa", "alias": ["Peteroa"],
    "id_mirova": "PlanchonPeteroa", "limite_km": 3.0,
    "y_limite_pct": 272/600,   # en vez de px absolutos
  },
  ...
}
```
importado por scraper, scraper_ocr, ocr_utils, merger y visualizador → una sola fuente de verdad. Elimina H2, H4 y la mitad de H3 de un golpe.

---
## Actualización 2026-06-12
- **H2 RESUELTO** (commit 62c34e27): 65 filas huérfanas "Peteroa" migradas a
  "PlanchonPeteroa" en consolidado (+1 en positivos), 3 claves del día de
  transición deduplicadas, registro_Peteroa.csv eliminado. Verificado: la alerta
  del 13-ene (1.06 MW) ahora aparece en registro_PlanchonPeteroa.csv (102 filas).
- Resueltos también desde la auditoría original: H1 parcial (geofence Nevados:
  cúmulo confirmado NO volcánico vía FIRMS, decisión de mantener 5 km validada),
  H3 (geometría medida por imagen, V29), H8 (deps pineadas + Dependabot),
  workflows Node24, Tupungatito 7km/243px.
- Pendientes: H4 (doble escala clasificación VRP), H5 (README drift), H6 (maestro
  completo nunca se escribe), H7 (except: desnudos), H10 (git add -A), H11→hecho
  (config_sentinel2 ya removido del validador), H12 (timestamp TZ), H13 (tests),
  H9 (almacenamiento imágenes).

## Actualización 2026-06-12 (tarde): Bundle de higiene V5.1 (commits c7229712 + a081e69c)
- **H4 RESUELTO**: clasificación única escala Coppola en `volcanes.py::clasificacion_mirova`
  (decisión de Nicolás); scraper delega (0/409 diferencias vs fórmula previa); OCR
  abandona su escala ad-hoc (las filas OCR nuevas usan la escala estándar).
- **H5 RESUELTO**: README v5.1 (Tupungatito 7/243, Planchón-Peteroa, geometría medida,
  changelog jun-2026, "Respaldo en Calma" removido por no implementado).
- **H6 RESUELTO**: código muerto del "maestro completo" eliminado (merger + visualizador).
- **H7 RESUELTO**: 0 `except:` desnudos en scrapers (ahora `except Exception` con log).
- **H10 RESUELTO**: `git add` selectivo en bots. Esto DESTAPÓ que `__pycache__/*.pyc`
  estaban trackeados (reliquia de add -A) y rompían el rebase del monitor → se
  eliminaron del repo, se creó `.gitignore` (no existía) y el pull usa `--autostash`.
- **H12 RESUELTO**: timestamp del scraper en UTC explícito.
- Pendientes: H13 (tests pytest), H9 (almacenamiento imágenes), ROI anclado a punteada (opcional).
