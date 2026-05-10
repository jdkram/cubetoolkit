import os

from toolkit.settings_ss import *

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

# settings_common.py sets TEMPLATES[0]["OPTIONS"]["debug"] = DEBUG at import
# time, before our DEBUG = True override takes effect. Fix it here so that
# the filesystem template loader does not cache templates in memory, allowing
# docker cp to update templates without a full image rebuild.
TEMPLATES[0]["OPTIONS"]["debug"] = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.environ.get("DB_NAME", "toolkit"),
        "USER": os.environ.get("DB_USER", "toolkit"),
        "PASSWORD": os.environ.get("DB_PASSWORD", "devserver_db_password"),
        "HOST": os.environ.get("DB_HOST", "mariadb"),
        "PORT": os.environ.get("DB_PORT", "3306"),
        "CONN_MAX_AGE": 10,
        "OPTIONS": {
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
            # Fail fast if MariaDB is unreachable rather than hanging a worker
            # indefinitely. Django's default has no timeout.
            "connect_timeout": 10,
        },
    }
}

SECRET_KEY = os.environ.get("SECRET_KEY", "insecure-dev-secret-key-change-in-production")

# Print emails to the container logs instead of attempting SMTP delivery.
# Change to smtp.EmailBackend and set EMAIL_HOST/PORT/etc. in production.
# Use whitenoise's manifest storage so the collectstatic run baked into the
# Docker image generates a manifest that matches what docker_settings_prod_ss
# uses at runtime. The dev runserver doesn't use STORAGES for static files.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
# Fail fast on SMTP connection attempts rather than hanging a worker.
# Django's default has no timeout. Only takes effect with smtp.EmailBackend.
EMAIL_TIMEOUT = 10

# Log to console only inside the container
del LOGGING["handlers"]["file"]
LOGGING["loggers"]["toolkit"]["handlers"] = ["console"]
LOGGING["root"] = {
    "handlers": ["console"],
    "level": "DEBUG",
}
