import re
import sys


def main():
    filepath = "gui/pages/simulator/page.py"
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Find the start of the results_panel tools section
    # show_pins is the first one at 3426.
    start_idx = content.find("        def show_pins():")
    if start_idx == -1:
        print("Could not find show_pins().")
        return

    # We want to replace everything from `def show_pins():` to the end of `def show_weekend_heat():` block.
    # The `def show_weekend_heat():` block ends before `def run_import_live():` or something else?
    # Let's just find the end by looking for the next top-level def in that scope, or end of file.
    # We can parse out the functions one by one using regex, but they are scattered.

    # Actually, all these functions are just blocks. Let's just do a regex replace for each function block.
    # But wait, there are local variables and logic.
    # Let's just inject the render_results_panel_tools call right before `def show_pins()`

    injection = """
        from gui.pages.simulator.results_panel import render_results_panel_tools
        results_tools = render_results_panel_tools(state, _apply_ranked_option, _apply_form_payload, set_plan, plan_box, _ui_safe, set_why)
        def show_search_history(): results_tools["show_search_history"]()
        def show_pins(): results_tools["show_pins"]()
        def show_slots(): results_tools["show_slots"]()
        def do_heat(): results_tools["do_heat"]()
        def show_weekend_heat(): results_tools["show_weekend_heat"]()
        def do_window_drill(): results_tools["do_window_drill"]()
"""

    # Now we need to DELETE the existing bodies of those 6 functions.
    # It's safer to find them and remove them.
    # Let's use ast to find and remove them.
    # Actually, manipulating code as strings is easier if we just split by lines.

    lines = content.split("\n")
    new_lines = []
    skip = False
    funcs_to_remove = [
        "def show_search_history(",
        "def show_pins(",
        "def show_slots(",
        "def do_heat(",
        "def show_weekend_heat(",
        "def do_window_drill(",
    ]

    for line in lines:
        if skip:
            if line.startswith("        def ") and not any(f in line for f in funcs_to_remove):
                skip = False
            elif (
                line.startswith("    def ")
                or line.startswith("def ")
                or line.startswith("    #")
                or line == "        # ── Commands ───────────────────────────────────────────────────────"
                or line == "        def _load_option(idx: int):"
            ):
                # Reached next block
                skip = False

        if not skip:
            if any(line.startswith(f"        {f}") for f in funcs_to_remove):
                skip = True
                continue
            new_lines.append(line)

    # Now insert the injection before `def _load_option` or at the end of the helper section
    # Let's find where to put the injection.
    # We can put it right before `def _load_option(idx: int):`

    content = "\n".join(new_lines)
    idx = content.find("        def _load_option(idx: int):")
    if idx == -1:
        idx = content.find("        def implement_plan():")

    content = content[:idx] + injection + "\n" + content[idx:]

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print("Replaced results panel tools.")


if __name__ == "__main__":
    main()
