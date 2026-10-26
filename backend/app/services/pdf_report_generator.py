import io
import os
import qrcode
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from fpdf.fonts import FontFace

from app.schemas.report import ReportDataStructure
from app.services.report_assembler import REPORT_LEGAL_DISCLAIMER

class BhumiSetuPDF(FPDF):
    def __init__(self, report_number: str, generated_at: str):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.report_number = report_number
        self.generated_at = generated_at
        self.set_auto_page_break(auto=True, margin=18)
        
        # Load Unicode font if available
        self.unicode_font_name = "Helvetica"
        for font_candidate, font_bold_candidate in [
            ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/segoeuib.ttf"),
            ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
            ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            ("/usr/share/fonts/TTF/DejaVuSans.ttf", "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf")
        ]:
            if os.path.exists(font_candidate):
                try:
                    self.add_font("CustomUnicode", "", font_candidate)
                    bold_file = font_bold_candidate if os.path.exists(font_bold_candidate) else font_candidate
                    self.add_font("CustomUnicode", "B", bold_file)
                    self.add_font("CustomUnicode", "I", font_candidate)
                    self.unicode_font_name = "CustomUnicode"
                    break
                except Exception:
                    pass

    def header(self):
        # Top banner
        self.set_fill_color(30, 58, 138)  # Deep Navy #1E3A8A
        self.rect(0, 0, 210, 16, "F")
        self.set_text_color(255, 255, 255)
        self.set_font(self.unicode_font_name, size=10)
        self.set_xy(10, 4)
        self.cell(100, 8, "BHUMI SETU  |  LAND INTELLIGENCE REPORT", align="L")
        self.set_xy(110, 4)
        self.cell(90, 8, f"ID: {self.report_number}", align="R")
        self.ln(12)

    def footer(self):
        self.set_y(-14)
        self.set_font(self.unicode_font_name, size=7)
        self.set_text_color(120, 120, 120)
        self.cell(95, 8, "Bhumi Setu Property Dossier  •  Evidence Before Conclusions  •  Non-Authoritative", align="L")
        self.cell(95, 8, f"Page {self.page_no()}/{{nb}}", align="R")

    def sanitize(self, text: Any) -> str:
        """Ensures text can be safely rendered by the active font without codec errors."""
        if text is None:
            return "N/A"
        s = str(text).strip()
        if self.unicode_font_name == "Helvetica":
            # Replace non-latin-1 characters
            return s.encode("latin-1", "replace").decode("latin-1")
        return s

    def section_header(self, title: str, subtitle: Optional[str] = None):
        self.ln(3)
        self.set_fill_color(238, 242, 255)  # Soft Indigo-100
        self.set_text_color(30, 58, 138)
        self.set_font(self.unicode_font_name, size=11)
        self.cell(190, 7, f"  {title.upper()}", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")
        if subtitle:
            self.set_font(self.unicode_font_name, size=7.5)
            self.set_text_color(100, 116, 139)
            self.cell(190, 4, f"  {subtitle}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")
        self.set_text_color(33, 33, 33)
        self.ln(2)

def generate_land_intelligence_pdf(data: ReportDataStructure) -> bytes:
    """
    Renders the complete 8-section Land Intelligence Report PDF using fpdf2 and qrcode.
    Output is standard A4 with clean typography, tables, and verification QR code.
    """
    pdf = BhumiSetuPDF(
        report_number=data.section_1_cover.report_number,
        generated_at=data.section_1_cover.generated_at
    )
    pdf.alias_nb_pages()
    pdf.add_page()
    table_head = FontFace(emphasis="B", fill_color=(241, 245, 249))

    # =========================================================================
    # SECTION 1: REPORT COVER & SCOPE
    # =========================================================================
    pdf.set_font(pdf.unicode_font_name, size=15)
    pdf.set_text_color(30, 58, 138)
    pdf.cell(190, 8, "Property Diligence & Evidence Assessment", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")
    
    pdf.set_font(pdf.unicode_font_name, size=8.5)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(190, 5, f"Issued: {data.section_1_cover.generated_at}   |   Case: {data.section_1_cover.case_number}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")
    pdf.ln(2)

    # Metadata Summary Box
    pdf.set_fill_color(248, 250, 252)
    pdf.set_draw_color(203, 213, 225)
    pdf.rect(10, pdf.get_y(), 190, 32, "FD")
    
    start_y = pdf.get_y() + 2
    pdf.set_xy(14, start_y)
    pdf.set_font(pdf.unicode_font_name, size=8)
    pdf.set_text_color(33, 33, 33)

    # Left Column
    c1 = [
        f"Target Parcel BHUMI-ID: {pdf.sanitize(data.section_1_cover.parcel_bhumi_id)}",
        f"Case Number: {pdf.sanitize(data.section_1_cover.case_number)}",
        f"Case Workflow Status: {pdf.sanitize(data.section_1_cover.case_status)}",
        f"Report Identifier: {pdf.sanitize(data.section_1_cover.report_number)}"
    ]
    for i, line in enumerate(c1):
        pdf.set_xy(14, start_y + (i * 7))
        pdf.cell(90, 6, line)

    # Right Column: Location Hierarchy
    c2 = [
        f"District: {pdf.sanitize(data.section_1_cover.district)}",
        f"Anchal / Circle: {pdf.sanitize(data.section_1_cover.circle)}",
        f"Mauza / Village: {pdf.sanitize(data.section_1_cover.mauza)}",
        f"Khata: {pdf.sanitize(data.section_1_cover.khata)}  |  Khesra: {pdf.sanitize(data.section_1_cover.khesra)}"
    ]
    for i, line in enumerate(c2):
        pdf.set_xy(108, start_y + (i * 7))
        pdf.cell(90, 6, line)

    pdf.set_y(start_y + 32)
    pdf.ln(2)

    # Data Availability Badges
    pdf.set_font(pdf.unicode_font_name, size=8)
    pdf.cell(48, 6, f"Revenue (P1-01): {'[YES]' if data.section_1_cover.data_availability_summary.get('revenue_record_available') else '[NO]'}", border=1, align="C")
    pdf.cell(48, 6, f"Cadastral Map (P1-02): {'[YES]' if data.section_1_cover.data_availability_summary.get('cadastral_map_available') else '[NO]'}", border=1, align="C")
    pdf.cell(47, 6, f"Title Deed (P1-03): {'[YES]' if data.section_1_cover.data_availability_summary.get('documents_available') else '[NO]'}", border=1, align="C")
    pdf.cell(47, 6, f"Field Survey (P1-04): {'[YES]' if data.section_1_cover.data_availability_summary.get('field_survey_available') else '[NO]'}", border=1, align="C")
    pdf.ln(8)


    # =========================================================================
    # SECTION 2: PARCEL IDENTITY & REVENUE RECORDS (P1-01)
    # =========================================================================
    pdf.section_header("Section 2 — Parcel Identity & Revenue Records (Bihar Bhumi)", "Authoritative digitized revenue ledger (Register-II) records")
    s2 = data.section_2_revenue
    
    if s2.is_available:
        with pdf.table(col_widths=(45, 75, 70), text_align="L", line_height=5.5, headings_style=table_head) as table:
            row = table.row()
            row.cell("Parameter")
            row.cell("Persisted Value")
            row.cell("Source & Provenance")

            items = [
                ("Khata / Plot (Khesra)", f"Khata: {pdf.sanitize(s2.khata_number)} | Plot: {pdf.sanitize(s2.khesra_number)}", "Bihar Bhumi Register-II"),
                ("Jamabandi Number", pdf.sanitize(s2.jamabandi_number), "Circle Office Mutation Volume"),
                ("Recorded Area", f"{pdf.sanitize(s2.recorded_area_original)} ({s2.recorded_area_acres} Acres)", "Standard Unit Normalization"),
                ("Land Nature / Type", pdf.sanitize(s2.land_nature), "Revenue Classification"),
                ("Recorded Raiyat / Tenant", pdf.sanitize(s2.recorded_raiyat), "Government Ingestion Pipeline"),
                ("Evidence Reference", pdf.sanitize(s2.evidence_id or "Recorded in Case Evidence"), "SHA-256 Anchored Artifact")
            ]
            for param, val, prov in items:
                r = table.row()
                r.cell(param)
                r.cell(val)
                r.cell(prov)
    else:
        pdf.set_font(pdf.unicode_font_name, size=8)
        pdf.cell(190, 6, "No digitized Jamabandi revenue record linked to this parcel in local cache.", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)


    # =========================================================================
    # SECTION 3: CADASTRAL MAP & SPATIAL ANALYSIS (P1-02 & P2-04)
    # =========================================================================
    pdf.section_header("Section 3 — Cadastral Map & Boundary Discrepancy Intelligence", "Historical survey vector overlay, georeferencing, and spatial metrology")
    s3 = data.section_3_cadastral

    if s3.is_available:
        with pdf.table(col_widths=(50, 70, 70), text_align="L", line_height=5.5, headings_style=table_head) as table:
            row = table.row()
            row.cell("Spatial Dimension")
            row.cell("Evaluated Metric")
            row.cell("Epistemic Observation")

            items = [
                ("Coordinate Reference System", pdf.sanitize(s3.crs), "Standardized DILRMP Bihar Grid"),
                ("Geometry Validation", pdf.sanitize(s3.geometry_validation_status), "Topology & Boundary Polygon OK"),
                ("Spatially Calculated Area", f"{s3.calculated_area_acres} Acres", "Computed from Cadastral Coordinates"),
                ("Area Delta vs Recorded", f"{s3.area_delta_acres} Acres ({s3.variance_percentage}%)", "Concordant (Variance <= 5.0%)" if abs(s3.variance_percentage or 0) <= 5.0 else "Discrepancy Detected (> 5.0%)"),
                ("Spatial Provenance", pdf.sanitize(s3.spatial_provenance), "DLRS Bihar Bhu-Naksha / Overlay Engine")
            ]
            for dim, met, obs in items:
                r = table.row()
                r.cell(dim)
                r.cell(met)
                r.cell(obs)

        # TASK-P2-04: Cadastral Vector Overlay Discrepancy Table
        if s3.overlay_performed:
            pdf.ln(1)
            pdf.set_font(pdf.unicode_font_name, style="B", size=8.5)
            pdf.set_text_color(30, 41, 59)
            pdf.cell(190, 5, "Boundary Overlay Discrepancy Metrology (Historical CS vs Modern Survey):", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

            with pdf.table(col_widths=(45, 50, 50, 45), text_align="L", line_height=5.0, headings_style=table_head) as table:
                h = table.row()
                h.cell("Overlay Metric")
                h.cell("Measured Value")
                h.cell("Discrepancy Status")
                h.cell("Field Action")

                row = table.row()
                row.cell("IoU (Jaccard Index)")
                row.cell(f"{s3.iou_score:.3f}" if s3.iou_score is not None else "N/A")
                row.cell(pdf.sanitize(s3.discrepancy_status or "EVALUATED"))
                row.cell(pdf.sanitize(s3.field_task_number or "No Task Dispatched"))

                row2 = table.row()
                row2.cell("Centroid Shift / Hausdorff")
                row2.cell(f"Shift: {s3.centroid_displacement_meters}m | Max: {s3.hausdorff_distance_meters}m")
                row2.cell(f"Severity: {pdf.sanitize(s3.discrepancy_severity or 'LOW')}")
                row2.cell("LandAmin Verification" if s3.field_task_number else "Tolerable")

            if s3.statutory_cadastral_disclaimer:
                pdf.ln(1)
                pdf.set_font(pdf.unicode_font_name, style="I", size=7.2)
                pdf.set_text_color(120, 53, 15)  # Amber warning color
                pdf.multi_cell(190, 3.8, f"STATUTORY LIMITATION: {pdf.sanitize(s3.statutory_cadastral_disclaimer)}", border=1, fill=False)
                pdf.set_text_color(0, 0, 0)
    else:
        pdf.set_font(pdf.unicode_font_name, size=8)
        pdf.cell(190, 6, pdf.sanitize(s3.limitation_notes or "Cadastral map geometry unavailable."), border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)



    # =========================================================================
    # SECTION 4: DOCUMENT INTELLIGENCE & OCR FINDINGS (P1-03)
    # =========================================================================
    pdf.section_header("Section 4 — Document Intelligence & OCR Findings", "Multilingual extraction, page bounding boxes, and Chauhaddi boundary schedules")
    if data.section_4_documents:
        for doc in data.section_4_documents:
            pdf.set_font(pdf.unicode_font_name, size=8.5)
            pdf.set_fill_color(241, 245, 249)
            pdf.cell(190, 6, f"Document: {pdf.sanitize(doc.original_filename)} ({pdf.sanitize(doc.document_category)})  •  Pages: {doc.page_count}  •  Status: [{pdf.sanitize(doc.review_status)}]", fill=True, border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            
            # Chauhaddi table
            with pdf.table(col_widths=(45, 45, 50, 50), text_align="L", line_height=5, first_row_as_headings=False) as table:
                row = table.row()
                row.cell(f"North: {pdf.sanitize(doc.chauhaddi.get('north'))}")
                row.cell(f"South: {pdf.sanitize(doc.chauhaddi.get('south'))}")
                row.cell(f"East: {pdf.sanitize(doc.chauhaddi.get('east'))}")
                row.cell(f"West: {pdf.sanitize(doc.chauhaddi.get('west'))}")

            # Extracted Fields
            if doc.extracted_fields:
                field_strs = [f"{k}: {pdf.sanitize(v)}" for k, v in list(doc.extracted_fields.items())[:6]]
                pdf.set_font(pdf.unicode_font_name, size=7.5)
                pdf.multi_cell(190, 4, "Extracted Keys: " + "  |  ".join(field_strs), border="LRB")
            pdf.ln(1)
    else:
        pdf.set_font(pdf.unicode_font_name, size=8)
        pdf.cell(190, 6, "No uploaded title documents linked to this case.", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)


    # =========================================================================
    # SECTION 5: LANDAMIN FIELD VERIFICATION (P1-04)
    # =========================================================================
    pdf.section_header("Section 5 — LandAmin Field Verification & Ground Truth", "On-site GNSS boundary traverse, ground Chauhaddi, and possession verification")
    s5 = data.section_5_field

    if s5.is_available:
        with pdf.table(col_widths=(45, 75, 70), text_align="L", line_height=5.5, headings_style=table_head) as table:
            row = table.row()
            row.cell("Inspection Element")
            row.cell("Field Ground Observation")
            row.cell("Verification Metadata")

            f_items = [
                ("Task ID & Status", f"{pdf.sanitize(s5.task_number)} ({pdf.sanitize(s5.task_status)})", "Workflow Finite State Machine"),
                ("Assigned Field Amin", pdf.sanitize(s5.assigned_worker), "Registered Field Personnel"),
                ("GNSS Observations", f"{s5.gps_reading_count} Points (Accuracy ±{s5.reported_accuracy_meters}m)", "Consumer/Mobile GNSS Receiver"),
                ("Field Measured Area", f"{s5.measured_area_acres} Acres" if s5.measured_area_acres else "Not measured", "Planar Polygon Approximation"),
                ("Physical Possessor", pdf.sanitize(s5.physical_possessor_name or "Not recorded"), "Ground Interview / In-person Inspection"),
                ("Road Access & Frontage", f"{pdf.sanitize(s5.road_access_type)} ({s5.road_frontage_feet or 'N/A'} ft frontage)", "Ground Measurement"),
                ("Site Photographs", f"{len(s5.photograph_evidence_ids)} Photos Uploaded & Hashed", "Cryptographically Anchored Evidence")
            ]
            for el, obs, meta in f_items:
                r = table.row()
                r.cell(el)
                r.cell(obs)
                r.cell(meta)

        # Ground Chauhaddi
        pdf.set_font(pdf.unicode_font_name, size=8)
        gc = s5.ground_chauhaddi
        pdf.cell(190, 5, f"Ground Neighbors:  North: {pdf.sanitize(gc.get('north'))}  |  South: {pdf.sanitize(gc.get('south'))}  |  East: {pdf.sanitize(gc.get('east'))}  |  West: {pdf.sanitize(gc.get('west'))}", border="LRB", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    else:
        pdf.set_font(pdf.unicode_font_name, size=8)
        pdf.cell(190, 6, "Field verification has not been dispatched or completed for this parcel.", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)


    # =========================================================================
    # SECTION 6: CROSS-SOURCE CONSISTENCY MATRIX
    # =========================================================================
    pdf.section_header("Section 6 — Cross-Source Consistency & Discrepancy Matrix", "Automated reconciliation across Revenue, Cadastral Map, Deed, and Field Survey")
    if data.section_6_consistency:
        with pdf.table(col_widths=(40, 50, 45, 55), text_align="L", line_height=5.5, headings_style=table_head) as table:
            row = table.row()
            row.cell("Category")
            row.cell("Evaluated Sources")
            row.cell("Reconciliation Outcome")
            row.cell("Explanation & Follow-up")

            for c in data.section_6_consistency:
                r = table.row()
                r.cell(pdf.sanitize(c.category))
                r.cell(f"{pdf.sanitize(c.source_a)} vs {pdf.sanitize(c.source_b)}")
                r.cell(pdf.sanitize(c.outcome))
                r.cell(pdf.sanitize(c.difference_explanation))
    else:
        pdf.set_font(pdf.unicode_font_name, size=8)
        pdf.cell(190, 6, "Insufficient comparative sources available to build cross-source matrix.", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)


    # =========================================================================
    # SECTION 7: CONSOLIDATED EVIDENCE REGISTER
    # =========================================================================
    pdf.section_header("Section 7 — Consolidated Evidence Register & Provenance", "Immutable cryptographic digest of all supporting records, maps, photos, and filings")
    if data.section_7_evidence:
        with pdf.table(col_widths=(40, 40, 50, 60), text_align="L", line_height=5, headings_style=table_head) as table:
            row = table.row()
            row.cell("Evidence Type")
            row.cell("Authority Tier")
            row.cell("Source Name")
            row.cell("SHA-256 Digest")

            for ev in data.section_7_evidence[:8]:  # Limit top 8 for space
                r = table.row()
                r.cell(pdf.sanitize(ev.evidence_type))
                r.cell(pdf.sanitize(ev.authority_tier))
                r.cell(pdf.sanitize(ev.source_name)[:28])
                r.cell(f"{ev.sha256_hash[:16]}...{ev.sha256_hash[-8:]}")
    else:
        pdf.set_font(pdf.unicode_font_name, size=8)
        pdf.cell(190, 6, "No evidence artifacts anchored to this case.", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)


    # =========================================================================
    # SECTION JUDICIAL: JUDICIAL RISK INTELLIGENCE & LITIGATION SEARCH
    # =========================================================================
    if data.section_judicial_risk:
        j_data = data.section_judicial_risk
        pdf.section_header(
            "Judicial Risk Intelligence — eCourts & Patna High Court Litigations",
            f"Public court case cross-referencing ({len(j_data.candidate_cases)} candidates found, {j_data.active_injunctions_detected} active injunctions)"
        )
        if j_data.candidate_cases:
            with pdf.table(col_widths=(45, 30, 30, 45, 40), text_align="L", line_height=5, headings_style=table_head) as table:
                row = table.row()
                row.cell("Court & CNR")
                row.cell("Case No / Year")
                row.cell("Risk Domain")
                row.cell("Candidate Status")
                row.cell("Match Evidence & Notes")

                for j_item in j_data.candidate_cases[:5]:
                    r = table.row()
                    r.cell(f"{pdf.sanitize(j_item.court_name)[:22]}\nCNR: {j_item.cnr_number}")
                    r.cell(f"{pdf.sanitize(j_item.case_number)}\nStatus: {j_item.case_status}")
                    inj_tag = " [ACTIVE STAY/INJUNCTION]" if j_item.has_active_injunction else ""
                    r.cell(f"{j_item.risk_category}{inj_tag}")
                    r.cell(f"Category: {j_item.match_category}\nReview: {j_item.review_status}")
                    r.cell(pdf.sanitize(j_item.explanation)[:55])
            pdf.ln(1)
        else:
            pdf.set_font(pdf.unicode_font_name, size=8)
            pdf.cell(190, 6, "No matching or candidate court proceedings detected in public court registries for this parcel.", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(1)

        # Statutory Limitation Statement Box
        pdf.set_font(pdf.unicode_font_name, size=6)
        pdf.set_text_color(100, 116, 139)
        pdf.multi_cell(190, 2.8, j_data.limitation_statement, border=1)
        pdf.ln(2)


    # =========================================================================
    # SECTION VALUATION: BIHAR MVR CIRCLE RATE & STAMP DUTY VALUATION
    # =========================================================================
    if data.section_valuation and data.section_valuation.valuations:
        v_data = data.section_valuation
        pdf.section_header(
            "Valuation Intelligence — Bihar MVR Circle Rate & Statutory Taxes",
            f"Official circle rate valuation & Section 47-A stamp duty breakdown ({len(v_data.valuations)} assessed records)"
        )
        with pdf.table(col_widths=(45, 30, 35, 40, 40), text_align="L", line_height=5, headings_style=table_head) as table:
            row = table.row()
            row.cell("Jurisdiction & MVR Code")
            row.cell("Area & Category")
            row.cell("Guideline Land Value")
            row.cell("Stamp Duty & Reg Fee")
            row.cell("Discrepancy Status")

            for v_item in v_data.valuations[:4]:
                r = table.row()
                r.cell(f"{pdf.sanitize(v_item.district)} / {pdf.sanitize(v_item.anchal_circle)}\nMauza: {pdf.sanitize(v_item.mauza)}")
                r.cell(f"{v_item.total_area_decimal:.2f} Decimals\nCat: {v_item.property_category}")
                r.cell(f"Land: Rs. {v_item.calculated_land_value:,.2f}\nRate: Rs. {v_item.unit_circle_rate:,.2f}/dec")
                r.cell(f"Duty: Rs. {v_item.stamp_duty_amount:,.2f} ({v_item.stamp_duty_rate_percent}%)\nReg: Rs. {v_item.registration_fee_amount:,.2f}")
                r.cell(f"Status: {v_item.discrepancy_status}\nBase: Rs. {v_item.assessment_base:,.2f}")
        pdf.ln(1)

        # Statutory Valuation Limitation Statement
        pdf.set_font(pdf.unicode_font_name, size=6)
        pdf.set_text_color(100, 116, 139)
        pdf.multi_cell(190, 2.8, v_data.limitation_statement, border=1)
        pdf.ln(2)


    # =========================================================================
    # SECTION 8: FINDINGS, ACTIONS, QR CODE & DISCLAIMER
    # =========================================================================
    pdf.section_header("Section 8 — Findings, Next Actions & Cryptographic Verification", "Final synthesis, recommended due diligence actions, and tamper-evident verification")
    
    # Findings Summary
    if data.section_8_findings_actions:
        with pdf.table(col_widths=(35, 25, 65, 65), text_align="L", line_height=5, headings_style=table_head) as table:
            row = table.row()
            row.cell("Rule ID")
            row.cell("Severity")
            row.cell("Discrepancy Finding")
            row.cell("Recommended Action")

            for act in data.section_8_findings_actions:
                r = table.row()
                r.cell(pdf.sanitize(act.rule_id))
                r.cell(pdf.sanitize(act.severity))
                r.cell(pdf.sanitize(act.explanation)[:38])
                r.cell(pdf.sanitize(act.recommended_action or "Review by legal counsel.")[:38])
        pdf.ln(2)
    else:
        pdf.set_font(pdf.unicode_font_name, size=8)
        pdf.cell(190, 5, "No critical or high-severity findings recorded for this case.", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(2)

    # Verification Box & QR Code
    curr_y = pdf.get_y()
    if curr_y > 230:  # If close to bottom, add a new page
        pdf.add_page()
        curr_y = pdf.get_y()

    # Draw verification box
    pdf.set_fill_color(248, 250, 252)
    pdf.set_draw_color(203, 213, 225)
    pdf.rect(10, curr_y, 190, 36, "FD")

    # Generate QR Code image in memory
    try:
        qr = qrcode.QRCode(box_size=4, border=1)
        qr.add_data(data.verification_url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        qr_bytes_io = io.BytesIO()
        qr_img.save(qr_bytes_io, format="PNG")
        qr_bytes_io.seek(0)
        pdf.image(qr_bytes_io, x=14, y=curr_y + 3, w=30, h=30)
    except Exception:
        pdf.set_xy(14, curr_y + 10)
        pdf.cell(30, 10, "[QR CODE]", border=1, align="C")

    # QR Text
    pdf.set_xy(48, curr_y + 4)
    pdf.set_font(pdf.unicode_font_name, size=8.5)
    pdf.set_text_color(30, 58, 138)
    pdf.cell(145, 5, "Cryptographic Report Verification & Tamper-Evidence", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_xy(48, curr_y + 10)
    pdf.set_font(pdf.unicode_font_name, size=7)
    pdf.set_text_color(70, 70, 70)
    pdf.multi_cell(145, 3.8, (
        f"Scan the QR code to verify this report's authenticity against Bhumi Setu's ledger.\n"
        f"Verification URL: {data.verification_url}\n"
        f"Security Token: {data.verification_token[:20]}...\n"
        f"Notice: Verification reveals cryptographic validity without exposing private party dossiers."
    ))

    # Mandatory Legal Disclaimer Box
    pdf.set_y(curr_y + 38)
    pdf.set_font(pdf.unicode_font_name, size=6.5)
    pdf.set_text_color(100, 116, 139)
    pdf.multi_cell(190, 3.2, (
        f"STATUTORY DISCLAIMER & LEGAL BOUNDARY NOTICE: {REPORT_LEGAL_DISCLAIMER}"
    ), border=1)

    return bytes(pdf.output())
