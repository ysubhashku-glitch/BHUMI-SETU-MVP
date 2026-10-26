# 09 - Property Data Model Specification

**Project:** Bhumi Setu  
**Document:** Entity-Relationship Diagram & Database Schema  
**Target RDBMS:** PostgreSQL 16+ with PostGIS Extension (SQLite compatible for local development)  
**Date:** October 24, 2026  

---

## 1. Entity-Relationship Diagram (ERD)

```mermaid
erDiagram
    PARCEL ||--o{ PARCEL_IDENTIFIER : has
    PARCEL ||--o{ DOCUMENT_LINK : contains
    DOCUMENT ||--o{ DOCUMENT_LINK : linked_to
    DOCUMENT ||--o{ DOCUMENT_EXTRACTION : extracts
    PARCEL ||--o{ OWNERSHIP_RECORD : registers
    PARCEL ||--o{ TRANSACTION_EVENT : records
    PARCEL ||--o{ ENCUMBRANCE : bears
    PARCEL ||--o{ DISCREPANCY_FINDING : flags
    DISCREPANCY_FINDING ||--o{ EVIDENCE_LINK : supported_by
    DOCUMENT ||--o{ EVIDENCE_LINK : provides
    PARCEL ||--o{ LANDAMIN_TASK : triggers
    LANDAMIN_TASK ||--o{ FIELD_OBSERVATION : captures
    PARCEL ||--o{ AUDIT_LOG : tracks

    PARCEL {
        uuid id PK
        string canonical_property_id UK
        string state
        string district
        string circle
        string halka
        string mauza
        string khata_no
        string khesra_plot_no
        numeric recorded_area_sqm
        geometry boundary_geom
        string verification_status
        timestamp created_at
    }

    PARCEL_IDENTIFIER {
        uuid id PK
        uuid parcel_id FK
        string identifier_type
        string identifier_value
        string source_authority
    }

    DOCUMENT {
        uuid id PK
        string document_type
        string issuing_authority
        string official_document_no
        date registration_date
        string file_storage_path
        string sha256_checksum
        string source_url
        string retrieval_method
        timestamp retrieved_at
    }

    DOCUMENT_EXTRACTION {
        uuid id PK
        uuid document_id FK
        string extraction_model
        numeric overall_confidence
        jsonb structured_fields
        jsonb bounding_box_coordinates
        timestamp processed_at
    }

    OWNERSHIP_RECORD {
        uuid id PK
        uuid parcel_id FK
        uuid source_document_id FK
        string owner_name
        string father_husband_name
        string relation_type
        numeric share_percentage
        boolean is_current_recorded
    }

    TRANSACTION_EVENT {
        uuid id PK
        uuid parcel_id FK
        uuid deed_document_id FK
        string transaction_type
        date deed_date
        string deed_number
        jsonb transferor_parties
        jsonb transferee_parties
        numeric consideration_amount_inr
    }

    ENCUMBRANCE {
        uuid id PK
        uuid parcel_id FK
        string charge_type
        string lender_claimant_name
        numeric amount_inr
        date registered_date
        uuid source_document_id FK
        uuid release_document_id FK
        string status
    }

    DISCREPANCY_FINDING {
        uuid id PK
        uuid parcel_id FK
        string category
        string severity
        string title
        text description
        string status
        timestamp flagged_at
        timestamp resolved_at
    }

    LANDAMIN_TASK {
        uuid id PK
        uuid parcel_id FK
        uuid discrepancy_id FK
        string assigned_amin_id
        string task_type
        string status
        timestamp scheduled_date
        timestamp completed_date
    }

    FIELD_OBSERVATION {
        uuid id PK
        uuid task_id FK
        geometry gps_coordinates
        jsonb physical_boundary_measurements
        jsonb photograph_urls
        text witness_statements
        timestamp recorded_at
    }

    AUDIT_LOG {
        uuid id PK
        uuid parcel_id FK
        string actor_id
        string action_type
        string request_id
        jsonb payload_diff
        timestamp timestamp
    }
```

---

## 2. Core DDL Schema Definition (PostgreSQL / PostGIS)

