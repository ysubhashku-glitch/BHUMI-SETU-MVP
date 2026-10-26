# BHUMI SETU — PHASE 3 EXTRACTION SCHEMA SPECIFICATION

## Overview
This specification details the standardized extracted field schemas across the 5 primary Indian land record document types handled by the BhumiSetu pipeline.

---

## 1. Registered Sale Deed Schema (`REGISTERED_SALE_DEED`)
- **Category Code:** `REGISTERED_SALE_DEED`
- **Vernacular Terms:** विक्रय विलेख, केवाला, बयनामा

| Field Key | Data Type | Description | Example Value |
| :--- | :--- | :--- | :--- |
| `deed_number` | String | Sub-Registrar registered deed / document number | `"4521/2021"` |
| `registration_date` | Date (YYYY-MM-DD) | Date of formal execution / registration | `"2021-04-14"` |
| `deed_year` | Integer | Year of registration | `2021` |
| `consideration_amount` | Float / Decimal | Total financial consideration in INR | `1250000.00` |
| `stamp_duty` | Float / Decimal | Stamp duty paid in INR | `75000.00` |
| `seller_name` | String | Full name of transferor/seller | `"Ram Kumar Verma"` |
| `seller_parentage` | String | Parentage/spouse of seller | `"Late Harihar Verma"` |
| `buyer_name` | String | Full name of transferee/buyer | `"Anupama Devi"` |
| `buyer_parentage` | String | Parentage/spouse of buyer | `"W/o Rajesh Kumar"` |
| `district` | String | District administrative division | `"Deoghar"` |
| `sub_registrar_office` | String | Registration jurisdiction | `"Sub-Registrar Office, Deoghar"` |
| `circle` | String | Revenue circle / block | `"Mohanpur"` |
| `mauza` | String | Village / Mauza name | `"Jasidih"` |
| `thana_number` | String / Integer | Thana jurisdiction code | `"42"` |
| `khata_number` | String | Khata / Holding account number | `"42"` |
| `plot_number` | String | Khesra / Plot number | `"112/A"` |
| `area_raw` | String | Raw text representation of area | `"0.25 Acre"` |
| `area_sqm` | Float | Canonical normalized area in square meters | `1011.71` |
| `boundary_north` | String | Bounded neighbour on the North | `"Ramesh Sharma"` |
| `boundary_south` | String | Bounded neighbour on the South | `"Road"` |
| `boundary_east` | String | Bounded neighbour on the East | `"Plot 112/B"` |
| `boundary_west` | String | Bounded neighbour on the West | `"Govind Prasad"` |

---

## 2. Record of Rights / Khatiyan Schema (`KHATIYAN`)
- **Category Code:** `RECORD_OF_RIGHTS`
- **Vernacular Terms:** खतियान, अधिकार अभिलेख, CS/RS/Survey Khatiyan

| Field Key | Data Type | Description | Example Value |
| :--- | :--- | :--- | :--- |
| `khata_number` | String | Record of Rights holding number | `"42"` |
| `raiyat_name` | String | Recorded tenant name | `"Shyam Sundar Verma"` |
| `raiyat_parentage` | String | Father / Husband name | `"Gokul Verma"` |
| `caste_community` | String | Recorded social category (vital for SPT/CNT check)| `"General (Kayastha)"` |
| `survey_type` | String | Cadastral (CS), Revisional (RS), or Settlement | `"Revisional Survey (RS)"` |
| `total_plots` | Integer | Total count of plots recorded under Khata | `2` |
| `total_area_sqm` | Float | Sum of normalized area in sqm | `2832.79` |
| `annual_rent_lagan` | Float | Total fixed annual land revenue demand | `17.50` |
| `plots` | Array[Object] | Child plot records (plot_no, nature, area, rent) | `[{"plot_no": "112/A", "nature": "Dhani 2", "area_sqm": 2023.43}]` |

---

## 3. Jamabandi Register / Register II Schema (`JAMABANDI`)
- **Category Code:** `JAMABANDI_REGISTER`
- **Vernacular Terms:** पंजी II, रजिस्टर २, जमाबंदी पंजी

| Field Key | Data Type | Description | Example Value |
| :--- | :--- | :--- | :--- |
| `jamabandi_number` | String | Unique Jamabandi register entry ID | `"108"` |
| `halka_number` | String | Revenue sub-division code | `"04"` |
| `mauza` | String | Village jurisdiction name | `"Jasidih"` |
| `khata_number` | String | Cross-referenced Khata number | `"42"` |
| `plot_number` | String | Plot number | `"112/A"` |
| `tenant_name` | String | Current recorded tenant on Jamabandi | `"Ram Kumar Verma"` |
| `total_demand` | Float | Current land revenue + cess demand | `18.00` |
| `status` | String | Tax payment currency / demand status | `"Up to date (2025-2026)"` |
| `mutation_reference`| String | Reference to case creating the Jamabandi | `"Dakhil Kharij Case No. 89/2021-22"` |

---

## 4. Mutation Record / Dakhil Kharij Schema (`MUTATION_RECORD`)
- **Category Code:** `MUTATION_RECORD`
- **Vernacular Terms:** दाखिल खारिज, शुद्धि पत्र, शुद्धि पर्ची

| Field Key | Data Type | Description | Example Value |
| :--- | :--- | :--- | :--- |
| `case_number` | String | Revenue circle court mutation case number | `"89/2021-22"` |
| `order_date` | Date (YYYY-MM-DD) | Date of circle officer approval order | `"2021-06-28"` |
| `circle_office` | String | Issuing circle office | `"Mohanpur"` |
| `transferor` | String | Former owner removed from Jamabandi | `"Ram Kumar Verma"` |
| `transferee` | String | New owner entered onto Jamabandi | `"Anupama Devi"` |
| `deed_reference` | String | Deed grounding the mutation | `"Registered Deed No. 4521/2021"` |
| `mutated_area_sqm` | Float | Area transferred in square meters | `1011.71` |
| `order_status` | String | Legal status of mutation order | `"APPROVED / SANCTIONED"` |

---

## 5. Encumbrance Certificate Schema (`ENCUMBRANCE_CERTIFICATE`)
- **Category Code:** `ENCUMBRANCE_CERTIFICATE`
- **Vernacular Terms:** भारमुक्त प्रमाण पत्र, भार प्रमाण पत्र, ईसी (EC)

| Field Key | Data Type | Description | Example Value |
| :--- | :--- | :--- | :--- |
| `registration_sub_district` | String | Sub-registry authority issuing search | `"Deoghar"` |
| `search_period_start` | Date (YYYY-MM-DD) | Start date of inspection window | `"2010-01-01"` |
| `search_period_end` | Date (YYYY-MM-DD) | End date of inspection window | `"2025-12-31"` |
| `property_description`| String | Summary description of inspected property | `"Khata 42, Plot 112/A, Jasidih"` |
| `transactions_count` | Integer | Total registered transactions found in window | `1` |
| `encumbrance_status` | String | `NIL_ENCUMBRANCE` or `ENCUMBERED` | `"NIL_ENCUMBRANCE"` |
