#!/usr/bin/env python3
"""
Prove the Code 39 table in app/README.md actually encodes what it claims.

This is not a formality. A single wrong element in that table produces a barcode
that looks perfect and scans as a *different* string — which, for a voucher, is
worse than a barcode that doesn't scan at all. So the table is checked by drawing
it, printing it, and reading it back with an independent decoder.

    pip install playwright zxing-cpp pillow
    playwright install chromium
    python tools/verify-barcodes.py T123 T543 ABC-99

What it does:
  1. builds the same <i> element markup the app builds, from code39-table.json
  2. renders it to a real A4 PDF at print sizes
  3. rasterises that PDF at 300 dpi, the low end of an office laser printer
  4. decodes it with zxing and compares against what went in

Exit code is non-zero if any code fails to round-trip.
"""
import json, pathlib, subprocess, sys, tempfile

HERE = pathlib.Path(__file__).resolve().parent
TABLE = json.loads((HERE.parent / "app" / "code39-table.json").read_text())

NARROW, WIDE, HEIGHT = "0.4mm", "1.2mm", "14mm"


def bars(code: str) -> str:
    """The exact markup the app's Power Fx produces, minus the class names."""
    s = "*" + code.upper() + "*"
    out = []
    for i, ch in enumerate(s):
        if ch not in TABLE:
            raise SystemExit(f"{ch!r} is not encodable in Code 39")
        for j, el in enumerate(TABLE[ch]):
            w = WIDE if el == "w" else NARROW
            colour = "#000" if j % 2 == 0 else "#fff"
            out.append(
                f'<i style="display:inline-block;vertical-align:top;'
                f'height:{HEIGHT};width:{w};background:{colour}"></i>'
            )
        if i < len(s) - 1:
            out.append(
                f'<i style="display:inline-block;vertical-align:top;'
                f'height:{HEIGHT};width:{NARROW};background:#fff"></i>'
            )
    return "".join(out)


def main(codes):
    from playwright.sync_api import sync_playwright
    from PIL import Image
    import zxingcpp

    # font-size:0 kills the whitespace between inline-blocks; the padding is the
    # quiet zone, which Code 39 requires and without which nothing scans.
    cards = "".join(
        f'<div style="page-break-inside:avoid;padding:4mm">'
        f'<div style="font-size:0;white-space:nowrap;background:#fff;padding:2mm 5mm">{bars(c)}</div>'
        f'<div style="font-family:monospace;font-size:14px">{c}</div></div>'
        for c in codes
    )
    html = f'<html><body style="margin:0;background:#fff">{cards}</body></html>'

    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        (tmp / "in.html").write_text(html)
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page()
            page.goto((tmp / "in.html").as_uri())
            page.pdf(path=str(tmp / "out.pdf"), format="A4", print_background=True)
            browser.close()

        subprocess.run(
            ["pdftoppm", "-r", "300", "-png", str(tmp / "out.pdf"), str(tmp / "page")],
            check=True,
        )

        found = []
        for png in sorted(tmp.glob("page*.png")):
            found += [r.text for r in zxingcpp.read_barcodes(Image.open(png))]

    ok = True
    for c in codes:
        hit = c.upper() in found
        print(f"  {'PASS' if hit else 'FAIL'}  {c}")
        ok &= hit

    extra = [f for f in found if f not in {c.upper() for c in codes}]
    if extra:
        ok = False
        print(f"  FAIL  decoder also read something unexpected: {extra}")

    print(f"\n{len(codes)} code(s), {'all round-tripped' if ok else 'SOMETHING IS WRONG'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["T123", "T543", "T666", "T988", "T443"]))
