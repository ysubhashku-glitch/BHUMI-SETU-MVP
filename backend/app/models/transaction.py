import uuid
import sqlalchemy as sa
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.base import GUID, utc_now

class TransactionType(str):
    SALE = "SALE"
    PARTITION = "PARTITION"
    GIFT = "GIFT"
    INHERITANCE = "INHERITANCE"
    MORTGAGE = "MORTGAGE"
    LEASE = "LEASE"

class TransactionPartyRole(str):
    EXECUTANT_VENDOR = "EXECUTANT_VENDOR"
    CLAIMANT_BUYER = "CLAIMANT_BUYER"
    WITNESS = "WITNESS"
    IDENTIFIER = "IDENTIFIER"
    LEGAL_GUARDIAN = "LEGAL_GUARDIAN"

class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    org_id = sa.Column(GUID, sa.ForeignKey("organizations.org_id", ondelete="CASCADE"), nullable=False, index=True)
    transaction_type = sa.Column(sa.String(32), nullable=False, default=TransactionType.SALE)
    execution_date = sa.Column(sa.Date, nullable=True)
    registration_date = sa.Column(sa.Date, nullable=True)
    registration_identifier = sa.Column(sa.String(128), nullable=True)
    sro_code = sa.Column(sa.String(32), nullable=True)
    stated_consideration_inr = sa.Column(sa.Numeric(14, 2), nullable=True)
    status = sa.Column(sa.String(32), nullable=False, default="PROPOSED")
    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)

    parcels = relationship("TransactionParcel", back_populates="transaction", cascade="all, delete-orphan")
    parties = relationship("TransactionParty", back_populates="transaction", cascade="all, delete-orphan")
    cases = relationship("Case", back_populates="target_transaction")

class TransactionParcel(Base):
    __tablename__ = "transaction_parcels"

    transaction_id = sa.Column(GUID, sa.ForeignKey("transactions.transaction_id", ondelete="CASCADE"), primary_key=True)
    parcel_id = sa.Column(GUID, sa.ForeignKey("parcels.parcel_id", ondelete="CASCADE"), primary_key=True)
    transferred_area_acres = sa.Column(sa.Numeric(10, 4), nullable=False)

    transaction = relationship("Transaction", back_populates="parcels")
    parcel = relationship("Parcel")

class TransactionParty(Base):
    __tablename__ = "transaction_parties"

    transaction_id = sa.Column(GUID, sa.ForeignKey("transactions.transaction_id", ondelete="CASCADE"), primary_key=True)
    party_id = sa.Column(GUID, sa.ForeignKey("parties.party_id", ondelete="CASCADE"), primary_key=True)
    party_role = sa.Column(sa.String(32), primary_key=True, default=TransactionPartyRole.CLAIMANT_BUYER)
    share_percentage = sa.Column(sa.Numeric(5, 2), default=100.00, nullable=False)

    transaction = relationship("Transaction", back_populates="parties")
    party = relationship("Party", back_populates="transaction_associations")
