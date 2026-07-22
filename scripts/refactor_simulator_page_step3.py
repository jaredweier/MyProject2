import re
import sys


def main():
    filepath = "gui/pages/simulator/page.py"
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    step3_start = content.find("        # ── Step 3 · Manual Build")
    step4_start = content.find("        # ── Step 4 · Publish")

    if step3_start == -1 or step4_start == -1:
        print("Could not find step3 or step4 blocks.")
        return

    new_step3 = """        # ── Step 3 · Manual Build ──────────────────────────────────────────
        step3 = ui.element("div").classes("w-full").style("display:none")
        step_panels[3] = step3
        with step3:
            render_manual_editor(
                state=state,
                step_panels=step_panels,
                go_step=go_step,
                _baseline_kwargs=lambda: _baseline_kwargs(),
                _current_config=lambda: _current_config(),
                set_plan=set_plan,
                set_summary=set_summary,
                session=session,
                save_last_optimized_plan=save_last_optimized_plan,
                format_optimized_plan_view=format_optimized_plan_view,
                length_input=length,
                officers_input=officers,
                starts_input=starts,
            )

"""
    content = content[:step3_start] + new_step3 + content[step4_start:]

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print("Replaced manual editor.")


if __name__ == "__main__":
    main()
