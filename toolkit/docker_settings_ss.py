import os

from toolkit.settings_ss import *

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

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
        },
    }
}

SECRET_KEY = os.environ.get("SECRET_KEY", "insecure-dev-secret-key-change-in-production")

# Print emails to the container logs instead of attempting SMTP delivery.
# Change to smtp.EmailBackend and set EMAIL_HOST/PORT/etc. in production.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Log to console only inside the container
del LOGGING["handlers"]["file"]
LOGGING["loggers"]["toolkit"]["handlers"] = ["console"]
LOGGING["root"] = {
    "handlers": ["console"],
    "level": "DEBUG",
}
