"""
TEST_OCR_NAN.PY
Script para validar que ocr_utils.py detecta y descarta NaN correctamente

USO:
1. Subir a GitHub en raíz del repositorio
2. Ejecutar localmente con imágenes reales:
   python test_ocr_nan.py
3. O ejecutar con casos simulados (sin imágenes):
   python test_ocr_nan.py --mock
"""

import sys
import os

# Agregar directorio actual al path para importar ocr_utils
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ocr_utils import extraer_eventos_latest10nti
from PIL import Image, ImageDraw, ImageFont
import numpy as np

# =========================
# CASOS DE TEST
# =========================

CASOS_TEST = [
    {
        'nombre': 'VRP válido normal',
        'texto_ocr': """
10-Feb-2026 05:42:01    VRP =0.12 MW
09-Feb-2026 18:24:01    VRP =0.15 MW
09-Feb-2026 05:36:00    VRP =0.27 MW
Last Update:10-Feb-2026 05:42:01
        """,
        'esperado': 3,
        'vrps_esperados': [0.12, 0.15, 0.27]
    },
    {
        'nombre': 'VRP con NaN (debe descartar)',
        'texto_ocr': """
10-Feb-2026 05:18:00    VRP =NaN MW
10-Feb-2026 05:42:01    VRP =0.12 MW
09-Feb-2026 18:24:01    VRP =0.15 MW
Last Update:10-Feb-2026 05:42:01
        """,
        'esperado': 2,  # Solo 2 válidos
        'vrps_esperados': [0.12, 0.15]
    },
    {
        'nombre': 'VRP con variantes de NaN',
        'texto_ocr': """
10-Feb-2026 05:18:00    VRP =NaN MW
09-Feb-2026 18:24:01    VRP =nan MW
09-Feb-2026 06:00:01    VRP =N/A MW
08-Feb-2026 12:30:00    VRP =0.57 MW
Last Update:10-Feb-2026 05:42:01
        """,
        'esperado': 1,  # Solo 1 válido
        'vrps_esperados': [0.57]
    },
    {
        'nombre': 'VRP muy alto (debe descartar >1000 MW)',
        'texto_ocr': """
10-Feb-2026 05:18:00    VRP =9999 MW
10-Feb-2026 05:42:01    VRP =0.12 MW
09-Feb-2026 18:24:01    VRP =1500 MW
Last Update:10-Feb-2026 05:42:01
        """,
        'esperado': 1,  # Solo 1 válido
        'vrps_esperados': [0.12]
    },
    {
        'nombre': 'VRP muy bajo (debe descartar <0.01 MW)',
        'texto_ocr': """
10-Feb-2026 05:18:00    VRP =0.005 MW
10-Feb-2026 05:42:01    VRP =0.12 MW
09-Feb-2026 18:24:01    VRP =0.0001 MW
Last Update:10-Feb-2026 05:42:01
        """,
        'esperado': 1,  # Solo 1 válido
        'vrps_esperados': [0.12]
    },
    {
        'nombre': 'Sin eventos válidos (todos NaN)',
        'texto_ocr': """
10-Feb-2026 05:18:00    VRP =NaN MW
09-Feb-2026 18:24:01    VRP =nan MW
Last Update:10-Feb-2026 05:42:01
        """,
        'esperado': 0,
        'vrps_esperados': []
    }
]

# =========================
# FUNCIONES DE TEST
# =========================

