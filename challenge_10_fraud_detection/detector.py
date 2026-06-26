import csv
import math
from datetime import datetime

class FraudDetector:
    def __init__(self, severity_weights=None):
        # Configurable weights (1 to 5)
        self.weights = severity_weights or {
            "duplicate_claim": 5,
            "phantom_billing": 5,
            "rapid_resubmission": 4,
            "weekend_anomaly": 4,
            "upcoding": 3,
            "unbundling": 3,
            "diagnosis_procedure_mismatch": 3,
            "amount_clustering": 2
        }
        
        # Valid diagnosis-procedure pairs
        self.valid_associations = {
            "I10": {"P001"},
            "K21": {"P001", "P003"},
            "K02": {"P002", "P005", "P102_1", "P102_2", "P102_3"},
            "J06": {"P001"},
            "K35": {"P006", "P007"},
            "Z34": {"P008", "P105_1", "P105_2", "P105_3"},
            "M17": {"P009", "P103_1", "P103_2", "P103_3"},
            "H25": {"P010"},
            "G43": {"P001", "P004", "P104_1", "P104_2", "P104_3"},
            "E11": {"P001", "P003", "P101_1", "P101_2", "P101_3"}
        }
        
        # Unbundling mappings (5 bundles)
        self.bundles = {
            "B1": {"codes": {"P101_1", "P101_2", "P101_3"}, "desc": "Complete Lab Bundle (P101)"},
            "B2": {"codes": {"P102_1", "P102_2", "P102_3"}, "desc": "Complete Dental Clean Bundle (P102)"},
            "B3": {"codes": {"P103_1", "P103_2", "P103_3"}, "desc": "Knee Treatment Bundle (P103)"},
            "B4": {"codes": {"P104_1", "P104_2", "P104_3"}, "desc": "Cardiac Assessment Bundle (P104)"},
            "B5": {"codes": {"P105_1", "P105_2", "P105_3"}, "desc": "Prenatal Care Bundle (P105)"}
        }
        
        # Stat tables to be built on load
        self.proc_means = {}
        self.proc_stds = {}
        self.prov_weekend_volume = {}  # prov_id -> (weekend_claims, total_claims)
        self.prov_daily_claims = {}   # (prov_id, date) -> claim_count

    def calculate_stats(self, claims):
        # 1. Procedure statistics
        proc_amounts = {}
        for c in claims:
            # In case of multiple codes, we parse them
            p_codes = c["procedure_codes"].split(";")
            amount = float(c["submitted_amount"])
            
            # If single procedure, collect for upcoding check
            if len(p_codes) == 1:
                p_code = p_codes[0]
                if p_code not in proc_amounts:
                    proc_amounts[p_code] = []
                proc_amounts[p_code].append(amount)
                
        # Calculate mean & std dev
        for p_code, amts in proc_amounts.items():
            n = len(amts)
            if n > 0:
                mean = sum(amts) / n
                self.proc_means[p_code] = mean
                if n > 1:
                    variance = sum((x - mean) ** 2 for x in amts) / (n - 1)
                    self.proc_stds[p_code] = math.sqrt(variance)
                else:
                    self.proc_stds[p_code] = 0.0
                    
        # 2. Provider weekend volume & daily claims (weekend volume calculated excluding surgeries)
        for c in claims:
            p_id = c["provider_id"]
            is_wknd = c["is_weekend"] == "True" or c["is_weekend"] is True
            date = c["claim_date"]
            p_codes = c["procedure_codes"].split(";")
            is_surgery = "P006" in p_codes or "P010" in p_codes
            
            # Weekend volume tracking (exclude surgeries from baseline)
            if not is_surgery:
                if p_id not in self.prov_weekend_volume:
                    self.prov_weekend_volume[p_id] = [0, 0]
                self.prov_weekend_volume[p_id][1] += 1
                if is_wknd:
                    self.prov_weekend_volume[p_id][0] += 1
                
            # Daily claims tracking (include all claims)
            key = (p_id, date)
            self.prov_daily_claims[key] = self.prov_daily_claims.get(key, 0) + 1

    def analyze_claims(self, claims):
        # Ensure stats are populated
        self.calculate_stats(claims)
        
        # Sort claims by member and date for rapid resubmission and duplicates
        claims_by_member = {}
        for c in claims:
            m_id = c["member_id"]
            if m_id not in claims_by_member:
                claims_by_member[m_id] = []
            claims_by_member[m_id].append(c)
            
        for m_id in claims_by_member:
            claims_by_member[m_id].sort(key=lambda x: x["claim_date"])
            
        scored_claims = []
        
        for c in claims:
            claim_id = c["claim_id"]
            m_id = c["member_id"]
            p_id = c["provider_id"]
            p_name = c["provider_name"]
            c_date_str = c["claim_date"]
            c_date = datetime.strptime(c_date_str, "%Y-%m-%d").date()
            diag = c["diagnosis_code"]
            p_codes = c["procedure_codes"].split(";")
            amount = float(c["submitted_amount"])
            is_wknd = c["is_weekend"] == "True" or c["is_weekend"] is True
            
            flags = []
            
            # --- Rule 1: Duplicate Claim ---
            # same member + provider + date + diagnosis (excluding current claim_id)
            member_claims = claims_by_member[m_id]
            is_dup = False
            for mc in member_claims:
                if mc["claim_id"] != claim_id:
                    mc_date = datetime.strptime(mc["claim_date"], "%Y-%m-%d").date()
                    if mc_date == c_date and mc["provider_id"] == p_id and mc["diagnosis_code"] == diag and float(mc["submitted_amount"]) == amount:
                        is_dup = True
                        break
            if is_dup:
                flags.append({
                    "rule": "duplicate_claim",
                    "severity": self.weights["duplicate_claim"],
                    "evidence": f"Identical claim found for member {m_id} at provider {p_id} on date {c_date_str} for amount {amount:,.2f}"
                })
                
            # --- Rule 2: Rapid Re-submission ---
            # same member + same diagnosis within 7 days
            is_rapid = False
            for mc in member_claims:
                if mc["claim_id"] != claim_id and mc["diagnosis_code"] == diag:
                    mc_date = datetime.strptime(mc["claim_date"], "%Y-%m-%d").date()
                    diff = abs((c_date - mc_date).days)
                    if 0 < diff <= 7:
                        is_rapid = True
                        other_date = mc["claim_date"]
                        break
            if is_rapid:
                flags.append({
                    "rule": "rapid_resubmission",
                    "severity": self.weights["rapid_resubmission"],
                    "evidence": f"Re-submission of diagnosis {diag} within 7 days (compared with claim on {other_date})"
                })
                
            # --- Rule 3: Upcoding ---
            # amount > 2 standard deviations above mean for single procedure
            if len(p_codes) == 1:
                p_code = p_codes[0]
                mean = self.proc_means.get(p_code, 0.0)
                std = self.proc_stds.get(p_code, 0.0)
                if std > 0:
                    z_score = (amount - mean) / std
                    if z_score > 2.0:
                        flags.append({
                            "rule": "upcoding",
                            "severity": self.weights["upcoding"],
                            "evidence": f"Submitted amount {amount:,.2f} for procedure {p_code} is {z_score:.2f} standard deviations above the mean of {mean:,.2f}"
                        })
                        
            # --- Rule 4: Unbundling ---
            # multiple individual procedures when a bundled code exists
            p_code_set = set(p_codes)
            for b_id, b_info in self.bundles.items():
                if b_info["codes"].issubset(p_code_set):
                    flags.append({
                        "rule": "unbundling",
                        "severity": self.weights["unbundling"],
                        "evidence": f"Claim contains unbundled codes {list(b_info['codes'])} which should be billed under bundle {b_id} ({b_info['desc']})"
                    })
                    break
                    
            # --- Rule 5: Phantom Billing ---
            # provider submits > 30 claims in a single day
            daily_count = self.prov_daily_claims.get((p_id, c_date_str), 0)
            if daily_count > 30:
                flags.append({
                    "rule": "phantom_billing",
                    "severity": self.weights["phantom_billing"],
                    "evidence": f"Provider {p_id} submitted {daily_count} claims on {c_date_str}, exceeding limit of 30"
                })
                
            # --- Rule 6: Weekend Anomaly ---
            # surgical procedures (P006, P010) on weekends from providers with < 5% historical weekend volume
            is_surgery = "P006" in p_codes or "P010" in p_codes
            if is_wknd and is_surgery:
                wknd_claims, tot_claims = self.prov_weekend_volume.get(p_id, (0, 0))
                wknd_pct = (wknd_claims / tot_claims) if tot_claims > 0 else 0.0
                if wknd_pct < 0.05:
                    flags.append({
                        "rule": "weekend_anomaly",
                        "severity": self.weights["weekend_anomaly"],
                        "evidence": f"Surgical procedure performed on weekend by provider {p_id} with historical weekend volume of {wknd_pct*100:.1f}% (< 5%)"
                    })
                    
            # --- Rule 7: Diagnosis-Procedure Mismatch ---
            # procedure not clinically associated with diagnosis
            if diag in self.valid_associations:
                has_mismatch = False
                invalid_codes = []
                for p_code in p_codes:
                    if p_code not in self.valid_associations[diag]:
                        has_mismatch = True
                        invalid_codes.append(p_code)
                if has_mismatch:
                    flags.append({
                        "rule": "diagnosis_procedure_mismatch",
                        "severity": self.weights["diagnosis_procedure_mismatch"],
                        "evidence": f"Procedure codes {invalid_codes} are not clinically associated with diagnosis {diag}"
                    })
                    
            # --- Rule 8: Amount Clustering ---
            # claim amounts within 5% below the 50,000 auto-approval threshold (47,500–49,999)
            if 47500.0 <= amount <= 49999.99:
                flags.append({
                    "rule": "amount_clustering",
                    "severity": self.weights["amount_clustering"],
                    "evidence": f"Submitted amount {amount:,.2f} is clustered just below the 50,000.00 auto-approval threshold (95%-99.9%)"
                })
                
            # --- Calculate Composite Score ---
            # Composite score = weighted sum, normalized to 0-100
            # To normalize meaningfully: sum of weights of triggered flags.
            # Max possible weights triggered together. Let's divide by a scale of 10.0 to make it clean
            # e.g., triggering a duplicate (5) + upcoding (3) = 8 -> 80% risk.
            # Score is capped at 100.
            total_severity = sum(f["severity"] for f in flags)
            risk_score = min(100, int((total_severity / 10.0) * 100))
            
            scored_claims.append({
                "claim_id": claim_id,
                "member_id": m_id,
                "provider_id": p_id,
                "submitted_amount": amount,
                "risk_score": risk_score,
                "flags": flags,
                # Include actual labels for metric report
                "is_fraud_label": c["is_fraud"] == "True" or c["is_fraud"] is True,
                "fraud_type_label": c["fraud_type"]
            })
            
        return scored_claims
