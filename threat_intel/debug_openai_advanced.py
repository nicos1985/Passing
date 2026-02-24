"""
Script para probar diferentes formas de conectar con OpenAI en Windows.
"""

import os
import sys
from pathlib import Path
import threading
import time

sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'passing.settings')

import django
django.setup()

from django.conf import settings
import traceback
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_sync_client():
    """Prueba el cliente síncrono estándar."""
    logger.info("\n[TEST 1] Cliente OpenAI Síncrono (estándar)...")
    try:
        from openai import OpenAI
        
        def create():
            return OpenAI()
        
        thread = threading.Thread(target=create, daemon=True)
        thread.start()
        thread.join(timeout=3.0)
        
        if thread.is_alive():
            logger.error("  ✗ TIMEOUT (se cuelga)")
            return False
        
        logger.info("  ✓ Funciona")
        return True
    except Exception as e:
        logger.exception("  ✗ Error in test_sync_client: %s", e)
        return False


def test_async_client():
    """Prueba el cliente asíncrono."""
    logger.info("\n[TEST 2] Cliente OpenAI Asíncrono...")
    try:
        from openai import AsyncOpenAI
        import asyncio
        
        async def create_async():
            return AsyncOpenAI()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
            try:
                client = loop.run_until_complete(asyncio.wait_for(create_async(), timeout=3.0))
                logger.info("  ✓ Funciona")
                return True
            except asyncio.TimeoutError:
                logger.error("  ✗ TIMEOUT")
                return False
        finally:
            loop.close()
            
    except Exception as e:
        logger.exception("  ✗ Error in test_async_client: %s", e)
        return False


def test_with_httpx_config():
    """Prueba con configuración especial de httpx."""
    logger.info("\n[TEST 3] Cliente con configuración httpx especial...")
    try:
        from openai import OpenAI
        import httpx
        
        # Crear cliente HTTP con config especial para Windows
        http_client = httpx.Client(
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
            timeout=10.0,
        )
        
        def create():
            return OpenAI(http_client=http_client)
        
        thread = threading.Thread(target=create, daemon=True)
        thread.start()
        thread.join(timeout=3.0)
        
        if thread.is_alive():
            logger.error("  ✗ TIMEOUT")
            return False
        
        logger.info("  ✓ Funciona")
        return True
        
    except Exception as e:
        logger.exception("  ✗ Error in test_with_httpx_config: %s", e)
        return False


def test_openai_version():
    """Verifica versión y sugiere update."""
    logger.info("\n[TEST 4] Versión de OpenAI...")
    try:
        import openai
        logger.info("  Versión actual: %s", openai.__version__)
        
        # Versiones conocidas con problemas en Windows
        problematic = ['2.15.0', '2.14.0', '2.13.0']
        if openai.__version__ in problematic:
            logger.warning("  ⚠ Versión conocida con problemas en Windows")
            logger.info("    Prueba: pip install --upgrade openai")
        else:
            logger.info("  ✓ Versión parece estar bien")
        
    except Exception as e:
        logger.exception("  ✗ Error: %s", e)


def test_api_connectivity():
    """Prueba conectividad básica sin OpenAI SDK."""
    logger.info("\n[TEST 5] Conectividad HTTP básica...")
    try:
        import requests
        
        response = requests.get('https://api.openai.com/v1/models', timeout=5)
        if response.status_code == 401:  # Sin auth, pero al menos respondió
            logger.info("  ✓ Conectividad OK (OpenAI API responde)")
            return True
        else:
            logger.info("  ? Status: %s", response.status_code)
            return True
            
    except requests.Timeout:
        logger.error("  ✗ TIMEOUT en conexión")
        return False
    except requests.ConnectionError:
        logger.error("  ✗ Error de conexión")
        return False
    except Exception as e:
        logger.exception("  ✗ Error: %s", e)
        return False


if __name__ == '__main__':
    logger.info("%s", "="*60)
    logger.info("PRUEBAS MÚLTIPLES DE CONEXIÓN OPENAI EN WINDOWS")
    logger.info("%s", "="*60)
    
    test_openai_version()
    test_api_connectivity()
    
    results = {
        "Síncrono (estándar)": test_sync_client(),
        "Asíncrono": test_async_client(),
        "Con httpx config": test_with_httpx_config(),
    }
    
    logger.info("%s", "\n" + "="*60)
    logger.info("RESUMEN DE RESULTADOS:")
    logger.info("%s", "="*60)
    
    for test_name, result in results.items():
        status = "✓" if result else "✗"
        logger.info("  %s %s", status, test_name)
    
    # Recomendaciones
    logger.info("%s", "\n" + "="*60)
    logger.info("RECOMENDACIONES:")
    logger.info("%s", "="*60)
    
    if all(results.values()):
        logger.info("  ✓ Todo funciona. El problema podría estar en Django/tests.")
    elif results["Asíncrono"]:
        logger.info("  → El cliente asíncrono funciona. Considera usar AsyncOpenAI")
        logger.info("  → O mockearlo en tests")
    elif results["Con httpx config"]:
        logger.info("  → Usa la configuración httpx especial en OpenAIClientManager")
    else:
        logger.error("  → Problema grave de conectividad")
        logger.info("  → Intenta: pip install --upgrade openai")
        logger.info("  → O downgrade: pip install openai==2.10.0")
    
    logger.info("\n")
