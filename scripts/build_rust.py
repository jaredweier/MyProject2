"""Build the scheduler_core Rust extension via maturin."""

from __future__ import annotations

import glob
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _has_virtualenv() -> bool:
    if os.environ.get("VIRTUAL_ENV") or os.environ.get("CONDA_PREFIX"):
        return True
    path = ROOT
    while True:
        if os.path.isdir(os.path.join(path, ".venv")):
            return True
        parent = os.path.dirname(path)
        if parent == path:
            return False
        path = parent


def _verify_import() -> int:
    try:
        import scheduler_core

        print(f"build-rust: OK — {scheduler_core.backend_info()}")
        return 0
    except ImportError as exc:
        print(f"build-rust: built but import failed: {exc}")
        return 1


def run_build_rust(*, release: bool = True) -> int:
    os.chdir(ROOT)
    try:
        import maturin  # noqa: F401
    except ImportError:
        print("build-rust: installing maturin...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "maturin"])

    profile = ["--release"] if release else []

    if _has_virtualenv():
        cmd = [sys.executable, "-m", "maturin", "develop", *profile]
        print("build-rust:", " ".join(cmd))
        result = subprocess.run(cmd, cwd=ROOT)
        if result.returncode != 0:
            return result.returncode
        return _verify_import()

    cmd = [sys.executable, "-m", "maturin", "build", *profile]
    print("build-rust:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        return result.returncode

    wheel_glob = os.path.join(ROOT, "rust", "scheduler_core", "target", "wheels", "*.whl")
    wheels = sorted(glob.glob(wheel_glob), key=os.path.getmtime, reverse=True)
    if not wheels:
        print(f"build-rust: no wheel found at {wheel_glob}")
        return 1

    pip_cmd = [sys.executable, "-m", "pip", "install", "--force-reinstall", wheels[0]]
    print("build-rust:", " ".join(pip_cmd))
    pip_result = subprocess.run(pip_cmd, cwd=ROOT)
    if pip_result.returncode != 0:
        return pip_result.returncode
    return _verify_import()


if __name__ == "__main__":
    release = "--debug" not in sys.argv
    raise SystemExit(run_build_rust(release=release))
