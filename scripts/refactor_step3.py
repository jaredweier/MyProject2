import re

with open("gui/pages/simulator/page.py", "r") as f:
    content = f.read()

imports = """from config import SIMULATOR_ROTATION_TYPES
from gui import session
from gui.pages.simulator.state import SimulatorState
from gui.pages.simulator.manual_editor import render_manual_editor
"""
content = re.sub(r"from config import SIMULATOR_ROTATION_TYPES\nfrom gui import session\n", imports, content)

state_init = """        state_obj = SimulatorState()
        state = state_obj.to_dict() # Temporary shim to keep dict access working
"""
content = re.sub(r'        state: dict = \{.*?"max_step_reached": 1,\n        \}', state_init, content, flags=re.DOTALL)

call_update = """            if n == 3:
                try:
                    if _manual_refresh_view:
                        _manual_refresh_view()
                except Exception:
                    pass"""
content = re.sub(
    r"            if n == 3:\n                try:\n                    _manual_refresh_view\(\)\n                except Exception:\n                    pass",
    call_update,
    content,
)

step_3_block = r"        # ── Step 3 · Manual Build ──────────────────────────────────────────.*?        # ── Step 4 · Publish ───────────────────────────────────────────────"
new_step_3 = """        # ── Step 3 · Manual Build ──────────────────────────────────────────
        _manual_refresh_view = render_manual_editor(
            state=state,
            step_panels=step_panels,
            go_step=go_step,
            _baseline_kwargs=lambda: _baseline_kwargs(),
            _current_config=lambda: _current_config(),
            set_plan=lambda p: set_plan(p),
            set_summary=lambda s: set_summary(s),
            session=session,
            save_last_optimized_plan=save_last_optimized_plan,
            format_optimized_plan_view=format_optimized_plan_view,
            length_input=length,
            officers_input=officers,
            starts_input=starts,
        )

        # ── Step 4 · Publish ───────────────────────────────────────────────"""
content = re.sub(step_3_block, new_step_3, content, flags=re.DOTALL)

with open("gui/pages/simulator/page.py", "w") as f:
    f.write(content)

print("page.py updated")
