# 🌋 Mirova-OVDAS VRP Monitor (Chile) - V5.0

**Mirova-OVDAS VRP Monitor** es una plataforma de **automatización y visualización científica** diseñada para el seguimiento de la Potencia Radiada Volcánica (VRP) en los principales centros eruptivos de Chile. El sistema actúa como un nodo de respaldo y análisis que captura, procesa y grafica la información pública de la plataforma **MIROVA** (Universidad de Turín).

⚠️ **Aclaración:** Este software es una herramienta independiente de soporte técnico. No reemplaza los canales oficiales de alerta temprana de instituciones estatales.

---

## 📡 Dashboard e Interfaz de Auditoría 

El sistema cuenta con un **Dashboard** que permite visualizar el estado de salud del monitor y las tendencias térmicas en tiempo real.

> [!IMPORTANT]
> **[👉 ACCEDER AL MONITOR EN VIVO (Standard OVDAS)](https://mendozavolcanic.github.io/Mirova-v1/)**

### 🟢 Semáforo de Salud del Sistema

El Dashboard integra una **Barra de Auditoría Técnica** que verifica la sincronización con los satélites:

* **Monitor Operativo:** Confirma que el robot ha procesado los datos exitosamente en el último ciclo.
* **Sincronización UTC:** Indica la hora exacta de la última captura de datos desde MIROVA.
* **📅 Tiempo Universal:** Todas las fechas se muestran en **hora UTC** para consistencia científica internacional.

---

## 📈 Visualización de Tendencias (V4.1)

El módulo `visualizador.py` genera gráficos de alta precisión con las siguientes características técnicas:

### **Gráficos Duales (Escala Lineal y Logarítmica)**

* **Escala Lineal:** Para visualización intuitiva de tendencias y comparación de magnitudes relativas.
* **Escala Logarítmica:** Permite detectar eventos de baja energía que serían invisibles en escala lineal, esencial para monitoreo de fondo térmico.

### **Características Avanzadas**

* **Sombreado Dinámico Inteligente:** El fondo del gráfico se colorea automáticamente (Verde, Amarillo, Naranja) solo si la energía detectada alcanza los umbrales de alerta, evitando distorsiones visuales en niveles bajos.

* **Iconografía Multisensor:** Diferenciación visual de la fuente del dato para auditoría científica:
  * `▲` **MODIS**: Sensor histórico de amplio espectro.
  * `■` **VIIRS 375m**: Alta resolución para detección de anomalías pequeñas.
  * `●` **VIIRS 750m**: Alta sensibilidad térmica.

* **Etiquetado Automático:** Marcado dinámico del valor **MAX** (en MW) detectado en el periodo mensual y anual.

* **Sistema de Confianza OCR:** Los eventos capturados por OCR se marcan con nivel de confianza:
  * 🟢 **Alta**: Evento confirmado con grupo de píxeles rojos en ROI (V19)
  * 🟡 **Media**: Evento validado por estrella verde (V16)

---

## 🛰️ Estrategia de Captura Dual: latest.php + OCR (V5.0)

El sistema implementa una **arquitectura de doble captura** que combina dos fuentes complementarias:

### **1. Scraper Primario (latest.php)**

Motor principal de captura que ejecuta ciclos cada **5 minutos**:

* **Detección de Alerta:** Si se detecta **VRP > 0** dentro del radio de seguridad, el sistema descarga el set de evidencia completo.
* **Soporte Tri-Sensor:** Captura simultánea de **MODIS**, **VIIRS 375m** y **VIIRS 750m** para el mismo evento.
* **Respaldo en Calma:** En ausencia de alertas (VRP = 0), prioriza **VIIRS 375m** para una captura diaria de referencia.
* **Auditoría de Procesamiento:** Detecta cuando MIROVA actualiza datos NRT a Standard y sincroniza el registro histórico.

### **2. Scraper Secundario OCR (Recuperación de Eventos Perdidos - V5.0)**

Sistema de **detección visual automática** que opera cada **1 hora** para recuperar eventos no capturados por latest.php:

#### **Pipeline OCR (3 etapas mejoradas):**

**ETAPA 1: Extracción de texto (Latest10NTI.png)**
* Descarga imágenes `Latest10NTI.png` de cada volcán × sensor
* Usa **Tesseract OCR** con estrategias múltiples para extraer fechas y valores VRP
* Detecta hasta 10 eventos simultáneos por imagen
* **Robustez:** 3 estrategias de extracción garantizan 10/10 detecciones
* **NUEVO V18:** Filtro de fecha 24h - Solo procesa eventos de últimas 24 horas

**ETAPA 2: Validación visual (Dist.png - V19 MEJORADO)**

**Sistema de 3 Fases para clasificación inteligente:**

**FASE 1 (V19): Detección de Grupos de Píxeles Rojos**
* Analiza **ROI Temporal** (últimas 24h del gráfico)
  * Área optimizada: 0.6% del gráfico total (3,162 px² vs 510,000 px²)
  * Máxima precisión temporal sin mezcla de días
* **NUEVO:** Detecta **grupos separados** de píxeles rojos usando clustering (cv2.findContours)
* Asocia cada grupo a su evento correspondiente
* Valida posición Y de cada grupo vs límite del volcán:
  * `Y_grupo >= Y_LIMITE_PX` → **ALERTA_TERMICA_OCR** ✅
  * `Y_grupo < Y_LIMITE_PX` → **FALSO_POSITIVO_OCR** ❌

**FASE 2 (V16): Validación por Estrella Verde**
* Si no hay grupo individual detectado, busca estrella verde (última detección MIROVA)
* **Filtro de zona crítico:** Solo busca en gráfico (Y>100, X>250), NO en interfaz
* Valida posición Y de estrella vs límite del volcán

**FASE 3 (V17): Píxeles Negros (Fallback)**
* Si ratio_negros > 0.70 → Evento fuera de límite
* Sin señal clara → Falso positivo

**INNOVACIÓN V19 - Solución para Eventos Superpuestos:**

*Caso real: Lastarria 14-Feb-2026*
```
Antes (V17):
  05:42:00 | 0.05 MW (VRP REAL dentro 3km)  → ❌ SE PERDÍA
  06:06:01 | 0.34 MW (FALSO fuera 3km)      → ✅ Detectado

Ahora (V19):
  Detecta 2 grupos separados de píxeles rojos:
  Grupo 1 (Y=259) → Asociado a 06:06 → FALSO_POSITIVO ❌
  Grupo 2 (Y=275) → Asociado a 05:42 → ALERTA_TERMICA_OCR ✅
```

**ETAPA 3: Clasificación y almacenamiento selectivo**
* **Confianza alta:** Grupo píxeles rojos dentro límite (V19)
* **Confianza media:** Estrella verde dentro límite (V16)
* **Falso positivo:** Fuera de límite o ROI vacío

#### **Almacenamiento inteligente:**
* **Se guardan imágenes SOLO si:** Confianza alta o media (eventos probables)
* **NO se guardan imágenes si:** Falsos positivos o eventos descartados
* **Auditoría completa:** Todos los eventos (incluso falsos) se registran en `registro_vrp_ocr.csv`

#### **Integración con sistema principal:**
* `merger_maestro.py` combina datos de latest.php + OCR
* Elimina duplicados (mismo timestamp + volcán + sensor)
* Genera `registro_vrp_maestro_publicable.csv` con eventos validados
* **Solo se publican:** ALERTA_TERMICA (alta/media), NO falsos positivos

---

## 🎯 Red de Vigilancia (Configuración OVDAS)

Se aplica un filtro de precisión geográfica (**Geofencing**) calibrado en Photoshop para validar que las anomalías térmicas provengan del cráter activo:

| Volcán | ID MIROVA | Límite (km) | Y_LIMITE_PX | Región |
| --- | --- | --- | --- | --- |
| **Isluga** | 355030 | 5.0 | 257 | Tarapacá |
| **Láscar** | 355100 | 5.0 | 257 | Antofagasta |
| **Lastarria** | 355120 | 3.0 | 272 | Antofagasta |
| **Tupungatito** | 357010 | 5.0 | 257 | Metropolitana |
| **Peteroa** | 357040 | 3.0 | 272 | Maule |
| **N. de Chillán** | 357070 | 5.0 | 257 | Ñuble |
| **Copahue** | 357090 | 4.0 | 266 | Biobío |
| **Llaima** | 357110 | 5.0 | 257 | Araucanía |
| **Villarrica** | 357120 | 5.0 | 257 | Araucanía |
| **Puyehue-C. Caulle** | 357150 | 20.0 | 148 | Los Ríos |
| **Chaitén** | 358041 | 5.0 | 257 | Los Lagos |

---

## 📂 Estructura de Datos

### **Bases de datos maestras:**
* `registro_vrp_consolidado.csv`: Datos capturados por latest.php (fuente primaria)
* `registro_vrp_ocr.csv`: Eventos recuperados por OCR (incluye falsos positivos para auditoría)
* `registro_vrp_maestro_publicable.csv`: Base final combinada y filtrada para el Dashboard

### **Registros por volcán:**
* `registro_[Volcan].csv`: CSV individual por cada volcán (se actualiza automáticamente)

### **Evidencia visual:**
* `imagenes_satelitales/`: Repositorio organizado por volcán y fecha con la evidencia visual de los sensores
* `graficos_tendencia/`: Gráficos de actividad térmica procesados para el Dashboard

### **Logs técnicos:**
* `bitacora_robot.txt`: Registro técnico de cada ciclo de ejecución
* `ocr_logs/`: Logs detallados del sistema OCR con clasificación 3 fases

---

## 🔬 Innovaciones Técnicas (V5.0 - Feb 2026)

### **1. Sistema OCR Ultra-Robusto (V19)**
* **Múltiples estrategias de extracción** evitan pérdida de datos por inconsistencias de Tesseract
* **Detección de grupos separados (clustering)** para eventos superpuestos en misma hora
* **Filtro temporal 24h (V18)** evita procesar eventos antiguos de Latest10NTI
* **ROI Temporal optimizado (V17)** reduce área análisis en 99.4% manteniendo precisión

### **2. Validación Visual 3 Fases (V19)**
* **FASE 1:** Validación por grupo individual de píxeles (NUEVO - precisión máxima)
* **FASE 2:** Validación por estrella verde con filtro de zona (Y>100, X>250)
* **FASE 3:** Detección píxeles negros (fallback para casos ambiguos)

### **3. Prevención de Regresiones (V17+)**
* **GitHub Actions:** Validación automática en cada commit
  * ✅ ROI temporal (coordenadas exactas)
  * ✅ Sistema 3 fases completo
  * ✅ Filtro estrella verde
  * ✅ Filtro fecha 24h
  * ✅ 11 volcanes configurados
* **Script validación local:** `validar_sistema_v17.py`

### **4. Almacenamiento Eficiente**
* **Descarga selectiva de imágenes** solo para eventos probables
* **Auditoría completa** mantiene registro de falsos positivos sin desperdiciar espacio
* **Actualización automática** de registros individuales por volcán

---

## 🛠️ Tecnologías y Autoría

* **Motor:** Python 3.10 (Pandas, Matplotlib, Plotly, BeautifulSoup4, Pytesseract, OpenCV, NumPy)
* **OCR Engine:** Tesseract 4.x/5.x
* **Clustering:** OpenCV cv2.findContours() para detección grupos
* **Infraestructura:** GitHub Actions (Automated Workflows)
* **Validación:** GitHub Actions + Scripts Python locales
* **Arquitectura:** Mendoza Volcanic
* **Asistencia Técnica:** Claude AI (Anthropic)

---

## 🙏 Acknowledgements

Toda la información térmica utilizada en este proyecto es procesada y obtenida a través de la infraestructura de la plataforma **MIROVA** (Middle InfraRed Observation of Volcanic Activity).

* **Desarrollo y Mantenimiento:** Departamento de Ciencias de la Tierra de la [Universidad de Turín](https://www.unito.it/) (Italia), en colaboración con la [Universidad de Florencia](https://www.unifi.it/).
* **Investigador Principal:** Diego Coppola.
* **Referencias Científicas:**
  * Coppola, D., et al. (2016). *Enhanced volcanic hot-spot detection using MODIS IR data: results from the MIROVA system*.
  * Coppola, D., et al. (2020). *Thermal Remote Sensing for Global Volcano Monitoring: Experiences From the MIROVA System*.
* Para más información, visite el sitio oficial de MIROVA.
* We gratefully acknowledge NASA LANCE for access to MODIS and VIIRS Near Real Time products. Sentinel-2 and Landsat 8 data are accessed through the Copernicus Open Access Hub.

---

## 📊 Estadísticas del Sistema (V5.0)

* **Cobertura:** 11 volcanes activos de Chile (Tupungatito agregado en V17)
* **Frecuencia latest.php:** Cada 5 minutos
* **Frecuencia OCR:** Cada 1 hora
* **Filtro temporal:** Últimas 24 horas (V18)
* **Sensores monitoreados:** MODIS, VIIRS 375m, VIIRS 750m
* **Tasa de recuperación OCR:** ~5-10% de eventos perdidos
* **Precisión de clasificación:** 
  * Alta (V19): Grupo píxeles dentro límite
  * Media (V16): Estrella verde dentro límite
* **ROI Temporal:** 99.4% reducción área análisis (3,162 px² vs 510,000 px²)
* **Validación automática:** 5 checks críticos en cada commit

---

## 📝 Changelog

### **V5.0 (Feb 2026) - Detección Grupos Píxeles**
- ➕ FASE 1 mejorada: Detección grupos separados (clustering)
- ➕ Solución eventos superpuestos (ej: Lastarria 05:42 + 06:06)
- ➕ Asociación inteligente grupo ↔ evento
- ✅ Preserva ROI temporal, 3 fases, filtro estrella, filtro fecha 24h

### **V4.1 (Feb 2026) - Filtro Temporal**
- ➕ Filtro fecha 24h en scraper_ocr.py
- ➕ Evita procesar eventos antiguos de Latest10NTI
- ➕ Sistema prevención regresiones (GitHub Actions + scripts)

### **V4.0 (Ene 2026) - ROI Temporal + Tupungatito**
- ➕ ROI Temporal restaurado (perdido V5-V16)
- ➕ Tupungatito agregado (11 volcanes totales)
- ➕ Sistema 3 fases completo documentado

### **V3.0 (Ene 2026) - Filtro Estrella Verde**
- ➕ Filtro zona estrella verde (Y>100, X>250)
- ➕ Evita confusión con interfaz MIROVA
- ➕ FASE 2 implementada correctamente

---

## 🔐 Funcionalidades Críticas Inmutables

**Estas decisiones están protegidas por validación automática:**

1. ✅ **ROI Temporal:** x: 0.8424-0.8635, y: 0.1817-0.4933
2. ✅ **Sistema 3 Fases:** rojos → estrella → negros
3. ✅ **Límites por Volcán:** 11 volcanes en LIMITES_Y_COORDENADAS
4. ✅ **Filtro Estrella Verde:** mask_grafico[100:, 250:]
5. ✅ **Filtro Fecha 24h:** VENTANA_HORAS = 24
6. ✅ **import os:** Presente en ocr_utils.py

---

**Versión:** 5.0
**Última actualización:** Febrero 2026
**Autor:** Nicolás Mendoza
**Asistente:** Claude (Anthropic)
