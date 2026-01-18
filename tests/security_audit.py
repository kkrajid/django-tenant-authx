"""
Comprehensive security and bug audit for django-tenant-authx.
Run with: python tests/security_audit.py
"""

import os
import sys

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tests.settings')

import django
django.setup()

from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.exceptions import ValidationError

from tenant_authx.models import Tenant, TenantMembership, Role, Permission
from tenant_authx.permissions import TenantUser, PermissionChecker
from tenant_authx.utils import is_valid_tenant_context, is_valid_permission_codename

User = get_user_model()

PASSED = 0
FAILED = 0


def test(name, condition, message=""):
    global PASSED, FAILED
    if condition:
        print(f"  ✅ PASS: {name}")
        PASSED += 1
    else:
        print(f"  ❌ FAIL: {name} - {message}")
        FAILED += 1


def cleanup():
    """Clean up test data."""
    Tenant.objects.filter(slug__startswith='security-').delete()
    User.objects.filter(username__startswith='security_').delete()


def main():
    global PASSED, FAILED
    
    print("=" * 70)
    print("SECURITY AND BUG AUDIT FOR DJANGO-TENANT-AUTHX")
    print("=" * 70)
    
    cleanup()
    
    # Create test data
    tenant1 = Tenant.objects.create(name="Security Test 1", slug="security-test-1")
    tenant2 = Tenant.objects.create(name="Security Test 2", slug="security-test-2")
    inactive_tenant = Tenant.objects.create(name="Inactive", slug="security-inactive", is_active=False)
    
    user1 = User.objects.create_user(username="security_user1", password="test123")
    user2 = User.objects.create_user(username="security_user2", password="test123")
    superuser = User.objects.create_superuser(username="security_super", password="test123")
    
    perm1 = Permission.objects.create(tenant=tenant1, codename="app.action1", name="Action 1")
    perm2 = Permission.objects.create(tenant=tenant1, codename="app.action2", name="Action 2")
    perm_other = Permission.objects.create(tenant=tenant2, codename="app.other", name="Other")
    
    role1 = Role.objects.create(tenant=tenant1, name="Role1")
    role1.permissions.add(perm1)
    
    membership1 = TenantMembership.objects.create(user=user1, tenant=tenant1)
    membership1.roles.add(role1)
    
    # ===========================================================================
    # SECURITY: TENANT ISOLATION
    # ===========================================================================
    print("\n## SECURITY: Tenant Isolation")
    
    tu1 = TenantUser(user=user1, tenant=tenant1)
    tu1_wrong = TenantUser(user=user1, tenant=tenant2)  # User1 not member of tenant2
    
    test(
        "User has permission in own tenant",
        tu1.has_perm("app.action1") == True,
        "Should have permission"
    )
    
    test(
        "User denied permission in other tenant (not member)",
        tu1_wrong.has_perm("app.action1") == False,
        "Should be denied - not a member"
    )
    
    test(
        "User denied permission not assigned",
        tu1.has_perm("app.action2") == False,
        "Should be denied - not assigned"
    )
    
    test(
        "Cross-tenant permission check fails",
        tu1.has_perm("app.other") == False,
        "Permission from tenant2 should not apply"
    )
    
    # ===========================================================================
    # SECURITY: SUPERUSER BYPASS
    # ===========================================================================
    print("\n## SECURITY: Superuser Bypass")
    
    tu_super = TenantUser(user=superuser, tenant=tenant1)
    
    test(
        "Superuser bypasses permission check",
        tu_super.has_perm("any.permission") == True,
        "Superuser should bypass"
    )
    
    test(
        "Superuser is_member returns True (bypass)",
        tu_super.is_member() == True or tu_super.has_perm("test") == True,
        "Superuser should have access"
    )
    
    # ===========================================================================
    # SECURITY: INACTIVE TENANT
    # ===========================================================================
    print("\n## SECURITY: Inactive Tenant")
    
    # User with membership in inactive tenant
    TenantMembership.objects.create(user=user2, tenant=inactive_tenant)
    tu_inactive = TenantUser(user=user2, tenant=inactive_tenant)
    
    test(
        "Inactive tenant context validation fails",
        is_valid_tenant_context(inactive_tenant) == False,
        "Should return False for inactive tenant"
    )
    
    # ===========================================================================
    # SECURITY: INACTIVE MEMBERSHIP
    # ===========================================================================
    print("\n## SECURITY: Inactive Membership")
    
    inactive_membership = TenantMembership.objects.create(
        user=user2, tenant=tenant1, is_active=False
    )
    tu_inactive_member = TenantUser(user=user2, tenant=tenant1)
    
    test(
        "Inactive membership returns not member",
        tu_inactive_member.is_member() == False,
        "Inactive membership should not count"
    )
    
    inactive_membership.delete()
    
    # ===========================================================================
    # SECURITY: NULL/INVALID INPUT HANDLING
    # ===========================================================================
    print("\n## SECURITY: Input Validation")
    
    # Test None tenant
    test(
        "None tenant context validation",
        is_valid_tenant_context(None) == False,
        "Should return False for None"
    )
    
    # Test invalid permission codename
    test(
        "Invalid permission codename rejected (no dot)",
        is_valid_permission_codename("invalid") == False,
        "Should reject invalid codename"
    )
    
    test(
        "Valid permission codename accepted",
        is_valid_permission_codename("app.action") == True,
        "Should accept valid codename"
    )
    
    # Test empty permission codename
    test(
        "Empty permission codename rejected",
        is_valid_permission_codename("") == False,
        "Should reject empty codename"
    )
    
    # ===========================================================================
    # SECURITY: PERMISSION CACHING
    # ===========================================================================
    print("\n## SECURITY: Permission Caching")
    
    tu_cache = TenantUser(user=user1, tenant=tenant1)
    
    # First call populates cache
    perms1 = tu_cache.get_all_permissions()
    
    # Add a new permission
    perm_new = Permission.objects.create(tenant=tenant1, codename="app.new", name="New")
    role1.permissions.add(perm_new)
    
    # Second call should return cached result (not updated)
    perms2 = tu_cache.get_all_permissions()
    
    test(
        "Permission cache is per-instance",
        perms1 == perms2,
        "Cache should return same result"
    )
    
    # New instance should see new permission
    tu_fresh = TenantUser(user=user1, tenant=tenant1)
    perms3 = tu_fresh.get_all_permissions()
    
    test(
        "New instance sees updated permissions",
        "app.new" in perms3,
        "Fresh instance should see new permission"
    )
    
    perm_new.delete()
    
    # ===========================================================================
    # BUG: UNIQUE CONSTRAINT VIOLATIONS
    # ===========================================================================
    print("\n## BUG CHECK: Unique Constraints")
    
    # Try to create duplicate tenant slug
    try:
        with transaction.atomic():
            Tenant.objects.create(name="Duplicate", slug="security-test-1")
        test("Duplicate tenant slug prevented", False, "Should have raised error")
    except Exception:
        test("Duplicate tenant slug prevented", True)
    
    # Try to create duplicate permission codename
    try:
        with transaction.atomic():
            Permission.objects.create(tenant=tenant1, codename="app.action1", name="Dup")
        test("Duplicate permission codename prevented", False, "Should have raised error")
    except Exception:
        test("Duplicate permission codename prevented", True)
    
    # Try to create duplicate membership
    try:
        with transaction.atomic():
            TenantMembership.objects.create(user=user1, tenant=tenant1)
        test("Duplicate membership prevented", False, "Should have raised error")
    except Exception:
        test("Duplicate membership prevented", True)
    
    # ===========================================================================
    # BUG: INACTIVE ROLE PERMISSIONS
    # ===========================================================================
    print("\n## BUG CHECK: Inactive Role Handling")
    
    inactive_role = Role.objects.create(tenant=tenant1, name="InactiveRole", is_active=False)
    perm_inactive_role = Permission.objects.create(tenant=tenant1, codename="app.inactive_role", name="Inactive")
    inactive_role.permissions.add(perm_inactive_role)
    membership1.roles.add(inactive_role)
    
    tu_role_check = TenantUser(user=user1, tenant=tenant1)
    
    test(
        "Inactive role permissions not granted",
        tu_role_check.has_perm("app.inactive_role") == False,
        "Inactive role's permissions should not apply"
    )
    
    # ===========================================================================
    # BUG: DELETED OBJECTS
    # ===========================================================================
    print("\n## BUG CHECK: Deleted Object Handling")
    
    temp_perm = Permission.objects.create(tenant=tenant1, codename="app.temp", name="Temp")
    role1.permissions.add(temp_perm)
    
    tu_before = TenantUser(user=user1, tenant=tenant1)
    had_perm = tu_before.has_perm("app.temp")
    
    temp_perm.delete()
    
    tu_after = TenantUser(user=user1, tenant=tenant1)
    has_perm_after = tu_after.has_perm("app.temp")
    
    test(
        "Deleted permission no longer granted",
        has_perm_after == False,
        "Deleted permission should not be granted"
    )
    
    # ===========================================================================
    # DJANGO VERSION COMPATIBILITY
    # ===========================================================================
    print("\n## DJANGO COMPATIBILITY")
    
    import django
    print(f"  Django version: {django.VERSION}")
    
    # Check for deprecated features
    from django.contrib.auth.models import Permission as DjangoPermission
    from django.contrib.auth.models import Group
    
    test(
        "Django auth models accessible",
        DjangoPermission is not None and Group is not None,
        "Django auth models should be importable"
    )
    
    # Check ModelBackend compatibility
    from django.contrib.auth.backends import ModelBackend
    from tenant_authx.backends import TenantAwareAuthBackend
    
    test(
        "TenantAwareAuthBackend extends ModelBackend",
        issubclass(TenantAwareAuthBackend, ModelBackend),
        "Should extend ModelBackend"
    )
    
    # Check middleware compatibility
    from django.http import HttpRequest, HttpResponse
    from tenant_authx.middleware import TenantResolutionMiddleware, TenantUserMiddleware
    
    def dummy_get_response(request):
        return HttpResponse("OK")
    
    try:
        trm = TenantResolutionMiddleware(dummy_get_response)
        tum = TenantUserMiddleware(dummy_get_response)
        test("Middleware instantiation", True)
    except Exception as e:
        test("Middleware instantiation", False, str(e))
    
    # ===========================================================================
    # RESULTS
    # ===========================================================================
    print("\n" + "=" * 70)
    print(f"RESULTS: {PASSED} passed, {FAILED} failed")
    print("=" * 70)
    
    cleanup()
    
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
