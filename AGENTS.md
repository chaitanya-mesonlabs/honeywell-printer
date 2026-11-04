# Repository Guidelines

## Project Overview

Single-file Python CLI for printing 50 mm × 25 mm die-cut labels on a **Honeywell / Datamax-O'Neil I-Class Mark II (I-4212e)** thermal printer. Labels are rasterized entirely host-side (Pillow, 1-bit monochrome, 203 DPI = 400×200 dots), encoded into **DPL** (Datamax Programming Language — *not* ZPL), and streamed over **USB bulk transfer** via PyUSB. There is no network, service, or package — one executable script plus vendor PDFs. macOS is the assumed host (font search paths, USB workflow).

## Architecture & Data Flow

Flat, procedural, single module: `honeywell_print.py` (5 functions, no classes).

```
argv → main()                                    argparse CLI
     → create_label_image()                      PIL mode-'1' render (mm→dots: (mm/25.4)×dpi)
         ├─ overlay: --image file OR lazy-imported qrcode
         ├─ auto font sizing: probe 48→14 pt via draw.textbbox
         └─ optional border, 1.5 mm safe margin
     → img.save(preview PNG)                     ALWAYS written, even when printing
     → [ --preview: stop here ]
     → pil_to_dpl_image()                        bitmap → DPL IAAF hex-image download
     → build_dpl_print_job()                     STX L / H<heat> / S<speed> / 1Y11 recall / Q<copies> / E
     → send_to_printer()                         usb.core.find(0x0B0B, 0x106E) → bulk OUT endpoint 0x02, 5 s timeout
```

Key invariants:
- **Pixel semantics**: PIL mode `'1'` where 1=white, 0=black; black (0) burns a dot. DPL row bytes pack bits big-endian (`0x80 >> x%8`), hex-encoded uppercase.
- `DPI_DEFAULT = 203` is hardcoded; no `--dpi` flag exists.
- `main()` calls the DPL functions with stored-image name `"STK01"`, overriding their `"LBL01"` default — don't "fix" one without the other.
- Optional deps are guarded by capability flags (`HAS_USB`) or lazy import (`qrcode`), so `--preview` works with only Pillow installed.

## Key Directories

None — the repo is flat. Root inventory:

| Path | Purpose |
| :--- | :--- |
| `honeywell_print.py` | Entire codebase + CLI entry point |
| `requirements.txt` | 3 unpinned-floor deps |
| `README.md` | Quick-start examples + full CLI option table |
| `Honeywell_I-Class_Calibration_Guide.pdf` | Media loading, sensor adjustment, calibration procedures |
| `Honeywell_I-Class_Mark_II_Operator_Manual.pdf` | 92-page operator manual (setup, menus, troubleshooting, §6.2 Hex Dump Mode) |

## Development Commands

No build system, Makefile, or package manager beyond pip. Fresh setup:

```bash
brew install libusb                              # PyUSB's C backend — pip does not provide it
# Apple Silicon: /opt/homebrew/lib is not on the default dylib search path; without this,
# ctypes.util.find_library("usb-1.0") returns None and PyUSB raises NoBackendException:
export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib
python3 -m venv .venv && source .venv/bin/activate   # Python >= 3.8 (Pillow>=10 floor)
pip install -r requirements.txt
```

Run (script has exec bit; `python3 honeywell_print.py` also works):

```bash
./honeywell_print.py "MESONLABS" --preview --output preview.png   # offline — no printer needed
./honeywell_print.py "MESONLABS" --subtext "R&D LAB" --font Monaco --border
./honeywell_print.py "MESONLABS" --qr "https://example.com" --image logo.png --copies 2
```

No-args/empty-input run prints help and exits 1.

## Code Conventions & Common Patterns

