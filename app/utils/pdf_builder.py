from io import BytesIO
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

styles = getSampleStyleSheet()
HEADER_BG = colors.HexColor("#2F4858")
STRIPE_BG = colors.HexColor("#F2F4F6")


def _table(headers, rows, col_widths, amount_col):
    t = Table([headers, *rows], colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, STRIPE_BG]),
        ("ALIGN", (amount_col, 0), (amount_col, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        # Bold the last row (Total)
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
    ]))
    return t


def _page_number(canvas, doc):
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(A4[0] - 15 * mm, 10 * mm, f"Page {doc.page}")


def _collector_type(is_tenant, is_external) -> str:
    if is_external:
        return "External"
    if is_tenant:
        return "Tenant"
    return "Owner"


def build_ledger_pdf(year, collections, expenses) -> bytes:
    """
    collections: DB rows with name, phone_number, wing, is_tenant, is_external, amount
    expenses:    DB rows with expense_name, description, amount
    Rows are read by column name, so the column order in the SQL doesn't matter.
    """
    total_c = sum((Decimal(r.amount) for r in collections), Decimal(0))
    total_e = sum((Decimal(r.amount) for r in expenses), Decimal(0))

    coll_rows = [
        [
            r.name,
            r.phone_number or "-",
            r.wing or "-",
            _collector_type(r.is_tenant, r.is_external),
            f"{r.amount:,.2f}",
        ]
        for r in collections
    ]
    coll_rows.append(["Total", "", "", "", f"{total_c:,.2f}"])

    exp_rows = [
        [r.expense_name, r.description or "-", f"{r.amount:,.2f}"]
        for r in expenses
    ]
    exp_rows.append(["Total", "", f"{total_e:,.2f}"])

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15*mm, rightMargin=15*mm,
                            topMargin=15*mm, bottomMargin=18*mm)
    doc.build([
        Paragraph(f"Ledger Report {year}", styles["Title"]),
        Paragraph(f"Collection: {total_c:,.2f} &nbsp;|&nbsp; Expense: {total_e:,.2f} "
                  f"&nbsp;|&nbsp; Balance: {total_c - total_e:,.2f}", styles["Normal"]),
        Spacer(1, 8 * mm),
        Paragraph("Collections", styles["Heading2"]),
        _table(["Name", "Phone", "Wing", "Type", "Amount"], coll_rows,
               [55*mm, 32*mm, 18*mm, 28*mm, 47*mm], amount_col=4),
        Spacer(1, 8 * mm),
        Paragraph("Expenses", styles["Heading2"]),
        _table(["Expense", "Description", "Amount"], exp_rows,
               [60*mm, 80*mm, 40*mm], amount_col=2),
    ], onFirstPage=_page_number, onLaterPages=_page_number)
    return buf.getvalue()