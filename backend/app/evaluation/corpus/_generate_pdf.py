"""
Generate financial_summary.pdf using fpdf2.
Called by runner.py at evaluation setup if the PDF does not exist.
"""
from pathlib import Path


def generate_financial_pdf(output_path: Path) -> None:
    """Generate the synthetic financial summary PDF for the evaluation corpus."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "ACME Corp - Financial Summary Report FY2024", ln=True)
    pdf.set_font("Helvetica", size=10)
    pdf.cell(0, 6, "Confidential | Prepared by: Finance Department | Date: March 14, 2025", ln=True)
    pdf.ln(6)

    def section(title: str) -> None:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, title, ln=True)
        pdf.set_font("Helvetica", size=10)

    def row(label: str, value: str) -> None:
        pdf.cell(90, 7, label, border=0)
        pdf.cell(0, 7, value, ln=True, border=0)

    section("Annual Revenue & Profitability")
    row("FY2024 Total Revenue:", "$47,300,000")
    row("Year-over-Year Growth:", "23% (FY2023: $38,455,000)")
    row("Total Operating Costs:", "$31,800,000")
    row("Net Profit:", "$15,500,000")
    row("Net Profit Margin:", "32.8%")
    pdf.ln(4)

    section("Quarterly Breakdown")
    row("Q1 2024 Revenue:", "$9,400,000")
    row("Q2 2024 Revenue:", "$11,200,000")
    row("Q3 2024 Revenue:", "$12,500,000")
    row("Q4 2024 Revenue:", "$14,200,000 (strongest quarter)")
    pdf.ln(4)

    section("R&D Investment")
    row("Total R&D Spending FY2024:", "$8,900,000")
    row("R&D as % of Revenue:", "18.8%")
    row("R&D Headcount:", "47 full-time researchers")
    pdf.ln(4)

    section("Capital Allocation")
    row("Infrastructure:", "$6,200,000")
    row("Sales & Marketing:", "$9,400,000")
    row("General & Administrative:", "$7,300,000")
    pdf.ln(4)

    section("Major Project Investments")
    row("Project Atlas (data platform):", "$2,800,000 allocated")
    row("  Note:", "This is the original planning allocation from Nov 2024.")
    row("  Approved budget per project doc:", "$2,400,000 (revised)")
    row("Cloud Migration Initiative:", "$1,450,000")
    row("Security Infrastructure:", "$980,000")
    pdf.ln(4)

    section("Outlook FY2025")
    pdf.multi_cell(
        0,
        7,
        "Management projects 18-22% revenue growth in FY2025, driven by enterprise "
        "contract renewals and three new product launches scheduled for H1 2025. "
        "Operating cost efficiency improvements are targeted at 3-5% reduction.",
    )
    pdf.ln(4)

    pdf.set_font("Helvetica", "I", 9)
    pdf.multi_cell(
        0,
        6,
        "This document is generated for evaluation purposes and contains synthetic data. "
        "The figures above do not represent any real organization's financials.",
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(output_path))


if __name__ == "__main__":
    out = Path(__file__).parent / "financial_summary.pdf"
    generate_financial_pdf(out)
    print(f"Generated: {out}")