- **Style**: sync, procedural, module-level functions; no classes, no async, no logging module. Status via emoji `print()` to stdout; warnings/errors via `print(..., file=sys.stderr)`.
- **Error handling**: best-effort `try/except Exception` around font lookup, image/QR load, and USB ops — print a warning and continue. Kernel-driver detach failures are silently swallowed in `send_to_printer()`, which returns `bool` success instead of raising.
- **Typing**: full type hints and one-line docstrings on every function; no dataclasses.
- **Naming**: `snake_case` functions, `UPPER_SNAKE` constants at module top (`VENDOR_ID`, `PRODUCT_ID`, `DPI_DEFAULT`, `FONT_DIRECTORIES`), `HAS_*` capability flags.
- **Optional dependencies**: try/except-ImportError at module top setting a flag; `qrcode` imported lazily inside the QR branch only.
- **Platform assumptions**: `FONT_DIRECTORIES` searches only macOS paths (`/System/Library/Fonts`, `/Library/Fonts`, `~/Library/Fonts`); USB targets are hardcoded `VENDOR_ID = 0x0B0B` / `PRODUCT_ID = 0x106E`.
- **CLI ↔ function defaults mirror each other** (e.g. `--heat 24`, `--speed 2`, `--copies 1` in both argparse and `build_dpl_print_job` signature).

Known gotchas when editing:
- `HAS_PIL` is set but never checked — Pillow is de facto required; the guard only survives the import.
- `Tuple` is imported but unused.
- With `pyusb` importable but no libusb backend, `send_to_printer()` dies with an unhandled `usb.core.NoBackendException` — `usb.core.find()` sits before its try/except.
- `.gitignore` ignores `*.png` globally, so preview outputs *and any logo assets* are untracked — don't expect committed images.

## Important Files

- `honeywell_print.py` — the only source; everything happens here.
  - Module-top constants (`VENDOR_ID`, `PRODUCT_ID`, `DPI_DEFAULT`, `FONT_DIRECTORIES`) — USB IDs, 203 DPI, macOS font dirs
  - `resolve_font()` — path → name search (`*.ttf`, `" Bold"`, `.otf`) → hardcoded macOS fallbacks → `load_default()`
  - `pil_to_dpl_image()` — DPL `STX IAAF<name>` + per-row `80<len><hex>` + `FFFF` terminator; docstring cites Programmer's Manual "Appendix N"
  - `build_dpl_print_job()` — heat/speed/recall/quantity DPL commands
  - `send_to_printer()` — kernel-driver detach, `set_configuration()`, bulk write to endpoint `0x02`
- `README.md` — authoritative CLI table; update it when adding flags.
- PDFs are hardware references only: consult the Calibration Guide for media-sensor/gap-sensing issues (blank labels, `CALIBRATION FAILED`); consult the Operator Manual §6.2 **Hex Dump Mode** to debug the raw DPL byte stream. The actual DPL command-language spec (Programmer's Manual) is **not** in this repo — the `pil_to_dpl_image()` docstring cites its Appendix N from memory.

## Runtime/Tooling Preferences

- **Python ≥ 3.8**, unpinned (no `.python-version`, no pyproject). Uses `Image.Resampling.LANCZOS` (Pillow ≥ 9.1 API).
- **pip + venv**; no poetry/uv/lockfile/hashes.
- Dependency roles: `Pillow` required for anything; `pyusb` only for real printing — it is a wrapper, not a USB stack, and needs the **libusb C library** (`brew install libusb`, plus `DYLD_FALLBACK_LIBRARY_PATH` on Apple Silicon, see Development Commands); `qrcode` only for `--qr`.
- Real printing needs the physical printer attached over USB — there is no network/IP path. On non-macOS hosts, font resolution and USB permissions are untested.

## Testing & QA

**No tests, CI, lint, or type-checking exist** (no pytest/unittest/tox/ruff/mypy/pre-commit/.github). Verification is manual:

- **Offline smoke test (use this for any change)**: `./honeywell_print.py "TEXT" --preview --output preview.png`, then inspect the 400×200 1-bit PNG. Exercises rendering, fonts, layout, and DPL conversion inputs without touching USB.
- **DPL payload inspection**: call `pil_to_dpl_image(img) + build_dpl_print_job()` in a REPL and hex-dump the result; cross-check with the printer's Hex Dump Mode (manual §6.2).
- **Full E2E**: requires the physical I-4212e over USB; script prints a diagnostic checklist when the device isn't found.

If adding tests, pytest with Pillow-rendering assertions (image size, pixel polarity, DPL byte framing) is the natural fit — but respect the project's current zero-test state and don't introduce CI scaffolding uninvited.
