# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-01-18

### Added

- Core `Tenant`, `TenantMembership`, `Role`, and `Permission` models.
- `TenantAwareAuthBackend` for authenticating users within tenants.
- `TenantResolutionMiddleware` for identifying tenants from requests.
- `TenantUser` helper for easy permission checking.
- View decorators: `@tenant_login_required`, `@tenant_permission_required`, `@tenant_role_required`.
- DRF integration with `TenantTokenAuthentication` and permission classes.
- Comprehensive test suite with property-based testing and security audit.
- Django 4.2 LTS, 5.2 LTS, and 6.0 support.
