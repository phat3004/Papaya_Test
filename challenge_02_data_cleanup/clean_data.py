import csv
import re
from datetime import datetime

def parse_date(date_str):
    if not date_str:
        return None
    date_str = date_str.strip()
    
    # Try YYYY-MM-DD
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%B %d, %Y"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None

def parse_amount(amount_val):
    if amount_val is None or amount_val == "":
        return None
    
    if isinstance(amount_val, (int, float)):
        return float(amount_val)
        
    val_str = str(amount_val).strip().replace(",", "")
    try:
        return float(val_str)
    except ValueError:
        return None

def clean_claim_type(ct_str):
    if not ct_str:
        return None
    ct = ct_str.strip().upper()
    if ct in ("OUTPATIENT", "OUTPATEINT", "OP"):
        return "OUTPATIENT"
    if ct in ("INPATIENT", "IP"):
        return "INPATIENT"
    if ct in ("DENTAL",):
        return "DENTAL"
    if ct in ("MATERNITY", "MATERNITY CARE", "MATERNITY"):
        return "MATERNITY"
    return ct

def clean_currency(curr_str):
    if not curr_str:
        return None
    c = curr_str.strip().upper()
    if c in ("THB", "BAHT"):
        return "THB"
    if c in ("VND",):
        return "VND"
    return c

