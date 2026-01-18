# Architecture Documentation

This document describes the architecture and design decisions behind django-tenant-authx.

## Overview

django-tenant-authx provides tenant-aware authentication and authorization for Django multi-tenant SaaS applications. It extends Django's authentication system without replacing or monkey-patching it.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                          HTTP Request                                │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    TenantResolutionMiddleware                        │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐      │
│  │ DomainResolver  │  │ SubdomainRes.   │  │ PathResolver    │      │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘      │
│                              │                                       │
│                              ▼                                       │
│                    request.tenant = Tenant                           │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      TenantUserMiddleware                            │
│                              │                                       │
│                              ▼                                       │
│            request.tenant_user = TenantUser(user, tenant)            │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         View / API Endpoint                          │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ @tenant_permission_required("orders.view_order")            │    │
│  │                                                              │    │
│  │    if request.tenant_user.has_perm("orders.edit_order"):    │    │
│  │        # User has permission in this tenant                 │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Data Models

#### Entity Relationship Diagram

```
┌──────────────┐       ┌──────────────────────┐       ┌──────────────┐
│    Tenant    │       │  TenantMembership    │       │     User     │
├──────────────┤       ├──────────────────────┤       ├──────────────┤
│ id (UUID)    │───┐   │ id (UUID)            │   ┌───│ id           │
│ name         │   │   │ user (FK)        ────│───┘   │ username     │
│ slug (unique)│   │   │ tenant (FK)      ────│───┐   │ email        │
│ domain       │   │   │ roles (M2M)          │   │   │ ...          │
│ is_active    │   │   │ is_active            │   │   └──────────────┘
│ metadata     │   │   │ joined_at            │   │
└──────────────┘   │   └──────────────────────┘   │
        │          │              │                │
        │          └──────────────┼────────────────┘
        │                         │
        │                         ▼
        │          ┌──────────────────────┐
        │          │        Role          │
        │          ├──────────────────────┤
        │          │ id (UUID)            │
        └──────────│ tenant (FK)          │
                   │ name                 │
                   │ permissions (M2M)    │
                   │ is_active            │
                   └──────────────────────┘
                              │
                              ▼
                   ┌──────────────────────┐
                   │     Permission       │
                   ├──────────────────────┤
                   │ id (UUID)            │
                   │ tenant (FK)      ────│───────┐
                   │ codename             │       │
                   │ name                 │       │
                   │ description          │       │
                   └──────────────────────┘       │
                                                  │
                                          (to Tenant)
```

#### Design Decisions

- **UUID Primary Keys**: Prevents enumeration attacks and makes merging tenants easier.
- **Tenant Scoping**: All permission-related models (Role, Permission) are scoped to a specific Tenant.
- **ManyToMany Relationships**: Flexible role and permission assignment.
- **Unique Constraints**: Enforced at database level for data integrity.

### 2. Middleware

The middleware stack is critical for tenant context:

```python
MIDDLEWARE = [
    # ... Django middleware ...
    "django.contrib.auth.middleware.AuthenticationMiddleware",  # Sets request.user
    "tenant_authx.middleware.TenantResolutionMiddleware",       # Sets request.tenant
    "tenant_authx.middleware.TenantUserMiddleware",             # Sets request.tenant_user
    # ... more middleware ...
]
```

**Order matters!** TenantResolutionMiddleware must run after AuthenticationMiddleware.

### 3. Permission Checking Flow

```
TenantUser.has_perm("orders.view_order")
                    │
                    ▼
        ┌──────────────────────┐
        │ Is user superuser?   │──── YES ──▶ Return True
        └──────────────────────┘
                    │ NO
                    ▼
        ┌──────────────────────┐
        │ Get membership in    │──── NOT FOUND ──▶ Return False
        │ current tenant       │
        └──────────────────────┘
                    │ FOUND
                    ▼
        ┌──────────────────────┐
        │ Get all roles from   │
        │ membership           │
        └──────────────────────┘
                    │
                    ▼
        ┌──────────────────────┐
        │ Check if any role    │──── NO ──▶ Return False
        │ has permission       │
        └──────────────────────┘
                    │ YES
                    ▼
              Return True
```

### 4. Resolution Strategies

| Strategy      | Use Case                   | Configuration                                        |
| ------------- | -------------------------- | ---------------------------------------------------- |
| **Domain**    | Each tenant has own domain | `TENANT_AUTHX_TENANT_RESOLUTION_STRATEGY = "domain"` |
| **Subdomain** | `tenant.example.com`       | Requires `TENANT_AUTHX_BASE_DOMAIN`                  |
| **Path**      | `/t/tenant-slug/...`       | Default, easiest for development                     |
| **Header**    | API with `X-Tenant-Slug`   | For microservices                                    |

## Security Considerations

### Tenant Isolation

1. **Query Filtering**: Always filter database queries by tenant!
2. **Permission Scoping**: Permissions are evaluated only within tenant context.
3. **Object Permission**: Use `TenantObjectPermission` to verify objects belong to current tenant.

### Audit Logging

All authentication and authorization events are logged:

```python
from tenant_authx.utils import audit_log

audit_log(
    event="permission_check",
    user=request.user,
    tenant=request.tenant,
    permission="orders.view_order",
    success=True,
)
```

### Best Practices

1. **Never trust client-provided tenant identifiers** - always resolve from request.
2. **Always include tenant filter in querysets** - the library does NOT do this automatically.
3. **Use decorators on all views** - don't rely on manual permission checks.
4. **Enable audit logging in production** - monitor for suspicious activity.

## Extension Points

### Custom Resolver

```python
from tenant_authx.resolvers import BaseTenantResolver

class MyCustomResolver(BaseTenantResolver):
    def resolve(self, request):
        # Your custom logic
        return self.get_tenant_by_slug(some_slug)
```

### Custom Permission Logic

Extend `PermissionChecker` or override `TenantUser.has_perm()`:

```python
class CustomTenantUser(TenantUser):
    def has_perm(self, perm, obj=None):
        # Custom logic before standard check
        if self.is_special_user():
            return True
        return super().has_perm(perm, obj)
```
