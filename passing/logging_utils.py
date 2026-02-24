import logging
import re
from typing import Iterable, Optional


class RedactingFilter(logging.Filter):
    """Logging filter that redacts sensitive key/value pairs from log messages.

    It performs a simple regex-based replacement for common secret keys
    such as `otp_secret`, `password`, `token`, `api_key`, `access_token`.

    Usage in Django `LOGGING` config:
      "filters": {
          "redact": {
              "()": "passing.logging_utils.RedactingFilter",
              "fields": ["otp_secret","password","token"]
          }
      }

    The filter rewrites `record.msg` to a redacted string and clears `record.args`
    so formatted messages don't leak secrets via args.
    """

    def __init__(self, fields: Optional[Iterable[str]] = None):
        super().__init__()
        self.fields = list(fields) if fields else [
            "otp_secret",
            "password",
            "token",
            "api_key",
            "access_token",
        ]
        # Build a regex to match patterns like "key: value", "key=value", or JSON-ish "\"key\": \"value\""
        joined = "|".join(re.escape(f) for f in self.fields)
        # capture key then the separator and the value token (non-greedy)
        self._pattern = re.compile(rf'(?i)(?:"?\b({joined})\b"?\s*[:=]\s*)([\"\']?)([^\s,\]\}};]+)\2')

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            # Obtain the fully rendered message (safe even if msg is format string)
            message = record.getMessage()
            if message:
                redacted = self._pattern.sub(lambda m: f"{m.group(1)}=[REDACTED]", message)
                # Replace the msg and clear args so formatting isn't reapplied
                record.msg = redacted
                record.args = ()
        except Exception:
            # Never raise from a logging filter
            pass
        return True


def get_redacting_filter(fields: Optional[Iterable[str]] = None) -> RedactingFilter:
    """Convenience constructor for use in programmatic setups or tests."""
    return RedactingFilter(fields=fields)
