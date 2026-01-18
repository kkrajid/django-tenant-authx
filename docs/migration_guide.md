# Migration Guide

This guide helps you migrate from vanilla Django authentication to django-tenant-authx.

## From Django's Built-in Auth

### Step 1: Install the Library

```bash
pip install django-tenant-authx
```

### Step 2: Add to INSTALLED_APPS

```python
INSTALLED_APPS = [
    # ... existing apps ...
    'tenant_authx',
]
```

### Step 3: Add Middleware

Add after `AuthenticationMiddleware`:

```python
MIDDLEWARE = [
    # ... existing middleware ...
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'tenant_authx.middleware.TenantResolutionMiddleware',  # Add this
    'tenant_authx.middleware.TenantUserMiddleware',        # Add this
    # ... rest of middleware ...
]
```

### Step 4: Configure Authentication Backend

```python
AUTHENTICATION_BACKENDS = [
    'tenant_authx.backends.TenantAwareAuthBackend',
    'django.contrib.auth.backends.ModelBackend',  # Keep as fallback
]
```

### Step 5: Configure Tenant Resolution

```python
# Choose resolution strategy
TENANT_AUTHX_TENANT_RESOLUTION_STRATEGY = "path"

# For path-based resolution
TENANT_AUTHX_TENANT_PATH_PATTERN = r"^/t/(?P<tenant_slug>[\w-]+)/"

# URLs that don't require tenant (e.g., login, admin)
TENANT_AUTHX_TENANT_EXEMPT_URLS = [
    r"^/admin/",
    r"^/accounts/",
]
```

### Step 6: Run Migrations

```bash
python manage.py migrate tenant_authx
```

### Step 7: Create Your First Tenant

```python
from tenant_authx.models import Tenant, TenantMembership, Role, Permission

# Create tenant
tenant = Tenant.objects.create(
    name="My Company",
    slug="my-company",
)

# Create permissions
view_perm = Permission.objects.create(
    tenant=tenant,
    codename="myapp.view_item",
    name="Can view items",
)

# Create role
admin_role = Role.objects.create(
    tenant=tenant,
    name="Admin",
)
admin_role.permissions.add(view_perm)

# Add user to tenant
user = User.objects.get(username="john")
membership = TenantMembership.objects.create(
    user=user,
    tenant=tenant,
)
membership.roles.add(admin_role)
```

## Migrating from Django's Group/Permission System

### Before (Django Groups)

```python
# Old way: Django groups
from django.contrib.auth.models import Group, Permission

managers = Group.objects.create(name="Managers")
permission = Permission.objects.get(codename="add_order")
managers.permissions.add(permission)

user.groups.add(managers)

# In views
if user.has_perm("myapp.add_order"):
    ...
```

### After (Tenant AuthX)

```python
# New way: Tenant-scoped roles
from tenant_authx.models import Tenant, Role, Permission, TenantMembership

# Create tenant-specific role
managers = Role.objects.create(
    tenant=tenant,
    name="Managers",
)

# Create tenant-specific permission
permission = Permission.objects.create(
    tenant=tenant,
    codename="myapp.add_order",
    name="Can add orders",
)
managers.permissions.add(permission)

# Add to membership (not directly to user)
membership = TenantMembership.objects.get(user=user, tenant=tenant)
membership.roles.add(managers)

# In views - use tenant_user instead
if request.tenant_user.has_perm("myapp.add_order"):
    ...
```

### Key Differences

| Django Built-in        | Tenant AuthX                     |
| ---------------------- | -------------------------------- |
| `user.has_perm()`      | `request.tenant_user.has_perm()` |
| Global permissions     | Tenant-scoped permissions        |
| `User.groups`          | `TenantMembership.roles`         |
| `@permission_required` | `@tenant_permission_required`    |
| `@login_required`      | `@tenant_login_required`         |

## Migrating Views

### Function-Based Views

