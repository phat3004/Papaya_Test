# Data Quality & Cleanup Report

## 1. Summary Statistics

- **Total Rows Before Cleaning:** 500
- **Total Rows After Cleaning:** 474
- **Exact Duplicate Rows Removed:** 8
- **Invalid Rows Dropped (Missing ID / Invalid Amount / Unparseable Date):** 18

## 2. Issues Detected and Normalizations Applied

| Issue / Normalization Type | Count of Affected Rows |
|----------------------------|------------------------|
| Duplicate exact rows removed | 8 |
| Duplicate `claim_id` found (but unique content) | 12 |
| Missing `claim_id` (dropped) | 10 |
| Missing `policy_id` (set to empty) | 7 |
| Inconsistent `member_name` casing normalized | 12 |
| `claim_type` typos corrected | 15 |
| Invalid or empty `diagnosis` normalized to null | 14 |
| Invalid amount (negative or zero, dropped) | 8 |
| Currency standardized to uppercase ISO | 9 |
| Date format normalized to ISO 8601 | 14 |

## 3. Cleansed Dataset Analytics

### Claims Count and Average Amount by Type

| Claim Type | Claims Count | Average Submitted Amount |
|------------|--------------|--------------------------|
| DENTAL | 122 | 8,228.69 |
| INPATIENT | 125 | 8,042.40 |
| MATERNITY | 111 | 7,812.61 |
| OUTPATIENT | 116 | 8,358.62 |

### Claims Count by Status

| Status | Claims Count |
|--------|--------------|
| APPROVED | 123 |
| IN_REVIEW | 128 |
| PENDING | 130 |
| REJECTED | 93 |

### Top 5 Most Common Diagnoses

| Rank | Diagnosis | Count |
|------|-----------|-------|
| 1 | Hypertension | 50 |
| 2 | Allergy | 49 |
| 3 | Sprain | 44 |
| 4 | Gastroenteritis | 42 |
| 5 | Asthma | 40 |
