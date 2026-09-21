from django.contrib.staticfiles.storage import StaticFilesStorage


class PublicStaticFilesStorage(StaticFilesStorage):
    """Public assets must remain readable by Nginx; uploads stay private (0600)."""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('file_permissions_mode', 0o644)
        kwargs.setdefault('directory_permissions_mode', 0o755)
        super().__init__(*args, **kwargs)
