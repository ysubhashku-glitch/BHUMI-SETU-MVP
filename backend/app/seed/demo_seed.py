import uuid
from datetime import datetime, timezone, date
from app.database import SessionLocal
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.models.party import Party, PartyType, CommunityCategory
from app.models.parcel import Parcel
from app.models.case import Case, CaseStatus, TransactionReadinessState, CaseParcel
from app.models.evidence import Evidence, CaseEvidence, EvidenceType, AuthorityTier
from app.models.claim import Claim, ClaimStatus, ClaimPredicate
from app.models.finding import Finding, FindingSeverity, FindingStatus, RequiredAction, ActionStatus
from app.core.security import hash_password

def seed_demo_database():
    db = SessionLocal()
    try:
        print("[INFO] Seeding BhumiSetu Development Demo Environment [DEMO_DATA]...")

        # 1. Organization / Tenant
        demo_org = db.query(Organization).filter(Organization.name == "DEMO_DATA: Deoghar Operations").first()
        if not demo_org:
            demo_org = Organization(
                name="DEMO_DATA: Deoghar Operations",
                slug="deoghar-demo"
            )
            db.add(demo_org)
            db.flush()
            print(f"  + Created Tenant: {demo_org.name} ({demo_org.org_id})")

        # 2. Demo Users
        users_to_seed = [
            ("admin@bhumisetu-demo.local", "DEMO_DATA: System Administrator", "9800000001", UserRole.ADMIN),
            ("operator@bhumisetu-demo.local", "DEMO_DATA: Case Desk Operator", "9800000002", UserRole.CASE_OPERATOR),
            ("amin@bhumisetu-demo.local", "DEMO_DATA: Lead Field Amin", "9800000003", UserRole.FIELD_EXPERT),
            ("advocate@bhumisetu-demo.local", "DEMO_DATA: Legal Title Advocate", "9800000004", UserRole.LEGAL_REVIEWER)
        ]

        for email, name, phone, role in users_to_seed:
            existing_user = db.query(User).filter(User.email == email).first()
            if not existing_user:
                u = User(
                    org_id=demo_org.org_id,
                    email=email,
                    hashed_password=hash_password("DemoPassword123!"),
                    full_name=name,
                    phone_number=phone,
                    role=role,
                    is_active=True
                )
                db.add(u)
                print(f"  + Created User: {email} ({role})")
        db.flush()

        # 3. Parties
        buyer_party = db.query(Party).filter(Party.primary_name == "DEMO_DATA: Ramesh Kumar (Buyer)").first()
        if not buyer_party:
            buyer_party = Party(
                org_id=demo_org.org_id,
                party_type=PartyType.PERSON,
                primary_name="DEMO_DATA: Ramesh Kumar (Buyer)",
                phone_number="9876543210",
                community_caste_category=CommunityCategory.GENERAL,
                is_tribal=False
            )
            db.add(buyer_party)

        raiyat_party = db.query(Party).filter(Party.primary_name == "DEMO_DATA: Suresh Marandi (Raiyat)").first()
        if not raiyat_party:
            raiyat_party = Party(
                org_id=demo_org.org_id,
                party_type=PartyType.PERSON,
                primary_name="DEMO_DATA: Suresh Marandi (Raiyat)",
                phone_number="9876543211",
                community_caste_category=CommunityCategory.ST,
                is_tribal=True
            )
            db.add(raiyat_party)
        db.flush()

        # 4. Parcel (Mohanpur, Deoghar, Plot 542)
        demo_bhumi_id = "DEMO-JH-DEO-364-542"
        demo_parcel = db.query(Parcel).filter(Parcel.bhumi_id == demo_bhumi_id).first()
        if not demo_parcel:
            demo_parcel = Parcel(
                org_id=demo_org.org_id,
                bhumi_id=demo_bhumi_id,
                state_code="JH",
                district_name="Deoghar",
                subdistrict_anchal_name="Mohanpur",
                halka_number="04",
                mauza_village_name="Chopamo",
                census_village_code="364000",
                khata_number="12",
                plot_khesra_number="542",
                recorded_area_acres=1.5000,
                land_nature="AGRICULTURAL_RAIYATI"
            )
            db.add(demo_parcel)
            db.flush()
            print(f"  + Created Demo Parcel: {demo_parcel.bhumi_id}")

        # 5. Case
        demo_case_num = "DEMO-BS-JH-2026-0001"
        demo_case = db.query(Case).filter(Case.case_number == demo_case_num).first()
        if not demo_case:
            demo_case = Case(
                org_id=demo_org.org_id,
                case_number=demo_case_num,
                primary_client_party_id=buyer_party.party_id,
                status=CaseStatus.PROPERTY_IDENTIFIED,
                transaction_readiness_state=TransactionReadinessState.NOT_READY
            )
            db.add(demo_case)
            db.flush()

            # Associate parcel
            cp = CaseParcel(case_id=demo_case.case_id, parcel_id=demo_parcel.parcel_id, is_primary=True)
            db.add(cp)
            print(f"  + Created Demo Case: {demo_case.case_number}")

        # 6. Evidence
        demo_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        demo_evidence = db.query(Evidence).filter(Evidence.sha256_hash == demo_hash).first()
        if not demo_evidence:
            demo_evidence = Evidence(
                evidence_type=EvidenceType.GOVERNMENT_RECORD,
                authority_tier=AuthorityTier.REVENUE_RECORD,
                source_name="DEMO_DATA: Certified Khatiyan Volume Extract (Mock)",
                storage_uri="mock://storage/demo_khatiyan_extract.pdf",
                sha256_hash=demo_hash,
                evidence_metadata={
                    "khatiyan_type": "Cadastral Survey",
                    "circle": "Mohanpur",
                    "mauza": "Chopamo",
                    "note": "SYNTHETIC_DEVELOPMENT_SAMPLE"
                }
            )
            db.add(demo_evidence)
            db.flush()

            case_ev = CaseEvidence(case_id=demo_case.case_id, evidence_id=demo_evidence.evidence_id)
            db.add(case_ev)

        # 7. Claim
        demo_claim = db.query(Claim).filter(Claim.case_id == demo_case.case_id).first()
        if not demo_claim:
            demo_claim = Claim(
                case_id=demo_case.case_id,
                parcel_id=demo_parcel.parcel_id,
                evidence_id=demo_evidence.evidence_id,
                subject_entity_type="PARCEL",
                subject_id=demo_parcel.parcel_id,
                predicate=ClaimPredicate.RECORDED_OWNER,
                object_value={
                    "owner_name": "DEMO_DATA: Suresh Marandi",
                    "khata_number": "12",
                    "raiyati_nature": "Pradhani Raiyati"
                },
                authority_tier=AuthorityTier.REVENUE_RECORD,
                confidence_score=0.98,
                status=ClaimStatus.ACTIVE
            )
            db.add(demo_claim)

        # 8. Finding & Action
        demo_finding = db.query(Finding).filter(Finding.case_id == demo_case.case_id).first()
        if not demo_finding:
            demo_finding = Finding(
                case_id=demo_case.case_id,
                parcel_id=demo_parcel.parcel_id,
                rule_id="LEGAL_RULE_JH_SPT_SEC_20",
                severity=FindingSeverity.CRITICAL,
                status=FindingStatus.OPEN,
                observed_values={
                    "district": "Deoghar",
                    "record_holder": "DEMO_DATA: Suresh Marandi",
                    "community_category": "SCHEDULED_TRIBE",
                    "land_nature": "AGRICULTURAL_RAIYATI"
                },
                explanation="DEMO_DATA: Statutory transfer prohibition under Section 20 of Santhal Parganas Tenancy Act, 1949.",
                recommended_action="Conduct Deputy Commissioner revenue record verification and obtain certified circle clearance."
            )
            db.add(demo_finding)
            db.flush()

            demo_action = RequiredAction(
                finding_id=demo_finding.finding_id,
                case_id=demo_case.case_id,
                action_type="STATUTORY_CLEARANCE_INSPECTION",
                assigned_role="LEGAL_ADVOCATE",
                status=ActionStatus.OPEN
            )
            db.add(demo_action)

        db.commit()
        print("[SUCCESS] Demo environment seeded successfully. All records strictly marked DEMO_DATA.")
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Error seeding demo database: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_demo_database()
