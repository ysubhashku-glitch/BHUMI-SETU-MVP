import pytest
import uuid
from datetime import datetime, date, timezone
from app.models.claim import Claim, ClaimStatus, ClaimPredicate
from app.models.parcel import Parcel, ParcelRelationship, ParcelRelationshipType
from app.models.evidence import Evidence, EvidenceType, AuthorityTier
from app.models.case import Case, CaseStatus, TransactionReadinessState
from app.models.party import Party, PartyType, CommunityCategory
from app.services.consistency_service import check_area_delta, check_mutation_gap, check_chauhadri_boundaries
from app.services.legal_rule_service import evaluate_spt_act_section_20
from app.services.finding_service import create_finding, create_required_action, resolve_finding
from app.models.finding import FindingSeverity, FindingStatus, ActionStatus

def test_competing_claims_coexistence(db_session, tenant_a, client_party):
    # Setup parcel & case
    parcel = Parcel(
        org_id=tenant_a.org_id,
        bhumi_id="JH-DEO-COMPETE-01",
        state_code="JH",
        district_name="Deoghar",
        subdistrict_anchal_name="Mohanpur",
        mauza_village_name="Chopamo",
        census_village_code="364",
        khata_number="88",
        plot_khesra_number="210",
        recorded_area_acres=1.0
    )
    case = Case(
        org_id=tenant_a.org_id,
        case_number="BS-TEST-COMPETING",
        primary_client_party_id=client_party.party_id
    )
    db_session.add_all([parcel, case])
    db_session.flush()

    evidence1 = Evidence(
        evidence_type=EvidenceType.GOVERNMENT_RECORD,
        authority_tier=AuthorityTier.REVENUE_RECORD,
        source_name="Khatiyan Record",
        storage_uri="mock://khatiyan.pdf",
        sha256_hash="hash1" + "0"*59
    )
    evidence2 = Evidence(
        evidence_type=EvidenceType.REGISTERED_DOCUMENT,
        authority_tier=AuthorityTier.STATUTORY_REGISTRY,
        source_name="Registered Sale Deed",
        storage_uri="mock://deed.pdf",
        sha256_hash="hash2" + "0"*59
    )
    db_session.add_all([evidence1, evidence2])
    db_session.flush()

    # Claim A: Recorded owner is Party X (from Revenue Khatiyan)
    claim_a = Claim(
        case_id=case.case_id,
        parcel_id=parcel.parcel_id,
        evidence_id=evidence1.evidence_id,
        subject_entity_type="PARCEL",
        subject_id=parcel.parcel_id,
        predicate=ClaimPredicate.RECORDED_OWNER,
        object_value={"owner_name": "Suresh Raiyat", "khata": "88"},
        authority_tier=AuthorityTier.REVENUE_RECORD,
        confidence_score=0.95,
        status=ClaimStatus.ACTIVE
    )

    # Claim B: Registered Transfer to Party Y (from Sale Deed)
    claim_b = Claim(
        case_id=case.case_id,
        parcel_id=parcel.parcel_id,
        evidence_id=evidence2.evidence_id,
        subject_entity_type="PARCEL",
        subject_id=parcel.parcel_id,
        predicate=ClaimPredicate.POSSESSION_HOLDER,
        object_value={"transferee_name": "Ramesh Buyer", "deed_number": "1042/2021"},
        authority_tier=AuthorityTier.STATUTORY_REGISTRY,
        confidence_score=1.00,
        status=ClaimStatus.ACTIVE
    )
    db_session.add_all([claim_a, claim_b])
    db_session.commit()

    # Verify both competing claims coexist and are queryable independently
    claims = db_session.query(Claim).filter(Claim.parcel_id == parcel.parcel_id).all()
    assert len(claims) == 2
    predicates = [c.predicate for c in claims]
    assert ClaimPredicate.RECORDED_OWNER in predicates
    assert ClaimPredicate.POSSESSION_HOLDER in predicates

