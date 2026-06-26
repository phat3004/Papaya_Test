import csv
import random
from datetime import datetime, timedelta

def generate_messy_claims():
    random.seed(42)  # For reproducibility

    first_names = ["John", "Jane", "Alice", "Bob", "Charlie", "Diana", "Ethan", "Fiona", "George", "Hannah", "David", "Linda", "Sarah", "Michael", "James"]
    last_names = ["Doe", "Smith", "Johnson", "Brown", "Taylor", "Miller", "Davis", "Garcia", "Rodriguez", "Wilson", "Jones", "Williams", "Davis"]
    diagnoses = ["Flu", "Acute bronchitis", "Hypertension", "Dental caries", "Pregnancy checkup", "Migraine", "Gastroenteritis", "Food poisoning", "Asthma", "Allergy", "Sprain", "Fever"]
    statuses = ["APPROVED", "REJECTED", "PENDING", "IN_REVIEW"]
    
    # Generate 500 claims
    claims = []
    
    # Track some clean IDs to intentionally introduce duplicates
    generated_ids = []
    
    for i in range(1, 481):  # Generate 480 base claims, and we'll add duplicates to reach 500
        claim_num = f"{i:05d}"
        claim_id = f"CLM-{claim_num}"
        policy_id = f"POL-{random.randint(100, 999)}"
        
        member_name = f"{random.choice(first_names)} {random.choice(last_names)}"
        claim_type = random.choice(["OUTPATIENT", "INPATIENT", "DENTAL", "MATERNITY"])
        diagnosis = random.choice(diagnoses)
        submitted_amount = float(random.randint(10, 150)) * 100
        currency = random.choice(["THB", "VND"])
        
        # Base date
        days_offset = random.randint(0, 360)
        base_date = datetime(2024, 1, 1) + timedelta(days=days_offset)
        submitted_date = base_date.strftime("%Y-%m-%d")
        
        status = random.choice(statuses)
        
        # Determine if we should introduce a data quality issue in this row
        # (Targeting 15-20% total rows with issues)
        issue_prob = random.random()
        
        if issue_prob < 0.20:
            issue_type = random.choice([
                "missing_claim_id",
                "missing_policy_id",
                "casing_name",
                "claim_type_typo",
                "diagnosis_null",
                "invalid_amount",
                "currency_format",
                "date_format"
            ])
            
            if issue_type == "missing_claim_id":
                claim_id = ""
            elif issue_type == "missing_policy_id":
                policy_id = ""
            elif issue_type == "casing_name":
                casing_choice = random.choice(["upper", "lower"])
                if casing_choice == "upper":
                    member_name = member_name.upper()
                else:
                    member_name = member_name.lower()
            elif issue_type == "claim_type_typo":
                # OUTPATIENT typos: "outpatient", "Outpateint", "OP"
                claim_type = random.choice(["outpatient", "Outpateint", "OP", "dental", "Inpatient", "MATERnity"])
            elif issue_type == "diagnosis_null":
                diagnosis = random.choice(["", "N/A", "n/a", "none"])
            elif issue_type == "invalid_amount":
                # negative, zero, or string with commas
                amount_choice = random.choice(["negative", "zero", "string_comma"])
                if amount_choice == "negative":
                    submitted_amount = -submitted_amount
                elif amount_choice == "zero":
                    submitted_amount = 0.0
                else:
                    # formatted as string with comma e.g. "15,000"
                    submitted_amount = f"{int(submitted_amount):,}"
            elif issue_type == "currency_format":
                currency = random.choice(["thb", "Baht", "vnd"])
            elif issue_type == "date_format":
                date_choice = random.choice(["slash", "text"])
                if date_choice == "slash":
                    # DD/MM/YYYY
                    submitted_date = base_date.strftime("%d/%m/%Y")
                else:
                    # Month DD, YYYY
                    submitted_date = base_date.strftime("%B %d, %Y")
        
        claim_row = {
            "claim_id": claim_id,
            "policy_id": policy_id,
            "member_name": member_name,
            "claim_type": claim_type,
            "diagnosis": diagnosis,
            "submitted_amount": submitted_amount,
            "currency": currency,
            "submitted_date": submitted_date,
            "status": status
        }
        claims.append(claim_row)
        
        if claim_id: # Keep valid IDs to duplicate
            generated_ids.append(claim_row)

    # Now add 20 duplicates or exact clones to reach 500 rows
    for _ in range(20):
        # 10 exact duplicate rows
        if random.random() < 0.5 and generated_ids:
            dup_row = random.choice(generated_ids).copy()
            claims.append(dup_row)
        else:
            # 10 duplicate claim_id but different other values (meaning duplicate claim_id issue)
            if generated_ids:
                dup_base = random.choice(generated_ids)
                dup_row = dup_base.copy()
                # change amount and diagnosis
                dup_row["submitted_amount"] = float(random.randint(50, 200)) * 100
                dup_row["diagnosis"] = random.choice(diagnoses)
                claims.append(dup_row)

    # Shuffle claims to distribute issues
    random.shuffle(claims)
    
    # Write to dirty_claims.csv
    fieldnames = ["claim_id", "policy_id", "member_name", "claim_type", "diagnosis", "submitted_amount", "currency", "submitted_date", "status"]
    
    with open("dirty_claims.csv", mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in claims:
            writer.writerow(row)
            
    print("Generated 500 claims in 'dirty_claims.csv' with intentional data quality issues.")

if __name__ == "__main__":
    generate_messy_claims()
