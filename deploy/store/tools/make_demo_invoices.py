"""Draws three made-up invoices (fictional companies, no real data) used for
store screenshots. Output goes next to this script."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent
F = "C:/Windows/Fonts/"


def font(size, bold=False):
    return ImageFont.truetype(F + ("arialbd.ttf" if bold else "arial.ttf"), size)


def invoice(filename, colour, seller, seller_lines, buyer, buyer_lines, number, date, due, currency, items, tax_rate):
    W, H = 1240, 1754
    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 190], fill=colour)
    d.text((70, 55), seller, font=font(52, True), fill="white")
    d.text((70, 125), seller_lines[0], font=font(24), fill="white")
    d.text((W - 70, 70), "INVOICE", font=font(60, True), fill="white", anchor="ra")

    y = 240
    for line in seller_lines[1:]:
        d.text((70, y), line, font=font(24), fill="#444444")
        y += 34
    d.text((W - 380, 240), "Invoice No:", font=font(26, True), fill="#222222")
    d.text((W - 70, 240), number, font=font(26), fill="#222222", anchor="ra")
    d.text((W - 380, 280), "Invoice Date:", font=font(26, True), fill="#222222")
    d.text((W - 70, 280), date, font=font(26), fill="#222222", anchor="ra")
    d.text((W - 380, 320), "Due Date:", font=font(26, True), fill="#222222")
    d.text((W - 70, 320), due, font=font(26), fill="#222222", anchor="ra")

    d.text((70, 420), "Bill To", font=font(24, True), fill=colour)
    d.text((70, 456), buyer, font=font(30, True), fill="#111111")
    y = 500
    for line in buyer_lines:
        d.text((70, y), line, font=font(24), fill="#444444")
        y += 34

    top = 660
    d.rectangle([70, top, W - 70, top + 56], fill=colour)
    cols = [(90, "Description", "la"), (760, "Qty", "ra"), (960, "Unit Price", "ra"), (W - 90, "Total", "ra")]
    for x, label, anchor in cols:
        d.text((x, top + 14), label, font=font(24, True), fill="white", anchor=anchor)
    y = top + 56
    subtotal = 0.0
    for i, (desc, qty, price) in enumerate(items):
        if i % 2:
            d.rectangle([70, y, W - 70, y + 58], fill="#F3F5F9")
        total = qty * price
        subtotal += total
        d.text((90, y + 16), desc, font=font(24), fill="#222222")
        d.text((760, y + 16), f"{qty:g}", font=font(24), fill="#222222", anchor="ra")
        d.text((960, y + 16), f"{price:,.2f}", font=font(24), fill="#222222", anchor="ra")
        d.text((W - 90, y + 16), f"{total:,.2f}", font=font(24), fill="#222222", anchor="ra")
        y += 58
    d.line([70, y, W - 70, y], fill="#999999", width=2)

    tax = round(subtotal * tax_rate, 2)
    y += 40
    for label, value, bold in [("Sub-Total", subtotal, False), (f"Tax ({tax_rate:.0%})", tax, False), ("Grand Total", subtotal + tax, True)]:
        d.text((W - 520, y), label, font=font(28 if bold else 26, bold), fill="#111111")
        d.text((W - 90, y), f"{currency} {value:,.2f}", font=font(28 if bold else 26, bold), fill="#111111", anchor="ra")
        y += 48

    d.text((70, H - 150), "Payment terms: 30 days. Thank you for your business.", font=font(22), fill="#555555")
    d.text((70, H - 110), "This is a sample document made for demonstration. All names are fictional.", font=font(20), fill="#888888")
    path = OUT / filename
    if filename.endswith(".pdf"):
        im.save(path, "PDF", resolution=150.0)
    else:
        im.save(path)
    print("wrote", path.name)


invoice("Northwind-Office-Supplies-INV-2041.pdf", "#1F3A8A", "Northwind Office Supplies", ["Stationery and office equipment", "14 Harbour Road, Dubai, UAE", "accounts@northwind-office.example"],
        "Brightline Consulting Ltd", ["Suite 8, Marina Plaza", "Dubai, UAE"], "INV-2041", "2026-11-03", "2026-12-03", "USD",
        [("A4 copier paper, 80 gsm (box of 5 reams)", 12, 24.50), ("Laser toner cartridge, black", 4, 86.00), ("Ergonomic office chair", 2, 189.00), ("Whiteboard markers (pack of 10)", 6, 7.25)], 0.05)

invoice("Blue-Harbor-Logistics-BH-7730.pdf", "#0F766E", "Blue Harbor Logistics", ["Freight and customs clearance", "Port Avenue 22, Karachi, Pakistan", "billing@blueharbor.example"],
        "Crescent Textiles", ["Plot 41, Industrial Area", "Faisalabad, Pakistan"], "BH-7730", "2026-11-09", "2026-11-24", "USD",
        [("Ocean freight, 20 ft container, Karachi to Jebel Ali", 1, 1450.00), ("Customs clearance and documentation", 1, 220.00), ("Inland transport to port", 1, 310.00)], 0.0)

invoice("Greenfield-Electrical-GE-0318.png", "#7C2D12", "Greenfield Electrical Co.", ["Electrical contracting and supplies", "5 Mill Lane, Leeds, United Kingdom", "sales@greenfield-electrical.example"],
        "Oakwood Property Management", ["77 Station Road", "Leeds, United Kingdom"], "GE-0318", "2026-11-12", "2026-12-12", "GBP",
        [("LED panel light 600x600, 40 W", 20, 31.50), ("Cable, twin and earth 2.5 mm, 100 m drum", 3, 94.00), ("Installation labour (hours)", 16, 42.00), ("Consumer unit, 12-way", 1, 168.00), ("Emergency exit sign, illuminated", 4, 27.75)], 0.20)
