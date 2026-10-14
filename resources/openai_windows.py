"""Cliente HTTPS aislado para Windows, donde Python/OpenSSL puede fallar con la BD."""

import json
import subprocess
from pathlib import Path

from django.conf import settings


class WindowsOpenAIClient:
    def create_message(self, system_prompt, user_message, temperature=0, max_tokens=220):
        key = settings.OPENAI_API_KEY
        if not key:
            raise RuntimeError('Falta OPENAI_API_KEY.')
        payload = {
            'key': key,
            'model': settings.THREAT_INTEL.get('OPENAI_MODEL') or 'gpt-4.1-mini',
            'system': system_prompt,
            'message': user_message,
            'temperature': temperature,
            'max_tokens': max_tokens,
        }
        script = Path(__file__).with_name('openai_windows.ps1')
        try:
            result = subprocess.run(
                ['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', str(script)],
                input=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                capture_output=True, timeout=45, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError('No se pudo consultar el servicio de IA.') from exc
        if result.returncode != 0:
            # No revelar cuerpo HTTP: podría contener datos de diagnóstico del proveedor.
            raise RuntimeError('El servicio de IA no respondió correctamente.')
        try:
            return result.stdout.decode('utf-8')
        except UnicodeDecodeError as exc:
            raise RuntimeError('Respuesta inválida del servicio de IA.') from exc