def clean_data():
    input_file = "dirty_claims.csv"
    output_file = "clean_claims.csv"
    report_file = "report.md"
    
    # Read rows
    raw_rows = []
    with open(input_file, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            raw_rows.append(r)
            
    total_raw_rows = len(raw_rows)
    
    # Metrics counters
    exact_duplicates_removed = 0
    missing_claim_id_count = 0
    missing_policy_id_count = 0
    casing_issues_count = 0
    typo_claim_type_count = 0
    null_diagnosis_count = 0
    invalid_amount_count = 0
    currency_standardized_count = 0
    date_formatted_count = 0
    
    # Set to track exact duplicates
    seen_exact_rows = set()
    unique_raw_rows = []
    
    for row in raw_rows:
        # Convert row dict to a hashable tuple of values
        row_tuple = tuple(row.items())
        if row_tuple in seen_exact_rows:
            exact_duplicates_removed += 1
        else:
            seen_exact_rows.add(row_tuple)
            unique_raw_rows.append(row)
            
    cleaned_rows = []
    dropped_invalid_rows = 0
    
    # To track claim_id uniqueness
    seen_claim_ids = set()
    duplicate_claim_id_issue_count = 0
    
    for row in unique_raw_rows:
        has_issue = False
        
        # 1. Check claim_id
        c_id = row["claim_id"].strip()
        if not c_id:
            missing_claim_id_count += 1
            has_issue = True
            # Drop rows with missing claim ID
            dropped_invalid_rows += 1
            continue
            
        if c_id in seen_claim_ids:
            duplicate_claim_id_issue_count += 1
            # We keep it but flag it or we can let it be (the prompt says: "claim_id: string - Some missing, some duplicated")
            # In real system, duplicate claim IDs are invalid. We will append a suffix to make it unique or keep it.
            # Let's keep it but track it.
        seen_claim_ids.add(c_id)
        
        # 2. Check policy_id
        p_id = row["policy_id"].strip()
        if not p_id:
            missing_policy_id_count += 1
            # Keep the row but leave policy_id as empty (null)
            p_id = ""
            
        # 3. Clean member_name casing
        name = row["member_name"].strip()
        if name:
            if name != name.title():
                casing_issues_count += 1
                name = name.title()
                
        # 4. Clean claim_type and check typos
        raw_ct = row["claim_type"]
        cleaned_ct = clean_claim_type(raw_ct)
        if cleaned_ct != raw_ct:
            typo_claim_type_count += 1
            
        # 5. Clean diagnosis and check nulls
        diag = row["diagnosis"].strip()
        if diag.lower() in ("", "n/a", "none"):
            null_diagnosis_count += 1
            diag = ""  # Normalize to empty string (null marker)
            
        # 6. Clean amount
        raw_amt = row["submitted_amount"]
        parsed_amt = parse_amount(raw_amt)
        
        # If amount is string with commas, check if it was converted correctly
        if parsed_amt is not None and "," in str(raw_amt):
            # Commas were removed and parsed, this is a minor data correction
            pass
            
        if parsed_amt is None or parsed_amt <= 0:
            invalid_amount_count += 1
            # Drop invalid amounts
            dropped_invalid_rows += 1
            continue
            
        # 7. Clean currency
        raw_curr = row["currency"]
        cleaned_curr = clean_currency(raw_curr)
        if cleaned_curr != raw_curr:
            currency_standardized_count += 1
            
        # 8. Clean date format
        raw_date = row["submitted_date"]
        cleaned_date = parse_date(raw_date)
        if cleaned_date != raw_date:
            date_formatted_count += 1
            
        if not cleaned_date:
            # If date couldn't be parsed, it's invalid
            dropped_invalid_rows += 1
            continue
            
        cleaned_row = {
            "claim_id": c_id,
            "policy_id": p_id,
            "member_name": name,
            "claim_type": cleaned_ct,
            "diagnosis": diag,
            "submitted_amount": parsed_amt,
            "currency": cleaned_curr,
            "submitted_date": cleaned_date,
            "status": row["status"].strip().upper()
        }
        cleaned_rows.append(cleaned_row)

    # Write to clean_claims.csv
    fieldnames = ["claim_id", "policy_id", "member_name", "claim_type", "diagnosis", "submitted_amount", "currency", "submitted_date", "status"]
    with open(output_file, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in cleaned_rows:
            writer.writerow(row)
            
    # Calculate statistics for the report
    total_clean_rows = len(cleaned_rows)
    
    # Claims by Type
    claims_by_type = {}
    total_amount_by_type = {}
    for r in cleaned_rows:
        ct = r["claim_type"]
        amt = r["submitted_amount"]
        claims_by_type[ct] = claims_by_type.get(ct, 0) + 1
        total_amount_by_type[ct] = total_amount_by_type.get(ct, 0.0) + amt
        
    avg_amount_by_type = {}
    for ct, count in claims_by_type.items():
        avg_amount_by_type[ct] = total_amount_by_type[ct] / count
        
    # Claims by Status
    claims_by_status = {}
    for r in cleaned_rows:
        st = r["status"]
        claims_by_status[st] = claims_by_status.get(st, 0) + 1
        
    # Top 5 Diagnoses
    diagnoses_counts = {}
    for r in cleaned_rows:
        d = r["diagnosis"]
        if d:  # Only count non-empty diagnoses
            diagnoses_counts[d] = diagnoses_counts.get(d, 0) + 1
            
    sorted_diagnoses = sorted(diagnoses_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    
    # Write report.md
    with open(report_file, mode="w", encoding="utf-8") as f:
        f.write("# Data Quality & Cleanup Report\n\n")
        f.write("## 1. Summary Statistics\n\n")
        f.write(f"- **Total Rows Before Cleaning:** {total_raw_rows}\n")
        f.write(f"- **Total Rows After Cleaning:** {total_clean_rows}\n")
        f.write(f"- **Exact Duplicate Rows Removed:** {exact_duplicates_removed}\n")
        f.write(f"- **Invalid Rows Dropped (Missing ID / Invalid Amount / Unparseable Date):** {dropped_invalid_rows}\n\n")
        
        f.write("## 2. Issues Detected and Normalizations Applied\n\n")
        f.write("| Issue / Normalization Type | Count of Affected Rows |\n")
        f.write("|----------------------------|------------------------|\n")
        f.write(f"| Duplicate exact rows removed | {exact_duplicates_removed} |\n")
        f.write(f"| Duplicate `claim_id` found (but unique content) | {duplicate_claim_id_issue_count} |\n")
        f.write(f"| Missing `claim_id` (dropped) | {missing_claim_id_count} |\n")
        f.write(f"| Missing `policy_id` (set to empty) | {missing_policy_id_count} |\n")
        f.write(f"| Inconsistent `member_name` casing normalized | {casing_issues_count} |\n")
        f.write(f"| `claim_type` typos corrected | {typo_claim_type_count} |\n")
        f.write(f"| Invalid or empty `diagnosis` normalized to null | {null_diagnosis_count} |\n")
        f.write(f"| Invalid amount (negative or zero, dropped) | {invalid_amount_count} |\n")
        f.write(f"| Currency standardized to uppercase ISO | {currency_standardized_count} |\n")
        f.write(f"| Date format normalized to ISO 8601 | {date_formatted_count} |\n\n")
        
        f.write("## 3. Cleansed Dataset Analytics\n\n")
        
        f.write("### Claims Count and Average Amount by Type\n\n")
        f.write("| Claim Type | Claims Count | Average Submitted Amount |\n")
        f.write("|------------|--------------|--------------------------|\n")
        for ct in sorted(claims_by_type.keys()):
            f.write(f"| {ct} | {claims_by_type[ct]} | {avg_amount_by_type[ct]:,.2f} |\n")
        f.write("\n")
        
        f.write("### Claims Count by Status\n\n")
        f.write("| Status | Claims Count |\n")
        f.write("|--------|--------------|\n")
        for st in sorted(claims_by_status.keys()):
            f.write(f"| {st} | {claims_by_status[st]} |\n")
        f.write("\n")
        
        f.write("### Top 5 Most Common Diagnoses\n\n")
        f.write("| Rank | Diagnosis | Count |\n")
        f.write("|------|-----------|-------|\n")
        for idx, (diag_name, count) in enumerate(sorted_diagnoses, 1):
            f.write(f"| {idx} | {diag_name} | {count} |\n")
            
    print(f"Cleaned CSV output generated in '{output_file}'.")
    print(f"Data quality report written to '{report_file}'.")

if __name__ == "__main__":
    clean_data()
