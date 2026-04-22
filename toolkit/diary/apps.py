from django.apps import AppConfig


class DiaryConfig(AppConfig):
    name = "toolkit.diary"

    def ready(self):
        import toolkit.diary.signals  # noqa: F401
