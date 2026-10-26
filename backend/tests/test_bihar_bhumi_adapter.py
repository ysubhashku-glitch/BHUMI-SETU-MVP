import pytest
import uuid
import httpx
from datetime import datetime, timezone

from app.models.parcel import Parcel
from app.models.evidence import Evidence, EvidenceType, AuthorityTier
from app.models.claim import Claim, ClaimPredicate, ClaimStatus
from app.models.case import Case
from app.models.party import Party, PartyType
from app.models.finding import Finding
from app.services.consistency_service import evaluate_claims_consistency
from app.services.scrapers.bihar_bhumi import (
    BiharBhumiJamabandiAdapter,
    BiharJamabandiSearchQuery,
    BiharJamabandiRecord,
    BiharJamabandiSearchResult,
    BiharSearchType,
    SearchOutcomeStatus,
    BiharBhumiError,
    BiharBhumiSourceUnavailableError,
    BiharBhumiInvalidQueryError,
    BiharBhumiRateLimitError
)

# Sanitized official fixture modeled after Bihar Bhumi Register-II
SAMPLE_BIHAR_JAMABANDI_HTML = """
<!DOCTYPE html>
<html>
<head><title>Online Mutation - Register-II</title></head>
<body>
    <div id="content">
        <h2>बिहार सरकार राजस्व एवं भूमि सुधार विभाग</h2>
        <h3>पंजी-II प्रतिवेदन</h3>
        <table class="table table-bordered table-striped" id="ctl00_MainContent_grdJamabandi">
            <thead>
                <tr>
                    <th>क्र० सं०</th>
                    <th>हल्का</th>
                    <th>मौजा</th>
                    <th>खाता संख्या</th>
                    <th>खेसरा संख्या</th>
                    <th>जमाबंदी संख्या</th>
                    <th>कंप्यूटरीकृत जमाबंदी संख्या</th>
                    <th>रैयत का नाम</th>
                    <th>पिता/पति का नाम</th>
                    <th>भाग वर्तमान</th>
                    <th>पृष्ठ संख्या वर्तमान</th>
                    <th>रकबा (डिसमिल)</th>
                    <th>कार्रवाई</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>1</td>
                    <td>हल्का-02</td>
                    <td>कोठवां</td>
                    <td>48</td>
                    <td>112</td>
                    <td>412</td>
                    <td>2021020048112001</td>
                    <td>रामेश्वर प्रसाद सिंह</td>
                    <td>जगन्नाथ सिंह</td>
                    <td>2</td>
                    <td>45</td>
                    <td>50 डिसमिल</td>
                    <td><a href="ViewDetails.aspx?id=12345">देखें</a></td>
                </tr>
            </tbody>
        </table>
    </div>
</body>
</html>
"""

SAMPLE_MULTI_MATCH_HTML = """
<!DOCTYPE html>
<html>
<body>
    <table>
        <tr>
            <th>क्र० सं०</th>
            <th>खाता संख्या</th>
            <th>खेसरा संख्या</th>
            <th>जमाबंदी संख्या</th>
            <th>रैयत का नाम</th>
            <th>पिता/पति का नाम</th>
        </tr>
        <tr>
            <td>1</td>
            <td>48</td>
            <td>112</td>
            <td>412</td>
            <td>राम कुमार</td>
            <td>श्याम लाल</td>
        </tr>
        <tr>
            <td>2</td>
            <td>52</td>
            <td>115</td>
            <td>418</td>
            <td>राम कुमार</td>
            <td>मोहन लाल</td>
        </tr>
    </table>
</body>
</html>
"""

SAMPLE_EMPTY_HTML = """
<!DOCTYPE html>
<html>
<body>
    <div class="alert alert-warning">
        कोई रिकॉर्ड नहीं मिला / No Record Found
    </div>
</body>
</html>
"""


def test_solve_arithmetic_captcha():
    adapter = BiharBhumiJamabandiAdapter()
    assert adapter.solve_arithmetic_captcha("5 + 3") == 8
    assert adapter.solve_arithmetic_captcha("14 - 9") == 5
    assert adapter.solve_arithmetic_captcha("सुरक्षा कोड : 2 + 7 = ") == 9
    assert adapter.solve_arithmetic_captcha("invalid text") is None


def test_query_validation_success():
    query = BiharJamabandiSearchQuery(
        district="Patna",
        circle="Danapur",
        mauza="Kothawan",
        search_type=BiharSearchType.KHATA,
        search_value="48"
    )
    assert query.district == "Patna"
    assert query.circle == "Danapur"
    assert query.search_value == "48"


def test_query_validation_invalid_district():
    with pytest.raises(ValueError, match="is not recognized as one of the 38 administrative districts"):
        BiharJamabandiSearchQuery(
            district="London",
            circle="Danapur",
            mauza="Kothawan",
            search_type=BiharSearchType.KHATA,
            search_value="48"
        )


def test_query_validation_blank_search_value():
    with pytest.raises(ValueError, match="Search value cannot be blank"):
        BiharJamabandiSearchQuery(
            district="Gaya",
            circle="Bodhyaga",
            mauza="Rampur",
            search_type=BiharSearchType.PLOT,
            search_value="   "
        )


