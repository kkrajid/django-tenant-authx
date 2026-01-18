import os
import sys
import django

# Add project to path
sys.path.insert(0, os.path.abspath('..'))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.settings")
django.setup()

project = 'django-tenant-authx'
copyright = '2026, RAJID K K'
author = 'RAJID K K'
release = '0.1.0'

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.viewcode',
    'sphinx.ext.napoleon',
    'myst_parser',
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

html_theme = 'sphinx_rtd_theme'
html_static_path = []

# MyST settings
myst_enable_extensions = [
    "colon_fence",
    "deflist",
]
