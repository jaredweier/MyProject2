# Rust Scheduling Core

**Policy:** All scheduling logic, reasoning, complex math, and scenario simulation run in **Rust** (`scheduler_core`). Python handles SQLite, validators, request workflow, and UI only.

## What runs in Rust

| Domain | Rust module | Python entry |
|--------|-------------|--------------|
| Rotation | `rotation.rs` | `rust_bridge.get_cycle_day`, `get_squad_on_duty` |
| Officer status | `status.rs` | `rust_bridge.batch_day_status`, `officer_rotation_working` |
| Live calendar | `status.rs` + `lib.rs` | `build_schedule_matrix` |
| Coverage counts | `coverage.rs` | `compute_coverage_counts` |
| Minimum rest | `rest.rs` | `minimum_rest_gap` |
| Consecutive work | `compliance.rs` | `consecutive_work_days` |
| Bump chains | `bump.rs` | `suggest_bump_chain` |
| Simulator | `simulator.rs` | `simulate_schedule` |

Command staff (Chief, Lieutenant) Mon–Fri schedules and training bumped statuses are handled in Rust `status.rs`.

## Architecture

```
validators.py → logic/requests.py (DB, workflow)
                    ↓
              logic/scheduling.py  (load snapshots, apply results)
                    ↓
              logic/rust_bridge.py  (primary API)
                    ↓
         scheduler_core (Rust)  |  logic/rust_fallback.py (emergency only)
```

- **`logic/rust_bridge.py`** — single entry for all scheduling math; returns `backend_name()` of `rust` or `python-fallback`.
- **`logic/rust_fallback.py`** — Python implementations used only when the extension is not built.
- Set `SCHEDULER_ALLOW_PYTHON_MATH=1` to force Python paths in tests that patch `_RUST`.

## Build (Windows)

1. Install Rust: `.\scripts\install_rust.ps1` (restart terminal).
2. Build: `python dev.py build-rust`
3. Verify:
   ```bash
   python -c "from logic import rust_bridge; print(rust_bridge.backend_name())"
   python dev.py doctor
   python dev.py cheap-check
   ```

`python dev.py doctor` reports **rust scheduler_core** as failed when the extension is missing — scheduling still works via `rust_fallback.py`, but production should always use Rust.

## Files

| Path | Role |
|------|------|
| `rust/scheduler_core/src/` | Rust crate |
| `logic/rust_bridge.py` | Primary bridge + policy |
| `logic/rust_fallback.py` | Emergency Python math |
| `logic/scheduling.py` | DB I/O + orchestration |
| `tests/test_rust_bridge.py` | Bridge parity tests |
