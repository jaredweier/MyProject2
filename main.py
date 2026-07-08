"""Entry point for Dodgeville PD Scheduler."""

import os
import sys
import traceback

from ui.display import enable_windows_dpi_awareness

enable_windows_dpi_awareness()


def _bootstrap_runtime() -> None:
    """Frozen .exe: cwd + crash log next to the executable."""
    try:
        from paths import app_dir, data_path, ensure_data_dirs, is_frozen

        if is_frozen():
            os.chdir(app_dir())
        ensure_data_dirs()
        crash_log = data_path(os.path.join("logs", "crash.log"))

        def _hook(exc_type, exc, tb):
            try:
                with open(crash_log, "a", encoding="utf-8") as fh:
                    fh.write("".join(traceback.format_exception(exc_type, exc, tb)))
                    fh.write("\n")
            except Exception:
                pass
            sys.__excepthook__(exc_type, exc, tb)

        sys.excepthook = _hook
    except Exception:
        pass


_bootstrap_runtime()

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
