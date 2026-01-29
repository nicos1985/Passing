"""
threat_intel/services/openai_api.py

Cliente de OpenAI usando HTTP directo, sin SDK problemático.
Evita los problemas de threading/Windows del SDK oficial.
"""

import json
from typing import Optional, Dict, Any, List
import requests
from django.conf import settings


class OpenAIAPIClient:
    """Cliente directo a OpenAI API sin usar el SDK oficial."""
    
    BASE_URL = "https://api.openai.com/v1"
    
    def __init__(self):
        """Inicializa con API key de settings."""
        self.api_key = (
            getattr(settings, "OPENAI_API_KEY", None) 
            or getattr(settings, "THREAT_INTEL", {}).get("OPENAI_API_KEY")
        )
        self.model = (
            getattr(settings, "THREAT_INTEL", {}).get("OPENAI_MODEL") 
            or "gpt-4.1-mini"
        )
        
        if not self.api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set in settings or THREAT_INTEL config"
            )
        
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })
        
        print(f"[OpenAI API] Cliente inicializado - Modelo: {self.model}", flush=True)
    
    def create_message(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """
        Envía un mensaje a OpenAI y obtiene la respuesta.
        
        Args:
            system_prompt: Instrucción del sistema
            user_message: Mensaje del usuario
            temperature: Creatividad (0-2)
            max_tokens: Tokens máximos en respuesta
            
        Returns:
            str: Texto de la respuesta
            
        Raises:
            requests.RequestException: Si falla la conexión
            ValueError: Si hay error en la respuesta
        """
        print("[OpenAI API] Enviando request...", flush=True)
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        
        try:
            response = self.session.post(
                f"{self.BASE_URL}/chat/completions",
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            
        except requests.Timeout:
            print("[OpenAI API] ✗ TIMEOUT", flush=True)
            raise
        except requests.ConnectionError as e:
            print(f"[OpenAI API] ✗ Connection error: {e}", flush=True)
            raise
        except requests.HTTPError as e:
            error_data = response.json() if response.text else {}
            print(f"[OpenAI API] ✗ HTTP {response.status_code}: {error_data}", flush=True)
            raise ValueError(f"OpenAI API error: {error_data.get('error', {}).get('message', str(e))}")
        
        data = response.json()
        
        # Extraer contenido
        try:
            content = data["choices"][0]["message"]["content"]
            print("[OpenAI API] ✓ Response recibida", flush=True)
            return content
            
        except (KeyError, IndexError) as e:
            print(f"[OpenAI API] ✗ Error parsing response: {e}", flush=True)
            raise ValueError(f"Unexpected response format: {data}")
    
    def __del__(self):
        """Cleanup de sesión."""
        if hasattr(self, 'session'):
            self.session.close()


def get_openai_api_client() -> OpenAIAPIClient:
    """Factory function para obtener el cliente."""
    return OpenAIAPIClient()
