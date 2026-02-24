"""
Tests para threat_intel/services/ai.py

NOTA: Usamos OpenAI API directamente (sin SDK) para evitar 
el issue de access violation en Windows.
"""
import json
from unittest.mock import Mock, patch, MagicMock
from django.test import override_settings
from django.utils import timezone
from django.conf import settings
from django_tenants.test.cases import TenantTestCase
from django_tenants.utils import get_tenant_model

from threat_intel.models import IntelItem, AIAnalysis, Run, TechTag
from threat_intel.services.ai import (
    _build_item_text,
    _safe_json_loads,
    analyze_item,
    analyze_relevant_items_for_run,
    PROMPT_V1_SYSTEM,
    MAX_TEXT_CHARS,
)


class TestBuildItemText(TenantTestCase):
    """Tests para _build_item_text"""

    def setUp(self):
        """Crea datos de prueba"""
        self.item = IntelItem(
            canonical_id="CVE-2024-1234",
            kind="CVE",
            title="SQL Injection Vulnerability",
            description="A critical SQL injection vulnerability in Laravel",
            cvss=9.5,
            severity="critical",
            primary_url="https://example.com/cve",
            references=["https://ref1.com", "https://ref2.com"],
        )

    def test_build_item_text_basic(self):
        """Verifica que se construye el texto correctamente"""
        text = _build_item_text(self.item)
        
        self.assertIn("CVE-2024-1234", text)
        self.assertIn("SQL Injection Vulnerability", text)
        self.assertIn("9.5", text)
        self.assertIn("critical", text)

    def test_build_item_text_without_cvss(self):
        """Verifica manejo de items sin CVSS"""
        self.item.cvss = None
        text = _build_item_text(self.item)
        
        self.assertIn("null", text)
        self.assertIn("CVE-2024-1234", text)

    def test_build_item_text_truncation(self):
        """Verifica que se trunca si excede MAX_TEXT_CHARS"""
        self.item.description = "x" * (MAX_TEXT_CHARS + 1000)
        text = _build_item_text(self.item)
        
        self.assertLessEqual(len(text), MAX_TEXT_CHARS + 50)  # pequeño margen
        self.assertIn("[TRUNCADO]", text)

    def test_build_item_text_with_many_references(self):
        """Verifica que limita las referencias a 10"""
        self.item.references = [f"https://ref{i}.com" for i in range(20)]
        text = _build_item_text(self.item)
        
        # Solo debe incluir las primeras 10
        self.assertIn("https://ref0.com", text)
        self.assertIn("https://ref9.com", text)


class TestSafeJsonLoads(TenantTestCase):
    """Tests para _safe_json_loads"""

    def test_valid_json(self):
        """Verifica parsing de JSON válido"""
        data = _safe_json_loads('{"key": "value", "number": 42}')
        
        self.assertEqual(data["key"], "value")
        self.assertEqual(data["number"], 42)

    def test_json_with_spaces(self):
        """Verifica parsing con espacios extras"""
        data = _safe_json_loads('  {"key": "value"}  ')
        
        self.assertEqual(data["key"], "value")

    def test_json_wrapped_in_backticks(self):
        """Verifica parsing de JSON envuelto en ```"""
        data = _safe_json_loads('```json\n{"key": "value"}\n```')
        
        self.assertEqual(data["key"], "value")

    def test_json_wrapped_in_backticks_without_json_label(self):
        """Verifica parsing sin etiqueta 'json'"""
        data = _safe_json_loads('```\n{"key": "value"}\n```')
        
        self.assertEqual(data["key"], "value")

    def test_invalid_json(self):
        """Verifica que lanza error con JSON inválido"""
        with self.assertRaises(json.JSONDecodeError):
            _safe_json_loads('{"invalid": json}')


