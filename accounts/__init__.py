default_app_config = 'accounts.apps.AccountsConfig'

# Import signals eagerly to ensure they register in interactive shells and
# management commands even if AppConfig.ready() was not executed for any
# reason in this environment.
try:
	from . import signals  # noqa: F401
except Exception:
	# Avoid raising during migrations or initial import stages
	pass