def test_parse_jamabandi_html_valid_record():
    adapter = BiharBhumiJamabandiAdapter()
    query = BiharJamabandiSearchQuery(
        district="Patna",
        circle="Danapur",
        mauza="Kothawan",
        search_type=BiharSearchType.KHATA,
        search_value="48"
    )
    records = adapter.parse_jamabandi_html(SAMPLE_BIHAR_JAMABANDI_HTML, query)
    assert len(records) == 1
    rec = records[0]
    assert rec.khata_number == "48"
    assert rec.plot_khesra_number == "112"
    assert rec.jamabandi_number == "412"
    assert rec.computerized_jamabandi_number == "2021020048112001"
    assert rec.raiyat_name == "रामेश्वर प्रसाद सिंह"
    assert rec.father_husband_name == "जगन्नाथ सिंह"
    assert rec.recorded_area_decimal == 50.0
    assert rec.recorded_area_total_acres == 0.5
    assert rec.recorded_area_sqm == 2023.43
    assert rec.canonical_property_id.startswith("BR-PAT-DAN-KOTHAW")


def test_parse_jamabandi_html_empty_result():
    adapter = BiharBhumiJamabandiAdapter()
    query = BiharJamabandiSearchQuery(
        district="Patna",
        circle="Danapur",
        mauza="Kothawan",
        search_type=BiharSearchType.PLOT,
        search_value="999"
    )
    records = adapter.parse_jamabandi_html(SAMPLE_EMPTY_HTML, query)
    assert len(records) == 0


def test_parse_jamabandi_html_ambiguous_matches():
    adapter = BiharBhumiJamabandiAdapter()
    query = BiharJamabandiSearchQuery(
        district="Patna",
        circle="Danapur",
        mauza="Kothawan",
        search_type=BiharSearchType.NAME,
        search_value="राम कुमार"
    )
    records = adapter.parse_jamabandi_html(SAMPLE_MULTI_MATCH_HTML, query)
    assert len(records) == 2
    assert records[0].father_husband_name == "श्याम लाल"
    assert records[1].father_husband_name == "मोहन लाल"


def test_manual_record_ingestion():
    adapter = BiharBhumiJamabandiAdapter()
    query = BiharJamabandiSearchQuery(
        district="Patna",
        circle="Danapur",
        mauza="Kothawan",
        search_type=BiharSearchType.KHATA,
        search_value="48"
    )
    result = adapter.ingest_manual_record(query, SAMPLE_BIHAR_JAMABANDI_HTML)
    assert result.status == SearchOutcomeStatus.FOUND
    assert result.total_matches == 1
    assert result.records[0].retrieval_method == "MANUAL_ENTRY"
    assert result.raw_response_sha256 is not None


def test_manual_record_ingestion_blank_error():
    adapter = BiharBhumiJamabandiAdapter()
    query = BiharJamabandiSearchQuery(
        district="Patna",
        circle="Danapur",
        mauza="Kothawan",
        search_type=BiharSearchType.KHATA,
        search_value="48"
    )
    with pytest.raises(BiharBhumiInvalidQueryError):
        adapter.ingest_manual_record(query, "   ")


@pytest.mark.asyncio
async def test_live_search_source_unavailable_error():
    # Mock transport raising ConnectTimeout
    def handler(request):
        raise httpx.ConnectTimeout("Connection timed out to Bihar portal")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as mock_client:
        adapter = BiharBhumiJamabandiAdapter(client=mock_client)
        query = BiharJamabandiSearchQuery(
            district="Patna",
            circle="Danapur",
            mauza="Kothawan",
            search_type=BiharSearchType.KHATA,
            search_value="48"
        )
        with pytest.raises(BiharBhumiSourceUnavailableError, match="timed out"):
            await adapter.execute_live_search(query)


@pytest.mark.asyncio
async def test_live_search_rate_limited():
    def handler(request):
        return httpx.Response(429, text="Too Many Requests")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as mock_client:
        adapter = BiharBhumiJamabandiAdapter(client=mock_client)
        query = BiharJamabandiSearchQuery(
            district="Patna",
            circle="Danapur",
            mauza="Kothawan",
            search_type=BiharSearchType.KHATA,
            search_value="48"
        )
        with pytest.raises(BiharBhumiRateLimitError):
            await adapter.execute_live_search(query)


