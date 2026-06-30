"""
Static UI aesthetics, spelling, and wording review for Dodgeville PD Scheduler.

Scans ui/*.py for user-facing strings, theme consistency, and copy issues.
Writes logs/ui_review/<timestamp>/report.json and report.md.

Run: python dev.py ui-review
"""

from __future__ import annotations

import ast
import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_DIR = os.path.join(ROOT, "ui")
LOG_DIR = os.path.join(ROOT, "logs", "ui_review")
WHITELIST_PATH = os.path.join(ROOT, "scripts", "data", "ui_review_whitelist.txt")

# Approved theme color names (imported symbol or literal from config)
THEME_COLOR_SYMBOLS = {
    "DODGEVILLE_BLUE",
    "DODGEVILLE_ACCENT",
    "DODGEVILLE_RED",
    "DODGEVILLE_GOLD",
    "DODGEVILLE_SUCCESS",
    "DODGEVILLE_DANGER",
    "DODGEVILLE_WARNING",
    "DODGEVILLE_ORANGE",
    "UI_BG",
    "UI_SURFACE",
    "UI_SURFACE_LIGHT",
    "UI_BORDER",
    "UI_TEXT_MUTED",
    "UI_SIDEBAR",
    "transparent",
}
THEME_COLOR_LITERALS = {
    "#0D1B2A",
    "#1E88E5",
    "#C62828",
    "#F4C430",
    "#2E7D32",
    "#FF9800",
    "#E67E22",
    "#0A1420",
    "#152232",
    "#1C2D42",
    "#2A3F5F",
    "#8BA3C7",
    "#6B7280",
    "#FFFFFF",
    "#27AE60",
    "#4A5568",
    "#F39C12",
    "#9B59B6",
    "#3498DB",
    "#95A5A6",
}

COMMON_TYPOS = {
    "acheive": "achieve",
    "adress": "address",
    "aestetic": "aesthetic",
    "aestetically": "aesthetically",
    "calender": "calendar",
    "comming": "coming",
    "definately": "definitely",
    "occured": "occurred",
    "occurence": "occurrence",
    "recieve": "receive",
    "seperate": "separate",
    "sucess": "success",
    "sucessful": "successful",
    "teh": "the",
    "thier": "their",
    "untill": "until",
    "wierd": "weird",
}

# Pairs of terms that should not both appear as primary labels (wording consistency)
TERMINOLOGY_GROUPS = [
    ("time-off", "time off", "day-off", "day off", "timeoff"),
    ("dispatch alerts", "notifications", "alerts"),
    ("patrol roster", "officers", "officer roster"),
    ("current monthly schedule", "current monthly", "updated schedule", "updated roster"),
    ("shift exchange", "swaps", "shift swap"),
    ("blackout dates", "availability", "unavailable"),
    ("access control", "user accounts", "users"),
    ("ops reports", "reports", "analytics"),
    ("command post", "dashboard"),
]

STRING_KWARGS = frozenset(
    {
        "text",
        "placeholder_text",
        "title",
        "label",
        "message",
    }
)

HEX_RE = re.compile(r"#[0-9A-Fa-f]{3,8}")
DOUBLE_SPACE_RE = re.compile(r"  +")
WORD_RE = re.compile(r"[A-Za-z']+")


@dataclass
class Finding:
    category: str
    severity: str  # info | warn | error
    message: str
    file: str = ""
    line: int = 0
    context: str = ""
    suggestion: str = ""


@dataclass
class ReviewReport:
    generated_at: str
    ui_files_scanned: int
    strings_found: int
    findings: list[Finding] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)
    screenshots_dir: str = ""

    def add(self, finding: Finding) -> None:
        self.findings.append(finding)

    def finalize(self) -> None:
        counts: Counter[str] = Counter()
        for f in self.findings:
            counts[f.severity] += 1
            counts[f.category] += 1
        self.summary = dict(counts)


