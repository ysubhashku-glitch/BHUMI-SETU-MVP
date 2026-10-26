# BhumiSetu Security & Compliance Architecture

## 1. Document Vault Security
1. **Cryptographic Hashing**: Every ingested document is stamped with its `SHA-256` hash at intake. Hashes are permanently recorded to prevent evidence tampering.
2. **Access Control**: Documents are stored outside the public web root. Access is gated via signed URLs or authenticated Express streams requiring case permission.
3. **No PII Exposure**: Personal contact details of Raiyats and buyers are masked in public preview reports.

## 2. Role-Based Access Control (RBAC) Matrix
| Action | Buyer | Seller | Amin | Lawyer | Admin |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Create Case | YES | YES | NO | NO | YES |
| Upload Deeds | YES | YES | NO | YES | YES |
| Submit GPS Survey | NO | NO | YES | NO | YES |
| Sign-off Legal Opinion | NO | NO | NO | YES | YES |
| Issue Land Passport | NO | NO | NO | NO | YES |

## 3. Auditability
All state modifications generate immutable records in the `audit_logs` table containing `(user_id, action, timestamp, entity_id, diff)`.
