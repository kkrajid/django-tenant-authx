"""
PostgreSQL-specific Django test settings.

Run tests with: DJANGO_SETTINGS_MODULE=tests.settings_postgres pytest tests/
"""

import os
from tests.settings import *  # noqa: F401,F403

# Override database for PostgreSQL
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "tenant_authx_test"),
        "USER": os.environ.get("POSTGRES_USER", "postgres"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "asd12345#Ra"),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "TEST": {
            "NAME": "tenant_authx_test",
        },
    }
}

# PostgreSQL specific optimizations
if "default" in DATABASES:
    DATABASES["default"]["OPTIONS"] = {
        "connect_timeout": 10,
    }
