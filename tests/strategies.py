"""
Hypothesis test strategies for tenant_authx.

Provides reusable generators for property-based testing.
"""

import string
from hypothesis import strategies as st

from django.contrib.auth import get_user_model


# Strategy for valid slugs
slug_strategy = st.text(
    alphabet=string.ascii_lowercase + string.digits + "-",
    min_size=3,
    max_size=50,
).filter(
    lambda s: s and not s.startswith("-") and not s.endswith("-") and "--" not in s
)

# Strategy for valid domain names
domain_strategy = st.from_regex(
    r"[a-z][a-z0-9]{2,20}\.(com|org|net|io|app)",
    fullmatch=True,
)

# Strategy for valid permission codenames (app_label.action_model format)
permission_codename_strategy = st.from_regex(
    r"[a-z][a-z0-9_]{1,20}\.[a-z][a-z0-9_]{1,30}",
    fullmatch=True,
)

# Strategy for valid role names
role_name_strategy = st.text(
    alphabet=string.ascii_letters + string.digits + " -_",
    min_size=2,
    max_size=50,
).filter(lambda s: s.strip() == s and len(s.strip()) >= 2)

# Strategy for valid tenant names
tenant_name_strategy = st.text(
    alphabet=string.ascii_letters + string.digits + " -_.",
    min_size=2,
    max_size=100,
).filter(lambda s: s.strip() == s and len(s.strip()) >= 2)

# Strategy for usernames
username_strategy = st.text(
    alphabet=string.ascii_lowercase + string.digits + "_",
    min_size=3,
    max_size=30,
).filter(lambda s: s and s[0].isalpha())

# Strategy for emails
email_strategy = st.emails()

# Strategy for passwords
password_strategy = st.text(
    alphabet=string.ascii_letters + string.digits + "!@#$%",
    min_size=8,
    max_size=30,
)


@st.composite
def tenant_data_strategy(draw):
    """Generate valid tenant creation data."""
    return {
        "name": draw(tenant_name_strategy),
        "slug": draw(slug_strategy),
        "domain": draw(st.one_of(st.none(), domain_strategy)),
        "is_active": draw(st.booleans()),
    }


@st.composite
def user_data_strategy(draw):
    """Generate valid user creation data."""
    return {
        "username": draw(username_strategy),
        "email": draw(email_strategy),
        "password": draw(password_strategy),
    }


@st.composite
def role_data_strategy(draw, tenant):
    """Generate valid role creation data for a tenant."""
    return {
        "tenant": tenant,
        "name": draw(role_name_strategy),
        "description": draw(st.text(max_size=200)),
    }


@st.composite
def permission_data_strategy(draw, tenant):
    """Generate valid permission creation data for a tenant."""
    return {
        "tenant": tenant,
        "codename": draw(permission_codename_strategy),
        "name": draw(st.text(min_size=2, max_size=100)),
    }


# List of permission actions for generating codenames
PERMISSION_ACTIONS = ["view", "add", "change", "delete", "manage", "export", "import"]

# List of model names for generating codenames
MODEL_NAMES = ["order", "invoice", "customer", "product", "report", "setting", "user"]


def generate_permission_codename():
    """Generate a valid permission codename."""
    import random
    action = random.choice(PERMISSION_ACTIONS)
    model = random.choice(MODEL_NAMES)
    app_label = random.choice(["core", "billing", "inventory", "reports", "admin"])
    return f"{app_label}.{action}_{model}"
