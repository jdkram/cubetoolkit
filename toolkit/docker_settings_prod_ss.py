import os

from toolkit.settings_ss import *

# --- Core production overrides ---

DEBUG = False

# Set via environment variable. Generate with:
#   python3 -c "import secrets; print(secrets.token_urlsafe(50))"
SECRET_KEY = os.environ["SECRET_KEY"]

ALLOWED_HOSTS = [os.environ["ALLOWED_HOST"]]

# Required for Django 4+ when behind a reverse proxy with HTTPS.
# Form submissions (login, event edits, rota) will 403 without this.
CSRF_TRUSTED_ORIGINS = [
    f"https://{os.environ['ALLOWED_HOST']}"
]

# The whole domain is dedicated to this app, so no subpath prefix is needed.
# FORCE_SCRIPT_NAME is only needed when serving at a subpath alongside other
# apps on the same domain.

# Tell Django that the real protocol comes from nginx's X-Forwarded-Proto header.
# Without this, request.is_secure() returns False and some redirects break.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# FORCE_SCRIPT_NAME already prepends /sns_toolkit to all URLs, so STATIC_URL
# must NOT include that prefix — doing so causes double-prefixing like
# /sns_toolkit/sns_toolkit/static/. Whitenoise sees PATH_INFO after WSGI
# strips SCRIPT_NAME, so it correctly serves requests at /static/*.
STATIC_URL = "/static/"

# Content-hashed filenames so browsers pick up fresh CSS/JS immediately on deploy.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Insert whitenoise after SecurityMiddleware so it serves static files.
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "wagtail.contrib.redirects.middleware.RedirectMiddleware",
]

# --- Database ---
# Same MariaDB config as dev — credentials come from environment variables.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.environ.get("DB_NAME", "toolkit"),
        "USER": os.environ.get("DB_USER", "toolkit"),
        "PASSWORD": os.environ["DB_PASSWORD"],
        "HOST": os.environ.get("DB_HOST", "mariadb"),
        "PORT": os.environ.get("DB_PORT", "3306"),
        "CONN_MAX_AGE": 60,
        "OPTIONS": {
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
            # Fail fast if MariaDB is unreachable rather than hanging a worker
            # indefinitely. Django's default has no timeout.
            "connect_timeout": 10,
        },
    }
}

# --- Email ---
# Set EMAIL_BACKEND to smtp.EmailBackend and configure these if you want
# mailouts to actually send. Console backend is safe for now.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
# Fail fast on SMTP connection attempts rather than hanging a worker.
# Django's default has no timeout. Only takes effect with smtp.EmailBackend.
EMAIL_TIMEOUT = 10
# EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
# EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
# EMAIL_PORT = int(os.environ.get("EMAIL_PORT", 587))
# EMAIL_USE_TLS = True
# EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
# EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")

# --- Logging ---
del LOGGING["handlers"]["file"]
LOGGING["loggers"]["toolkit"]["handlers"] = ["console"]
LOGGING["root"] = {
    "handlers": ["console"],
    "level": "WARNING",
}
