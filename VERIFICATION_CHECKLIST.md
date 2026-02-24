# Verification Checklist

Purpose: short, actionable checklist to verify security/PR readiness for this project.

## Pre-PR (author)
- [ ] Run tests locally:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py test --verbosity 2
```

- [ ] Run quick security scans locally:

```bash
pip install bandit pip-audit
bandit -r . -x migrations
pip-audit
```

- [ ] Ensure no secrets are committed (search for `BREVO_API_KEY`, `OPENAI_API_KEY`, `EMAIL_HOST_PASSWORD`, `SSO_SIGNING_SALT`, `FERNET_KEY`, etc.).
- [ ] Remove or convert any `print()` that may leak secrets to `logging` and ensure `RedactingFilter` is applied.
- [ ] Validate `passbase` reversible encryption key length/format (Fernet: 32 url-safe base64 bytes).
- [ ] Add/adjust tests for any code changes; if adding logging redaction, add unit tests for the filter.
- [ ] Run linters/formatters if used (optional): `flake8`, `black`.

## PR Description
- [ ] Explain what the change does and why (one paragraph).
- [ ] List security-sensitive areas touched (crypto, logging, secrets handling, third-party APIs).
- [ ] Include commands to reproduce test/scan results locally.

## Review Checklist (reviewer)
- [ ] Confirm tests pass locally or in CI.
- [ ] Check that no secrets are present in diffs.
- [ ] Confirm logging changes avoid printing secrets (spot-check new logs and outputs).
- [ ] Verify new dependencies are necessary and from trusted sources.
- [ ] Confirm any migration or tenant-related changes are safe for production.
- [ ] If crypto is changed, ensure backward compatibility or migration plan is included.

## Post-merge (ops)
- [ ] Rotate any keys/credentials that were exposed or used in examples (if applicable).
- [ ] Update deployment secrets in CI/CD and production environment securely.
- [ ] Monitor new logs for unexpected sensitive output for 24–72 hours after deploy.

## Notes / How to run scans in CI
- Add the following steps to CI to automate checks:
  - `bandit -r . -x migrations`
  - `pip-audit`
  - `python manage.py test`

## Quick references
- Redacting filter file: `passing/logging_utils.py`
- Critical settings to review: `passing/settings.py`
- Reversible crypto: `passbase/crypto.py`

