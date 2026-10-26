# BhumiSetu AI Land Expert Architecture

## 1. Principles & Grounding Standard
The AI Land Expert is designed around one supreme rule:
**Evidence First: Source ──► Evidence ──► Structured Data ──► Rules Engine ──► AI Explanation.**
The AI model is forbidden from inventing land rights, legal advice, or unverified claims.

## 2. Retrieval-Augmented Generation (RAG) Schema
Each user query undergoes metadata-filtered retrieval:
1. **Case Filter**: `case_id` restricts search strictly to documents and records of the specific parcel.
2. **Deterministic Pre-Check**: The Rules Engine runs first to verify tenancy acts (SPT/CNT) and boundary variances.
3. **Structured Context Injection**:
   - `recorded_area` vs `measured_area`
   - `extracted_entities` from deeds and Khatiyans
   - `active_risk_findings`
4. **Output Contract (Contract 09)**:
   - `answer`: Clear, concise explanation in English / Hindi.
   - `evidence`: Direct deed clause or Khatiyan page citation.
   - `confidence`: Calculated score (0.0 to 1.0).
   - `uncertainties`: Explicit declaration of missing documents.
   - `recommended_action`: Concrete steps for the buyer/lawyer.
