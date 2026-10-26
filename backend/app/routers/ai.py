import uuid
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.case import Case
from app.core.dependencies import get_current_user
from app.core.exceptions import EntityNotFoundError, CrossTenantAccessError
from app.services.mock_ai_service import query_ai_land_expert

router = APIRouter(prefix="/cases", tags=["AI Land Expert (Read-Only)"])

class AIQueryRequest(BaseModel):
    query: str

@router.post("/{case_id}/ai/query")
def ask_ai_land_expert(
    case_id: uuid.UUID,
    request: AIQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    case = db.query(Case).filter(Case.case_id == case_id).first()
    if not case:
        raise EntityNotFoundError("Case", case_id)
    if case.org_id != current_user.org_id:
        raise CrossTenantAccessError()

    result = query_ai_land_expert(db=db, case_id=case_id, question=request.query)
    return result
