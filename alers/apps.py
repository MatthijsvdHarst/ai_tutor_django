from django.apps import AppConfig


class AlersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'alers'

    def ready(self):  # pragma: no cover - ensures signal registration
        from . import signals  # noqa: F401
