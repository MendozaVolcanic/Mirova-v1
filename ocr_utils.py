"""
OCR UTILS V5 - Validación con Estrella Verde
Incluye 3 fases de clasificación:
1. Píxeles rojos (actual)
2. Estrella verde (nuevo)
3. Fallback píxeles negros
"""

import cv2
import numpy as np

# ========================================
# COORDENADAS DE LÍMITES (desde Photoshop)
# ========================================
LIMITES_Y_COORDENADAS = {
    'Lastarria': {
        'Y_LIMITE_PX': 272,
        'Y_EJE_X_PX': 335,
        'LIMITE_KM': 3.0
    },
    'PlanchonPeteroa': {
        'Y_LIMITE_PX': 272,
        'Y_EJE_X_PX': 335,
        'LIMITE_KM': 3.0
    },
    'Peteroa': {  # Alias
        'Y_LIMITE_PX': 272,
        'Y_EJE_X_PX': 335,
        'LIMITE_KM': 3.0
    },
    'Copahue': {
        'Y_LIMITE_PX': 266,
        'Y_EJE_X_PX': 335,
        'LIMITE_KM': 4.0
    },
    'Lascar': {
        'Y_LIMITE_PX': 257,
        'Y_EJE_X_PX': 335,
        'LIMITE_KM': 5.0
    },
    'Isluga': {
        'Y_LIMITE_PX': 257,
        'Y_EJE_X_PX': 335,
        'LIMITE_KM': 5.0
    },
    'Nevados de Chillan': {
        'Y_LIMITE_PX': 257,
        'Y_EJE_X_PX': 335,
        'LIMITE_KM': 5.0
    },
    'ChillanNevadosde': {  # Alias MIROVA
        'Y_LIMITE_PX': 257,
        'Y_EJE_X_PX': 335,
        'LIMITE_KM': 5.0
    },
    'Llaima': {
        'Y_LIMITE_PX': 257,
        'Y_EJE_X_PX': 335,
        'LIMITE_KM': 5.0
    },
    'Villarrica': {
        'Y_LIMITE_PX': 257,
        'Y_EJE_X_PX': 335,
        'LIMITE_KM': 5.0
    },
    'Chaiten': {
        'Y_LIMITE_PX': 257,
        'Y_EJE_X_PX': 335,
        'LIMITE_KM': 5.0
    },
    'Puyehue-Cordon Caulle': {
        'Y_LIMITE_PX': 148,
        'Y_EJE_X_PX': 335,
        'LIMITE_KM': 20.0
    },
    'PuyehueCordonCaulle': {  # Alias MIROVA
        'Y_LIMITE_PX': 148,
        'Y_EJE_X_PX': 335,
        'LIMITE_KM': 20.0
    }
}


# ========================================
# FASE 1: Análisis de píxeles rojos
# ========================================
def analizar_pixeles_rojos(roi):
    """
    Analiza píxeles rojos en ROI de Dist.png
    
    Returns:
        (confianza, metodo): ('alta'/'media'/None, str)
    """
    if roi is None or roi.size == 0:
        return None, None
    
    # Detectar píxeles rojos
    mask_rojos = cv2.inRange(roi, (200, 0, 0), (255, 50, 50))
    pixeles_rojos = np.sum(mask_rojos > 0)
    total_pixeles = roi.shape[0] * roi.shape[1]
    
    if total_pixeles == 0:
        return None, None
    
    porcentaje_rojos = (pixeles_rojos / total_pixeles) * 100
    
    # Si hay muchos píxeles rojos → DENTRO del límite
    if porcentaje_rojos > 30:
        return 'alta', 'rojo_dominante'
    elif porcentaje_rojos > 10:
        return 'media', 'rojo_presente'
    else:
        return None, None


