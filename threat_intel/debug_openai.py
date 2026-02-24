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
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def debug_openai_connection():
    """Debuggea la conexión con OpenAI paso a paso."""
    
    logger.info("%s", "="*60)
    logger.info("DEBUGGING CONEXIÓN OPENAI")
    logger.info("%s", "="*60)
    
    # Paso 1: Verificar configuración
    logger.info("\n[PASO 1] Verificando configuración de settings...")
    openai_api_key = getattr(settings, 'OPENAI_API_KEY', None)
    threat_intel_cfg = getattr(settings, 'THREAT_INTEL', {})
    
    logger.info("  settings.OPENAI_API_KEY: %s", ('✓ Encontrada' if openai_api_key else '✗ No encontrada'))
    logger.info("  settings.THREAT_INTEL: %s", bool(threat_intel_cfg))
    
    api_key = openai_api_key or threat_intel_cfg.get('OPENAI_API_KEY')
    if api_key:
        logger.info("  API Key final: <redacted>")
    else:
        logger.error("  ✗ ERROR: No hay API key disponible")
        return False
    
    # Paso 2: Verificar variable de entorno
    logger.info("\n[PASO 2] Verificando variable de entorno...")
    logger.info("  OPENAI_API_KEY en env (antes): %s", ('✓' if os.environ.get('OPENAI_API_KEY') else '✗'))
    
    try:
        os.environ['OPENAI_API_KEY'] = api_key
        logger.info("  OPENAI_API_KEY en env (después): ✓")
    except Exception as e:
        logger.exception("  ✗ Error setting env")
        return False
    
    # Paso 3: Verificar versión de OpenAI
    logger.info("\n[PASO 3] Verificando versión de OpenAI...")
    try:
        import openai
        logger.info("  openai.__version__: %s", openai.__version__)
        logger.info("  openai location: %s", openai.__file__)
    except Exception as e:
        logger.exception("  ✗ Error: %s", e)
    
    # Paso 4: Intentar crear cliente sin usar API (con timeout)
    logger.info("\n[PASO 4] Intentando instanciar OpenAI()...")
    logger.info("  (Si esto se cuelga, es un problema de threading en Windows)")
    
    import threading
    import time
    
    client = None
    error = None
    
    def create_client_in_thread():
        nonlocal client, error
        try:
            logger.info("  [Thread] Llamando: client = OpenAI()")
            client = OpenAI()
            logger.info("  [Thread] ✓ Cliente creado")
        except Exception as e:
            error = e
            logger.exception("  [Thread] ✗ Error: %s", type(e).__name__)
    
    # Crear en thread separado con timeout
    thread = threading.Thread(target=create_client_in_thread, daemon=True)
    thread.start()
    thread.join(timeout=5.0)
    
    if thread.is_alive():
        logger.error("  ✗ TIMEOUT: La creación del cliente se colgó después de 5 segundos")
        logger.error("  Esto indica un problema de threading/Windows con OpenAI SDK")
        return False
    
    if error:
        logger.exception("  ✗ Error creating client: %s", type(error).__name__)
        logger.debug("Traceback (most recent call last):")
        logger.debug(traceback.format_exc())
        return False
    
    if not client:
        logger.error("  ✗ No se pudo crear el cliente (desconocido)")
        return False
    
    logger.info("  ✓ Cliente creado exitosamente")
    
    # Paso 5: Intentar hacer un request simple
    logger.info("\n[PASO 5] Intentando hacer un request simple...")
    try:
        logger.info("  Llamando: client.models.list()")
        models = client.models.list()
        logger.info("  ✓ Modelos disponibles: %d", len(list(models)))
    except Exception as e:
        logger.exception("  ✗ Error during models.list(): %s", type(e).__name__)
        logger.debug(traceback.format_exc())
        return False
    
    logger.info("\n" + "="*60)
    logger.info("✓ TODO FUNCIONÓ CORRECTAMENTE")
    logger.info("="*60)
    return True


if __name__ == '__main__':
    try:
        success = debug_openai_connection()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.warning("Interrumpido por el usuario")
        sys.exit(1)
    except Exception as e:
        logger.exception("✗ ERROR NO ESPERADO: %s", e)
        logger.debug(traceback.format_exc())
        sys.exit(1)
