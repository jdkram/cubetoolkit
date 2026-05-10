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
# Generate a hashed staticfiles manifest during the Docker build so that
# whitenoise's CompressedManifestStaticFilesStorage can read it at runtime.
# We use a permissive subclass of Django's ManifestStaticFilesStorage rather
# than whitenoise's version because whitenoise aborts on missing source-map
# references (e.g. bootstrap.bundle.min.js.map) that aren't shipped in our
# static tree. manifest_strict=False silences those without skipping the file.
# The manifest format is identical so whitenoise reads it correctly.
from django.contrib.staticfiles.storage import ManifestStaticFilesStorage  # noqa: E402


class _PermissiveManifestStorage(ManifestStaticFilesStorage):
    manifest_strict = False

    def hashed_name(self, name, content=None, filename=None):
        # During collectstatic post-processing, hashed_name() raises ValueError
        # for referenced files that don't exist in the static tree (e.g. source
        # maps that bootstrap ships references to but doesn't include). Return
        # the name unchanged so the build doesn't abort.
        try:
            return super().hashed_name(name, content=content, filename=filename)
        except ValueError:
            return name


STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "toolkit.docker_settings_ss._PermissiveManifestStorage",
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
