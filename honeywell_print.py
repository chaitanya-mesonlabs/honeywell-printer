#!/usr/bin/env python3
"""
Honeywell / Datamax-O'Neil I-Class Mark II Thermal Printer CLI
Supports custom TrueType/OpenType fonts, graphics/images, barcodes, and borders.
Renders to 1-bit monochrome bitmap and prints over USB (or saves preview).
"""

import argparse
import os
import sys
from typing import Optional, Tuple

try:
    import usb.core
    import usb.util
    HAS_USB = True
except ImportError:
    HAS_USB = False

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


# Printer hardware identifiers
VENDOR_ID = 0x0B0B   # Datamax-O'Neil / Honeywell
PRODUCT_ID = 0x106E  # I-Class Mark II / I-4212e
DPI_DEFAULT = 203    # 8 dots/mm

# Standard macOS font search paths
FONT_DIRECTORIES = [
    "/System/Library/Fonts/Supplemental",
    "/System/Library/Fonts",
    "/Library/Fonts",
    os.path.expanduser("~/Library/Fonts"),
]


def resolve_font(font_name_or_path: Optional[str], size: int) -> ImageFont.ImageFont:
    """Find and load a TrueType/OpenType font on macOS, with safe fallbacks."""
    if font_name_or_path and os.path.isfile(font_name_or_path):
        return ImageFont.truetype(font_name_or_path, size)

    # Search by filename or common name
    targets = []
    if font_name_or_path:
        base = font_name_or_path.lower()
        if not base.endswith((".ttf", ".otf", ".ttc")):
            targets.extend([f"{font_name_or_path}.ttf", f"{font_name_or_path} Bold.ttf", f"{font_name_or_path}.otf"])
        else:
            targets.append(font_name_or_path)

    # Defaults to check
    targets.extend([
        "Arial Bold.ttf",
        "Arial.ttf",
        "Helvetica.ttc",
        "Geneva.ttf",
        "Monaco.ttf",
    ])

    for target in targets:
        for font_dir in FONT_DIRECTORIES:
            candidate = os.path.join(font_dir, target)
            if os.path.isfile(candidate):
                try:
                    return ImageFont.truetype(candidate, size)
                except Exception:
                    continue

    # Built-in Pillow fallback
    return ImageFont.load_default()


