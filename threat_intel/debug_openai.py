"""
Script de debugging para analizar la conexión con OpenAI.
Ejecutar sin Django para aislar el problema.

Uso:
    python threat_intel/debug_openai.py
"""

import os
import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'passing.settings')

import django
django.setup()

from django.conf import settings
from openai import OpenAI
import traceback


def debug_openai_connection():
    """Debuggea la conexión con OpenAI paso a paso."""
    
    print("="*60)
    print("DEBUGGING CONEXIÓN OPENAI")
    print("="*60)
    
    # Paso 1: Verificar configuración
    print("\n[PASO 1] Verificando configuración de settings...")
    openai_api_key = getattr(settings, 'OPENAI_API_KEY', None)
    threat_intel_cfg = getattr(settings, 'THREAT_INTEL', {})
    
    print(f"  settings.OPENAI_API_KEY: {'✓ Encontrada' if openai_api_key else '✗ No encontrada'}")
    print(f"  settings.THREAT_INTEL: {bool(threat_intel_cfg)}")
    
    api_key = openai_api_key or threat_intel_cfg.get('OPENAI_API_KEY')
    if api_key:
        print(f"  API Key final: {api_key[:10]}...{api_key[-4:]}")
    else:
        print("  ✗ ERROR: No hay API key disponible")
        return False
    
    # Paso 2: Verificar variable de entorno
    print("\n[PASO 2] Verificando variable de entorno...")
    print(f"  OPENAI_API_KEY en env (antes): {'✓' if os.environ.get('OPENAI_API_KEY') else '✗'}")
    
    try:
        os.environ['OPENAI_API_KEY'] = api_key
        print(f"  OPENAI_API_KEY en env (después): ✓")
    except Exception as e:
        print(f"  ✗ Error setting env: {e}")
        return False
    
    # Paso 3: Verificar versión de OpenAI
    print("\n[PASO 3] Verificando versión de OpenAI...")
    try:
        import openai
        print(f"  openai.__version__: {openai.__version__}")
        print(f"  openai location: {openai.__file__}")
    except Exception as e:
        print(f"  ✗ Error: {e}")
    
    # Paso 4: Intentar crear cliente sin usar API (con timeout)
    print("\n[PASO 4] Intentando instanciar OpenAI()...")
    print("  (Si esto se cuelga, es un problema de threading en Windows)")
    
    import threading
    import time
    
    client = None
    error = None
    
    def create_client_in_thread():
        nonlocal client, error
        try:
            print("  [Thread] Llamando: client = OpenAI()")
            client = OpenAI()
            print("  [Thread] ✓ Cliente creado")
        except Exception as e:
            error = e
            print(f"  [Thread] ✗ Error: {type(e).__name__}: {e}")
    
    # Crear en thread separado con timeout
    thread = threading.Thread(target=create_client_in_thread, daemon=True)
    thread.start()
    thread.join(timeout=5.0)
    
    if thread.is_alive():
        print("  ✗ TIMEOUT: La creación del cliente se colgó después de 5 segundos")
        print("  Esto indica un problema de threading/Windows con OpenAI SDK")
        return False
    
    if error:
        print(f"  ✗ Error: {type(error).__name__}: {error}")
        print(f"\nTraceback completo:")
        print(traceback.print_exc())
        return False
    
    if not client:
        print("  ✗ No se pudo crear el cliente (desconocido)")
        return False
    
    print("  ✓ Cliente creado exitosamente")
    
    # Paso 5: Intentar hacer un request simple
    print("\n[PASO 5] Intentando hacer un request simple...")
    try:
        print("  Llamando: client.models.list()")
        models = client.models.list()
        print(f"  ✓ Modelos disponibles: {len(list(models))}")
    except Exception as e:
        print(f"  ✗ Error: {type(e).__name__}: {e}")
        print(f"\nTraceback completo:")
        print(traceback.format_exc())
        return False
    
    print("\n" + "="*60)
    print("✓ TODO FUNCIONÓ CORRECTAMENTE")
    print("="*60)
    return True


if __name__ == '__main__':
    try:
        success = debug_openai_connection()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nInterrumpido por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ ERROR NO ESPERADO: {e}")
        print(traceback.format_exc())
        sys.exit(1)
