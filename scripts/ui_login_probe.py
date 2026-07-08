"""Probe login branding + post-login shell (subprocess gate — catches real UI failures)."""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def main() -> int:
    os.environ["SCHEDULER_UI_TEST"] = "1"
    errors: list[str] = []

    from paths import resource_path

    for name in ("logo.png", "team_photo.jpg"):
        if not os.path.isfile(resource_path(name)):
            errors.append(f"missing asset: {name}")

    from ui.assets import load_logo, load_team_photo

    if load_logo((64, 64)) is None:
        errors.append("load_logo returned None")
    if load_team_photo((320, 200), cover=True, rounded=False, border=False) is None:
        errors.append("load_team_photo returned None")

    import customtkinter as ctk

    from ui.login import LoginFrame

    root = ctk.CTk()
    root.withdraw()
    frame = LoginFrame(root, on_success=lambda _u: None)
    frame.update_idletasks()
    frame.update()
    frame._paint_brand_images()
    frame.update_idletasks()
    frame.update()
    from ui.helpers import destroy_tk_root, label_has_image

    if frame._photo_label is None:
        errors.append("login photo label missing")
    elif not label_has_image(frame._photo_label):
        errors.append("login team photo not painted")
    if frame._logo_label is None or not label_has_image(frame._logo_label):
        errors.append("login logo not painted")
    frame.destroy()
    destroy_tk_root(root)

    from scripts.ui_test_helpers import (
        authenticate_role,
        create_headless_app,
        destroy_app,
        headless_login,
        shell_ready,
        visit_all_pages,
    )

    user = authenticate_role("admin", "admin")
    if not user:
        errors.append("admin login failed")
    else:
        app, callback_errors = create_headless_app()
        try:
            headless_login(app, user)
            if not shell_ready(app):
                errors.append("shell not ready after login")
            visited = visit_all_pages(app, errors)
            if visited < 10:
                errors.append(f"only visited {visited} pages")
            if callback_errors:
                errors.append(f"{len(callback_errors)} Tk callback errors")
        finally:
            destroy_app(app.root)

    if errors:
        for err in errors:
            print(f"FAIL: {err}", file=sys.stderr)
        return 1
    print("OK: login probe passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
