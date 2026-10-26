# BhumiSetu External Integrations & Data Source Registry

## 1. Governance Rules
In accordance with Rule 4 ("No Hallucinated Infrastructure") and Contract 05 ("Data Source Contract"), external government sources are labeled explicitly by their actual connectivity state:
- `CONNECTED`: Active production API / automated connector.
- `NOT_CONNECTED`: Source identified and schema modeled, but live integration deferred to Phase 2.
- `MOCK`: Development test fixtures simulating realistic edge cases.

## 2. Source Inventory

### Source 01: Jharbhoomi (Jharkhand Land Records)
- **Authority**: Department of Revenue, Registration & Land Reforms, Govt. of Jharkhand.
- **Geography**: Jharkhand (All 24 Districts).
- **Official URL**: `https://jharbhoomi.jharkhand.gov.in/`
- **Source Type**: State Revenue Web Portal.
- **Access Method**: HTTP Form Post / Session Cookie Emulation.
- **Data Provided**: Register II (Jamabandi), Khatian details, Lagan payment status.
- **Status in Dev**: `NOT_CONNECTED` (Mocked in `src/services/mockData.ts`).
- **Known Limitations**: Frequent downtime, Devanagari image CAPTCHA, unindexed legacy tenants.

### Source 02: Jhar-Nibandhan (Jharkhand Deed Registry)
- **Authority**: Department of Registration, Govt. of Jharkhand.
- **Geography**: Jharkhand SROs.
- **Official URL**: `https://jharnibandhan.jharkhand.gov.in/`
- **Data Provided**: Registered Sale Deeds, Encumbrance Certificates (EC).
- **Status in Dev**: `NOT_CONNECTED`.

### Source 03: eCourts Services (NJDG)
- **Authority**: e-Committee, Supreme Court of India.
- **Official URL**: `https://services.ecourts.gov.in/`
- **Data Provided**: Civil suits, partition suits, title disputes.
- **Status in Dev**: `NOT_CONNECTED`.

### Source 04: BhumiSetu Field Amin PWA
- **Authority**: Certified Private & Empaneled Amins.
- **Access Method**: Native Mobile Geolocation API (HTML5 / W3C GPS).
- **Data Provided**: RTK-GPS corner boundary pins ($P_1..P_n$), boundary ridge (*aal*) photos, neighbor interviews.
- **Status**: `CONNECTED`.
