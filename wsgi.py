import os

# Point Django to settings file (can be overridden by DJANGO_SETTINGS_MODULE env var):
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "toolkit.settings")

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
