"""
Demo Django application settings.

This demonstrates how to configure a Django project to use tenant_authx.
"""

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SECRET_KEY = "demo-secret-key-change-in-production"

DEBUG = True

ALLOWED_HOSTS = ["*", "localhost", "127.0.0.1"]

# =============================================================================
# Application definition
# =============================================================================

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    
    # Third-party
    "rest_framework",
    "rest_framework.authtoken",
    
    # Our library
    "tenant_authx",
    
    # Demo app
    "demo.core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    
    # Tenant AuthX middleware - MUST be after AuthenticationMiddleware
    "tenant_authx.middleware.TenantResolutionMiddleware",
    "tenant_authx.middleware.TenantUserMiddleware",
    
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "demo.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "demo", "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "demo.wsgi.application"

# =============================================================================
# Database
# =============================================================================

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(BASE_DIR, "demo_db.sqlite3"),
    }
}

# =============================================================================
# Authentication
# =============================================================================

AUTHENTICATION_BACKENDS = [
    # Tenant-aware authentication backend
    "tenant_authx.backends.TenantAwareAuthBackend",
    # Fallback to standard Django auth
    "django.contrib.auth.backends.ModelBackend",
]

AUTH_PASSWORD_VALIDATORS = []

# =============================================================================
# Internationalization
# =============================================================================

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# =============================================================================
# Static files
# =============================================================================

STATIC_URL = "/static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# =============================================================================
# Django REST Framework
# =============================================================================

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

# =============================================================================
# Tenant AuthX Configuration
# =============================================================================

# Resolution strategy: 'domain', 'subdomain', 'path', or 'header'
TENANT_AUTHX_TENANT_RESOLUTION_STRATEGY = "path"

# Pattern for extracting tenant from URL path
# Example: /t/acme-corp/dashboard/ -> tenant_slug = "acme-corp"
TENANT_AUTHX_TENANT_PATH_PATTERN = r"^/t/(?P<tenant_slug>[\w-]+)/"

# URLs that don't require tenant resolution
TENANT_AUTHX_TENANT_EXEMPT_URLS = [
    r"^/admin/",
    r"^/api/public/",
    r"^/accounts/",
    r"^/$",
]

# Allow superusers to bypass tenant permission checks
TENANT_AUTHX_SUPERUSER_BYPASS = True

# Enable audit logging for auth/authz events
TENANT_AUTHX_AUDIT_ENABLED = True

# =============================================================================
# Logging
# =============================================================================

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "tenant_authx.audit": {
            "handlers": ["console"],
            "level": "INFO",
        },
    },
}
