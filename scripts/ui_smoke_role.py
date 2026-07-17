"""Run one UI smoke role in an isolated process (fresh Tk root)."""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ["SCHEDULER_UI_TEST"] = "1"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--role-label", required=True)
    args = parser.parse_args()

    from scripts.ui_test_helpers import (
        assert_login_handlers_cleared,
        assert_nav_contains,
        assert_nav_excludes,
        authenticate_role,
        create_headless_app,
        destroy_app,
        headless_login,
        visit_all_pages,
    )

    errors: list[str] = []
    user = authenticate_role(args.username, args.password)
    if not user:
        print(f"FAIL: login failed for {args.username!r}")
        return 1

    app, callback_errors = create_headless_app()
    try:
        headless_login(app, user)
        assert_login_handlers_cleared(app.root, errors)
        if args.role_label in ("Administration", "Supervisor"):
            assert_nav_contains(app, "simulator", errors, role=args.role_label)
        if args.role_label == "Officer":
            assert_nav_excludes(app, "simulator", errors, role=args.role_label)
        # Brand images optional (runtime upload) — API only
        try:
            from photos import chronos_logo_path, department_logo_path

            chronos_logo_path()
            department_logo_path()
        except Exception as exc:
            errors.append(f"brand APIs: {exc}")
        visited = visit_all_pages(app, errors)
        if visited < 10:
            errors.append(f"only visited {visited} pages")
        if callback_errors:
            errors.append(f"{len(callback_errors)} Tk callback error(s)")
    except Exception as exc:
        errors.append(str(exc))
    finally:
        destroy_app(app.root)

    if errors:
        for err in errors:
            print(f"FAIL: {err}", file=sys.stderr)
        return 1
    print(f"OK: {args.role_label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
