import sys
import argparse
import contextlib
from typing import Optional, List, Dict, Any, Generator
from sqlalchemy.orm import Session
from mcp.server import MCPServer

from app.database import SessionLocal
from app.config import settings
from app.mcp.tools import (
    execute_get_parcel_summary,
    execute_get_revenue_record_summary,
    execute_get_spatial_summary,
    execute_get_document_extraction_summary,
    execute_get_evidence_register,
    execute_get_consistency_findings,
    execute_get_field_verification_status,
    execute_create_field_verification_request,
    execute_get_report_metadata,
    execute_generate_land_intelligence_report,
    execute_verify_report_integrity
)

_db_session_override: Optional[Session] = None

def set_mcp_db_override(session: Optional[Session]) -> None:
    """Sets a global database session override for test environments."""
    global _db_session_override
    _db_session_override = session

@contextlib.contextmanager
def get_mcp_db() -> Generator[Session, None, None]:
    """Yields a managed SQLAlchemy database session for an MCP tool execution."""
    global _db_session_override
    if _db_session_override is not None:
        yield _db_session_override
    else:
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()


def create_mcp_server(name: Optional[str] = None) -> MCPServer:
    """
    Factory creating and configuring the Bhumi Setu Agent MCPServer instance
    with all 11 governed tools registered.
    """
    server_name = name or settings.MCP_SERVER_NAME
    server = MCPServer(
        name=server_name,
        instructions=(
            "Bhumi Setu Agent MCP Server provides governed access to Bihar land intelligence records, "
            "cadastral maps, document OCR findings, field verification tasks, and diligence reports. "
            "All tools enforce strict tenant isolation, role authorization, and audit logging. "
            "Evidence Before Conclusions: tools distinguish between source records, field observations, "
            "and unreviewed OCR. They never declare ownership guarantees or certified legal titles."
        )
    )

    # -------------------------------------------------------------------------
    # Group A — Parcel Intelligence
    # -------------------------------------------------------------------------

    @server.tool(
        name="get_parcel_summary",
        description="Retrieves a consolidated summary of a parcel across revenue records, cadastral geometry, document extractions, field verification status, and open discrepancies."
    )
    def mcp_get_parcel_summary(
        parcel_id: str,
        auth_token: Optional[str] = None,
        summary_scope: str = "FULL"
    ) -> Dict[str, Any]:
        with get_mcp_db() as db:
            return execute_get_parcel_summary(db, parcel_id=parcel_id, auth_token=auth_token, summary_scope=summary_scope).model_dump()

    @server.tool(
        name="get_revenue_record_summary",
        description="Retrieves persisted Bihar Bhumi Jamabandi revenue record details (Register-II) including Khata, Khesra, Jamabandi number, recorded area, and raiyat name."
    )
    def mcp_get_revenue_record_summary(
        parcel_id: str,
        auth_token: Optional[str] = None
    ) -> Dict[str, Any]:
        with get_mcp_db() as db:
            return execute_get_revenue_record_summary(db, parcel_id=parcel_id, auth_token=auth_token).model_dump()

    @server.tool(
        name="get_spatial_summary",
        description="Retrieves cadastral vector geometry metadata, CRS, and area variance calculations comparing Bhu-Naksha map geometry against recorded revenue area."
    )
    def mcp_get_spatial_summary(
        parcel_id: str,
        auth_token: Optional[str] = None
    ) -> Dict[str, Any]:
        with get_mcp_db() as db:
            return execute_get_spatial_summary(db, parcel_id=parcel_id, auth_token=auth_token).model_dump()

    @server.tool(
        name="get_document_extraction_summary",
        description="Retrieves OCR extraction results, page counts, confidence scores, and 4-direction Chauhaddi boundary schedules for documents linked to an authorized case."
    )
    def mcp_get_document_extraction_summary(
        case_id: str,
        document_id: Optional[str] = None,
        auth_token: Optional[str] = None
    ) -> Dict[str, Any]:
        with get_mcp_db() as db:
            return execute_get_document_extraction_summary(db, case_id=case_id, document_id=document_id, auth_token=auth_token).model_dump()

    # -------------------------------------------------------------------------
    # Group B — Evidence & Discrepancies
    # -------------------------------------------------------------------------

    @server.tool(
        name="get_evidence_register",
        description="Retrieves the cryptographic evidence register for an authorized case, including evidence types, authority tiers, timestamps, and SHA-256 hashes."
    )
    def mcp_get_evidence_register(
        case_id: str,
        auth_token: Optional[str] = None
    ) -> Dict[str, Any]:
        with get_mcp_db() as db:
            return execute_get_evidence_register(db, case_id=case_id, auth_token=auth_token).model_dump()

    @server.tool(
        name="get_consistency_findings",
        description="Retrieves cross-source discrepancies and findings generated by the consistency engine across Revenue, Map, Document, and Field evidence."
    )
    def mcp_get_consistency_findings(
        case_id: str,
        parcel_id: Optional[str] = None,
        auth_token: Optional[str] = None
    ) -> Dict[str, Any]:
        with get_mcp_db() as db:
            return execute_get_consistency_findings(db, case_id=case_id, parcel_id=parcel_id, auth_token=auth_token).model_dump()

    # -------------------------------------------------------------------------
    # Group C — Field Verification
    # -------------------------------------------------------------------------

    @server.tool(
        name="get_field_verification_status",
        description="Retrieves field verification task lifecycle status, GNSS observations, ground Chauhaddi, physical possessor details, and reviewer sign-off states."
    )
    def mcp_get_field_verification_status(
        task_id: Optional[str] = None,
        case_id: Optional[str] = None,
        parcel_id: Optional[str] = None,
        auth_token: Optional[str] = None
    ) -> Dict[str, Any]:
        with get_mcp_db() as db:
            return execute_get_field_verification_status(db, task_id=task_id, case_id=case_id, parcel_id=parcel_id, auth_token=auth_token).model_dump()

    @server.tool(
        name="create_field_verification_request",
        description="State-changing tool: Creates an auditable field-verification task in Bhumi Setu. Requires CASE_OPERATOR or ADMIN role."
    )
    def mcp_create_field_verification_request(
        case_id: str,
        parcel_id: Optional[str] = None,
        title: str = "Field Boundary Inspection",
        reason: str = "Ground truth verification requested by agent",
        priority: str = "MEDIUM",
        finding_id: Optional[str] = None,
        requested_activities: Optional[List[str]] = None,
        special_instructions: Optional[str] = None,
        auth_token: Optional[str] = None
    ) -> Dict[str, Any]:
        with get_mcp_db() as db:
            return execute_create_field_verification_request(
                db,
                case_id=case_id,
                parcel_id=parcel_id,
                title=title,
                reason=reason,
                priority=priority,
                finding_id=finding_id,
                requested_activities=requested_activities,
                special_instructions=special_instructions,
                auth_token=auth_token
            ).model_dump()

    # -------------------------------------------------------------------------
    # Group D — Land Intelligence Reports
    # -------------------------------------------------------------------------

    @server.tool(
        name="get_report_metadata",
        description="Retrieves authorized report metadata (version, status, cryptographic hash, and section summaries) without exposing the raw binary PDF."
    )
    def mcp_get_report_metadata(
        report_id: Optional[str] = None,
        case_id: Optional[str] = None,
        auth_token: Optional[str] = None
    ) -> Dict[str, Any]:
        with get_mcp_db() as db:
            return execute_get_report_metadata(db, report_id=report_id, case_id=case_id, auth_token=auth_token).model_dump()

    @server.tool(
        name="generate_land_intelligence_report",
        description="State-changing tool: Assembles multi-source land evidence, compiles the 8-section dossier, seals the PDF with SHA-256 digest, and returns report metadata with QR URL."
    )
    def mcp_generate_land_intelligence_report(
        case_id: str,
        parcel_id: Optional[str] = None,
        auth_token: Optional[str] = None
    ) -> Dict[str, Any]:
        with get_mcp_db() as db:
            return execute_generate_land_intelligence_report(
                db,
                case_id=case_id,
                parcel_id=parcel_id,
                auth_token=auth_token
            ).model_dump()

    @server.tool(
        name="verify_report_integrity",
        description="Verifies report authenticity and cryptographic SHA-256 hash against the stored disk artifact with strict data minimization."
    )
    def mcp_verify_report_integrity(
        verification_token: str,
        auth_token: Optional[str] = None
    ) -> Dict[str, Any]:
        with get_mcp_db() as db:
            return execute_verify_report_integrity(db, verification_token=verification_token, auth_token=auth_token).model_dump()

    return server


# Default singleton instance
mcp_server = create_mcp_server()


def main():
    """CLI entry point for running the Bhumi Setu MCP Server."""
    parser = argparse.ArgumentParser(description="Bhumi Setu Agent MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default=settings.MCP_TRANSPORT,
        help="MCP transport protocol (stdio, sse, streamable-http)"
    )
    parser.add_argument(
        "--host",
        default=settings.MCP_HOST,
        help="Host address for remote network transports"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=settings.MCP_PORT,
        help="Port number for remote network transports"
    )
    args = parser.parse_args()

    print(f"Starting Bhumi Setu MCP Server (transport={args.transport})...", file=sys.stderr)
    mcp = create_mcp_server()
    if args.transport == "stdio":
        mcp.run(transport="stdio")
    elif args.transport == "sse":
        mcp.run(transport="sse", host=args.host, port=args.port)
    elif args.transport == "streamable-http":
        mcp.run(transport="streamable-http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
