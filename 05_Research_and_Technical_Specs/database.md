# BhumiSetu Database Specification & Schema Architecture

## 1. Overview
BhumiSetu uses a normalized relational architecture powered by **PostgreSQL 16** with the **PostGIS 3.4** extension for geospatial parcel geometries.

## 2. Entity-Relationship Model

```text
ORGANIZATIONS (id, name, type)
      │
      ├──< USERS (id, org_id, name, email, phone, role)
             │
             ├──< PROPERTY_CASES (id, case_number, parcel_id, client_id, assigned_amin_id, status, trust_score)
                    │
                    ├──< CASE_DOCUMENTS (id, case_id, doc_type, file_path, file_hash_sha256, provenance)
                    │         │
                    │         └──< DOCUMENT_EXTRACTIONS (id, document_id, field_name, value, confidence, page)
                    │
                    ├──< FIELD_VERIFICATIONS (id, case_id, amin_id, measured_area_sqft, area_delta_percent)
                    │         │
                    │         └──< SURVEY_PINS (id, verification_id, label, coordinate, accuracy_m)
                    │
                    ├──< RISK_FINDINGS (id, case_id, dimension, rule_code, severity, penalty, observed, expected)
                    │
                    └──< AUDIT_LOGS (id, case_id, user_id, action, entity_type, payload_diff)

PARCELS (id, bhumi_id, state, district, block_circle, village_mouza, plot_no, khata_no, recorded_area_sqft)
      │
      ├──< PARCEL_GEOMETRIES (id, parcel_id, geometry_type, boundary, centroid, source_provenance)
      └──< OWNERSHIP_CHAIN (id, parcel_id, person_id, deed_id, transfer_year, share_fraction)
```

## 3. Data Provenance & Confidence Standard
Every row in `parcels`, `documents`, and `risk_findings` must maintain:
- `source_id`: Reference to external source registry (`JHARBHOOMI`, `FIELD_SURVEY`, `USER_UPLOAD`).
- `provenance_type`: `OFFICIAL_SOURCE` | `LICENSED_SOURCE` | `USER_DOCUMENT` | `FIELD_VERIFICATION` | `EXPERT_REVIEW` | `DERIVED` | `AI_INFERENCE`.
- `confidence_score`: Float between `0.00` and `1.00`.
- `verification_status`: `UNVERIFIED` | `PENDING_AUDIT` | `HUMAN_VERIFIED` | `DISCREPANCY_FLAGGED`.

## 4. Multi-Tenant Isolation
Tenant isolation is enforced via `org_id` on the `users` and `property_cases` tables. All queries to `property_cases` must apply a tenant filter:
`WHERE org_id = :current_user_org_id OR :current_user_role = 'ADMIN'`

## 5. Storage Engine
- Development: Persistent JSON/SQLite file store with ACID write-ahead logging.
- Production: AWS RDS PostgreSQL 16 with Multi-AZ replication and PostGIS enabled.