def test_parcel_lineage_subdivision(db_session, tenant_a):
    parent = Parcel(
        org_id=tenant_a.org_id,
        bhumi_id="JH-DEO-PARENT-01",
        state_code="JH",
        district_name="Deoghar",
        subdistrict_anchal_name="Mohanpur",
        mauza_village_name="Chopamo",
        census_village_code="364",
        khata_number="12",
        plot_khesra_number="500",
        recorded_area_acres=2.0
    )
    child1 = Parcel(
        org_id=tenant_a.org_id,
        bhumi_id="JH-DEO-CHILD-01",
        state_code="JH",
        district_name="Deoghar",
        subdistrict_anchal_name="Mohanpur",
        mauza_village_name="Chopamo",
        census_village_code="364",
        khata_number="12",
        plot_khesra_number="500/1",
        recorded_area_acres=1.0
    )
    child2 = Parcel(
        org_id=tenant_a.org_id,
        bhumi_id="JH-DEO-CHILD-02",
        state_code="JH",
        district_name="Deoghar",
        subdistrict_anchal_name="Mohanpur",
        mauza_village_name="Chopamo",
        census_village_code="364",
        khata_number="12",
        plot_khesra_number="500/2",
        recorded_area_acres=1.0
    )
    db_session.add_all([parent, child1, child2])
    db_session.flush()

    rel1 = ParcelRelationship(
        parent_parcel_id=parent.parcel_id,
        child_parcel_id=child1.parcel_id,
        relationship_type=ParcelRelationshipType.SUBDIVIDED_TO,
        effective_date=date(2023, 5, 10),
        mutation_order_reference="MUT-2023-9981"
    )
    rel2 = ParcelRelationship(
        parent_parcel_id=parent.parcel_id,
        child_parcel_id=child2.parcel_id,
        relationship_type=ParcelRelationshipType.SUBDIVIDED_TO,
        effective_date=date(2023, 5, 10),
        mutation_order_reference="MUT-2023-9981"
    )
    db_session.add_all([rel1, rel2])
    db_session.commit()

    children = db_session.query(ParcelRelationship).filter(
        ParcelRelationship.parent_parcel_id == parent.parcel_id
    ).all()
    assert len(children) == 2
    assert {c.child_parcel_id for c in children} == {child1.parcel_id, child2.parcel_id}

def test_consistency_service_area_delta():
    # Within tolerance (3% delta)
    res_pass = check_area_delta(deed_area_sqm=1000.0, survey_area_sqm=970.0, tolerance_pct=5.0)
    assert res_pass.passed is True
    assert res_pass.severity == FindingSeverity.INFORMATIONAL

    # Exceeding tolerance (20% delta)
    res_fail = check_area_delta(deed_area_sqm=1000.0, survey_area_sqm=800.0, tolerance_pct=5.0)
    assert res_fail.passed is False
    assert res_fail.severity == FindingSeverity.CRITICAL
    assert "Discrepancy" in res_fail.explanation

def test_consistency_service_mutation_gap():
    # Unmutated deed
    deed_dt = datetime(2022, 1, 15, tzinfo=timezone.utc)
    res_unmutated = check_mutation_gap(deed_date=deed_dt, mutation_date=None)
    assert res_unmutated.passed is False
    assert res_unmutated.severity == FindingSeverity.CRITICAL

    # Delayed mutation
    mut_dt = datetime(2023, 3, 10, tzinfo=timezone.utc)
    res_delayed = check_mutation_gap(deed_date=deed_dt, mutation_date=mut_dt)
    assert res_delayed.passed is False
    assert res_delayed.severity == FindingSeverity.MEDIUM

def test_legal_rule_spt_act_section_20():
    # Deoghar tribal raiyati -> CRITICAL statutory hazard
    res_hazard = evaluate_spt_act_section_20(
        state="Jharkhand",
        district="Deoghar",
        vendor_community_category="SCHEDULED_TRIBE",
        is_raiyati_holding=True
    )
    assert res_hazard.statutory_hazard is True
    assert res_hazard.severity == FindingSeverity.CRITICAL
    assert "Section 20 of SPT Act, 1949" in res_hazard.explanation

    # Non-tribal vendor in Deoghar -> Not a statutory blocker
    res_non_tribal = evaluate_spt_act_section_20(
        state="Jharkhand",
        district="Deoghar",
        vendor_community_category="GENERAL",
        is_raiyati_holding=True
    )
    assert res_non_tribal.statutory_hazard is False

    # Outside Santhal Parganas (e.g. Ranchi) -> SPT does not apply
    res_outside = evaluate_spt_act_section_20(
        state="Jharkhand",
        district="Ranchi",
        vendor_community_category="SCHEDULED_TRIBE",
        is_raiyati_holding=True
    )
    assert res_outside.statutory_hazard is False
    assert res_outside.severity == FindingSeverity.INFORMATIONAL
