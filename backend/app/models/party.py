import uuid
import sqlalchemy as sa
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.base import GUID, utc_now

class PartyType(str):
    PERSON = "PERSON"
    ORGANIZATION = "ORGANIZATION"
    GOVERNMENT_ENTITY = "GOVERNMENT_ENTITY"
    TRUST = "TRUST"
    HUF = "HUF"
    OTHER = "OTHER"

class RelationshipType(str):
    SON_OF = "SON_OF"
    DAUGHTER_OF = "DAUGHTER_OF"
    WIFE_OF = "WIFE_OF"
    REPRESENTED_BY = "REPRESENTED_BY"
    OTHER = "OTHER"

class CommunityCategory(str):
    GENERAL = "GENERAL"
    OBC = "OBC"
    SC = "SC"
    ST = "ST"  # Scheduled Tribe - Critical for Santhal Parganas Tenancy (SPT) Act Sec 20 statutory audit

class Party(Base):
    __tablename__ = "parties"

    party_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    org_id = sa.Column(GUID, sa.ForeignKey("organizations.org_id", ondelete="CASCADE"), nullable=False, index=True)
    party_type = sa.Column(sa.String(32), nullable=False, default=PartyType.PERSON)
    primary_name = sa.Column(sa.String(128), nullable=False)
    canonical_transliterated_name = sa.Column(sa.String(128), index=True)
    father_or_husband_name = sa.Column(sa.String(128), index=True)
    relationship_type = sa.Column(sa.String(16), default=RelationshipType.SON_OF)
    
    # Lawful Statutory Purpose: Required for SPT Act Section 20 and CNT Act Section 46 tribal land transfer restrictions
    community_caste_category = sa.Column(sa.String(32), nullable=False, default=CommunityCategory.GENERAL)
    is_tribal = sa.Column(sa.Boolean, nullable=False, default=False)
    
    phone_number = sa.Column(sa.String(20), nullable=True)
    residence_village_lgd = sa.Column(sa.String(32), nullable=True)
    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)

    cases = relationship("Case", back_populates="client_party")
    transaction_associations = relationship("TransactionParty", back_populates="party")
