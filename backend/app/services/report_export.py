from typing import Dict, Any, List, Optional
from datetime import datetime
from io import BytesIO
import base64

try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        PageBreak, KeepTogether, ListFlowable, ListItem
    )
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


class ReportExportService:
    """Service for generating PDF and JSON report exports."""

    def __init__(self):
        self.styles = self._create_styles() if REPORTLAB_AVAILABLE else None
        if REPORTLAB_AVAILABLE:
            from reportlab.lib.colors import HexColor
            self.COLORS = {
                "primary": HexColor("#1a1a2e"),
                "secondary": HexColor("#16213e"),
                "accent": HexColor("#e94560"),
                "success": HexColor("#0f3460"),
                "warning": HexColor("#e94560"),
                "text": HexColor("#eaeaea"),
                "text_muted": HexColor("#a0a0a0"),
                "border": HexColor("#2d2d44"),
                "white": HexColor("#ffffff"),
                "light_bg": HexColor("#1f1f3a"),
            }
        else:
            self.COLORS = {}

    def _create_styles(self):
        """Create custom paragraph styles."""
        styles = getSampleStyleSheet()

        # Title style
        styles.add(ParagraphStyle(
            name='ReportTitle',
            parent=styles['Title'],
            fontSize=24,
            leading=28,
            textColor=self.COLORS["white"],
            spaceAfter=6,
            alignment=TA_LEFT,
        ))

        # Section heading
        styles.add(ParagraphStyle(
            name='SectionHeading',
            parent=styles['Heading1'],
            fontSize=16,
            leading=20,
            textColor=self.COLORS["accent"],
            spaceBefore=16,
            spaceAfter=8,
            borderWidth=0,
            borderPadding=0,
        ))

        # Subsection heading
        styles.add(ParagraphStyle(
            name='SubsectionHeading',
            parent=styles['Heading2'],
            fontSize=13,
            leading=16,
            textColor=self.COLORS["text"],
            spaceBefore=10,
            spaceAfter=6,
        ))

        # Body text
        styles.add(ParagraphStyle(
            name='BodyText2',
            parent=styles['Normal'],
            fontSize=10,
            leading=14,
            textColor=self.COLORS["text"],
            spaceAfter=6,
            alignment=TA_JUSTIFY,
        ))

        # Bullet text
        styles.add(ParagraphStyle(
            name='BulletText',
            parent=styles['Normal'],
            fontSize=10,
            leading=14,
            textColor=self.COLORS["text"],
            spaceAfter=4,
            leftIndent=20,
            bulletIndent=8,
        ))

        # Small text
        styles.add(ParagraphStyle(
            name='SmallText',
            parent=styles['Normal'],
            fontSize=8,
            leading=10,
            textColor=self.COLORS["text_muted"],
            spaceAfter=4,
        ))

        # Metric label
        styles.add(ParagraphStyle(
            name='MetricLabel',
            parent=styles['Normal'],
            fontSize=9,
            leading=12,
            textColor=self.COLORS["text_muted"],
        ))

        # Metric value
        styles.add(ParagraphStyle(
            name='MetricValue',
            parent=styles['Normal'],
            fontSize=14,
            leading=18,
            textColor=self.COLORS["white"],
            alignment=TA_CENTER,
        ))

        return styles

    async def generate_pdf(self, report_data: Dict[str, Any]) -> bytes:
        """Generate PDF report from structured data."""
        if not REPORTLAB_AVAILABLE:
            # Fallback: return simple text-based PDF placeholder
            return self._generate_fallback_pdf(report_data)

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=0.75 * inch,
            rightMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
        )

        story = []

        # Cover page
        story.extend(self._build_cover_page(report_data))
        story.append(PageBreak())

        # Table of contents
        story.extend(self._build_toc(report_data))
        story.append(PageBreak())

        # Report sections
        for section in report_data.get("sections", []):
            story.extend(self._build_section(section))
            story.append(PageBreak())

        # Methodology and limitations
        story.extend(self._build_methodology(report_data))

        # Build PDF
        doc.build(story, onFirstPage=self._add_page_number, onLaterPages=self._add_page_number)

        buffer.seek(0)
        return buffer.read()

    def _generate_fallback_pdf(self, report_data: Dict[str, Any]) -> bytes:
        """Generate a minimal PDF when reportlab is not available."""
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas

        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        # Title
        c.setFont("Helvetica-Bold", 24)
        c.drawString(72, height - 72, report_data.get("report", {}).get("title", "Security Report"))

        # Metadata
        c.setFont("Helvetica", 10)
        y = height - 120
        report_info = report_data.get("report", {})
        for key, value in report_info.items():
            if value:
                c.drawString(72, y, f"{key}: {value}")
                y -= 16

        # Sections
        c.setFont("Helvetica", 10)
        for section in report_data.get("sections", []):
            if y < 100:
                c.showPage()
                y = height - 72
            c.setFont("Helvetica-Bold", 12)
            c.drawString(72, y, section.get("section_title", ""))
            y -= 18
            c.setFont("Helvetica", 9)
            content = section.get("content", {})
            for k, v in content.items():
                if y < 100:
                    c.showPage()
                    y = height - 72
                c.drawString(90, y, f"{k}: {str(v)[:100]}")
                y -= 14

        c.save()
        buffer.seek(0)
        return buffer.read()

    def _build_cover_page(self, report_data: Dict) -> List:
        """Build cover page elements."""
        story = []
        report = report_data.get("report", {})

        # Spacer
        story.append(Spacer(1, 1.5 * inch))

        # Title
        title = report.get("title", "Security Report")
        story.append(Paragraph(title, self.styles["ReportTitle"]))

        # Subtitle
        report_type = report.get("report_type", "").replace("_", " ").title()
        story.append(Paragraph(f"{report_type} Report", self.styles["SubsectionHeading"]))
        story.append(Spacer(1, 0.5 * inch))

        # Metadata table
        meta_data = [
            ["Workspace ID", report.get("workspace_id", "N/A")[:8] + "..."],
            ["Report Type", report_type],
            ["Format", report.get("format", "pdf").upper()],
            ["Schema Version", report.get("schema_version", "report-v1")],
            ["Risk Engine", report.get("risk_engine_version", "risk-v1")],
            ["Verification Policy", report.get("verification_policy_version", "verification-policy-v1")],
            ["Period Start", report.get("period_start", "N/A")],
            ["Period End", report.get("period_end", "N/A")],
            ["Data Cutoff", report.get("data_cutoff", "N/A")],
            ["Generated By", report.get("generated_by", "N/A")[:8] + "..."],
            ["Generated At", report.get("completed_at", report.get("created_at", "N/A"))],
        ]

        table = Table(meta_data, colWidths=[2 * inch, 4 * inch])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), self.COLORS["text_muted"]),
            ('TEXTCOLOR', (1, 0), (1, -1), self.COLORS["text"]),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -1), 0.5, self.COLORS["border"]),
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [self.COLORS["light_bg"], self.COLORS["primary"]]),
        ]))
        story.append(table)
        story.append(Spacer(1, 1 * inch))

        # Confidentiality notice
        story.append(Paragraph(
            "<b>CONFIDENTIAL</b> — This report contains sensitive security information. "
            "Distribution is limited to authorized personnel only.",
            ParagraphStyle(
                name='Confidential',
                parent=self.styles['Normal'],
                fontSize=10,
                leading=14,
                textColor=self.COLORS["accent"],
                alignment=TA_CENTER,
            )
        ))

        return story

    def _build_toc(self, report_data: Dict) -> List:
        """Build table of contents."""
        story = []
        story.append(Paragraph("Table of Contents", self.styles["SectionHeading"]))
        story.append(Spacer(1, 0.25 * inch))

        sections = report_data.get("sections", [])
        for i, section in enumerate(sections, 1):
            toc_entry = f"{i}. {section.get('section_title', section.get('section_key', ''))}"
            story.append(Paragraph(toc_entry, ParagraphStyle(
                name='TOCEntry',
                parent=self.styles['Normal'],
                fontSize=11,
                leading=18,
                textColor=self.COLORS["text"],
                leftIndent=20,
            )))

        story.append(PageBreak())
        return story

    def _build_section(self, section: Dict) -> List:
        """Build a report section."""
        story = []

        # Section title
        story.append(Paragraph(section.get("section_title", ""), self.styles["SectionHeading"]))

        # Horizontal rule
        story.append(Spacer(1, 4))
        from reportlab.platypus import HRFlowable
        story.append(HRFlowable(width="100%", thickness=1, color=self.COLORS["accent"]))
        story.append(Spacer(1, 12))

        # Section content
        content = section.get("content", {})
        story.extend(self._render_content(content))

        # Data references
        refs = section.get("data_references", {})
        if refs:
            story.append(Spacer(1, 12))
            story.append(Paragraph("Data References", self.styles["SubsectionHeading"]))
            for ref_type, ref_ids in refs.items():
                if isinstance(ref_ids, list) and ref_ids:
                    story.append(Paragraph(
                        f"{ref_type.replace('_', ' ').title()}: {', '.join(ref_ids[:5])}"
                        + (f" (+{len(ref_ids)-5} more)" if len(ref_ids) > 5 else ""),
                        self.styles["SmallText"]
                    ))

        return story

    def _render_content(self, content: Dict, level: int = 0) -> List:
        """Recursively render content dictionary."""
        story = []
        indent = level * 20

        for key, value in content.items():
            if isinstance(value, dict):
                story.append(Paragraph(
                    key.replace("_", " ").title(),
                    ParagraphStyle(
                        name=f'SubHeading{level}',
                        parent=self.styles["SubsectionHeading"],
                        fontSize=max(11 - level, 9),
                        leftIndent=indent,
                    )
                ))
                story.extend(self._render_content(value, level + 1))
            elif isinstance(value, list):
                story.append(Paragraph(
                    key.replace("_", " ").title(),
                    ParagraphStyle(
                        name=f'SubHeading{level}',
                        parent=self.styles["SubsectionHeading"],
                        fontSize=max(11 - level, 9),
                        leftIndent=indent,
                    )
                ))
                for item in value:
                    if isinstance(item, dict):
                        story.extend(self._render_content(item, level + 1))
                    else:
                        story.append(Paragraph(
                            f"• {str(item)[:200]}",
                            ParagraphStyle(
                                name=f'Bullet{level}',
                                parent=self.styles["BulletText"],
                                leftIndent=indent + 20,
                            )
                        ))
            else:
                # Simple key-value
                label = key.replace("_", " ").title()
                val = str(value)[:500] if value is not None else "N/A"
                if len(str(value)) > 500:
                    val = val + "..."

                # Color code certain values
                if key.lower() in ["severity", "status", "outcome"]:
                    color = self._get_status_color(str(value))
                    val = f'<font color="{color}">{val}</font>'

                story.append(Paragraph(
                    f"<b>{label}:</b> {val}",
                    ParagraphStyle(
                        name=f'KV{level}',
                        parent=self.styles["BodyText2"],
                        leftIndent=indent,
                    )
                ))

        return story

    def _get_status_color(self, value: str) -> str:
        """Get color for status/severity values."""
        value_lower = value.lower()
        if value_lower in ["critical", "failed", "error"]:
            return "#e94560"
        elif value_lower in ["high", "warning", "blocked"]:
            return "#ffa500"
        elif value_lower in ["medium", "pending", "running"]:
            return "#ffd700"
        elif value_lower in ["low", "passed", "completed", "verified"]:
            return "#00ff88"
        elif value_lower in ["info", "queued", "pending_review"]:
            return "#64b5f6"
        return "#eaeaea"

    def _build_methodology(self, report_data: Dict) -> List:
        """Build methodology and limitations section."""
        story = []
        story.append(Paragraph("Methodology & Limitations", self.styles["SectionHeading"]))
        story.append(Spacer(1, 4))
        from reportlab.platypus import HRFlowable
        story.append(HRFlowable(width="100%", thickness=1, color=self.COLORS["accent"]))
        story.append(Spacer(1, 12))

        methodology = [
            "This report is generated from automated security scanning, analysis, and verification systems.",
            "All metrics are derived from persisted records in the ShadowOps platform.",
            "Risk scores are calculated using the deterministic risk engine (risk-v1) based on attack path analysis.",
            "Findings originate from Semgrep static analysis, AI security analysis, and manual triage.",
            "Remediation proposals are AI-generated and require human approval before application.",
            "Verification jobs perform independent post-patch rescans and regression analysis.",
        ]

        for point in methodology:
            story.append(Paragraph(f"• {point}", self.styles["BulletText"]))

        # Limitations
        limitations = report_data.get("limitations", [])
        if limitations:
            story.append(Spacer(1, 12))
            story.append(Paragraph("Limitations", self.styles["SubsectionHeading"]))
            for lim in limitations:
                story.append(Paragraph(f"• {lim}", self.styles["BulletText"]))

        # Completeness
        completeness = report_data.get("completeness", {})
        if completeness:
            story.append(Spacer(1, 12))
            story.append(Paragraph("Data Completeness", self.styles["SubsectionHeading"]))
            for key, value in completeness.items():
                status = "✓ Available" if value else "✗ Unavailable"
                story.append(Paragraph(f"• {key.replace('_', ' ').title()}: {status}", self.styles["BulletText"]))

        return story

    def _add_page_number(self, canvas, doc):
        """Add page numbers to PDF."""
        page_num = canvas.getPageNumber()
        text = f"Page {page_num}"
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(self.COLORS["text_muted"])
        canvas.drawCentredString(
            A4[0] / 2, 0.5 * inch, text
        )
        canvas.restoreState()


# JSON export is handled by standard json.dumps in the report service