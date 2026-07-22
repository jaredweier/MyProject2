import re
import sys


def main():
    filepath = "gui/pages/simulator/page.py"
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    step4_start = content.find("        # ── Step 4 · Publish")
    logic_helpers = content.find("        # ── Logic helpers")

    if step4_start == -1 or logic_helpers == -1:
        print("Could not find step4 or logic helpers.")
        return

    new_step4 = """        # ── Step 4 · Publish ───────────────────────────────────────────────
        from gui.pages.simulator.publish_panel import render_publish_panel
        step4, pub_elements = render_publish_panel(state, go_step)
        step_panels[4] = step4
        impl_date = pub_elements.get("impl_date")
        apply_officers = pub_elements.get("apply_officers")
        force_regen = pub_elements.get("force_regen")
        save_defaults = pub_elements.get("save_defaults")
        set_action_log = pub_elements.get("set_action_log")
        btn_impl = pub_elements.get("btn_impl")
        btn_preview = pub_elements.get("btn_preview")
        btn_apply_stay = pub_elements.get("btn_apply_stay")
        btn_apply_pub = pub_elements.get("btn_apply_pub")
        btn_save = pub_elements.get("btn_save")
        btn_csv = pub_elements.get("btn_csv")
        btn_bid = pub_elements.get("btn_bid")

"""
    content = content[:step4_start] + new_step4 + content[logic_helpers:]

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print("Replaced publish panel.")


if __name__ == "__main__":
    main()
