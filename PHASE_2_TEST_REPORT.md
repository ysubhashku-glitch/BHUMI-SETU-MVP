# BHUMISETU — PHASE 2 TEST REPORT
**Document Code:** BS-TEST-REP-V1.1  
**Date:** September 2026  
**Test Suite:** Pytest 9.1.1 / Python 3.14.7  
**Test Result:** 18 PASSED, 0 FAILED (100% Pass Rate)  
**Execution Duration:** 3.22 seconds  
**Status:** ALL TESTS VERIFIED & PASSING  

---

## 1. Executive Summary

A comprehensive automated test suite was constructed and executed against the BhumiSetu Phase 2 foundation. The tests validate database constraints, tenant boundaries, API endpoints, deterministic consistency rules, statutory legal restrictions, epistemic claim coexistence, and the complete end-to-end vertical slice from customer intake to verified finding resolution.

All 18 test cases passed with zero regressions.

---

## 2. Test Execution Matrix

| Test Identifier | Category | Test Objective | Result |
| :--- | :--- | :--- | :--- |
| `tests/test_database.py::test_tenant_creation_and_guid_pk` | Database | Verifies UUID primary keys and default timestamp generators on Tenant entities. | **PASS** |
| `tests/test_database.py::test_unique_user_email_constraint` | Database | Enforces unique email constraint across system users. | **PASS** |
| `tests/test_database.py::test_unique_bhumi_id_constraint` | Database | Enforces unique `bhumi_id` constraint across all parcels. | **PASS** |
| `tests/test_database.py::test_cascade_delete_organization` | Database | Verifies that deleting a tenant safely cascades to internal users and domain objects. | **PASS** |
| `tests/test_api.py::test_auth_login_success` | API | Validates password verification and JWT token issuance with tenant and role claims. | **PASS** |
| `tests/test_api.py::test_auth_login_invalid_password` | API | Rejects invalid credentials with structured `AUTHENTICATION_FAILED` code. | **PASS** |
| `tests/test_api.py::test_create_and_get_parcel` | API | Tests parcel creation with natural `bhumi_id` assignment and retrieval. | **PASS** |
| `tests/test_api.py::test_create_case_and_invalid_state_transition` | API / State Machine | Verifies state machine transition guards (rejects illegal transition from `DRAFT` directly to `FINAL`). | **PASS** |
| `tests/test_api.py::test_document_upload_and_evidence_attachment` | API / Storage | Tests multipart binary document upload, SHA-256 calculation, and vault registration. | **PASS** |
| `tests/test_domain.py::test_competing_claims_coexistence` | Domain Engine | Validates that competing claims (Revenue Khatiyan Owner vs Registered Deed Transferee) coexist without clobbering. | **PASS** |
| `tests/test_domain.py::test_parcel_lineage_subdivision` | Domain Engine | Validates cadastral lineage tracking (parent parcel subdivided into two child parcels). | **PASS** |
| `tests/test_domain.py::test_consistency_service_area_delta` | Consistency Engine | Verifies area delta tolerance evaluation (tolerates <=5%, flags HIGH/CRITICAL if >5%). | **PASS** |
| `tests/test_domain.py::test_consistency_service_mutation_gap` | Consistency Engine | Flags critical defect on unmutated registered deeds and medium defect on delayed mutations. | **PASS** |
| `tests/test_domain.py::test_legal_rule_spt_act_section_20` | Legal Rule Engine | Identifies CRITICAL statutory hazard under Section 20 of Santhal Parganas Tenancy Act for Raiyati ST land in Deoghar. | **PASS** |
| `tests/test_security.py::test_cross_tenant_case_access_denied` | Security | Prohibits User from Tenant A from accessing or mutating Tenant B's case records (`HTTP 403`). | **PASS** |
| `tests/test_security.py::test_cross_tenant_parcel_access_denied` | Security | Prohibits User from Tenant A from viewing Tenant B's parcel records (`HTTP 403`). | **PASS** |
| `tests/test_security.py::test_unauthenticated_request_denied` | Security | Prohibits anonymous unauthenticated requests (`HTTP 401`). | **PASS** |
| `tests/test_vertical_slice.py::test_complete_vertical_slice` | Vertical Slice E2E | Executes the full 12-step lifecycle from tenant creation to verified finding resolution and read-only AI grounding. | **PASS** |

---

## 3. End-to-End Vertical Slice Verification Details

The primary integration test `tests/test_vertical_slice.py::test_complete_vertical_slice` executed and validated the following unbroken chain:

1. **Tenant Provisioned:** Created Organization `Tenant A`.
2. **User Authenticated:** Operator authenticated with JWT token containing `org_id` and role `CASE_OPERATOR`.
3. **Case Created:** Initialized Case `BS-JH-2026-XXXX` in status `DRAFT` with transaction readiness `NOT_READY`.
4. **Parcel Created:** Created Mohanpur Plot 542 with `bhumi_id: JH-DEO-364000-542-XXXX`.
5. **Parcel Linked:** Associated Plot 542 with the Case.
6. **State Transition Guard:** Case successfully transitioned from `DRAFT` to `PROPERTY_IDENTIFIED` (guard verified parcel link presence).
7. **Document Uploaded:** Multipart upload of mock certified Jamabandi Panji II. Computed SHA-256 hash `e3b0c442...` and stored in immutable vault path.
8. **Evidence Created:** Standalone Evidence record created in Evidence Vault with `authority_tier: REVENUE_RECORD`.
9. **Evidence Associated:** Linked Evidence to Case via `CaseEvidence`.
10. **Claim Asserted:** Asserted atomic Claim on Plot 542 (`predicate: RECORDED_OWNER`, `confidence: 0.98`, `status: ACTIVE`).
11. **Finding Generated:** Automated rule flagged CRITICAL finding: `LEGAL_RULE_JH_SPT_SEC_20` (Tribal Raiyati holding subject to statutory transfer prohibition). Status: `OPEN`.
12. **Required Action Created:** Generated task `STATUTORY_CLEARANCE_VERIFICATION` assigned to `LEGAL_ADVOCATE`. Status: `OPEN`.
13. **Finding Resolved:** Fulfill action using certified DC Revenue Permission Order evidence. Finding transitioned to `RESOLVED` and audit log generated.
14. **Grounded AI Land Expert Queried:** Invoked `POST /cases/{case_id}/ai/query` in `MOCK_AI` mode. Verified that the response is grounded in the 6-point evidence contract and canonical data remained strictly unmutated.

---

## 4. Test Execution Command

To execute the test suite in any environment:

```powershell
$env:PYTHONPATH="backend\.venv\Lib\site-packages;backend"
$env:PYTHONIOENCODING="utf-8"
python -m pytest -v
```