class TestAnalyzeItem(TenantTestCase):
    """Tests para analyze_item"""

    def setUp(self):
        """Configura datos de prueba"""
        self.item = IntelItem(
            canonical_id="CVE-2024-5678",
            kind="CVE",
            title="Test Vulnerability",
            description="Test description",
            cvss=7.5,
            severity="high",
            primary_url="https://example.com",
            references=[],
        )
        self.mock_client = Mock()

    def test_analyze_item_success(self):
        """Verifica análisis exitoso del item"""
        mock_response = Mock()
        mock_response.output_text = json.dumps({
            "summary_es": "Vulnerabilidad crítica",
            "applies_to_stack": True,
            "affected_tech": ["Laravel", "PHP"],
            "impact_previ": "Alto",
            "recommended_action": "Actualizar framework",
            "recommended_deadline": "2024-02-15",
            "priority": "high",
            "requires_management": True,
            "notes": "Se requiere análisis adicional",
        })
        
        self.mock_client.responses.create.return_value = mock_response

        result = analyze_item(self.mock_client, self.item, "gpt-4", "v1")

        self.assertEqual(result["summary_es"], "Vulnerabilidad crítica")
        self.assertTrue(result["applies_to_stack"])
        self.assertEqual(result["priority"], "high")
        self.assertIn("Laravel", result["affected_tech"])

    def test_analyze_item_affected_tech_as_string(self):
        """Verifica normalización de affected_tech como string"""
        mock_response = Mock()
        mock_response.output_text = json.dumps({
            "summary_es": "Test",
            "applies_to_stack": False,
            "affected_tech": "Laravel",  # string, no list
            "priority": "medium",
        })
        
        self.mock_client.responses.create.return_value = mock_response

        result = analyze_item(self.mock_client, self.item, "gpt-4", "v1")

        # Debe convertirse a lista
        self.assertIsInstance(result["affected_tech"], list)
        self.assertEqual(result["affected_tech"], ["Laravel"])

    def test_analyze_item_with_json_backticks(self):
        """Verifica análisis cuando la IA devuelve JSON con backticks"""
        mock_response = Mock()
        mock_response.output_text = '```json\n{"summary_es": "Test", "applies_to_stack": true, "priority": "critical"}\n```'
        
        self.mock_client.responses.create.return_value = mock_response

        result = analyze_item(self.mock_client, self.item, "gpt-4", "v1")

        self.assertEqual(result["summary_es"], "Test")
        self.assertTrue(result["applies_to_stack"])

    def test_analyze_item_missing_fields(self):
        """Verifica manejo de respuesta con campos faltantes"""
        mock_response = Mock()
        mock_response.output_text = json.dumps({
            "summary_es": "Minimal response",
        })
        
        self.mock_client.responses.create.return_value = mock_response

        result = analyze_item(self.mock_client, self.item, "gpt-4", "v1")

        self.assertEqual(result["summary_es"], "Minimal response")
        # Los campos faltantes no deberían causar error


