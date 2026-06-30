# Rust Scheduling Core

High-performance scheduling math for Dodgeville PD Scheduler, exposed to Python via **PyO3** (`scheduler_core`).

## What runs in Rust

| Domain | Functions | Python entry |
|--------|-----------|--------------|
| Rotation | cycle day, squad on duty | `logic/scheduling.py` |
| Live calendar | schedule matrix with overrides | `build_schedule_matrix` |
| Day-off / bumping | bump chain planning | `suggest_bump_chain` |
| Coverage counts | shift headcount batch | `get_shift_coverage_counts_for_range` |
| Simulator | coverage simulation loop | `simulator.simulate_schedule` |

SQLite, UI, validators, and request workflow stay in Python. Rust receives officer/override snapshots and returns computed results.

## Architecture

```
validators.py → logic/requests.py (DB, workflow)
                    ↓
              logic/scheduling.py
                    ↓
              logic/rust_bridge.py
                    ↓
         scheduler_core (Rust)  |  Python fallback
```

When the extension is not built, `rust_bridge` uses identical Python implementations — all tests pass without Rust.

## Build (Windows)

1. Install Rust:
   ```powershell
   .\scripts\install_rust.ps1
   ```
   Restart terminal.

2. Build extension:
   ```bash
   python dev.py build-rust
   ```

3. Verify:
   ```bash
   python -c "from logic import rust_bridge; print(rust_bridge.backend_name())"
   python dev.py doctor
   python dev.py check
   ```

**Note:** PyO3 wheels target Python 3.10–3.12 most reliably. Python 3.14 may require a local `maturin develop` build from source.

## Files

| Path | Role |
|------|------|
| `rust/scheduler_core/` | Rust crate (rotation, coverage, bump, simulator) |
| `logic/rust_bridge.py` | Load extension + Python fallback |
| `pyproject.toml` | maturin build config |
| `scripts/build_rust.py` | Build helper |
| `tests/test_rust_bridge.py` | Bridge parity tests |

## Live calendar updates

When a day-off request is approved, `process_day_off_request` inserts overrides, then UI refreshes call `build_schedule_matrix` / `build_monthly_roster_by_date`. Those paths use the Rust matrix builder when available — calendar cells update with the same statuses (`working`, `bumped`, `covering`, etc.) computed faster on large rosters.
