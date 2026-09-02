"""
Generate architecture_spec.docx using python-docx.
Called by runner.py at evaluation setup if the DOCX does not exist.
"""
from pathlib import Path


def generate_architecture_docx(output_path: Path) -> None:
    """Generate the synthetic architecture specification DOCX for the evaluation corpus."""
    from docx import Document

    doc = Document()

    doc.add_heading("ACME Platform — System Architecture Specification", 0)
    doc.add_paragraph(
        "Document Version: 3.7 | Status: Approved | Owner: Alice Johnson (CTO)"
    )
    doc.add_paragraph(
        "Classification: Internal Technical Reference | Last Updated: July 2026"
    )

    doc.add_heading("1. Architecture Overview", 1)
    doc.add_paragraph(
        "The ACME platform uses a 3-tier architecture: Presentation Tier, "
        "Application Tier, and Data Tier. All inter-service communication uses "
        "gRPC for internal APIs and REST/JSON for external-facing endpoints."
    )

    doc.add_heading("2. Infrastructure", 1)
    p = doc.add_paragraph()
    p.add_run("Database: ").bold = True
    p.add_run("PostgreSQL 16 with 250 GB allocated storage across three replicas.")
    p = doc.add_paragraph()
    p.add_run("Load Balancer: ").bold = True
    p.add_run("NGINX 1.25 with round-robin distribution and health-check interval of 10 seconds.")
    p = doc.add_paragraph()
    p.add_run("Backup Schedule: ").bold = True
    p.add_run("Incremental backups every 4 hours; full backup weekly on Sundays at 02:00 UTC.")
    p = doc.add_paragraph()
    p.add_run("API Response Time SLA: ").bold = True
    p.add_run("99th percentile latency must be below 200 ms under normal load.")

    doc.add_heading("3. Security & Encryption", 1)
    doc.add_paragraph(
        "All data at rest is encrypted using the Quantum Encryption Standard (QES). "
        "The implementation uses the CRYSTALS-Kyber QES-K4 algorithm with 8,192-bit keys."
    )
    doc.add_paragraph(
        "Note: The QES technical reference document specifies a 4,096-bit key size. "
        "The 8,192-bit figure above reflects an internal security hardening decision "
        "made by the Security team in Q2 2024. Both documents are authoritative for "
        "their respective contexts (standard vs. internal deployment configuration)."
    )
    doc.add_paragraph(
        "TLS 1.3 is required for all external endpoints. TLS 1.2 is permitted for "
        "legacy internal systems until Q1 2025 deprecation."
    )

    doc.add_heading("4. Microservices", 1)
    doc.add_paragraph(
        "The platform consists of 47 active microservices as of July 2026. "
        "Service mesh is implemented using Istio 1.22. Each service runs in "
        "a separate Kubernetes namespace with NetworkPolicy isolation."
    )

    doc.add_heading("5. Monitoring & Observability", 1)
    doc.add_paragraph("Metrics: Prometheus 2.53 + Grafana 11.")
    doc.add_paragraph("Distributed Tracing: Jaeger 1.58.")
    doc.add_paragraph("Log Aggregation: Loki 3.1 + Grafana.")
    doc.add_paragraph("On-call rotation: 24/7 coverage with 5-minute P1 response SLA.")

    doc.add_heading("6. Disaster Recovery", 1)
    doc.add_paragraph("Recovery Time Objective (RTO): 4 hours for critical services.")
    doc.add_paragraph("Recovery Point Objective (RPO): 1 hour (aligned with backup cadence).")
    doc.add_paragraph("Primary data center: AWS us-east-1. DR failover: AWS us-west-2.")

    doc.add_paragraph(
        "\nThis document is generated for evaluation purposes and contains synthetic data.",
        style="Caption",
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))


if __name__ == "__main__":
    out = Path(__file__).parent / "architecture_spec.docx"
    generate_architecture_docx(out)
    print(f"Generated: {out}")
