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


def test_sync_client():
    """Prueba el cliente síncrono estándar."""
    print("\n[TEST 1] Cliente OpenAI Síncrono (estándar)...")
    try:
        from openai import OpenAI
        
        def create():
            return OpenAI()
        
        thread = threading.Thread(target=create, daemon=True)
        thread.start()
        thread.join(timeout=3.0)
        
        if thread.is_alive():
            print("  ✗ TIMEOUT (se cuelga)")
            return False
        
        print("  ✓ Funciona")
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def test_async_client():
    """Prueba el cliente asíncrono."""
    print("\n[TEST 2] Cliente OpenAI Asíncrono...")
    try:
        from openai import AsyncOpenAI
        import asyncio
        
        async def create_async():
            return AsyncOpenAI()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            client = loop.run_until_complete(asyncio.wait_for(create_async(), timeout=3.0))
            print("  ✓ Funciona")
            return True
        except asyncio.TimeoutError:
            print("  ✗ TIMEOUT")
            return False
        finally:
            loop.close()
            
    except Exception as e:
        print(f"  ✗ Error: {e}")
        traceback.print_exc()
        return False


def test_with_httpx_config():
    """Prueba con configuración especial de httpx."""
    print("\n[TEST 3] Cliente con configuración httpx especial...")
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
            print("  ✗ TIMEOUT")
            return False
        
        print("  ✓ Funciona")
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        traceback.print_exc()
        return False


def test_openai_version():
    """Verifica versión y sugiere update."""
    print("\n[TEST 4] Versión de OpenAI...")
    try:
        import openai
        print(f"  Versión actual: {openai.__version__}")
        
        # Versiones conocidas con problemas en Windows
        problematic = ['2.15.0', '2.14.0', '2.13.0']
        if openai.__version__ in problematic:
            print(f"  ⚠ Versión conocida con problemas en Windows")
            print(f"    Prueba: pip install --upgrade openai")
        else:
            print(f"  ✓ Versión parece estar bien")
        
    except Exception as e:
        print(f"  ✗ Error: {e}")


def test_api_connectivity():
    """Prueba conectividad básica sin OpenAI SDK."""
    print("\n[TEST 5] Conectividad HTTP básica...")
    try:
        import requests
        
        response = requests.get('https://api.openai.com/v1/models', timeout=5)
        if response.status_code == 401:  # Sin auth, pero al menos respondió
            print("  ✓ Conectividad OK (OpenAI API responde)")
            return True
        else:
            print(f"  ? Status: {response.status_code}")
            return True
            
    except requests.Timeout:
        print("  ✗ TIMEOUT en conexión")
        return False
    except requests.ConnectionError:
        print("  ✗ Error de conexión")
        return False
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


if __name__ == '__main__':
    print("="*60)
    print("PRUEBAS MÚLTIPLES DE CONEXIÓN OPENAI EN WINDOWS")
    print("="*60)
    
    test_openai_version()
    test_api_connectivity()
    
    results = {
        "Síncrono (estándar)": test_sync_client(),
        "Asíncrono": test_async_client(),
        "Con httpx config": test_with_httpx_config(),
    }
    
    print("\n" + "="*60)
    print("RESUMEN DE RESULTADOS:")
    print("="*60)
    
    for test_name, result in results.items():
        status = "✓" if result else "✗"
        print(f"  {status} {test_name}")
    
    # Recomendaciones
    print("\n" + "="*60)
    print("RECOMENDACIONES:")
    print("="*60)
    
    if all(results.values()):
        print("  ✓ Todo funciona. El problema podría estar en Django/tests.")
    elif results["Asíncrono"]:
        print("  → El cliente asíncrono funciona. Considera usar AsyncOpenAI")
        print("  → O mockearlo en tests")
    elif results["Con httpx config"]:
        print("  → Usa la configuración httpx especial en OpenAIClientManager")
    else:
        print("  → Problema grave de conectividad")
        print("  → Intenta: pip install --upgrade openai")
        print("  → O downgrade: pip install openai==2.10.0")
    
    print("\n")
