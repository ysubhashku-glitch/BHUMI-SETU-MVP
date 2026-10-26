# BhumiSetu REST API Specification (v1.0)

All endpoints are versioned under `/api/v1`.

## Endpoints Summary

### 1. Case Management
- `GET /api/v1/cases`
  - Returns list of property cases with status, SLA timers, and trust scores.
- `POST /api/v1/cases`
  - Creates a new due diligence case for a parcel.
  - Body: `{ bhumi_id, buyer_objective, client_notes }`
- `GET /api/v1/cases/:id`
  - Returns single case detail with parcel, documents, and 6-realities matrix.
- `GET /api/v1/cases/:id/passport`
  - Returns the official Land Passport data object.
- `GET /api/v1/cases/:id/report`
  - Returns the formatted Markdown / HTML Land Intelligence Report.

### 2. Document Vault
- `GET /api/v1/cases/:id/documents`
  - Returns all documents attached to a case with SHA-256 hashes and OCR entities.
- `POST /api/v1/cases/:id/documents`
  - Ingests a new document (Deed, Khatiyan, Mutation Order) with file hash and metadata.

### 3. Field Survey & Verification
- `POST /api/v1/cases/:id/verify-field`
  - Ingests field Amin survey data: corner pins, measured area, road access width, and possession holder.
  - Automatically triggers Area Delta ($\Delta_{\text{area}}\%$) calculation.

### 4. AI Land Expert (Grounded RAG)
- `POST /api/v1/ai/query`
  - Body: `{ case_id, question }`
  - Returns: Structured answer strictly grounded in case documents, citations, confidence score, and recommended verification steps.

### 5. Spatial GIS & Tools
- `POST /api/v1/spatial/calculate-polygon`
  - Body: `{ coordinates: [[lat, lng], ...] }`
  - Returns: Shoelace geodesic area in Sq.Ft, Acres, Kathas, and Dhurs.
- `GET /api/v1/spatial/convert-units`
  - Query: `?amount=2.4&from=acre&to=katha`
  - Returns exact converted quantities.
