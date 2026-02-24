"""
Tests para threat_intel/services/openai_client.py

Aislamos los tests del cliente OpenAI para debuggear problemas de creación.
"""

from unittest.mock import Mock, patch
from django.test import override_settings
from django_tenants.test.cases import TenantTestCase
from django.conf import settings

from threat_intel.services.openai_client import OpenAIClientManager, get_openai_manager
import logging

logger = logging.getLogger(__name__)


class TestOpenAIClientManager(TenantTestCase):
    """Tests para OpenAIClientManager."""

    def test_manager_initialization(self):
        """Verifica que el manager se inicializa correctamente."""
        manager = OpenAIClientManager()
        
        # Debe cargar configuración
        self.assertIsNotNone(manager.cfg)
        self.assertTrue(len(manager.model_name) > 0)
        logger.info("[TEST] Modelo configurado: %s", manager.model_name)

    def test_api_key_validation(self):
        """Verifica que detecta cuando falta API key."""
        with override_settings(OPENAI_API_KEY="", THREAT_INTEL={}):
            manager = OpenAIClientManager()
            
            with self.assertRaises(RuntimeError) as cm:
                manager.validate_api_key()
            
            self.assertIn("OPENAI_API_KEY", str(cm.exception))
            logger.info("[TEST] Validación de API key funciona: %s", cm.exception)

    def test_api_key_found(self):
        """Verifica que encuentra la API key en settings."""
        api_key = settings.OPENAI_API_KEY or getattr(settings, 'THREAT_INTEL', {}).get('OPENAI_API_KEY')
        
        if not api_key:
            self.skipTest("OPENAI_API_KEY no configurada en settings")
        
        manager = OpenAIClientManager()
        
        # Debe encontrar la API key
        self.assertIsNotNone(manager.api_key)
        self.assertTrue(len(manager.api_key) > 0)
        logger.info("[TEST] API Key encontrada en manager")

    @patch('threat_intel.services.openai_client.OpenAI')
    def test_create_client_success(self, mock_openai_class):
        """Verifica creación exitosa del cliente."""
        api_key = settings.OPENAI_API_KEY or getattr(settings, 'THREAT_INTEL', {}).get('OPENAI_API_KEY')
        
        if not api_key:
            self.skipTest("OPENAI_API_KEY no configurada en settings")
        
        # Mock el cliente
        mock_client = Mock()
        mock_openai_class.return_value = mock_client
        
        manager = OpenAIClientManager()
        client = manager.create_client()
        
        self.assertIsNotNone(client)
        self.assertEqual(client, mock_client)
        logger.info("[TEST] Cliente creado exitosamente")

    @patch('threat_intel.services.openai_client.OpenAI')
    def test_create_client_exception(self, mock_openai_class):
        """Verifica manejo de excepciones al crear cliente."""
        api_key = settings.OPENAI_API_KEY or getattr(settings, 'THREAT_INTEL', {}).get('OPENAI_API_KEY')
        
        if not api_key:
            self.skipTest("OPENAI_API_KEY no configurada en settings")
        
        # Mock falla
        mock_openai_class.side_effect = Exception("Connection error")
        
        manager = OpenAIClientManager()
        
        with self.assertRaises(Exception) as cm:
            manager.create_client()
        
        self.assertIn("Connection error", str(cm.exception))
        logger.info("[TEST] Excepción capturada correctamente: %s", cm.exception)

    @patch('threat_intel.services.openai_client.OpenAI')
    def test_get_client_singleton(self, mock_openai_class):
        """Verifica que get_client retorna el mismo cliente."""
        api_key = settings.OPENAI_API_KEY or getattr(settings, 'THREAT_INTEL', {}).get('OPENAI_API_KEY')
        
        if not api_key:
            self.skipTest("OPENAI_API_KEY no configurada en settings")
        
        mock_client = Mock()
        mock_openai_class.return_value = mock_client
        
        manager = OpenAIClientManager()
        
        # Primera llamada crea el cliente
        client1 = manager.get_client()
        # Segunda llamada reutiliza el mismo
        client2 = manager.get_client()
        
        self.assertEqual(client1, client2)
        # OpenAI() debe llamarse solo una vez
        self.assertEqual(mock_openai_class.call_count, 1)
        logger.info("[TEST] Cliente se reutiliza correctamente (singleton)")

    def test_get_model_name(self):
        """Verifica obtención del nombre del modelo."""
        manager = OpenAIClientManager()
        model = manager.get_model_name()
        
        self.assertTrue(len(model) > 0)
        logger.info("[TEST] Modelo obtenido: %s", model)

    def test_get_config(self):
        """Verifica obtención de configuración."""
        manager = OpenAIClientManager()
        config = manager.get_config()
        
        self.assertIsInstance(config, dict)
        logger.info("[TEST] Configuración obtenida: %s", config)

    def test_factory_function(self):
        """Verifica que la factory function funciona."""
        manager = get_openai_manager()
        
        self.assertIsInstance(manager, OpenAIClientManager)
        self.assertIsNotNone(manager.cfg)
        logger.info("[TEST] Factory function funciona")

    @override_settings(OPENAI_API_KEY="", THREAT_INTEL={})
    def test_error_without_api_key(self):
        """Verifica que falla gracefully sin API key."""
        manager = OpenAIClientManager()
        
        # validate_api_key debe fallar
        with self.assertRaises(RuntimeError):
            manager.validate_api_key()
        
        # create_client también debe fallar
        with self.assertRaises(RuntimeError):
            manager.create_client()
        
        logger.info("[TEST] Errores sin API key capturados correctamente")


class TestOpenAIClientIntegration(TenantTestCase):
    """Tests de integración del cliente OpenAI."""

    def test_full_flow_with_mock(self):
        """Verifica el flujo completo: init -> validate -> create."""
        api_key = settings.OPENAI_API_KEY or getattr(settings, 'THREAT_INTEL', {}).get('OPENAI_API_KEY')
        
        if not api_key:
            self.skipTest("OPENAI_API_KEY no configurada en settings")
        
        with patch('threat_intel.services.openai_client.OpenAI') as mock_openai:
            mock_client = Mock()
            mock_openai.return_value = mock_client
            
            # Flujo completo
            manager = OpenAIClientManager()
            manager.validate_api_key()
            client = manager.create_client()
            
            self.assertIsNotNone(client)
                logger.info("[TEST] Flujo completo ejecutado exitosamente")
