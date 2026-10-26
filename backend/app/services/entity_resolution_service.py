import uuid
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.models.party import Party
from app.models.parcel import Parcel

class EntityMatchOutcome(str):
    MATCHED = "MATCHED"
    PROBABLE_MATCH = "PROBABLE_MATCH"
    POSSIBLE_MATCH = "POSSIBLE_MATCH"
    CONFLICT = "CONFLICT"
    UNMATCHED = "UNMATCHED"

class ParcelMatchOutcome(str):
    MATCHED = "MATCHED"
    AMBIGUOUS_MATCH = "AMBIGUOUS_MATCH"
    UNMATCHED = "UNMATCHED"

class PartyMatchResult:
    def __init__(
        self,
        outcome: str,
        matched_party_id: Optional[uuid.UUID],
        confidence: float,
        matching_signals: Dict[str, Any],
        explanation: str
    ):
        self.outcome = outcome
        self.matched_party_id = matched_party_id
        self.confidence = round(confidence, 2)
        self.matching_signals = matching_signals
        self.explanation = explanation

    def to_dict(self) -> Dict[str, Any]:
        return {
            "outcome": self.outcome,
            "matched_party_id": str(self.matched_party_id) if self.matched_party_id else None,
            "confidence": self.confidence,
            "matching_signals": self.matching_signals,
            "explanation": self.explanation
        }

class ParcelMatchResult:
    def __init__(
        self,
        outcome: str,
        matched_parcel_id: Optional[uuid.UUID],
        candidate_parcel_ids: List[uuid.UUID],
        confidence: float,
        explanation: str
    ):
        self.outcome = outcome
        self.matched_parcel_id = matched_parcel_id
        self.candidate_parcel_ids = candidate_parcel_ids
        self.confidence = round(confidence, 2)
        self.explanation = explanation

    def to_dict(self) -> Dict[str, Any]:
        return {
            "outcome": self.outcome,
            "matched_parcel_id": str(self.matched_parcel_id) if self.matched_parcel_id else None,
            "candidate_parcel_ids": [str(p) for p in self.candidate_parcel_ids],
            "confidence": self.confidence,
            "explanation": self.explanation
        }

class EntityResolutionService:
    """
    Candidate entity matching service.
    Matches extracted parties and parcels against existing database records without silent merges.
    """
    @classmethod
    def resolve_party(
        cls,
        extracted_name: str,
        relative_name: Optional[str],
        org_id: uuid.UUID,
        db: Session
    ) -> PartyMatchResult:
        if not extracted_name or extracted_name == "UNKNOWN":
            return PartyMatchResult(
                outcome=EntityMatchOutcome.UNMATCHED,
                matched_party_id=None,
                confidence=0.0,
                matching_signals={},
                explanation="No valid name provided for party matching."
            )

        clean_ext_name = extracted_name.strip().lower()
        candidates = db.query(Party).filter(Party.org_id == org_id).all()

        exact_matches = []
        probable_matches = []

        for p in candidates:
            p_name = p.primary_name.strip().lower()
            if p_name == clean_ext_name:
                exact_matches.append(p)
            elif clean_ext_name in p_name or p_name in clean_ext_name:
                probable_matches.append(p)

        if len(exact_matches) == 1:
            party = exact_matches[0]
            return PartyMatchResult(
                outcome=EntityMatchOutcome.MATCHED,
                matched_party_id=party.party_id,
                confidence=0.95,
                matching_signals={"primary_name": party.primary_name, "match_type": "EXACT"},
                explanation=f"Exact match on primary name '{party.primary_name}'."
            )
        elif len(exact_matches) > 1:
            return PartyMatchResult(
                outcome=EntityMatchOutcome.CONFLICT,
                matched_party_id=None,
                confidence=0.50,
                matching_signals={"count": len(exact_matches)},
                explanation="Multiple distinct parties exist with the exact same name in this tenant."
            )
        elif len(probable_matches) == 1:
            party = probable_matches[0]
            return PartyMatchResult(
                outcome=EntityMatchOutcome.PROBABLE_MATCH,
                matched_party_id=party.party_id,
                confidence=0.75,
                matching_signals={"primary_name": party.primary_name, "match_type": "SUBSTRING"},
                explanation=f"Probable substring match with '{party.primary_name}'. Requires verification."
            )

        return PartyMatchResult(
            outcome=EntityMatchOutcome.UNMATCHED,
            matched_party_id=None,
            confidence=0.0,
            matching_signals={},
            explanation="No matching party found in tenant records."
        )

    @classmethod
    def resolve_parcel(
        cls,
        district: Optional[str],
        circle: Optional[str],
        village: Optional[str],
        khata: Optional[str],
        plot: Optional[str],
        org_id: uuid.UUID,
        db: Session
    ) -> ParcelMatchResult:
        if not plot or plot == "UNKNOWN":
            return ParcelMatchResult(
                outcome=ParcelMatchOutcome.UNMATCHED,
                matched_parcel_id=None,
                candidate_parcel_ids=[],
                confidence=0.0,
                explanation="Missing plot / khesra number for parcel identity matching."
            )

        query = db.query(Parcel).filter(Parcel.org_id == org_id)
        if plot:
            query = query.filter(Parcel.plot_khesra_number.ilike(f"%{plot}%"))
        if village and village != "UNKNOWN":
            query = query.filter(Parcel.mauza_village_name.ilike(f"%{village}%"))

        matches = query.all()
        if len(matches) == 1:
            return ParcelMatchResult(
                outcome=ParcelMatchOutcome.MATCHED,
                matched_parcel_id=matches[0].parcel_id,
                candidate_parcel_ids=[matches[0].parcel_id],
                confidence=0.95,
                explanation=f"Unique parcel matched on plot '{plot}' in village '{village}'."
            )
        elif len(matches) > 1:
            return ParcelMatchResult(
                outcome=ParcelMatchOutcome.AMBIGUOUS_MATCH,
                matched_parcel_id=None,
                candidate_parcel_ids=[m.parcel_id for m in matches],
                confidence=0.50,
                explanation=f"Ambiguous match: {len(matches)} candidate parcels match plot '{plot}'."
            )

        return ParcelMatchResult(
            outcome=ParcelMatchOutcome.UNMATCHED,
            matched_parcel_id=None,
            candidate_parcel_ids=[],
            confidence=0.0,
            explanation=f"No existing parcel found matching plot '{plot}' in village '{village}'."
        )