```sql
-- Enable PostGIS spatial extension
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Master Parcels Table
CREATE TABLE parcels (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    canonical_property_id VARCHAR(64) UNIQUE NOT NULL, -- e.g., 'BR-PAT-DAN-KOT-KH12-PL45'
    state VARCHAR(50) NOT NULL DEFAULT 'Bihar',
    district VARCHAR(100) NOT NULL,
    circle VARCHAR(100) NOT NULL,
    halka VARCHAR(100),
    mauza VARCHAR(100) NOT NULL,
    khata_no VARCHAR(50) NOT NULL,
    khesra_plot_no VARCHAR(50) NOT NULL,
    recorded_area_sqm NUMERIC(12, 4),
    boundary_geom GEOMETRY(Polygon, 4326),
    verification_status VARCHAR(32) NOT NULL DEFAULT 'UNVERIFIED', -- 'UNVERIFIED', 'PROVISIONAL', 'VERIFIED', 'FLAGGED'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_parcels_location ON parcels(state, district, circle, mauza);
CREATE INDEX idx_parcels_khata_khesra ON parcels(khata_no, khesra_plot_no);
CREATE INDEX idx_parcels_spatial ON parcels USING GIST(boundary_geom);

-- 2. Document Master Ledger
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_type VARCHAR(64) NOT NULL, -- 'JAMABANDI_PANJI2', 'SALE_DEED', 'BHUNAKSHA_MAP', 'EC_FORM15', 'MUTATION_EXTRACT'
    issuing_authority VARCHAR(128) NOT NULL, -- 'Bihar LRC', 'IGRS Bihar', 'Survey Dept'
    official_document_no VARCHAR(128),
    registration_date DATE,
    file_storage_path TEXT NOT NULL,
    sha256_checksum CHAR(64) NOT NULL,
    source_url TEXT,
    retrieval_method VARCHAR(32) NOT NULL, -- 'DIGITAL_SOURCE', 'SRO_COUNTER_AMN', 'USER_UPLOAD'
    retrieved_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_documents_checksum ON documents(sha256_checksum);

-- 3. Document Extractions & Bounding Boxes
CREATE TABLE document_extractions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    extraction_model VARCHAR(64) NOT NULL,
    overall_confidence NUMERIC(5, 2) NOT NULL,
    structured_fields JSONB NOT NULL,
    bounding_box_coordinates JSONB NOT NULL,
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. Discrepancies and Findings
CREATE TABLE discrepancy_findings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    parcel_id UUID NOT NULL REFERENCES parcels(id) ON DELETE CASCADE,
    category VARCHAR(64) NOT NULL, -- 'NAME_VARIANCE', 'AREA_MISMATCH', 'UNRELEASED_MORTGAGE', 'BROKEN_CHAIN', 'BOUNDARY_CONFLICT'
    severity VARCHAR(16) NOT NULL, -- 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    evidence_document_ids UUID[] DEFAULT '{}',
    status VARCHAR(32) NOT NULL DEFAULT 'OPEN', -- 'OPEN', 'AMN_VERIFICATION_PENDING', 'ADVOCATE_REVIEW', 'RESOLVED'
    resolution_notes TEXT,
    flagged_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_findings_parcel ON discrepancy_findings(parcel_id);

-- 5. LandAmin Tasks & Field Observations
CREATE TABLE landamin_tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    parcel_id UUID NOT NULL REFERENCES parcels(id) ON DELETE CASCADE,
    discrepancy_id UUID REFERENCES discrepancy_findings(id) ON DELETE SET NULL,
    assigned_amin_id VARCHAR(64) NOT NULL,
    task_type VARCHAR(64) NOT NULL, -- 'BOUNDARY_DEMARCATION', 'POSSESSION_INSPECTION', 'PANCHNAMA_COLLECTION'
    status VARCHAR(32) NOT NULL DEFAULT 'ASSIGNED', -- 'ASSIGNED', 'IN_PROGRESS', 'SUBMITTED', 'VERIFIED'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE field_observations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id UUID NOT NULL REFERENCES landamin_tasks(id) ON DELETE CASCADE,
    gps_coordinates GEOMETRY(Point, 4326),
    physical_measurements JSONB NOT NULL,
    photo_urls TEXT[] DEFAULT '{}',
    witness_notes TEXT,
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```
