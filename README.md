# Honeywell / Datamax-O'Neil I-Class Mark II Label Tool

CLI utility and documentation for printing 50mm × 25mm labels on the Honeywell / Datamax-O'Neil I-4212e Mark II thermal transfer label printer over USB.

## Features
- **Host-side 1-bit rasterization**: Pixel-perfect rendering matching 203 DPI (400 × 200 dots).
- **Custom Fonts**: Loads any system TrueType/OpenType font (e.g. `Monaco`, `Arial`) or local `.ttf`/`.otf` files.
- **Logos & Graphics**: Imports and scales any `.png`, `.jpg`, `.bmp`.
- **QR Codes**: Native `--qr` generator with scannable error correction.
- **Safe Bounds**: Guaranteed to stay within 50mm × 25mm margins.
- **Preview Mode**: Generates a preview image offline without attempting USB communication.

## Quick Start

```bash
# Print a basic centered label
./honeywell_print.py "MESONLABS"

# Print with custom font, subtitle, and border
./honeywell_print.py "MESONLABS" --subtext "R&D LAB" --font Monaco --border

# Print with a QR code
./honeywell_print.py "MESONLABS" --subtext "SN-0024624" --qr "https://mesonlabs.com" --border

# Print with a custom logo
./honeywell_print.py "MESONLABS" --image logo.png --border

# Preview only (offline mode)
./honeywell_print.py "MESONLABS" --preview --output preview.png
```

## CLI Options

| Argument | Default | Description |
| :--- | :--- | :--- |
| `text` | `""` | Main text header |
| `--subtext` | `""` | Secondary subtitle |
| `--font` | System Bold | Font name or path to `.ttf`/`.otf` |
| `--size` | Auto | Font point size |
| `--qr` | None | Text or URL for QR code |
| `--image` | None | Path to logo / graphic |
| `--border` | Off | Draw a decorative outer border |
| `--width` | `50.0` | Width in mm |
| `--height` | `25.0` | Height in mm |
| `--heat` | `24` | Printhead burn temp (0–30) |
| `--speed` | `2` | Print speed in inches/sec |
| `--copies` | `1` | Number of copies |
| `--preview` | Off | Save preview image without USB transmission |

## Included Reference Manuals
- `Honeywell_I-Class_Calibration_Guide.pdf`: Extracted sensor adjustment and calibration guide with diagrams.
- `Honeywell_I-Class_Mark_II_Operator_Manual.pdf`: Full official operator manual (92 pages).
