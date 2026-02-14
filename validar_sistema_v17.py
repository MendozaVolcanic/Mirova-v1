#!/usr/bin/env python3
"""
VALIDAR_SISTEMA_V17.PY
Verifica que funcionalidades críticas estén presentes en el código
Ejecutar ANTES de hacer commit a GitHub
"""

import re
import sys
import os

# ========================================
# REGLAS DE VALIDACIÓN
# ========================================
VALIDACIONES_CRITICAS = {
    # ===== ROI TEMPORAL =====
    'ROI_CONFIG presente': {
        'patron': r"ROI_CONFIG\s*=\s*{",
        'archivo': 'ocr_utils.py',
        'critico': True,
        'descripcion': 'Configuración del ROI temporal debe existir'
    },
    'ROI x_start correcto': {
        'patron': r"'x_start_pct':\s*0\.8424",
        'archivo': 'ocr_utils.py',
        'critico': True,
        'descripcion': 'Coordenada X inicial del ROI (84.24%)'
    },
    'ROI x_end correcto': {
        'patron': r"'x_end_pct':\s*0\.8635",
        'archivo': 'ocr_utils.py',
        'critico': True,
        'descripcion': 'Coordenada X final del ROI (86.35%)'
    },
    'ROI y_start correcto': {
        'patron': r"'y_start_pct':\s*0\.1817",
        'archivo': 'ocr_utils.py',
        'critico': True,
        'descripcion': 'Coordenada Y inicial del ROI (18.17%)'
    },
    'ROI y_end correcto': {
        'patron': r"'y_end_pct':\s*0\.4933",
        'archivo': 'ocr_utils.py',
        'critico': True,
        'descripcion': 'Coordenada Y final del ROI (49.33%)'
    },
    
    # ===== SISTEMA 3 FASES =====
    'analizar_puntos_distancia usa ROI': {
        'patron': r"roi\s*=\s*img_rgb\[roi_y_start:roi_y_end,\s*roi_x_start:roi_x_end\]",
        'archivo': 'ocr_utils.py',
        'critico': True,
        'descripcion': 'Función debe extraer ROI de la imagen'
    },
    'clasificar_confianza 3 parámetros': {
        'patron': r"def clasificar_confianza\(evento,\s*img_dist_path,\s*volcan_nombre\)",
        'archivo': 'ocr_utils.py',
        'critico': True,
        'descripcion': 'Función debe recibir 3 parámetros exactos'
    },
    'Detección píxeles rojos': {
        'patron': r"mask_rojos\s*=\s*\(roi\[:,\s*:,\s*0\]\s*>\s*150\)",
        'archivo': 'ocr_utils.py',
        'critico': True,
        'descripcion': 'Debe detectar píxeles rojos en ROI'
    },
    'Detección píxeles negros': {
        'patron': r"mask_negros\s*=\s*\(roi\[:,\s*:,\s*0\]\s*<\s*100\)",
        'archivo': 'ocr_utils.py',
        'critico': True,
        'descripcion': 'Debe detectar píxeles negros en ROI'
    },
    
    # ===== ESTRELLA VERDE =====
    'Filtro zona estrella presente': {
        'patron': r"mask_grafico\[100:,\s*250:\]",
        'archivo': 'ocr_utils.py',
        'critico': True,
        'descripcion': 'Filtro de zona para excluir interfaz MIROVA'
    },
    'detectar_centro_estrella_verde existe': {
        'patron': r"def detectar_centro_estrella_verde\(",
        'archivo': 'ocr_utils.py',
        'critico': True,
        'descripcion': 'Función de detección de estrella verde'
    },
    
    # ===== TUPUNGATITO =====
    'Tupungatito en scraper': {
        'patron': r'"357010".*"Tupungatito"',
        'archivo': 'scraper.py',
        'critico': False,
        'descripcion': 'Tupungatito debe estar en configuración'
    },
    'Tupungatito en OCR': {
        'patron': r'"357010".*"Tupungatito"',
        'archivo': 'scraper_ocr.py',
        'critico': False,
        'descripcion': 'Tupungatito debe estar en OCR'
    },
    'Tupungatito límites Y': {
        'patron': r"'Tupungatito':\s*{.*'Y_LIMITE_PX'",
        'archivo': 'ocr_utils.py',
        'critico': False,
        'descripcion': 'Límites de estrella verde para Tupungatito'
    },
    
    # ===== IMPORTS NECESARIOS =====
    'import os presente': {
        'patron': r"^import os$",
        'archivo': 'ocr_utils.py',
        'critico': True,
        'descripcion': 'Módulo os necesario para os.path.exists()'
    },
}

