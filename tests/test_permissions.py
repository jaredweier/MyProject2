import unittest

from permissions import PERMISSIONS, USER_ROLES, role_has_permission
from ui.theme import NAV_ITEMS, NAV_PERMISSIONS


class PermissionsMatrixTests(unittest.TestCase):
    def test_every_permission_has_allowed_roles(self):
        for key, roles in PERMISSIONS.items():
            self.assertTrue(roles, f"{key} has no roles")
            for role in roles:
                self.assertIn(role, USER_ROLES, f"{key} references unknown role {role}")

    def test_administration_has_sensitive_permissions(self):
        sensitive = (
            "users.manage",
            "settings.manage",
            "holidays.manage",
        )
        for perm in sensitive:
            self.assertTrue(
                role_has_permission("Administration", perm),
                f"Administration should have {perm}",
            )

    def test_officer_denied_sensitive_permissions(self):
        denied = (
            "users.manage",
            "settings.manage",
            "payroll.lock_period",
            "database.backup",
            "officers.manage",
        )
        for perm in denied:
            self.assertFalse(
                role_has_permission("Officer", perm),
                f"Officer should not have {perm}",
            )

    def test_officer_cannot_manage_users(self):
        self.assertFalse(role_has_permission("Officer", "users.manage"))

    def test_supervisor_can_approve_requests(self):
        self.assertTrue(role_has_permission("Supervisor", "requests.approve"))

    def test_admin_has_settings_manage(self):
        self.assertTrue(role_has_permission("Administration", "settings.manage"))

    def test_supervisor_cannot_manage_settings(self):
        self.assertFalse(role_has_permission("Supervisor", "settings.manage"))

    def test_every_nav_permission_is_defined(self):
        for _key, perm in NAV_PERMISSIONS.items():
            perms = perm if isinstance(perm, tuple) else (perm,)
            for name in perms:
                self.assertIn(name, PERMISSIONS, f"NAV permission missing: {name}")

    def test_officer_cannot_access_gated_nav_permissions(self):
        for page_key, _label, _icon in NAV_ITEMS:
            perm = NAV_PERMISSIONS.get(page_key)
            if not perm:
                continue
            perms = perm if isinstance(perm, tuple) else (perm,)
            self.assertFalse(
                any(role_has_permission("Officer", p) for p in perms),
                f"Officer should not access gated nav '{page_key}' ({perms})",
            )


if __name__ == "__main__":
    unittest.main()