# ========================================
# FASE 2: Detección de estrella verde
# ========================================
def detectar_centro_estrella_verde(img_dist):
    """
    Detecta el centro de la estrella verde en Dist.png
    
    Args:
        img_dist: Imagen Dist.png completa (RGB)
    
    Returns:
        y_centro (int): Coordenada Y del centro de estrella
        None: Si no se detecta estrella
    """
    if img_dist is None or img_dist.size == 0:
        return None
    
    try:
        # Convertir a HSV para mejor detección de verde
        img_hsv = cv2.cvtColor(img_dist, cv2.COLOR_RGB2HSV)
        
        # Rango de verde para estrella MIROVA
        # Hue: 40-80 (verde), Saturation: 80-255, Value: 80-255
        mask_verde = cv2.inRange(img_hsv, (40, 80, 80), (80, 255, 255))
        
        # Encontrar contornos de estrella
        contornos, _ = cv2.findContours(mask_verde, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if len(contornos) == 0:
            return None
        
        # Tomar el contorno más grande (estrella principal)
        # Filtrar contornos muy pequeños (ruido)
        contornos_validos = [c for c in contornos if cv2.contourArea(c) > 10]
        
        if len(contornos_validos) == 0:
            return None
        
        contorno_max = max(contornos_validos, key=cv2.contourArea)
        
        # Calcular centro usando momentos
        M = cv2.moments(contorno_max)
        if M['m00'] == 0:
            return None
        
        cy = int(M['m01'] / M['m00'])
        
        return cy  # Solo necesitamos Y
    
    except Exception as e:
        print(f"Error detectando estrella verde: {e}")
        return None


def validar_con_estrella_verde(img_dist, volcan_nombre):
    """
    Valida si estrella verde está dentro del límite
    
    Args:
        img_dist: Imagen Dist.png completa (RGB)
        volcan_nombre: Nombre del volcán
    
    Returns:
        (confianza, tipo_registro, nota)
    """
    # Obtener coordenadas del volcán
    if volcan_nombre not in LIMITES_Y_COORDENADAS:
        return None, None, f"Volcán '{volcan_nombre}' sin coordenadas calibradas"
    
    coords = LIMITES_Y_COORDENADAS[volcan_nombre]
    
    # Detectar centro de estrella
    y_estrella = detectar_centro_estrella_verde(img_dist)
    
    if y_estrella is None:
        return None, None, "No se detectó estrella verde"
    
    # Validar posición
    y_limite = coords['Y_LIMITE_PX']
    y_eje_x = coords['Y_EJE_X_PX']
    
    # REGLA: Si Y estrella >= Y límite → DENTRO
    # (en imágenes, mayor Y = más abajo = más cerca del cráter)
    if y_estrella >= y_limite:
        # Calcular distancia estimada
        if y_estrella >= y_eje_x:
            dist_km = 0.0  # En el eje X o debajo
        else:
            # Proporción entre límite y eje X
            proporcion = (y_eje_x - y_estrella) / (y_eje_x - y_limite)
            dist_km = proporcion * coords['LIMITE_KM']
        
        nota = f"Estrella verde en Y={y_estrella} (dentro límite Y={y_limite}, dist≈{dist_km:.2f} km)"
        return 'alta', 'ALERTA_TERMICA_OCR', nota
    else:
        # Estrella fuera del límite
        nota = f"Estrella verde en Y={y_estrella} (fuera límite Y={y_limite}, límite={coords['LIMITE_KM']} km)"
        return 'baja', 'FALSO_POSITIVO_OCR', nota


# ========================================
# CLASIFICACIÓN INTEGRADA (3 FASES)
# ========================================
def clasificar_confianza_v5(img_dist_path, roi, volcan_nombre):
    """
    Clasificación completa en 3 fases:
    1. Píxeles rojos
    2. Estrella verde
    3. Píxeles negros (fallback)
    
    Args:
        img_dist_path: Path a imagen Dist.png
        roi: ROI extraído de Dist.png (para análisis de píxeles)
        volcan_nombre: Nombre del volcán
    
    Returns:
        (confianza, tipo_registro, metodo, nota)
    """
    
    # ===== FASE 1: Píxeles rojos =====
    confianza_rojos, metodo_rojos = analizar_pixeles_rojos(roi)
    
    if confianza_rojos == 'alta':
        return (
            'alta',
            'ALERTA_TERMICA_OCR',
            'pixeles_rojos_dominantes',
            'Píxeles rojos >30% del ROI - Evento dentro del límite'
        )
    
    if confianza_rojos == 'media':
        return (
            'media',
            'ALERTA_TERMICA_OCR',
            'pixeles_rojos_presentes',
            'Píxeles rojos 10-30% del ROI - Evento probable dentro del límite'
        )
    
    # ===== FASE 2: Estrella verde =====
    # Cargar imagen completa para detectar estrella
    try:
        img_dist = cv2.imread(img_dist_path)
        if img_dist is not None:
            img_dist_rgb = cv2.cvtColor(img_dist, cv2.COLOR_BGR2RGB)
            
            confianza_estrella, tipo_estrella, nota_estrella = validar_con_estrella_verde(
                img_dist_rgb, volcan_nombre
            )
            
            if confianza_estrella is not None:
                return (confianza_estrella, tipo_estrella, 'estrella_verde', nota_estrella)
    except Exception as e:
        print(f"Error en fase 2 (estrella verde): {e}")
    
    # ===== FASE 3: Píxeles negros (fallback) =====
    if roi is not None and roi.size > 0:
        mask_negros = cv2.inRange(roi, (0, 0, 0), (50, 50, 50))
        pixeles_negros = np.sum(mask_negros > 0)
        total_pixeles = roi.shape[0] * roi.shape[1]
        
        if total_pixeles > 0:
            porcentaje_negros = (pixeles_negros / total_pixeles) * 100
            
            if porcentaje_negros > 70:
                return (
                    'baja',
                    'FALSO_POSITIVO_OCR',
                    'pixeles_negros_dominantes',
                    f'Píxeles negros {porcentaje_negros:.1f}% - Sin señal clara de evento térmico'
                )
    
    # Sin señal clara
    return (
        'baja',
        'FALSO_POSITIVO_OCR',
        'sin_señal_clara',
        'No se detectaron píxeles rojos ni estrella verde'
    )


# ========================================
# FUNCIÓN DE PRUEBA
# ========================================
if __name__ == "__main__":
    # Test con caso Chaitén 30-Ene
    print("="*70)
    print("TEST: Clasificación OCR con estrella verde")
    print("="*70)
    
    # Simular caso Chaitén con estrella en Y=280
    # (en implementación real, esto viene de la imagen)
    
    volcan = "Chaiten"
    coords = LIMITES_Y_COORDENADAS[volcan]
    
    print(f"\nVolcán: {volcan}")
    print(f"Límite: {coords['LIMITE_KM']} km")
    print(f"Y límite: {coords['Y_LIMITE_PX']} px")
    print(f"Y eje X: {coords['Y_EJE_X_PX']} px")
    
    # Simular estrella en diferentes posiciones
    casos_prueba = [
        (280, "Chaitén 30-Ene (caso real)"),
        (250, "Estrella muy cerca del límite"),
        (260, "Estrella justo en el límite"),
        (200, "Estrella lejos (fuera)"),
        (330, "Estrella muy cerca del eje X")
    ]
    
    for y_estrella, descripcion in casos_prueba:
        print(f"\n{descripcion}:")
        print(f"  Y estrella: {y_estrella} px")
        
        if y_estrella >= coords['Y_LIMITE_PX']:
            proporcion = (coords['Y_EJE_X_PX'] - y_estrella) / (coords['Y_EJE_X_PX'] - coords['Y_LIMITE_PX'])
            dist_km = proporcion * coords['LIMITE_KM']
            print(f"  ✅ DENTRO del límite")
            print(f"  Distancia estimada: {dist_km:.2f} km")
            print(f"  Clasificación: ALTA - ALERTA_TERMICA_OCR")
        else:
            print(f"  ❌ FUERA del límite")
            print(f"  Clasificación: BAJA - FALSO_POSITIVO_OCR")
    
    print("\n" + "="*70)
    print("Para implementar en scraper_ocr.py:")
    print("  from ocr_utils_v5 import clasificar_confianza_v5")
    print("  confianza, tipo, metodo, nota = clasificar_confianza_v5(")
    print("      img_dist_path, roi, volcan_nombre")
    print("  )")
    print("="*70)
