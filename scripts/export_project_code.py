"""Concatenate project source into a single text file for offline reference."""

from __future__ import annotations

import base64
import os
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "docs" / "FULL_PROJECT_CODE.txt"

# Directories omitted from the dump (generated exports, session logs, etc.)
SKIP_DIRS = {
    ".git",
    "backups",
    "logs",
    "exports",
    "terminals",
    "node_modules",
    ".grok",
    "dist",  # full PyInstaller bundle — omit to keep dump small
}

SKIP_FILES = {
    OUTPUT.name,
    "check_result.log",
}

TEXT_SUFFIXES = {
    ".py",
    ".txt",
    ".md",
    ".bat",
    ".spec",
    ".json",
    ".toc",
    ".html",
    ".htm",
    ".tcl",
    ".tm",
    ".css",
    ".xml",
    ".yaml",
    ".yml",
    ".ini",
    ".cfg",
    ".csv",
    ".sql",
    ".rst",
    ".inc",
}


def should_include(path: Path) -> bool:
    if path.name in SKIP_FILES:
        return False
    try:
        path.relative_to(OUTPUT.parent)
        if path.resolve() == OUTPUT.resolve():
            return False
    except ValueError:
        pass
    return path.is_file()


def collect_files() -> list[Path]:
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            path = Path(dirpath) / name
            if should_include(path):
                files.append(path)
    return sorted(files, key=lambda p: str(p.relative_to(ROOT)).replace("\\", "/"))


def read_as_text(path: Path) -> str | None:
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def encode_binary(path: Path) -> tuple[str, int]:
    data = path.read_bytes()
    encoded = base64.b64encode(data).decode("ascii")
    wrapped = "\n".join(encoded[i : i + 76] for i in range(0, len(encoded), 76))
    return wrapped, len(data)


def write_file_section(out, path: Path) -> tuple[int, bool]:
    rel = path.relative_to(ROOT).as_posix()
    text = read_as_text(path)
    lines = 0
    if text is not None:
        out.write(f"{'=' * 80}\n")
        out.write(f"FILE: {rel}\n")
        out.write(f"{'=' * 80}\n")
        if text and not text.endswith("\n"):
            text += "\n"
        out.write(text)
        out.write("\n")
        lines = text.count("\n")
        return lines, False

    payload, byte_len = encode_binary(path)
    out.write(f"{'=' * 80}\n")
    out.write(f"FILE: {rel} (binary, base64, {byte_len} bytes)\n")
    out.write(f"{'=' * 80}\n")
    out.write(payload)
    out.write("\n\n")
    lines = payload.count("\n") + 2
    return lines, True


def main() -> None:
    files = collect_files()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    lines_written = 0
    binary_count = 0
    with OUTPUT.open("w", encoding="utf-8", newline="\n") as out:
        out.write("Dodgeville PD Scheduler — Full Project Code Dump\n")
        out.write(f"Generated: {date.today().isoformat()}\n")
        out.write(f"Root: {ROOT}\n")
        out.write(f"Files: {len(files)}\n")
        out.write(
            "Includes: source, docs, database (base64), build/, __pycache__/ (dist/ omitted — run build locally).\n"
        )
        out.write(
            "Binary files are base64-encoded. Decode with: "
            "python -c \"import base64,sys; open(sys.argv[2],'wb').write("
            'base64.b64decode(open(sys.argv[1]).read()))" SECTION.txt out.db\n'
        )
        out.write("=" * 80 + "\n\n")
        for path in files:
            lines, is_binary = write_file_section(out, path)
            lines_written += lines
            if is_binary:
                binary_count += 1
    size_kb = OUTPUT.stat().st_size / 1024
    size_mb = size_kb / 1024
    print(f"Wrote {OUTPUT}")
    print(f"  {len(files)} files ({binary_count} binary), ~{lines_written:,} lines, {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