class TestAnalyzeRelevantItemsForRun(TenantTestCase):
    """Tests para analyze_relevant_items_for_run"""

    def setUp(self):
        """Configura ambiente de prueba"""
        from datetime import timedelta
        
        super().setUp()  # Importante: llama al setUp del padre para configurar el tenant
        
        now = timezone.now()
        self.run = Run.objects.create(
            run_type="monthly",
            period_start=now - timedelta(days=30),
            period_end=now,
        )
        
        # Crear TechTag para poder referenciar
        self.tech_tag = TechTag.objects.create(name="Laravel")

    @patch('threat_intel.services.openai_api.get_openai_api_client')
    @patch('threat_intel.services.ai.analyze_item')
    def test_analyze_relevant_items_basic(self, mock_analyze_item, mock_get_client):
        """Verifica análisis básico de items relevantes con configuración real"""
        # Mock el cliente para evitar requests reales
        mock_client = Mock()
        mock_client.model = "gpt-4.1-mini"
        mock_get_client.return_value = mock_client
        
        mock_analyze_item.return_value = {
            "summary_es": "Análisis de prueba",
            "applies_to_stack": True,
            "affected_tech": ["Laravel"],
            "impact_previ": "Alto",
            "recommended_action": "Actualizar",
            "recommended_deadline": "2024-02-15",
            "priority": "high",
            "requires_management": False,
            "notes": "Test",
        }

        # Crear items para analizar
        from threat_intel.models import RunItem
        
        item_crit = IntelItem.objects.create(
            canonical_id="CVE-2024-CRIT",
            kind="CVE",
            title="Critical Issue",
            severity="critical",
            cvss=9.5,
            is_relevant=True,
        )
        RunItem.objects.create(run=self.run, item=item_crit)

        item_med = IntelItem.objects.create(
            canonical_id="CVE-2024-MED",
            kind="CVE",
            title="Medium Issue",
            severity="medium",
            cvss=5.0,
            is_relevant=True,
        )
        RunItem.objects.create(run=self.run, item=item_med)

        # Execute
        processed = analyze_relevant_items_for_run(self.run)

        # Verify
        self.assertEqual(processed, 2)
        self.assertTrue(AIAnalysis.objects.filter(run=self.run, item=item_crit).exists())
        self.assertTrue(AIAnalysis.objects.filter(run=self.run, item=item_med).exists())

        analysis = AIAnalysis.objects.get(run=self.run, item=item_crit)
        self.assertEqual(analysis.summary_es, "Análisis de prueba")
        self.assertTrue(analysis.applies_to_stack)
        self.assertEqual(analysis.priority, "high")

    @patch('threat_intel.services.openai_api.get_openai_api_client')
    @patch('threat_intel.services.ai.analyze_item')
    def test_analyze_skips_existing_analysis(self, mock_analyze_item, mock_get_client):
        """Verifica que no analiza items ya analizados"""
        mock_client = Mock()
        mock_client.model = "gpt-4.1-mini"
        mock_get_client.return_value = mock_client
        
        from threat_intel.models import RunItem
        
        item = IntelItem.objects.create(
            canonical_id="CVE-2024-EXISTING",
            kind="CVE",
            title="Already Analyzed",
            severity="high",
            cvss=8.0,
            is_relevant=True,
        )
        RunItem.objects.create(run=self.run, item=item)
        
        # Crear análisis previo
        AIAnalysis.objects.create(
            run=self.run,
            item=item,
            summary_es="Existing analysis",
            priority="high",
        )

        # Execute
        processed = analyze_relevant_items_for_run(self.run)

        # Verify - no debería llamar a analyze_item
        self.assertEqual(processed, 0)
        mock_analyze_item.assert_not_called()

    @override_settings(OPENAI_API_KEY="", THREAT_INTEL={})
    @patch('threat_intel.services.openai_api.get_openai_api_client')
    def test_analyze_missing_api_key(self, mock_get_client):
        """Verifica error cuando falta API key"""
        # Cuando no hay API key, debe lanzar ValueError
        mock_get_client.side_effect = ValueError("OPENAI_API_KEY no configurada")
        
        # Forzar la creación de items para que llegue al punto de verificar API
        from threat_intel.models import RunItem
        
        item = IntelItem.objects.create(
            canonical_id="CVE-2024-TEST-KEY",
            kind="CVE",
            title="Test",
            severity="high",
            cvss=8.0,
            is_relevant=True,
        )
        RunItem.objects.create(run=self.run, item=item)
        
        # Intentar analizar sin API key debe lanzar el error
        with self.assertRaises(ValueError) as cm:
            analyze_relevant_items_for_run(self.run)
        
        self.assertIn("OPENAI_API_KEY", str(cm.exception))

    @patch('threat_intel.services.openai_api.get_openai_api_client')
    @patch('threat_intel.services.ai.analyze_item')
    def test_analyze_handles_exception(self, mock_analyze_item, mock_get_client):
        """Verifica que maneja excepciones en el análisis sin fallar"""
        mock_client = Mock()
        mock_client.model = "gpt-4-mini"
        mock_get_client.return_value = mock_client
        
        # Primera llamada falla, segunda exitosa
        mock_analyze_item.side_effect = [
            Exception("API Error"),
            {
                "summary_es": "Segundo análisis",
                "applies_to_stack": False,
                "priority": "low",
            }
        ]

        from threat_intel.models import RunItem
        
        item1 = IntelItem.objects.create(
            canonical_id="CVE-2024-FAIL",
            kind="CVE",
            title="Will Fail",
            severity="critical",
            cvss=9.0,
            is_relevant=True,
        )
        RunItem.objects.create(run=self.run, item=item1)

        item2 = IntelItem.objects.create(
            canonical_id="CVE-2024-OK",
            kind="CVE",
            title="Will Succeed",
            severity="high",
            cvss=7.5,
            is_relevant=True,
        )
        RunItem.objects.create(run=self.run, item=item2)

        # Execute
        processed = analyze_relevant_items_for_run(self.run)

        # Verify - el segundo debería haberse creado
        self.assertEqual(processed, 1)
        self.assertFalse(AIAnalysis.objects.filter(run=self.run, item=item1).exists())
        self.assertTrue(AIAnalysis.objects.filter(run=self.run, item=item2).exists())


class TestPromptConstant(TenantTestCase):
    """Tests para las constantes del módulo"""

    def test_prompt_v1_system_is_not_empty(self):
        """Verifica que el prompt no esté vacío"""
        self.assertTrue(len(PROMPT_V1_SYSTEM) > 0)
        self.assertIn("ciberseguridad", PROMPT_V1_SYSTEM.lower())

    def test_max_text_chars_is_reasonable(self):
        """Verifica que MAX_TEXT_CHARS tiene un valor razonable"""
        self.assertGreater(MAX_TEXT_CHARS, 1000)
        self.assertLess(MAX_TEXT_CHARS, 100000)
