"""Cross-platform helper to add Cursor CLI to PATH (Windows PowerShell wrapper)."""

from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_install_cursor_cli(*, bin_path: str = "", add_expected: bool = False) -> int:
    os.chdir(ROOT)
    ps1 = os.path.join(ROOT, "scripts", "install_cursor_cli_path.ps1")
    if not os.path.isfile(ps1):
        print("install-cursor-cli: missing install_cursor_cli_path.ps1")
        return 1

    argv = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        ps1,
    ]
    if bin_path:
        argv.append(f"-CursorBinPath={bin_path}")
    if add_expected:
        argv.append("-AddExpectedPath")

    print("Dodgeville PD — install Cursor CLI")
    result = subprocess.run(argv, cwd=ROOT)
    return result.returncode


if __name__ == "__main__":
    path = ""
    add_expected = False
    for arg in sys.argv[1:]:
        if arg.startswith("--bin="):
            path = arg.split("=", 1)[1]
        if arg in ("--add-expected", "--add-expected-path"):
            add_expected = True
    raise SystemExit(run_install_cursor_cli(bin_path=path, add_expected=add_expected))