def test_persist_record_to_domain_deduplication(db_session, tenant_a, user_a):
    adapter = BiharBhumiJamabandiAdapter()
    query = BiharJamabandiSearchQuery(
        district="Patna",
        circle="Danapur",
        mauza="Kothawan",
        search_type=BiharSearchType.KHATA,
        search_value="48"
    )
    records = adapter.parse_jamabandi_html(SAMPLE_BIHAR_JAMABANDI_HTML, query)
    rec = records[0]

    # Setup test case for claims
    client_party = Party(
        org_id=tenant_a.org_id,
        party_type=PartyType.PERSON,
        primary_name="Deduplication Client"
    )
    db_session.add(client_party)
    db_session.flush()

    test_case = Case(
        org_id=tenant_a.org_id,
        case_number="CASE-BIHAR-DEDUP-001",
        primary_client_party_id=client_party.party_id
    )
    db_session.add(test_case)
    db_session.commit()

    # First persistence pass
    parcel1, ev1, claims1 = adapter.persist_record_to_domain(
        db=db_session,
        record=rec,
        org_id=tenant_a.org_id,
        case_id=test_case.case_id,
        uploader_party_id=user_a.user_id
    )

    assert parcel1.state_code == "BR"
    assert parcel1.khata_number == "48"
    assert parcel1.plot_khesra_number == "112"
    assert ev1.authority_tier == AuthorityTier.REVENUE_RECORD
    assert len(claims1) == 2

    # Second persistence pass for the same parcel (idempotency check)
    parcel2, ev2, claims2 = adapter.persist_record_to_domain(
        db=db_session,
        record=rec,
        org_id=tenant_a.org_id,
        case_id=test_case.case_id,
        uploader_party_id=user_a.user_id
    )

    # Must reuse the same parcel row without duplicating
    assert parcel1.parcel_id == parcel2.parcel_id
    parcels_in_db = db_session.query(Parcel).filter(
        Parcel.org_id == tenant_a.org_id,
        Parcel.khata_number == "48",
        Parcel.plot_khesra_number == "112"
    ).all()
    assert len(parcels_in_db) == 1


def test_consistency_engine_integration_with_jamabandi(db_session, tenant_a, user_a):
    adapter = BiharBhumiJamabandiAdapter()
    query = BiharJamabandiSearchQuery(
        district="Patna",
        circle="Danapur",
        mauza="Kothawan",
        search_type=BiharSearchType.KHATA,
        search_value="48"
    )
    records = adapter.parse_jamabandi_html(SAMPLE_BIHAR_JAMABANDI_HTML, query)
    rec = records[0]

    # Create Client Party and Case
    client_party = Party(
        org_id=tenant_a.org_id,
        party_type=PartyType.PERSON,
        primary_name="Rameshwar Prasad Singh"
    )
    db_session.add(client_party)
    db_session.flush()

    test_case = Case(
        org_id=tenant_a.org_id,
        case_number="CASE-BIHAR-2026-001",
        primary_client_party_id=client_party.party_id
    )
    db_session.add(test_case)
    db_session.commit()

    # Persist official Jamabandi record (2023.43 sqm = 50 decimal)
    parcel, evidence, claims = adapter.persist_record_to_domain(
        db=db_session,
        record=rec,
        org_id=tenant_a.org_id,
        case_id=test_case.case_id,
        uploader_party_id=user_a.user_id
    )

    # Inject a conflicting user-submitted deed claim (3000.0 sqm = ~74 decimal)
    deed_evidence = Evidence(
        evidence_type=EvidenceType.REGISTERED_DOCUMENT,
        authority_tier=AuthorityTier.STATUTORY_REGISTRY,
        source_name="Registered Sale Deed 1452/2021",
        storage_uri="mock://storage/sale_deed.pdf",
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )
    db_session.add(deed_evidence)
    db_session.flush()

    conflicting_deed_claim = Claim(
        case_id=test_case.case_id,
        parcel_id=parcel.parcel_id,
        evidence_id=deed_evidence.evidence_id,
        subject_entity_type="PARCEL",
        subject_id=parcel.parcel_id,
        predicate=ClaimPredicate.RECORDED_AREA,
        object_value={
            "raw_value": "74 Decimal",
            "normalized_value": {
                "normalized_sqm": 3000.0,
                "acre": 0.74,
                "decimal": 74.0
            }
        },
        authority_tier=AuthorityTier.STATUTORY_REGISTRY,
        confidence_score=0.95,
        status=ClaimStatus.ACTIVE
    )
    db_session.add(conflicting_deed_claim)
    db_session.commit()

    # Trigger Consistency Engine
    findings = evaluate_claims_consistency(test_case.case_id, parcel.parcel_id, db_session)
    assert len(findings) >= 1
    area_finding = [f for f in findings if f.rule_id == "RULE_AREA_DELTA_CHECK"][0]
    assert area_finding.severity == "CRITICAL"
    assert "Discrepancy" in area_finding.explanation


def test_api_endpoint_manual_ingestion(client, auth_headers_a):
    payload = {
        "query": {
            "state": "Bihar",
            "district": "Patna",
            "circle": "Danapur",
            "mauza": "Kothawan",
            "search_type": "KHATA",
            "search_value": "48"
        },
        "source_artifact": SAMPLE_BIHAR_JAMABANDI_HTML,
        "persist": True
    }
    response = client.post(
        "/api/v1/parcels/bihar/jamabandi/ingest-manual",
        json=payload,
        headers=auth_headers_a
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "FOUND"
    assert data["total_matches"] == 1
    assert data["records"][0]["raiyat_name"] == "रामेश्वर प्रसाद सिंह"
    assert data["records"][0]["khata_number"] == "48"
