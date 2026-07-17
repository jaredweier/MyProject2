from pathlib import Path

ADD = r"""
/* ===== 2026-07 residual visual redesign ===== */
:root {
  --cmd-blue: #3B7DD8;
  --cmd-blue-hi: #6BA3F5;
  --r: 12px;
  --shadow: 0 0 0 1px rgba(255,255,255,0.05), 0 20px 48px rgba(0,0,0,0.5);
}
.dc-sidebar {
  background: linear-gradient(180deg, #0c1a2e 0%, #081221 100%) !important;
  border-right: 1px solid rgba(197,206,217,0.14) !important;
  box-shadow: 8px 0 32px rgba(0,0,0,0.25);
}
.panel {
  border-radius: var(--r) !important;
  border: 1px solid rgba(197,206,217,0.16) !important;
  background: linear-gradient(165deg, rgba(19,42,69,0.94), rgba(10,22,40,0.98)) !important;
  box-shadow: var(--shadow) !important;
  backdrop-filter: blur(8px);
}
.panel-title {
  letter-spacing: 0.04em !important;
  font-weight: 750 !important;
  color: #F0F6FF !important;
}
.page-kicker {
  color: #6BA3F5 !important;
  letter-spacing: 0.14em !important;
  font-weight: 800 !important;
}
.page-title {
  font-weight: 800 !important;
  letter-spacing: -0.03em !important;
}
.q-btn.btn-primary, button.btn-primary {
  border-radius: 10px !important;
  font-weight: 700 !important;
  min-height: 2.4rem !important;
  transition: transform 0.12s ease, filter 0.12s ease !important;
}
.q-btn.btn-primary:active, button.btn-primary:active {
  transform: translateY(1px) scale(0.99);
}
.q-btn.btn-ghost, button.btn-ghost {
  border-radius: 10px !important;
  font-weight: 600 !important;
}
.q-field--outlined .q-field__control {
  border-radius: 10px !important;
  background: rgba(6,16,28,0.55) !important;
}
.q-field--outlined .q-field__control:before {
  border-color: rgba(197,206,217,0.22) !important;
}
.q-field--focused .q-field__control:before {
  border-color: rgba(107,163,245,0.75) !important;
  border-width: 2px !important;
}
.q-checkbox__label, .q-toggle__label {
  color: #E8EDF4 !important;
  font-weight: 600 !important;
}
.q-table, .q-markup-table {
  background: rgba(8,16,28,0.9) !important;
  color: #E8EDF4 !important;
  border-radius: 10px !important;
}
.q-table th {
  background: rgba(19,42,69,0.95) !important;
  color: #C5CED9 !important;
  font-weight: 700 !important;
}
.q-table tbody tr:hover {
  background: rgba(30,90,168,0.12) !important;
}
.offline-banner {
  position: sticky;
  top: 0;
  z-index: 9000;
  padding: 8px 14px;
  text-align: center;
  font-weight: 700;
  font-size: 0.85rem;
  background: linear-gradient(90deg, #7c2d12, #b45309);
  color: #fff7ed;
  border-bottom: 1px solid rgba(251,191,36,0.4);
}
.kpi-card, .action-tile {
  border-radius: 12px !important;
  border: 1px solid rgba(197,206,217,0.14) !important;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, transform 0.12s ease;
}
.action-tile:hover, .kpi-card:hover {
  border-color: rgba(107,163,245,0.45) !important;
  box-shadow: 0 8px 28px rgba(0,0,0,0.35);
  transform: translateY(-1px);
}
"""


def main() -> None:
    p = Path(__file__).resolve().parents[1] / "gui" / "theme.py"
    t = p.read_text(encoding="utf-8")
    if "2026-07 residual visual redesign" in t:
        print("already present")
        return
    if not t.rstrip().endswith('"""'):
        raise SystemExit(f"unexpected end: {t[-40:]!r}")
    body = t.rstrip()[:-3]
    p.write_text(body + "\n" + ADD + '\n"""\n', encoding="utf-8")
    print("appended", len(ADD))


if __name__ == "__main__":
    main()