def crear_imagen_mock(texto):
    """Crea una imagen temporal con texto simulado para OCR"""
    img = Image.new('RGB', (800, 600), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
    except:
        font = ImageFont.load_default()
    
    # Dibujar texto línea por línea
    y = 50
    for linea in texto.strip().split('\n'):
        draw.text((50, y), linea.strip(), fill=(0, 0, 0), font=font)
        y += 30
    
    # Guardar temporal
    temp_path = "/tmp/test_ocr_latest10nti.png"
    img.save(temp_path)
    return temp_path


def ejecutar_test_caso(caso):
    """Ejecuta un caso de test"""
    print(f"\n{'='*80}")
    print(f"TEST: {caso['nombre']}")
    print(f"{'='*80}")
    
    # Crear imagen mock
    img_path = crear_imagen_mock(caso['texto_ocr'])
    
    # Ejecutar OCR
    print("\n📝 Ejecutando OCR...")
    eventos = extraer_eventos_latest10nti(img_path)
    
    # Validar resultados
    cantidad_detectada = len(eventos)
    cantidad_esperada = caso['esperado']
    
    print(f"\n📊 RESULTADOS:")
    print(f"   Eventos detectados: {cantidad_detectada}")
    print(f"   Eventos esperados:  {cantidad_esperada}")
    
    if cantidad_detectada == cantidad_esperada:
        print(f"   ✅ PASS - Cantidad correcta")
    else:
        print(f"   ❌ FAIL - Esperaba {cantidad_esperada}, obtuvo {cantidad_detectada}")
        return False
    
    # Validar VRPs
    if eventos:
        vrps_detectados = [e['vrp_mw'] for e in eventos]
        vrps_esperados = caso['vrps_esperados']
        
        print(f"\n   VRPs detectados: {vrps_detectados}")
        print(f"   VRPs esperados:  {vrps_esperados}")
        
        if len(vrps_detectados) == len(vrps_esperados):
            for i, (det, esp) in enumerate(zip(vrps_detectados, vrps_esperados)):
                if abs(det - esp) < 0.01:
                    print(f"   ✅ VRP {i+1}: {det} ≈ {esp}")
                else:
                    print(f"   ❌ VRP {i+1}: {det} ≠ {esp}")
                    return False
        else:
            print(f"   ❌ FAIL - Número de VRPs no coincide")
            return False
    
    print(f"\n✅ TEST PASADO")
    return True


def test_con_imagenes_reales():
    """Test con imágenes reales de Lastarria subidas"""
    print(f"\n{'='*80}")
    print(f"TEST CON IMÁGENES REALES")
    print(f"{'='*80}")
    
    img_latest = "/mnt/user-data/uploads/Lastarria_VIIRS375_Latest10NTI.png"
    
    if not os.path.exists(img_latest):
        print(f"❌ Imagen no encontrada: {img_latest}")
        return False
    
    print(f"\n📸 Procesando imagen real de Lastarria...")
    eventos = extraer_eventos_latest10nti(img_latest)
    
    print(f"\n📊 RESULTADOS:")
    print(f"   Eventos detectados: {len(eventos)}")
    
    if eventos:
        print(f"\n   Eventos extraídos:")
        for i, evento in enumerate(eventos, 1):
            dt = evento['datetime'].strftime("%Y-%m-%d %H:%M:%S")
            vrp = evento['vrp_mw']
            print(f"   {i}. {dt} - VRP = {vrp:.2f} MW")
        
        # Validar que NO hay VRP = 9.0 (el bug original)
        if any(abs(e['vrp_mw'] - 9.0) < 0.01 for e in eventos):
            print(f"\n   ❌ FAIL - Detectado VRP = 9.0 (bug NaN no corregido)")
            return False
        
        # Validar que NaN fue descartado correctamente
        print(f"\n   ✅ PASS - No hay VRP = 9.0 (NaN descartado correctamente)")
    else:
        print(f"   ℹ️ No se detectaron eventos (puede ser correcto si imagen solo tiene NaN)")
    
    return True


def main():
    """Función principal"""
    print("="*80)
    print("🧪 TEST OCR NaN DETECTION V6")
    print("="*80)
    
    # Determinar modo
    usar_mock = '--mock' in sys.argv
    
    if usar_mock:
        print("\n🎭 MODO: Tests simulados (sin imágenes reales)")
        
        resultados = []
        for caso in CASOS_TEST:
            resultado = ejecutar_test_caso(caso)
            resultados.append(resultado)
        
        # Resumen
        print(f"\n{'='*80}")
        print(f"📊 RESUMEN")
        print(f"{'='*80}")
        print(f"Total tests: {len(resultados)}")
        print(f"✅ Pasados: {sum(resultados)}")
        print(f"❌ Fallidos: {len(resultados) - sum(resultados)}")
        
        if all(resultados):
            print(f"\n✅ TODOS LOS TESTS PASARON")
            return 0
        else:
            print(f"\n❌ ALGUNOS TESTS FALLARON")
            return 1
    
    else:
        print("\n📸 MODO: Test con imágenes reales")
        resultado = test_con_imagenes_reales()
        
        if resultado:
            print(f"\n✅ TEST CON IMÁGENES REALES PASÓ")
            return 0
        else:
            print(f"\n❌ TEST CON IMÁGENES REALES FALLÓ")
            return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
