"""Entry point for Dodgeville PD Scheduler."""

from ui.app import run

if __name__ == "__main__":
    from scripts.startup_gates import auto_before_gui

    gate_code = auto_before_gui()
    if gate_code != 0 and __import__("os").environ.get("SCHEDULER_BLOCK_ON_GATE_FAIL", "").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        raise SystemExit(gate_code)
    run()
