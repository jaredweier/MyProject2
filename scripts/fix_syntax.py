import sys


def main():
    filepath = "gui/pages/simulator/page.py"
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    bad_block = [
        "        from gui.pages.simulator.results_panel import render_results_panel_tools\n",
        "        results_tools = render_results_panel_tools(state, _apply_ranked_option, _apply_form_payload, set_plan, plan_box, _ui_safe, set_why)\n",
        '        def show_search_history(): results_tools["show_search_history"]()\n',
        '        def show_pins(): results_tools["show_pins"]()\n',
        '        def show_slots(): results_tools["show_slots"]()\n',
        '        def do_heat(): results_tools["do_heat"]()\n',
        '        def show_weekend_heat(): results_tools["show_weekend_heat"]()\n',
        '        def do_window_drill(): results_tools["do_window_drill"]()\n',
    ]

    new_lines = []
    for line in lines:
        if line in bad_block or "def do_window_drill(): results_tools" in line:
            continue
        new_lines.append(line)

    # Now we must place this block securely where the variables it needs are in scope.
    # It needs state, _apply_ranked_option, _apply_form_payload, set_plan, plan_box, _ui_safe, set_why.
    # Let's find where _apply_ranked_option is defined.
    # Then insert the block immediately after it.

    insert_idx = -1
    for i, line in enumerate(new_lines):
        if line.startswith("        def _apply_ranked_option"):
            # find end of this function
            # function ends when indentation goes back to 8 spaces with a non-empty line
            for j in range(i + 1, len(new_lines)):
                if new_lines[j].strip() and not new_lines[j].startswith("            "):
                    insert_idx = j
                    break
            break

    if insert_idx != -1:
        new_lines.insert(insert_idx, "".join(bad_block))
        print("Fixed and inserted correctly.")
    else:
        print("Could not find _apply_ranked_option.")

    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


if __name__ == "__main__":
    main()
