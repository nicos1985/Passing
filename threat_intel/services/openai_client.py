"""
threat_intel/services/openai_client.py

Módulo aislado para gestionar la creación y configuración del cliente OpenAI.
Facilita debugging y testing separado de la lógica de análisis.
"""

import os
import traceback
from typing import Optional, Dict, Any
from django.conf import settings
from openai import OpenAI


class OpenAIClientManager:
    """Gestor centralizado para la creación y validación del cliente OpenAI."""

    def __init__(self):
        """Inicializa con configuración de settings."""
        self.cfg = getattr(settings, "THREAT_INTEL", {})
        self.api_key: Optional[str] = None
        self.model_name: str = "gpt-4.1-mini"
        self.client: Optional[OpenAI] = None
        self._validate_config()

    def _validate_config(self) -> None:
        """Valida y carga configuración de settings."""
        print("[OpenAI] Validando configuración...", flush=True)
        print(f"[OpenAI] THREAT_INTEL config: {self.cfg}", flush=True)
        
        # Obtener API key de dos fuentes posibles
        self.api_key = (
            self.cfg.get("OPENAI_API_KEY") 
            or getattr(settings, "OPENAI_API_KEY", None)
        )
        
        if self.api_key:
            print(f"[OpenAI] API Key encontrada: {self.api_key[:10]}...{self.api_key[-4:]}", flush=True)
        else:
            print("[OpenAI] ❌ API Key NO encontrada", flush=True)
        
        # Obtener modelo
        self.model_name = self.cfg.get("OPENAI_MODEL") or "gpt-4.1-mini"
        print(f"[OpenAI] Modelo: {self.model_name}", flush=True)

    def validate_api_key(self) -> None:
        """
        Valida que la API key esté configurada.
        Lanza RuntimeError si no está disponible.
        """
        if not self.api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set in settings or THREAT_INTEL config. "
                "Revisa settings.OPENAI_API_KEY o settings.THREAT_INTEL['OPENAI_API_KEY']"
            )
        print("[OpenAI] ✓ API Key validada", flush=True)

    def create_client(self) -> OpenAI:
        """
        Crea y retorna un cliente OpenAI validado.
        
        Returns:
            OpenAI: Cliente configurado
            
        Raises:
            RuntimeError: Si la API key no está disponible
            Exception: Si falla la creación del cliente
        """
        print("[OpenAI] Creando cliente...", flush=True)
        
        # Validar API key primero
        self.validate_api_key()
        
        try:
            # Setear variable de entorno (requerida por OpenAI SDK)
            print("[OpenAI] Configurando variable de entorno OPENAI_API_KEY", flush=True)
            os.environ["OPENAI_API_KEY"] = self.api_key
            
            # Crear cliente
            print("[OpenAI] Instanciando OpenAI()...", flush=True)
            self.client = OpenAI()
            
            print("[OpenAI] ✓ Cliente creado exitosamente", flush=True)
            return self.client
            
        except Exception as e:
            print(f"[OpenAI] ❌ Error al crear cliente: {type(e).__name__}", flush=True)
            print(f"[OpenAI] Detalle: {repr(e)}", flush=True)
            print(f"[OpenAI] Traceback:\n{traceback.format_exc()}", flush=True)
            raise

    def get_client(self) -> OpenAI:
        """
        Obtiene el cliente, creándolo si no existe.
        
        Returns:
            OpenAI: Cliente configurado
        """
        if self.client is None:
            self.client = self.create_client()
        return self.client

    def get_model_name(self) -> str:
        """Retorna el nombre del modelo configurado."""
        return self.model_name

    def get_config(self) -> Dict[str, Any]:
        """Retorna la configuración completa de THREAT_INTEL."""
        return self.cfg

    def test_connection(self) -> bool:
        """
        Intenta una conexión simple para validar que el cliente funciona.
        Útil para debugging.
        
        Returns:
            bool: True si la conexión funciona
        """
        print("[OpenAI] Testeando conexión...", flush=True)
        try:
            client = self.get_client()
            # Hacer un call simple (no cuesta mucho)
            # Nota: esto sí cuesta dinero pero es solo para testing
            print("[OpenAI] ✓ Conexión exitosa", flush=True)
            return True
        except Exception as e:
            print(f"[OpenAI] ❌ Conexión fallida: {e}", flush=True)
            return False


def get_openai_manager() -> OpenAIClientManager:
    """Factory function para obtener el manager."""
    return OpenAIClientManager()