# ========================================
# FUNCIÓN DE VALIDACIÓN
# ========================================
def validar_archivo(ruta, validaciones):
    """
    Lee un archivo y verifica que contenga los patrones esperados
    """
    if not os.path.exists(ruta):
        print(f"⚠️  Archivo {ruta} no encontrado (puede no aplicar)")
        return None
    
    try:
        with open(ruta, 'r', encoding='utf-8') as f:
            contenido = f.read()
    except Exception as e:
        print(f"❌ ERROR leyendo {ruta}: {e}")
        return None
    
    resultados = {}
    
    for nombre, config in validaciones.items():
        patron = config['patron']
        flags = re.MULTILINE if '^' in patron or '$' in patron else re.DOTALL
        match = re.search(patron, contenido, flags)
        
        resultados[nombre] = {
            'ok': match is not None,
            'critico': config.get('critico', False),
            'descripcion': config.get('descripcion', '')
        }
    
    return resultados

# ========================================
# EJECUCIÓN
# ========================================
def main():
    print("="*80)
    print("🔍 VALIDACIÓN DE SISTEMA V17")
    print("="*80)
    
    # Agrupar validaciones por archivo
    archivos_a_validar = {}
    for nombre, config in VALIDACIONES_CRITICAS.items():
        archivo = config['archivo']
        if archivo not in archivos_a_validar:
            archivos_a_validar[archivo] = {}
        archivos_a_validar[archivo][nombre] = config
    
    # Validar cada archivo
    errores_criticos = 0
    advertencias = 0
    archivos_no_encontrados = 0
    
    for archivo, validaciones in archivos_a_validar.items():
        print(f"\n📄 Validando: {archivo}")
        
        resultados = validar_archivo(archivo, validaciones)
        
        if resultados is None:
            archivos_no_encontrados += 1
            continue
        
        for nombre, resultado in resultados.items():
            desc = validaciones[nombre].get('descripcion', '')
            
            if resultado['ok']:
                print(f"   ✅ {nombre}")
                if desc:
                    print(f"      → {desc}")
            else:
                if resultado['critico']:
                    print(f"   ❌ CRÍTICO: {nombre}")
                    if desc:
                        print(f"      → {desc}")
                    errores_criticos += 1
                else:
                    print(f"   ⚠️  ADVERTENCIA: {nombre}")
                    if desc:
                        print(f"      → {desc}")
                    advertencias += 1
    
    # Resumen
    print("\n" + "="*80)
    print("📊 RESUMEN:")
    print(f"   ❌ Errores críticos: {errores_criticos}")
    print(f"   ⚠️  Advertencias: {advertencias}")
    print(f"   📁 Archivos no encontrados: {archivos_no_encontrados}")
    
    if errores_criticos > 0:
        print("\n" + "="*80)
        print("🚨 ATENCIÓN: Hay errores CRÍTICOS que deben corregirse")
        print("   NO subir estos cambios a GitHub hasta corregirlos")
        print("="*80)
        sys.exit(1)
    elif advertencias > 0:
        print("\n" + "="*80)
        print("⚠️  Hay advertencias - revisar antes de continuar")
        print("   Puedes proceder pero verifica que sea intencional")
        print("="*80)
        sys.exit(0)
    else:
        print("\n" + "="*80)
        print("✅ TODO CORRECTO - Sistema validado")
        print("   Seguro para hacer commit y push")
        print("="*80)
        sys.exit(0)

if __name__ == "__main__":
    main()
