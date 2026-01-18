# django-tenant-authx

[![PyPI version](https://badge.fury.io/py/django-tenant-authx.svg)](https://badge.fury.io/py/django-tenant-authx)
[![Python Versions](https://img.shields.io/pypi/pyversions/django-tenant-authx.svg)](https://pypi.org/project/django-tenant-authx/)
[![Django Versions](https://img.shields.io/pypi/djversions/django-tenant-authx.svg)](https://pypi.org/project/django-tenant-authx/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Django library providing tenant-aware authentication and authorization for multi-tenant SaaS applications.

## Features

- **Tenant Management**: Manage multiple tenants with unique slugs and domains
- **Multi-Tenant Membership**: Users can belong to multiple tenants with different roles
- **Tenant-Scoped RBAC**: Roles and permissions isolated per tenant
- **Multiple Resolution Strategies**: Domain, subdomain, URL path, or header-based tenant resolution
- **Django Integration**: Works seamlessly with Django's auth system
- **DRF Support**: Full Django REST Framework integration
- **Audit Logging**: Comprehensive security event logging

## Installation

```bash
pip install django-tenant-authx
```

## Quick Start

### 1. Add to INSTALLED_APPS

```python
INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    # ...
    'tenant_authx',
]
```

### 2. Add Middleware

```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'tenant_authx.middleware.TenantResolutionMiddleware',  # After AuthenticationMiddleware
    'tenant_authx.middleware.TenantUserMiddleware',
    # ...
]
```

### 3. Configure Authentication Backend

```python
AUTHENTICATION_BACKENDS = [
    'tenant_authx.backends.TenantAwareAuthBackend',
    'django.contrib.auth.backends.ModelBackend',
]
```

### 4. Configure Tenant Resolution

```python
# Tenant resolution strategy: 'domain', 'subdomain', 'path', or 'header'
TENANT_AUTHX_TENANT_RESOLUTION_STRATEGY = 'subdomain'

# For subdomain resolution, set your base domain
TENANT_AUTHX_BASE_DOMAIN = 'example.com'

# For path resolution, customize the URL pattern (optional)
# TENANT_AUTHX_TENANT_PATH_PATTERN = r'^/(?P<tenant_slug>[\w-]+)/'
```

### 5. Run Migrations

```bash
python manage.py migrate tenant_authx
```

## Usage

### Creating a Tenant

```python
from tenant_authx.models import Tenant, Role, Permission

# Create a tenant
tenant = Tenant.objects.create(
    name="Acme Corporation",
    slug="acme-corp",
    domain="acme.example.com"  # Optional
)

# Create a permission
view_orders = Permission.objects.create(
    tenant=tenant,
    codename="orders.view_order",
    name="Can view orders"
)

# Create a role
manager_role = Role.objects.create(
    tenant=tenant,
    name="Manager",
    description="Can manage orders"
)
manager_role.permissions.add(view_orders)
```

### Adding Users to a Tenant

```python
from tenant_authx.models import TenantMembership

# Add user to tenant with a role
membership = tenant.add_member(user, roles=[manager_role])

# Or manually
membership = TenantMembership.objects.create(
    user=user,
    tenant=tenant
)
membership.roles.add(manager_role)
```

### Protecting Views

```python
from tenant_authx.decorators import tenant_login_required, tenant_permission_required

@tenant_login_required
def dashboard(request):
    # User is authenticated and a member of request.tenant
    return render(request, 'dashboard.html')

@tenant_permission_required('orders.view_order')
def order_list(request):
    # User has 'orders.view_order' permission in request.tenant
    orders = Order.objects.filter(tenant=request.tenant)
    return render(request, 'orders.html', {'orders': orders})
```

### Using with Django REST Framework

```python
from rest_framework import viewsets
from tenant_authx.drf import TenantSessionAuthentication, HasTenantPermission

class OrderViewSet(viewsets.ModelViewSet):
    authentication_classes = [TenantSessionAuthentication]
    permission_classes = [HasTenantPermission]
    required_permissions = ['orders.view_order']

    def get_queryset(self):
        # Always filter by tenant!
        return Order.objects.filter(tenant=self.request.tenant)
```

### Checking Permissions Programmatically

```python
# Using TenantUser (recommended)
if request.tenant_user.has_perm('orders.edit_order'):
    # User can edit orders
    pass

# Get all permissions
permissions = request.tenant_user.get_all_permissions()

# Check multiple permissions
if request.tenant_user.has_perms(['orders.view_order', 'orders.edit_order']):
    pass
```

## Configuration Options

| Setting                                   | Default                         | Description                                          |
| ----------------------------------------- | ------------------------------- | ---------------------------------------------------- |
| `TENANT_AUTHX_TENANT_RESOLUTION_STRATEGY` | `'domain'`                      | Resolution strategy: domain, subdomain, path, header |
| `TENANT_AUTHX_TENANT_PATH_PATTERN`        | `r'^/(?P<tenant_slug>[\w-]+)/'` | Regex pattern for path-based resolution              |
| `TENANT_AUTHX_TENANT_HEADER_NAME`         | `'X-Tenant-Slug'`               | Header name for header-based resolution              |
| `TENANT_AUTHX_BASE_DOMAIN`                | `None`                          | Base domain for subdomain extraction                 |
| `TENANT_AUTHX_SUPERUSER_BYPASS`           | `True`                          | Allow superusers to bypass tenant checks             |
| `TENANT_AUTHX_AUDIT_ENABLED`              | `True`                          | Enable audit logging                                 |
| `TENANT_AUTHX_TENANT_EXEMPT_URLS`         | `[]`                            | URL patterns to skip tenant resolution               |

## Security Considerations

1. **Always filter querysets by tenant**: The library doesn't automatically filter queries.
2. **Use decorators on all views**: Protect every view that requires tenant context.
3. **Enable audit logging**: Monitor for suspicious activity.
4. **Use HTTPS**: Especially with header or subdomain-based resolution.

## License

MIT License

## Author

**RAJID K K**  
Email: rajidkk34@gmail.com
GitHub: [@kkrajid](https://github.com/kkrajid)
