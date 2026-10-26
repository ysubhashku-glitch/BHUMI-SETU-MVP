from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.core.dependencies import get_current_user
from app.mcp.server import mcp_server
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

router = APIRouter(prefix="/mcp", tags=["Model Context Protocol (MCP)"])

@router.get("/tools", summary="List registered MCP tools and schemas")
async def list_mcp_tools():
    """
    Returns the metadata, description, and input schema for all 11 governed
    Bhumi Setu MCP tools.
    """
    tools = await mcp_server.list_tools()
    return [
        {
            "name": t.name,
            "description": t.description,
            "input_schema": t.input_schema
        }
        for t in tools
    ]

@router.post("/call/{tool_name}", summary="Invoke an MCP tool over HTTP")
async def call_mcp_tool(
    tool_name: str,
    arguments: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Invokes a governed MCP tool via HTTP using the caller's JWT authentication session.
    """
    # Map tool name to execution function
    tool_map = {
        "get_parcel_summary": lambda: execute_get_parcel_summary(
            db,
            parcel_id=arguments.get("parcel_id", ""),
            auth_token=None,  # pass current_user directly or simulate context
            summary_scope=arguments.get("summary_scope", "FULL")
        ),
        "get_revenue_record_summary": lambda: execute_get_revenue_record_summary(
            db,
            parcel_id=arguments.get("parcel_id", "")
        ),
        "get_spatial_summary": lambda: execute_get_spatial_summary(
            db,
            parcel_id=arguments.get("parcel_id", "")
        ),
        "get_document_extraction_summary": lambda: execute_get_document_extraction_summary(
            db,
            case_id=arguments.get("case_id", ""),
            document_id=arguments.get("document_id")
        ),
        "get_evidence_register": lambda: execute_get_evidence_register(
            db,
            case_id=arguments.get("case_id", "")
        ),
        "get_consistency_findings": lambda: execute_get_consistency_findings(
            db,
            case_id=arguments.get("case_id", ""),
            parcel_id=arguments.get("parcel_id")
        ),
        "get_field_verification_status": lambda: execute_get_field_verification_status(
            db,
            task_id=arguments.get("task_id"),
            case_id=arguments.get("case_id"),
            parcel_id=arguments.get("parcel_id")
        ),
        "create_field_verification_request": lambda: execute_create_field_verification_request(
            db,
            case_id=arguments.get("case_id", ""),
            parcel_id=arguments.get("parcel_id"),
            title=arguments.get("title", "Field Boundary Inspection"),
            reason=arguments.get("reason", "Ground truth verification"),
            priority=arguments.get("priority", "MEDIUM"),
            finding_id=arguments.get("finding_id"),
            requested_activities=arguments.get("requested_activities"),
            special_instructions=arguments.get("special_instructions")
        ),
        "get_report_metadata": lambda: execute_get_report_metadata(
            db,
            report_id=arguments.get("report_id"),
            case_id=arguments.get("case_id")
        ),
        "generate_land_intelligence_report": lambda: execute_generate_land_intelligence_report(
            db,
            case_id=arguments.get("case_id", ""),
            parcel_id=arguments.get("parcel_id")
        ),
        "verify_report_integrity": lambda: execute_verify_report_integrity(
            db,
            verification_token=arguments.get("verification_token", "")
        )
    }

    if tool_name not in tool_map:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MCP Tool '{tool_name}' not found."
        )

    # In HTTP router, we pass the current_user's access token if not present
    from app.core.security import create_access_token
    token = create_access_token(subject=str(current_user.user_id), tenant_id=str(current_user.org_id), role=current_user.role)
    if "auth_token" not in arguments:
        arguments["auth_token"] = token

    result = await mcp_server.call_tool(tool_name, arguments)
    return result.model_dump()