def _load_whitelist() -> set[str]:
    words: set[str] = set()
    if not os.path.isfile(WHITELIST_PATH):
        return words
    with open(WHITELIST_PATH, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            words.add(line.lower())
    return words


def _load_spellchecker():
    try:
        from spellchecker import SpellChecker  # type: ignore

        return SpellChecker(distance=1)
    except ImportError:
        return None


def _decode_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _extract_strings_from_ast(tree: ast.AST, path: str) -> list[tuple[int, str, str]]:
    """Return (line, kind, text) for user-facing strings."""
    results: list[tuple[int, str, str]] = []

    class Visitor(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:
            func_name = ""
            if isinstance(node.func, ast.Attribute):
                func_name = node.func.attr
            elif isinstance(node.func, ast.Name):
                func_name = node.func.id

            if func_name in ("showinfo", "showwarning", "showerror", "askyesno", "askokcancel"):
                if len(node.args) >= 1:
                    title = _decode_string(node.args[0])
                    if title:
                        results.append((node.lineno, "dialog_title", title))
                if len(node.args) >= 2:
                    body = _decode_string(node.args[1])
                    if body:
                        results.append((node.lineno, "dialog_message", body))
            elif func_name in ("CTkLabel", "CTkButton", "CTkCheckBox", "CTkRadioButton"):
                for kw in node.keywords:
                    if kw.arg in STRING_KWARGS:
                        val = _decode_string(kw.value)
                        if val:
                            results.append((node.lineno, kw.arg, val))
            elif func_name in ("CTkEntry", "CTkTextbox"):
                for kw in node.keywords:
                    if kw.arg == "placeholder_text":
                        val = _decode_string(kw.value)
                        if val:
                            results.append((node.lineno, "placeholder", val))

            for kw in node.keywords:
                if kw.arg in STRING_KWARGS:
                    val = _decode_string(kw.value)
                    if val:
                        results.append((node.lineno, kw.arg, val))

            self.generic_visit(node)

        def visit_Assign(self, node: ast.Assign) -> None:
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in (
                    "NAV_ITEMS",
                    "subtitles",
                    "officer_subtitles",
                    "titles",
                ):
                    val = _decode_string(node.value)
                    if val:
                        results.append((node.lineno, "assign", val))
            self.generic_visit(node)

    Visitor().visit(tree)

    # Regex fallback for dict literals and configure(text=...) patterns
    with open(path, encoding="utf-8") as fh:
        lines = fh.readlines()

    patterns = [
        (re.compile(r'\btext\s*=\s*["\']([^"\']{2,})["\']'), "text"),
        (re.compile(r'placeholder_text\s*=\s*["\']([^"\']{2,})["\']'), "placeholder"),
        (re.compile(r'\.title\s*\(\s*["\']([^"\']{2,})["\']'), "window_title"),
        (re.compile(r'["\']([A-Za-z][^"\']{4,})["\']\s*:\s*["\']'), "dict_key"),
        (re.compile(r':\s*["\']([^"\']{6,})["\']\s*,?\s*$'), "dict_value"),
    ]
    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if "import " in stripped or stripped.startswith("from "):
            continue
        for pattern, kind in patterns:
            for match in pattern.finditer(line):
                text = match.group(1)
                if "{" in text or "}" in text or text.startswith("f"):
                    continue
                if len(text) < 2:
                    continue
                results.append((idx, kind, text))

    # Deduplicate
    seen: set[tuple[int, str, str]] = set()
    unique: list[tuple[int, str, str]] = []
    for item in results:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def _is_probably_code(text: str) -> bool:
    if not text or text in ('"', "'", ""):
        return True
    if text.startswith(("http", "www.", ".png", ".jpg", ".ico")):
        return True
    if re.search(r"\{.*\}", text):
        return True
    if re.fullmatch(r"[\W\d_]+", text):
        return True
    if len(text) == 1 and not text.isalpha():
        return True
    code_markers = ("self.", "lambda", "command=", "fg_color=", "pack(", "grid(")
    return any(m in text for m in code_markers)


def _tokenize_for_spelling(text: str) -> list[str]:
    cleaned = re.sub(r"[{}\[\]$%@#^&*+=|\\/<>~`]", " ", text)
    cleaned = re.sub(r"\d+", " ", cleaned)
    return [w.lower() for w in WORD_RE.findall(cleaned) if len(w) >= 3]


def _check_spelling(
    report: ReviewReport,
    file: str,
    line: int,
    text: str,
    whitelist: set[str],
    spell: Any | None,
) -> None:
    for typo, fix in COMMON_TYPOS.items():
        if re.search(rf"\b{re.escape(typo)}\b", text, re.I):
            report.add(
                Finding(
                    category="spelling",
                    severity="error",
                    message=f"Likely typo: '{typo}'",
                    file=file,
                    line=line,
                    context=text[:120],
                    suggestion=f"Use '{fix}'",
                )
            )

    words = _tokenize_for_spelling(text)
    for word in words:
        bare = word.strip("'")
        if bare in whitelist or bare in COMMON_TYPOS:
            continue
        if spell is not None:
            if bare in spell:
                continue
            candidates = spell.candidates(bare)
            suggestion = next(iter(candidates), "") if candidates else ""
            if suggestion and suggestion != bare:
                report.add(
                    Finding(
                        category="spelling",
                        severity="warn",
                        message=f"Unknown word: '{bare}'",
                        file=file,
                        line=line,
                        context=text[:120],
                        suggestion=f"Did you mean '{suggestion}'?",
                    )
                )
        elif len(bare) >= 8 and bare.endswith(("tion", "ment", "able")) is False:
            # Heuristic: long rare-looking tokens without spellchecker
            if bare not in whitelist and re.search(r"[aeiou]", bare) is None:
                report.add(
                    Finding(
                        category="spelling",
                        severity="info",
                        message=f"Unusual token (install pyspellchecker for full check): '{bare}'",
                        file=file,
                        line=line,
                        context=text[:120],
                    )
                )


def _check_wording(report: ReviewReport, file: str, line: int, text: str) -> None:
    # Sidebar/toolbar buttons use "icon  Label" spacing intentionally
    if DOUBLE_SPACE_RE.search(text) and not re.match(
        r"^[\U0001F300-\U0001FAFF↻⎋💾★▦▧▬✉⇄🔔👮💲⚙📊📅🔐🕐•·]+\s{2,}",
        text,
    ):
        report.add(
            Finding(
                category="wording",
                severity="warn",
                message="Double space in user-facing text",
                file=file,
                line=line,
                context=text,
                suggestion="Collapse to a single space",
            )
        )

    if text != text.strip() and text.strip():
        report.add(
            Finding(
                category="wording",
                severity="info",
                message="Leading or trailing whitespace in string",
                file=file,
                line=line,
                context=repr(text),
            )
        )

    if re.search(r"\b(click here|please click|simply)\b", text, re.I):
        report.add(
            Finding(
                category="wording",
                severity="info",
                message="Informal or filler phrasing",
                file=file,
                line=line,
                context=text[:120],
                suggestion="Prefer direct, professional police-department tone",
            )
        )

    if "!!" in text or "??" in text:
        report.add(
            Finding(
                category="wording",
                severity="warn",
                message="Repeated punctuation",
                file=file,
                line=line,
                context=text[:120],
            )
        )


def _check_aesthetics_source(
    report: ReviewReport,
    path: str,
    rel: str,
) -> None:
    with open(path, encoding="utf-8") as fh:
        lines = fh.readlines()

    height_values: Counter[int] = Counter()
    radius_values: Counter[int] = Counter()
    raw_font_lines: list[int] = []

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue

        for match in HEX_RE.finditer(line):
            color = match.group(0).upper()
            if color in THEME_COLOR_LITERALS:
                continue
            if any(sym in line for sym in THEME_COLOR_SYMBOLS):
                continue
            if "GANTT_COLORS" in line or "STATUS_COLORS" in line:
                continue
            if rel == "ui/theme.py" and re.search(r"^UI_[A-Z_]+\s*=", stripped):
                continue
            report.add(
                Finding(
                    category="aesthetics",
                    severity="info",
                    message=f"Hardcoded color {color}",
                    file=rel,
                    line=idx,
                    context=stripped[:100],
                    suggestion="Prefer DODGEVILLE_* or UI_* constants from config/theme",
                )
            )

        if "CTkButton" in line:
            hm = re.search(r"\bheight\s*=\s*(\d+)", line)
            if hm:
                height_values[int(hm.group(1))] += 1

        rm = re.search(r"\bcorner_radius\s*=\s*(\d+)", line)
        if rm and "CTkButton" in line:
            radius_values[int(rm.group(1))] += 1

        if "CTkFont(" in line and "font(" not in line and rel != "ui/theme.py":
            raw_font_lines.append(idx)

    if len(height_values) > 3:
        report.add(
            Finding(
                category="aesthetics",
                severity="warn",
                message=f"Inconsistent button heights: {dict(height_values)}",
                file=rel,
                suggestion="Standardize primary actions to height=36–38, compact rows to 28–32",
            )
        )

    if len(radius_values) > 1:
        report.add(
            Finding(
                category="aesthetics",
                severity="info",
                message=f"Mixed button corner_radius values: {dict(radius_values)}",
                file=rel,
                suggestion="Consider ui.theme.CORNER_RADIUS (12) or consistent 8 for toolbar buttons",
            )
        )

    for idx in raw_font_lines[:5]:
        report.add(
            Finding(
                category="aesthetics",
                severity="info",
                message="Direct CTkFont() instead of theme.font()",
                file=rel,
                line=idx,
                suggestion="Use font('body'), font('heading'), etc. from ui.theme",
            )
        )


def _check_terminology(report: ReviewReport, all_strings: list[tuple[str, int, str]]) -> None:
    """Cross-file label consistency."""
    corpus = " ".join(t.lower() for _, _, t in all_strings)
    nav_labels: list[str] = []
    try:
        theme_path = os.path.join(UI_DIR, "theme.py")
        with open(theme_path, encoding="utf-8") as fh:
            theme_src = fh.read()
        nav_labels = re.findall(r'\("(?:\w+)",\s*"([^"]+)"', theme_src)
    except OSError:
        pass

    profile_aliases = []
    app_path = os.path.join(UI_DIR, "app.py")
    if os.path.isfile(app_path):
        with open(app_path, encoding="utf-8") as fh:
            app_src = fh.read()
        profile_aliases = re.findall(r'nav_row[^)]*text="([^"]+)"', app_src)

    mismatches = []
    alias_map = {
        "requests": "time-off",
        "updated schedule": "current monthly schedule",
        "notifications": "dispatch alerts",
    }
    for alias in profile_aliases:
        key = alias.lower()
        for nav in nav_labels:
            if key in alias_map and alias_map[key] in nav.lower():
                if alias.lower() != nav.lower().split()[0]:
                    mismatches.append((alias, nav))

    for alias, nav in mismatches:
        report.add(
            Finding(
                category="wording",
                severity="warn",
                message=f"Profile shortcut '{alias}' differs from nav label '{nav}'",
                file="ui/app.py",
                suggestion=f"Align wording — use '{nav}' or update NAV_ITEMS",
            )
        )

    for group in TERMINOLOGY_GROUPS:
        hits = [term for term in group if term in corpus]
        if len(hits) >= 3:
            report.add(
                Finding(
                    category="wording",
                    severity="info",
                    message=f"Mixed terminology for related concept: {hits}",
                    suggestion=f"Pick one primary term from: {group[0]}",
                )
            )


def _find_latest_screenshots() -> str:
    live_root = os.path.join(ROOT, "logs", "ui_live_test")
    if not os.path.isdir(live_root):
        return ""
    runs = [
        os.path.join(live_root, name)
        for name in os.listdir(live_root)
        if os.path.isdir(os.path.join(live_root, name)) and name != ".running.lock"
    ]
    if not runs:
        return ""
    runs.sort(key=os.path.getmtime, reverse=True)
    return runs[0]


def _write_markdown(report: ReviewReport, out_path: str) -> None:
    by_category: dict[str, list[Finding]] = defaultdict(list)
    for f in report.findings:
        by_category[f.category].append(f)

    lines = [
        "# UI Aesthetics Review",
        "",
        f"Generated: {report.generated_at}",
        f"Files scanned: {report.ui_files_scanned}",
        f"Strings extracted: {report.strings_found}",
        "",
        "## Summary",
        "",
    ]
    for key in ("error", "warn", "info"):
        count = report.summary.get(key, 0)
        if count:
            lines.append(f"- **{key}**: {count}")
    lines.append("")

    if report.screenshots_dir:
        lines.extend(
            [
                "## Screenshots",
                "",
                f"Latest ui-live run: `{report.screenshots_dir}`",
                "",
                "Review PNGs side-by-side with findings below for visual polish.",
                "",
            ]
        )

    for category in ("spelling", "wording", "aesthetics"):
        items = by_category.get(category, [])
        if not items:
            continue
        lines.append(f"## {category.title()}")
        lines.append("")
        for item in items:
            loc = f"`{item.file}:{item.line}`" if item.line else f"`{item.file}`"
            lines.append(f"- **[{item.severity}]** {item.message} ({loc})")
            if item.context:
                lines.append(f"  - Context: {item.context[:100]}")
            if item.suggestion:
                lines.append(f"  - Suggestion: {item.suggestion}")
        lines.append("")

    lines.extend(
        [
            "## Agent workflow",
            "",
            "1. Fix `error` and high-impact `warn` items in ui/*.py",
            "2. Run `python dev.py ui-live` and compare screenshots",
            "3. Re-run `python dev.py ui-review --strict` until clean",
            "",
        ]
    )

    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def run_ui_aesthetics_review(
    *,
    strict: bool = False,
    include_screenshots: bool = True,
    verbose: bool = False,
) -> int:
    os.makedirs(LOG_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join(LOG_DIR, stamp)
    os.makedirs(out_dir, exist_ok=True)

    whitelist = _load_whitelist()
    spell = _load_spellchecker()

    report = ReviewReport(
        generated_at=datetime.now().isoformat(timespec="seconds"),
        ui_files_scanned=0,
        strings_found=0,
    )
    if include_screenshots:
        report.screenshots_dir = _find_latest_screenshots()

    all_strings: list[tuple[str, int, str]] = []

    ui_files = sorted(f for f in os.listdir(UI_DIR) if f.endswith(".py") and f != "__init__.py")
    report.ui_files_scanned = len(ui_files)

    for name in ui_files:
        path = os.path.join(UI_DIR, name)
        rel = f"ui/{name}"
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        try:
            tree = ast.parse(source, filename=path)
        except SyntaxError as exc:
            report.add(
                Finding(
                    category="aesthetics",
                    severity="error",
                    message=f"Syntax error: {exc}",
                    file=rel,
                    line=exc.lineno or 0,
                )
            )
            continue

        strings = _extract_strings_from_ast(tree, path)
        _check_aesthetics_source(report, path, rel)

        for line_no, kind, text in strings:
            if _is_probably_code(text):
                continue
            if len(text.strip()) < 2:
                continue
            report.strings_found += 1
            all_strings.append((rel, line_no, text))
            _check_spelling(report, rel, line_no, text, whitelist, spell)
            _check_wording(report, rel, line_no, text)

    _check_terminology(report, all_strings)
    report.finalize()

    json_path = os.path.join(out_dir, "report.json")
    md_path = os.path.join(out_dir, "report.md")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "generated_at": report.generated_at,
                "ui_files_scanned": report.ui_files_scanned,
                "strings_found": report.strings_found,
                "summary": report.summary,
                "screenshots_dir": report.screenshots_dir,
                "spellchecker": spell is not None,
                "findings": [asdict(f) for f in report.findings],
            },
            fh,
            indent=2,
        )
    _write_markdown(report, md_path)

    errors = report.summary.get("error", 0)
    warns = report.summary.get("warn", 0)
    infos = report.summary.get("info", 0)

    print("Dodgeville PD Scheduler — UI aesthetics review")
    print("=" * 60)
    print(f"Scanned {report.ui_files_scanned} UI files, {report.strings_found} strings")
    print(f"Findings: {errors} error(s), {warns} warning(s), {infos} info")
    if spell is None:
        print("Tip: pip install pyspellchecker for fuller spelling checks")
    if report.screenshots_dir:
        print(f"Screenshots: {report.screenshots_dir}")
    print(f"Report: {md_path}")
    print("=" * 60)

    if verbose:
        for f in report.findings:
            loc = f"{f.file}:{f.line}" if f.line else f.file
            print(f"[{f.severity}] {f.category}: {f.message} @ {loc}")
            if f.suggestion:
                print(f"         → {f.suggestion}")

    if strict and (errors > 0 or warns > 0):
        return 1
    return 0


if __name__ == "__main__":
    strict_flag = "--strict" in sys.argv
    verbose_flag = "--verbose" in sys.argv or "-v" in sys.argv
    no_shots = "--no-screenshots" in sys.argv
    raise SystemExit(
        run_ui_aesthetics_review(
            strict=strict_flag,
            include_screenshots=not no_shots,
            verbose=verbose_flag,
        )
    )