```python
# Before
from django.contrib.auth.decorators import login_required, permission_required

@login_required
@permission_required("myapp.view_order")
def order_list(request):
    orders = Order.objects.all()
    return render(request, "orders.html", {"orders": orders})

# After
from tenant_authx.decorators import tenant_permission_required

@tenant_permission_required("myapp.view_order")
def order_list(request):
    # IMPORTANT: Filter by tenant!
    orders = Order.objects.filter(tenant=request.tenant)
    return render(request, "orders.html", {"orders": orders})
```

### Class-Based Views

```python
# Before
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin

class OrderListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "myapp.view_order"
    model = Order

# After
from django.utils.decorators import method_decorator
from tenant_authx.decorators import tenant_permission_required

@method_decorator(tenant_permission_required("myapp.view_order"), name="dispatch")
class OrderListView(ListView):
    model = Order

    def get_queryset(self):
        # IMPORTANT: Filter by tenant!
        return Order.objects.filter(tenant=self.request.tenant)
```

## Migrating DRF Views

### Before

```python
from rest_framework.permissions import IsAuthenticated

class OrderViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Order.objects.all()
```

### After

```python
from tenant_authx.drf import TenantSessionAuthentication, IsTenantMember

class OrderViewSet(viewsets.ModelViewSet):
    authentication_classes = [TenantSessionAuthentication]
    permission_classes = [IsTenantMember]

    def get_queryset(self):
        # IMPORTANT: Filter by tenant!
        return Order.objects.filter(tenant=self.request.tenant)
```

## Common Migration Patterns

### Pattern 1: Adding Tenant to Existing Model

```python
# 1. Add nullable tenant field first
class Order(models.Model):
    tenant = models.ForeignKey(
        "tenant_authx.Tenant",
        on_delete=models.CASCADE,
        null=True,  # Allow null initially
    )
    # ... other fields ...

# 2. Migrate existing data
def migrate_orders_to_tenant(apps, schema_editor):
    Order = apps.get_model("myapp", "Order")
    Tenant = apps.get_model("tenant_authx", "Tenant")

    default_tenant = Tenant.objects.first()
    Order.objects.filter(tenant__isnull=True).update(tenant=default_tenant)

# 3. Make tenant required
class Order(models.Model):
    tenant = models.ForeignKey(
        "tenant_authx.Tenant",
        on_delete=models.CASCADE,
        null=False,  # Now required
    )
```

### Pattern 2: Converting Groups to Roles

```python
from django.contrib.auth.models import Group
from tenant_authx.models import Role, Permission, TenantMembership

def migrate_groups_to_roles(tenant):
    for group in Group.objects.all():
        # Create tenant-scoped role
        role = Role.objects.create(
            tenant=tenant,
            name=group.name,
        )

        # Migrate permissions
        for perm in group.permissions.all():
            codename = f"{perm.content_type.app_label}.{perm.codename}"
            tenant_perm, _ = Permission.objects.get_or_create(
                tenant=tenant,
                codename=codename,
                defaults={"name": perm.name},
            )
            role.permissions.add(tenant_perm)

        # Migrate user memberships
        for user in group.user_set.all():
            membership, _ = TenantMembership.objects.get_or_create(
                user=user,
                tenant=tenant,
            )
            membership.roles.add(role)
```

## Troubleshooting

### "No tenant context available"

This error occurs when accessing a tenant-protected view without tenant resolution.

**Solution**: Check your URL patterns and `TENANT_AUTHX_TENANT_PATH_PATTERN` setting.

### "You are not a member of this tenant"

User authentication succeeded but they're not a member of the current tenant.

**Solution**: Create a `TenantMembership` for the user in the target tenant.

### Permission check always returns False

Common causes:

1. User is not a tenant member
2. Role is set to `is_active=False`
3. Permission codename format is wrong (should be `app.action_model`)

**Debug**:

```python
# Check membership
print(request.tenant_user.is_member())

# Check roles
print(request.tenant_user.get_roles())

# Check all permissions
print(request.tenant_user.get_all_permissions())
```
