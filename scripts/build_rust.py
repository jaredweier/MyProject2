"""Build the scheduler_core Rust extension via maturin."""

from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_build_rust(*, release: bool = True) -> int:
    os.chdir(ROOT)
    try:
        import maturin  # noqa: F401
    except ImportError:
        print("build-rust: installing maturin...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "maturin"])

    cmd = [sys.executable, "-m", "maturin", "develop"]
    if release:
        cmd.append("--release")
    print("build-rust:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode == 0:
        try:
            import scheduler_core

            print(f"build-rust: OK — {scheduler_core.backend_info()}")
        except ImportError as exc:
            print(f"build-rust: built but import failed: {exc}")
            return 1
    return result.returncode


if __name__ == "__main__":
    release = "--debug" not in sys.argv
    raise SystemExit(run_build_rust(release=release))