def create_label_image(
    width_mm: float = 50.0,
    height_mm: float = 25.0,
    dpi: int = 203,
    title: str = "",
    subtitle: str = "",
    font_name: Optional[str] = None,
    font_size: Optional[int] = None,
    image_path: Optional[str] = None,
    border: bool = False,
    barcode_text: Optional[str] = None,
    qr_text: Optional[str] = None,
) -> Image.Image:
    """
    Renders the label onto a 1-bit monochrome canvas matching the exact physical dimensions.
    """
    width_dots = int(round((width_mm / 25.4) * dpi))
    height_dots = int(round((height_mm / 25.4) * dpi))

    # White canvas (mode '1': 1=white, 0=black)
    img = Image.new("1", (width_dots, height_dots), 1)
    draw = ImageDraw.Draw(img)

    margin = int(round(1.5 * (dpi / 25.4)))  # ~1.5mm safe margin

    if border:
        draw.rectangle([margin, margin, width_dots - margin - 1, height_dots - margin - 1], outline=0, width=2)

    # 1. Overlay image if provided
    overlay_img = None
    if image_path and os.path.isfile(image_path):
        try:
            ov = Image.open(image_path).convert("L")
            overlay_img = ov.point(lambda p: 0 if p < 128 else 1, mode="1")
        except Exception as e:
            print(f"Warning: Failed to load image {image_path}: {e}", file=sys.stderr)
    elif qr_text:
        try:
            import qrcode
            qr = qrcode.QRCode(box_size=3, border=1)
            qr.add_data(qr_text)
            qr.make(fit=True)
            overlay_img = qr.make_image(fill_color="black", back_color="white").convert("1")
        except Exception as e:
            print(f"Warning: Failed to generate QR code: {e}", file=sys.stderr)

    if overlay_img:
        if title:
            avail_w = (width_dots - margin * 4) // 3
            avail_h = height_dots - margin * 3
            overlay_img.thumbnail((avail_w, avail_h), Image.Resampling.LANCZOS)
            img.paste(overlay_img, (margin * 2, (height_dots - overlay_img.height) // 2))
            text_left = margin * 2 + overlay_img.width + margin
        else:
            avail_w = width_dots - margin * 4
            avail_h = height_dots - margin * 4
            overlay_img.thumbnail((avail_w, avail_h), Image.Resampling.LANCZOS)
            pos_x = (width_dots - overlay_img.width) // 2
            pos_y = (height_dots - overlay_img.height) // 2
            img.paste(overlay_img, (pos_x, pos_y))
            return img
    else:
        text_left = margin * 2

    # Draw Text
    avail_text_w = width_dots - text_left - margin * 2
    avail_text_h = height_dots - margin * 2

    # Auto-calculate font size if not given
    if title:
        if font_size is None:
            # Test sizes starting from 44 down to 14
            for s in range(48, 14, -2):
                f = resolve_font(font_name, s)
                bbox = draw.textbbox((0, 0), title, font=f)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]
                target_h = avail_text_h * 0.6 if subtitle else avail_text_h * 0.75
                if tw <= avail_text_w and th <= target_h:
                    chosen_font = f
                    font_size = s
                    break
            else:
                chosen_font = resolve_font(font_name, 16)
        else:
            chosen_font = resolve_font(font_name, font_size)

        bbox_title = draw.textbbox((0, 0), title, font=chosen_font)
        title_w = bbox_title[2] - bbox_title[0]
        title_h = bbox_title[3] - bbox_title[1]

        if subtitle:
            sub_font = resolve_font(None, max(12, int(font_size * 0.45)))
            bbox_sub = draw.textbbox((0, 0), subtitle, font=sub_font)
            sub_w = bbox_sub[2] - bbox_sub[0]
            sub_h = bbox_sub[3] - bbox_sub[1]

            total_h = title_h + sub_h + 8
            start_y = (height_dots - total_h) // 2

            pos_x_title = text_left + (avail_text_w - title_w) // 2
            draw.text((pos_x_title, start_y), title, font=chosen_font, fill=0)

            pos_x_sub = text_left + (avail_text_w - sub_w) // 2
            draw.text((pos_x_sub, start_y + title_h + 8), subtitle, font=sub_font, fill=0)
        else:
            pos_x = text_left + (avail_text_w - title_w) // 2
            pos_y = (height_dots - title_h) // 2
            draw.text((pos_x, pos_y), title, font=chosen_font, fill=0)

    return img


def pil_to_dpl_image(img: Image.Image, image_name: str = "LBL01") -> bytes:
    """
    Converts a 1-bit PIL Image into the Datamax DPL 7-bit ASCII image download format.
    Appendix N: ^BIAAF<name><CR>80<len><hex><CR>...FFFF<CR>
    """
    img = img.convert("1")
    width, height = img.size
    bytes_per_row = (width + 7) // 8

    chunks = [f"\x02IAAF{image_name}\r".encode("ascii")]

    for y in range(height):
        row_bytes = bytearray(bytes_per_row)
        for x in range(width):
            # 0 is black in PIL mode '1', which burns a dot (1 bit) on thermal head
            if img.getpixel((x, y)) == 0:
                row_bytes[x // 8] |= 0x80 >> (x % 8)
        hex_data = row_bytes.hex().upper()
        hex_len = f"{bytes_per_row:02X}"
        chunks.append(f"80{hex_len}{hex_data}\r".encode("ascii"))

    chunks.append(b"FFFF\r")
    return b"".join(chunks)


def build_dpl_print_job(image_name: str = "LBL01", heat: int = 24, speed: int = 2, copies: int = 1) -> bytes:
    """Generates the DPL label format to recall and print the loaded image."""
    return b"".join([
        b"\x02L\r",
        f"H{heat:02d}\r".encode("ascii"),
        f"S{speed:01d}\r".encode("ascii"),
        b"D11\r",
        f"1Y1100000000000{image_name}\r".encode("ascii"),
        f"Q{copies:04d}\r".encode("ascii"),
        b"E\r",
    ])


def send_to_printer(payload: bytes) -> bool:
    """Sends raw bytes to the Honeywell I-Class printer over USB."""
    if not HAS_USB:
        print("Error: PyUSB is not installed (`pip install pyusb`).", file=sys.stderr)
        return False

    dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
    if dev is None:
        print("\n❌ PRINTER NOT FOUND ON USB", file=sys.stderr)
        print("   • Ensure the printer power is ON.", file=sys.stderr)
        print("   • Check that the USB cable / hub is connected to your Mac.", file=sys.stderr)
        return False

    try:
        # Reset & configure device
        try:
            if dev.is_kernel_driver_active(0):
                dev.detach_kernel_driver(0)
        except Exception:
            pass

        dev.set_configuration()
        # Endpoint 0x02 is bulk OUT for Datamax I-Class
        dev.write(0x02, payload, timeout=5000)
        print(f"✅ Successfully sent {len(payload)} bytes to Honeywell I-Class Mark II.")
        return True
    except Exception as e:
        print(f"❌ Error communicating with printer: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="Honeywell I-Class Mark II Thermal Label Printer CLI")
    parser.add_argument("text", nargs="?", default="", help="Main text to print on the sticker")
    parser.add_argument("--subtext", default="", help="Secondary/smaller text below the main title")
    parser.add_argument("--image", help="Path to an image/logo (PNG, JPG, BMP)")
    parser.add_argument("--qr", help="Text or URL to generate as a QR code")
    parser.add_argument("--font", default=None, help="TrueType font name (e.g. Arial, Monaco) or path to .ttf/.otf")
    parser.add_argument("--size", type=int, default=None, help="Font point size (auto-scaled by default)")
    parser.add_argument("--width", type=float, default=50.0, help="Label width in mm (default: 50.0)")
    parser.add_argument("--height", type=float, default=25.0, help="Label height in mm (default: 25.0)")
    parser.add_argument("--heat", type=int, default=24, help="Printhead burn temperature 0-30 (default: 24)")
    parser.add_argument("--speed", type=int, default=2, help="Print speed in IPS (default: 2)")
    parser.add_argument("--copies", type=int, default=1, help="Number of copies to print (default: 1)")
    parser.add_argument("--border", action="store_true", help="Draw a decorative border around the sticker")
    parser.add_argument("--preview", action="store_true", help="Generate and open preview PNG without printing")
    parser.add_argument("--output", default="label_preview.png", help="Path to save preview PNG")

    args = parser.parse_args()

    if not args.text and not args.image and not args.qr:
        parser.print_help()
        sys.exit(1)

    print(f"📐 Canvas: {args.width} mm × {args.height} mm @ {DPI_DEFAULT} DPI ({int(args.width/25.4*DPI_DEFAULT)}×{int(args.height/25.4*DPI_DEFAULT)} px)")

    # 1. Render label
    img = create_label_image(
        width_mm=args.width,
        height_mm=args.height,
        dpi=DPI_DEFAULT,
        title=args.text,
        subtitle=args.subtext,
        font_name=args.font,
        font_size=args.size,
        image_path=args.image,
        border=args.border,
        qr_text=args.qr,
    )

    # 2. Save preview PNG
    img.save(args.output)
    print(f"🖼️  Preview saved to: {os.path.abspath(args.output)}")

    if args.preview:
        print("Preview-only mode. Skipping USB print.")
        return

    # 3. Convert to DPL raster payload
    img_name = "STK01"
    dpl_image_data = pil_to_dpl_image(img, image_name=img_name)
    dpl_print_cmd = build_dpl_print_job(image_name=img_name, heat=args.heat, speed=args.speed, copies=args.copies)

    full_payload = dpl_image_data + dpl_print_cmd

    # 4. Transmit over USB
    send_to_printer(full_payload)


if __name__ == "__main__":
    main()
