import csv
import random
import math
from datetime import datetime, timedelta

def generate_fraud_dataset():
    random.seed(123)  # For reproducibility
    
    # 500 members
    members = [f"MEM-{i:03d}" for i in range(1, 501)]
    
    # 50 providers (including 5 suspect/anomaly providers)
    providers = []
    for i in range(1, 51):
        p_id = f"PROV-{i:02d}"
        if i <= 5:
            p_name = f"Suspect Health Clinic {i}"
        else:
            p_name = f"General Care Hospital {i}"
        providers.append((p_id, p_name))
        
    diagnoses = [
        ("I10", "Essential Hypertension"),
        ("K21", "GERD"),
        ("K02", "Dental caries"),
        ("J06", "Acute URI"),
        ("K35", "Acute appendicitis"),
        ("Z34", "Normal pregnancy"),
        ("M17", "Knee Osteoarthritis"),
        ("H25", "Senile cataract"),
        ("G43", "Migraine"),
        ("E11", "Type 2 diabetes")
    ]
    
    # Standard procedure pricing stats (mean, std_dev)
    proc_stats = {
        "P001": {"name": "General Consultation", "mean": 1500, "std": 300},
        "P002": {"name": "Basic Cleaning", "mean": 2000, "std": 400},
        "P003": {"name": "Blood Panel Lab Test", "mean": 3000, "std": 500},
        "P004": {"name": "MRI Scan", "mean": 15000, "std": 2000},
        "P005": {"name": "Root Canal", "mean": 12000, "std": 1500},
        "P006": {"name": "Appendix Surgery", "mean": 80000, "std": 10000},
        "P007": {"name": "Room & Board Inpatient", "mean": 6000, "std": 800},
        "P008": {"name": "Prenatal Ultrasound", "mean": 4000, "std": 600},
        "P009": {"name": "Physical Therapy", "mean": 2500, "std": 400},
        "P010": {"name": "Cataract Surgery", "mean": 40000, "std": 5000}
    }
    
    claims = []
    
    # Helper to generate normal claim amounts
    def get_normal_amount(proc_code):
        stats = proc_stats[proc_code]
        return round(random.normalvariate(stats["mean"], stats["std"]), 2)

    # 1. Generate 1,800 Clean Claims
    # We must ensure normal claims don't trigger anomalies by accident
    for i in range(1, 1801):
        claim_id = f"CLM-CLEAN-{i:04d}"
        member = random.choice(members)
        
        # Pick provider (PROV-01 is index 0 for phantom billing, PROV-02 is index 1 for weekend surgery anomaly)
        # We allow PROV-02 to have normal weekday claims in the clean dataset.
        if random.random() < 0.05:
            prov_idx = 1  # PROV-02
        else:
            prov_idx = random.randint(2, 49)  # Exclude PROV-01 (index 0)
        p_id, p_name = providers[prov_idx]
        
        # Date: not weekend for outpatient/dental, surgery only on weekdays mostly
        days_offset = random.randint(0, 360)
        claim_date = datetime(2024, 1, 1) + timedelta(days=days_offset)
        
        # Force weekday for PROV-02 and check standard weekend adjustment
        if prov_idx == 1 or claim_date.weekday() >= 5:
            if claim_date.weekday() == 5:
                claim_date -= timedelta(days=1)
            elif claim_date.weekday() == 6:
                claim_date += timedelta(days=1)
            
        diag_code, diag_name = random.choice(diagnoses)
        
        # Pick matching procedure
        if diag_code == "I10":
            proc = "P001"
        elif diag_code == "K21":
            proc = random.choice(["P001", "P003"])
        elif diag_code == "K02":
            proc = random.choice(["P002", "P005"])
        elif diag_code == "J06":
            proc = "P001"
        elif diag_code == "K35":
            proc = random.choice(["P006", "P007"])
        elif diag_code == "Z34":
            proc = "P008"
        elif diag_code == "M17":
            proc = "P009"
        elif diag_code == "H25":
            proc = "P010"
        elif diag_code == "G43":
            proc = random.choice(["P001", "P004"])
        else: # E11
            proc = random.choice(["P001", "P003"])
            
        amount = get_normal_amount(proc)
        
        # Ensure amount is not close to auto-approval threshold of 50,000 (unless it's surgery which is higher, or other which is lower)
        # 47,500 to 49,999 is threshold. Let's make sure normal amounts avoid this.
        if 47000 <= amount <= 50500:
            amount -= 4000
            
        claims.append({
            "claim_id": claim_id,
            "member_id": member,
            "provider_id": p_id,
            "provider_name": p_name,
            "claim_date": claim_date.strftime("%Y-%m-%d"),
            "claim_type": "INPATIENT" if proc in ("P006", "P007", "P010") else ("DENTAL" if proc in ("P002", "P005") else "OUTPATIENT"),
            "diagnosis_code": diag_code,
            "procedure_codes": proc,
            "submitted_amount": amount,
            "is_weekend": claim_date.weekday() >= 5,
            "is_fraud": "False",
            "fraud_type": "NONE"
        })

    # Keep track of generated claims index to embed fraud
    fraud_counter = 1
    
    # 2. Fraud Pattern 1: Duplicate claims (30 claims - 15 pairs)
    # Same member, provider, date, diagnosis, amount
    for _ in range(15):
        # Pick a clean claim and clone it
        base_claim = random.choice(claims)
        
        dup_claim1 = base_claim.copy()
        dup_claim1["claim_id"] = f"CLM-FRD-{fraud_counter:04d}"
        dup_claim1["is_fraud"] = "True"
        dup_claim1["fraud_type"] = "DUPLICATE"
        claims.append(dup_claim1)
        fraud_counter += 1
        
        dup_claim2 = base_claim.copy()
        dup_claim2["claim_id"] = f"CLM-FRD-{fraud_counter:04d}"
        dup_claim2["is_fraud"] = "True"
        dup_claim2["fraud_type"] = "DUPLICATE"
        claims.append(dup_claim2)
        fraud_counter += 1

    # 3. Fraud Pattern 2: Rapid re-submission (30 claims - 15 pairs)
    # Same member, same diagnosis, within 7 days
    for _ in range(15):
        base_claim = random.choice(claims)
        
        c_date = datetime.strptime(base_claim["claim_date"], "%Y-%m-%d")
        new_date1 = c_date + timedelta(days=random.randint(1, 4))
        new_date2 = c_date + timedelta(days=random.randint(5, 6))
        
        rc1 = base_claim.copy()
        rc1["claim_id"] = f"CLM-FRD-{fraud_counter:04d}"
        rc1["claim_date"] = new_date1.strftime("%Y-%m-%d")
        rc1["is_weekend"] = new_date1.weekday() >= 5
        rc1["is_fraud"] = "True"
        rc1["fraud_type"] = "RAPID_RESUBMISSION"
        claims.append(rc1)
        fraud_counter += 1
        
        rc2 = base_claim.copy()
        rc2["claim_id"] = f"CLM-FRD-{fraud_counter:04d}"
        rc2["claim_date"] = new_date2.strftime("%Y-%m-%d")
        rc2["is_weekend"] = new_date2.weekday() >= 5
        rc2["is_fraud"] = "True"
        rc2["fraud_type"] = "RAPID_RESUBMISSION"
        claims.append(rc2)
        fraud_counter += 1

    # 4. Fraud Pattern 3: Upcoding (30 claims)
    # Amount > 2.5 standard deviations above mean
    for _ in range(30):
        # Pick procedure
        proc = random.choice(list(proc_stats.keys()))
        stats = proc_stats[proc]
        
        # Upcoded amount (mean + 3*std)
        amount = round(stats["mean"] + 3.5 * stats["std"], 2)
        
        member = random.choice(members)
        p_id, p_name = random.choice(providers[3:])
        days_offset = random.randint(0, 360)
        c_date = datetime(2024, 1, 1) + timedelta(days=days_offset)
        
        # pick a valid diagnosis for that procedure to bypass mismatch rule
        diag_code = [d[0] for d in diagnoses if d[0] in ("I10" if proc=="P001" else "K02" if proc in ("P002","P005") else "K35" if proc in ("P006","P007") else "Z34" if proc=="P008" else "M17" if proc=="P009" else "H25" if proc=="P010" else "K21")][0]
        
        claims.append({
            "claim_id": f"CLM-FRD-{fraud_counter:04d}",
            "member_id": member,
            "provider_id": p_id,
            "provider_name": p_name,
            "claim_date": c_date.strftime("%Y-%m-%d"),
            "claim_type": "INPATIENT" if proc in ("P006", "P007", "P010") else ("DENTAL" if proc in ("P002", "P005") else "OUTPATIENT"),
            "diagnosis_code": diag_code,
            "procedure_codes": proc,
            "submitted_amount": amount,
            "is_weekend": c_date.weekday() >= 5,
            "is_fraud": "True",
            "fraud_type": "UPCODING"
        })
        fraud_counter += 1

    # 5. Fraud Pattern 4: Unbundling (25 claims)
    # Multiple individual procedures that should be a single bundled code
    # Unbundled codes:
    # B1: P101_1 (2500), P101_2 (1500), P101_3 (3500)
    # We will submit these 3 codes as separate claims for the SAME member on the SAME day!
    # Or in the same claim's procedure_codes list? The prompt says "procedure_codes string[] - individual procedures".
    # So a single claim has multiple individual procedure codes e.g. "P101_1;P101_2;P101_3" instead of "P101".
    # Let's do that! A claim containing multiple unbundled procedures.
    unbundled_procedures = [
        ("P101_1;P101_2;P101_3", 7500.0, "E11"),
        ("P102_1;P102_2;P102_3", 4500.0, "K02"),
        ("P103_1;P103_2;P103_3", 29000.0, "M17"),
        ("P104_1;P104_2;P104_3", 20500.0, "G43"),
        ("P105_1;P105_2;P105_3", 9000.0, "Z34")
    ]
    for _ in range(25):
        proc_str, amount, diag_code = random.choice(unbundled_procedures)
        member = random.choice(members)
        p_id, p_name = random.choice(providers[3:])
        days_offset = random.randint(0, 360)
        c_date = datetime(2024, 1, 1) + timedelta(days=days_offset)
        
        claims.append({
            "claim_id": f"CLM-FRD-{fraud_counter:04d}",
            "member_id": member,
            "provider_id": p_id,
            "provider_name": p_name,
            "claim_date": c_date.strftime("%Y-%m-%d"),
            "claim_type": "DENTAL" if "P102" in proc_str else "OUTPATIENT",
            "diagnosis_code": diag_code,
            "procedure_codes": proc_str,
            "submitted_amount": amount,
            "is_weekend": c_date.weekday() >= 5,
            "is_fraud": "True",
            "fraud_type": "UNBUNDLING"
        })
        fraud_counter += 1

    # 6. Fraud Pattern 5: Phantom billing (25 claims)
    # Providers with > 30 claims in a single day.
    # Let's pick PROV-01 (index 0) and generate 35 claims for it on a single day (e.g. 2024-06-15).
    # All these 35 claims will trigger the Phantom Billing rule.
    phantom_date = "2024-06-15"
    p_id, p_name = providers[0]
    for _ in range(35): # 35 claims on the same day -> all will trigger phantom billing!
        member = random.choice(members)
        diag_code, diag_name = random.choice(diagnoses)
        proc = "P001" if diag_code in ("I10", "J06", "K21", "G43", "E11") else "P002"
        amount = get_normal_amount(proc)
        
        claims.append({
            "claim_id": f"CLM-FRD-{fraud_counter:04d}",
            "member_id": member,
            "provider_id": p_id,
            "provider_name": p_name,
            "claim_date": phantom_date,
            "claim_type": "OUTPATIENT" if proc == "P001" else "DENTAL",
            "diagnosis_code": diag_code,
            "procedure_codes": proc,
            "submitted_amount": amount,
            "is_weekend": False, # June 15, 2024 was Saturday, but let's override is_weekend
            "is_fraud": "True",
            "fraud_type": "PHANTOM_BILLING"
        })
        fraud_counter += 1

    # 7. Fraud Pattern 6: Weekend surgical anomalies (20 claims)
    # Surgical procedures on weekends from providers with < 5% historical weekend volume.
    # Let's pick PROV-02 (Suspect Hospital 2).
    # We will generate 20 claims with surgical procedures on weekends for PROV-02.
    # And we'll ensure PROV-02 has very few/no other weekend claims.
    # Surgical procedure: P006 (Appendix Surgery) or P010 (Cataract Surgery).
    for _ in range(20):
        p_id, p_name = providers[1] # PROV-02
        member = random.choice(members)
        # Find a weekend date
        days_offset = random.randint(0, 50) * 7 + 5 # Saturdays
        c_date = datetime(2024, 1, 6) + timedelta(days=days_offset)
        
        diag_code = "K35"
        proc = "P006" # Appendix surgery
        amount = get_normal_amount(proc)
        
        claims.append({
            "claim_id": f"CLM-FRD-{fraud_counter:04d}",
            "member_id": member,
            "provider_id": p_id,
            "provider_name": p_name,
            "claim_date": c_date.strftime("%Y-%m-%d"),
            "claim_type": "INPATIENT",
            "diagnosis_code": diag_code,
            "procedure_codes": proc,
            "submitted_amount": amount,
            "is_weekend": True,
            "is_fraud": "True",
            "fraud_type": "WEEKEND_SURGERY"
        })
        fraud_counter += 1

    # 8. Fraud Pattern 7: Diagnosis-procedure mismatches (20 claims)
    # e.g. Cataract surgery for cold, dental cleaning for appendicitis
    mismatches = [
        ("J06", "P010"), # Acute URI -> Cataract Surgery
        ("K02", "P006"), # Dental caries -> Appendix Surgery
        ("I10", "P005"), # Hypertension -> Root Canal
        ("K35", "P002")  # Appendicitis -> Basic Cleaning
    ]
    for _ in range(20):
        diag_code, proc = random.choice(mismatches)
        member = random.choice(members)
        p_id, p_name = random.choice(providers[3:])
        days_offset = random.randint(0, 360)
        c_date = datetime(2024, 1, 1) + timedelta(days=days_offset)
        
        amount = proc_stats[proc]["mean"] + 100
        
        claims.append({
            "claim_id": f"CLM-FRD-{fraud_counter:04d}",
            "member_id": member,
            "provider_id": p_id,
            "provider_name": p_name,
            "claim_date": c_date.strftime("%Y-%m-%d"),
            "claim_type": "INPATIENT" if proc in ("P006", "P010") else "DENTAL",
            "diagnosis_code": diag_code,
            "procedure_codes": proc,
            "submitted_amount": amount,
            "is_weekend": c_date.weekday() >= 5,
            "is_fraud": "True",
            "fraud_type": "DIAGNOSIS_PROCEDURE_MISMATCH"
        })
        fraud_counter += 1

    # 9. Fraud Pattern 8: Amount clustering (20 claims)
    # Claim amounts within 5% below the 50,000 auto-approval threshold (47,500–49,999)
    for _ in range(20):
        member = random.choice(members)
        p_id, p_name = random.choice(providers[3:])
        days_offset = random.randint(0, 360)
        c_date = datetime(2024, 1, 1) + timedelta(days=days_offset)
        
        # Force amount in [47500, 49999]
        amount = round(random.uniform(47500, 49999), 2)
        diag_code = "K35"
        proc = "P006" # Appendix surgery normally costs 80,000, so a claim for 48,000 is under limit but clusters here
        
        claims.append({
            "claim_id": f"CLM-FRD-{fraud_counter:04d}",
            "member_id": member,
            "provider_id": p_id,
            "provider_name": p_name,
            "claim_date": c_date.strftime("%Y-%m-%d"),
            "claim_type": "INPATIENT",
            "diagnosis_code": diag_code,
            "procedure_codes": proc,
            "submitted_amount": amount,
            "is_weekend": c_date.weekday() >= 5,
            "is_fraud": "True",
            "fraud_type": "AMOUNT_CLUSTERING"
        })
        fraud_counter += 1

    # Now we have exactly 1,800 clean + 30 dup + 30 rapid + 30 upcoded + 25 unbundle + 35 phantom + 20 weekend + 20 mismatch + 20 clustering = 2,010 claims
    # Let's adjust to make it exactly 2,000 rows
    # We will trim 10 clean claims
    claims = claims[10:]
    
    # Shuffle the dataset
    random.shuffle(claims)
    
    # Write to claims.csv
    fieldnames = ["claim_id", "member_id", "provider_id", "provider_name", "claim_date", "claim_type", "diagnosis_code", "procedure_codes", "submitted_amount", "is_weekend", "is_fraud", "fraud_type"]
    with open("claims.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in claims:
            writer.writerow(r)
            
    print(f"Generated {len(claims)} claims in 'claims.csv' (with embedded fraud labels).")

if __name__ == "__main__":
    generate_fraud_dataset()
