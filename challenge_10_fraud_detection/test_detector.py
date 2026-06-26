import unittest
from detector import FraudDetector

class TestFraudDetectorRules(unittest.TestCase):
    def setUp(self):
        self.detector = FraudDetector()
        
    def test_rule_amount_clustering_triggered(self):
        # 47,500 to 49,999.99 triggers amount clustering
        claims = [{
            "claim_id": "CLM-001",
            "member_id": "MEM-01",
            "provider_id": "PROV-01",
            "provider_name": "General Care Hospital",
            "claim_date": "2024-03-01",
            "claim_type": "OUTPATIENT",
            "diagnosis_code": "I10",
            "procedure_codes": "P001",
            "submitted_amount": "48500.00",
            "is_weekend": "False",
            "is_fraud": "False",
            "fraud_type": "NONE"
        }]
        results = self.detector.analyze_claims(claims)
        self.assertEqual(len(results), 1)
        flags = [f["rule"] for f in results[0]["flags"]]
        self.assertIn("amount_clustering", flags)
        self.assertEqual(results[0]["risk_score"], 20)  # weight 2 -> score 20

    def test_rule_amount_clustering_not_triggered(self):
        claims = [{
            "claim_id": "CLM-001",
            "member_id": "MEM-01",
            "provider_id": "PROV-01",
            "provider_name": "General Care Hospital",
            "claim_date": "2024-03-01",
            "claim_type": "OUTPATIENT",
            "diagnosis_code": "I10",
            "procedure_codes": "P001",
            "submitted_amount": "45000.00",
            "is_weekend": "False",
            "is_fraud": "False",
            "fraud_type": "NONE"
        }]
        results = self.detector.analyze_claims(claims)
        flags = [f["rule"] for f in results[0]["flags"]]
        self.assertNotIn("amount_clustering", flags)
        self.assertEqual(results[0]["risk_score"], 0)

    def test_rule_diagnosis_procedure_mismatch(self):
        # Hypertension (I10) does not support Appendix Surgery (P006)
        claims = [{
            "claim_id": "CLM-002",
            "member_id": "MEM-01",
            "provider_id": "PROV-01",
            "provider_name": "General Care Hospital",
            "claim_date": "2024-03-01",
            "claim_type": "INPATIENT",
            "diagnosis_code": "I10",
            "procedure_codes": "P006",
            "submitted_amount": "1000.00",
            "is_weekend": "False",
            "is_fraud": "False",
            "fraud_type": "NONE"
        }]
        results = self.detector.analyze_claims(claims)
        flags = [f["rule"] for f in results[0]["flags"]]
        self.assertIn("diagnosis_procedure_mismatch", flags)
        self.assertEqual(results[0]["risk_score"], 30)  # weight 3 -> score 30

    def test_rule_duplicate_claim(self):
        # Two identical claims
        claims = [
            {
                "claim_id": "CLM-003a",
                "member_id": "MEM-02",
                "provider_id": "PROV-02",
                "provider_name": "Clinic",
                "claim_date": "2024-03-05",
                "claim_type": "OUTPATIENT",
                "diagnosis_code": "I10",
                "procedure_codes": "P001",
                "submitted_amount": "1500.00",
                "is_weekend": "False",
                "is_fraud": "False",
                "fraud_type": "NONE"
            },
            {
                "claim_id": "CLM-003b",
                "member_id": "MEM-02",
                "provider_id": "PROV-02",
                "provider_name": "Clinic",
                "claim_date": "2024-03-05",
                "claim_type": "OUTPATIENT",
                "diagnosis_code": "I10",
                "procedure_codes": "P001",
                "submitted_amount": "1500.00",
                "is_weekend": "False",
                "is_fraud": "False",
                "fraud_type": "NONE"
            }
        ]
        results = self.detector.analyze_claims(claims)
        # Both should flag as duplicates of each other
        self.assertIn("duplicate_claim", [f["rule"] for f in results[0]["flags"]])
        self.assertIn("duplicate_claim", [f["rule"] for f in results[1]["flags"]])

    def test_rule_rapid_resubmission(self):
        # Same member, same diagnosis, within 7 days
        claims = [
            {
                "claim_id": "CLM-004a",
                "member_id": "MEM-03",
                "provider_id": "PROV-02",
                "provider_name": "Clinic",
                "claim_date": "2024-03-01",
                "claim_type": "OUTPATIENT",
                "diagnosis_code": "I10",
                "procedure_codes": "P001",
                "submitted_amount": "1500.00",
                "is_weekend": "False",
                "is_fraud": "False",
                "fraud_type": "NONE"
            },
            {
                "claim_id": "CLM-004b",
                "member_id": "MEM-03",
                "provider_id": "PROV-03",
                "provider_name": "Hospital",
                "claim_date": "2024-03-05", # 4 days later
                "claim_type": "OUTPATIENT",
                "diagnosis_code": "I10",
                "procedure_codes": "P001",
                "submitted_amount": "1400.00", # different amount so not duplicate
                "is_weekend": "False",
                "is_fraud": "False",
                "fraud_type": "NONE"
            }
        ]
        results = self.detector.analyze_claims(claims)
        # The second claim should flag rapid_resubmission
        self.assertIn("rapid_resubmission", [f["rule"] for f in results[1]["flags"]])

    def test_rule_unbundling(self):
        claims = [{
            "claim_id": "CLM-005",
            "member_id": "MEM-04",
            "provider_id": "PROV-02",
            "provider_name": "Clinic",
            "claim_date": "2024-03-01",
            "claim_type": "OUTPATIENT",
            "diagnosis_code": "E11",
            "procedure_codes": "P101_1;P101_2;P101_3;P009", # contains lab bundle components
            "submitted_amount": "5000.00",
            "is_weekend": "False",
            "is_fraud": "False",
            "fraud_type": "NONE"
        }]
        results = self.detector.analyze_claims(claims)
        flags = [f["rule"] for f in results[0]["flags"]]
        self.assertIn("unbundling", flags)

    def test_rule_phantom_billing(self):
        # Create 32 claims for the same provider on the same day
        claims = []
        for i in range(32):
            claims.append({
                "claim_id": f"CLM-PHAN-{i}",
                "member_id": f"MEM-{i}",
                "provider_id": "PROV-PHANTOM",
                "provider_name": "Suspect Center",
                "claim_date": "2024-05-10",
                "claim_type": "OUTPATIENT",
                "diagnosis_code": "I10",
                "procedure_codes": "P001",
                "submitted_amount": "1500.00",
                "is_weekend": "False",
                "is_fraud": "False",
                "fraud_type": "NONE"
            })
        results = self.detector.analyze_claims(claims)
        for r in results:
            self.assertIn("phantom_billing", [f["rule"] for f in r["flags"]])

    def test_rule_weekend_anomaly(self):
        # We need historical weekend volume < 5%
        # Provider PROV-WKND will have 20 weekday claims and 1 weekend claim which is a surgery
        claims = []
        for i in range(20):
            claims.append({
                "claim_id": f"CLM-WKND-WD-{i}",
                "member_id": f"MEM-{i}",
                "provider_id": "PROV-WKND",
                "provider_name": "Suspect Surgery",
                "claim_date": "2024-05-13",  # Monday
                "claim_type": "INPATIENT",
                "diagnosis_code": "K35",
                "procedure_codes": "P007",
                "submitted_amount": "6000.00",
                "is_weekend": "False",
                "is_fraud": "False",
                "fraud_type": "NONE"
            })
            
        # Add the surgical weekend claim
        claims.append({
            "claim_id": "CLM-WKND-WE-SURG",
            "member_id": "MEM-WKND-SURG",
            "provider_id": "PROV-WKND",
            "provider_name": "Suspect Surgery",
            "claim_date": "2024-05-18",  # Saturday
            "claim_type": "INPATIENT",
            "diagnosis_code": "K35",
            "procedure_codes": "P006",  # Surgery
            "submitted_amount": "80000.00",
            "is_weekend": "True",
            "is_fraud": "True",
            "fraud_type": "WEEKEND_SURGERY"
        })
        results = self.detector.analyze_claims(claims)
        
        # Check that the surgical weekend claim triggers the flag
        surg_res = [r for r in results if r["claim_id"] == "CLM-WKND-WE-SURG"][0]
        self.assertIn("weekend_anomaly", [f["rule"] for f in surg_res["flags"]])

    def test_rule_upcoding(self):
        # Generate claims to establish mean and standard deviation
        claims = []
        # Mean will be around 1000, std will be low
        for i in range(10):
            claims.append({
                "claim_id": f"CLM-UP-{i}",
                "member_id": f"MEM-{i}",
                "provider_id": "PROV-UP",
                "provider_name": "Normal Hospital",
                "claim_date": "2024-05-10",
                "claim_type": "OUTPATIENT",
                "diagnosis_code": "I10",
                "procedure_codes": "P001",
                "submitted_amount": "1000.00" if i % 2 == 0 else "1050.00",
                "is_weekend": "False",
                "is_fraud": "False",
                "fraud_type": "NONE"
            })
            
        # Upcoded claim (amount: 3000, which is > 2 std above mean of ~1025, std is ~26)
        claims.append({
            "claim_id": "CLM-UP-HIGH",
            "member_id": "MEM-UP-HIGH",
            "provider_id": "PROV-UP",
            "provider_name": "Normal Hospital",
            "claim_date": "2024-05-11",
            "claim_type": "OUTPATIENT",
            "diagnosis_code": "I10",
            "procedure_codes": "P001",
            "submitted_amount": "3000.00",
            "is_weekend": "False",
            "is_fraud": "True",
            "fraud_type": "UPCODING"
        })
        results = self.detector.analyze_claims(claims)
        
        high_res = [r for r in results if r["claim_id"] == "CLM-UP-HIGH"][0]
        self.assertIn("upcoding", [f["rule"] for f in high_res["flags"]])

    def test_composite_scoring_multiple_flags(self):
        # Should flag upcoding & amount clustering
        # Triggering amount clustering (48500) and diagnosis-procedure mismatch
        claims = [{
            "claim_id": "CLM-MULT",
            "member_id": "MEM-MULT",
            "provider_id": "PROV-MULT",
            "provider_name": "Clinic",
            "claim_date": "2024-03-01",
            "claim_type": "INPATIENT",
            "diagnosis_code": "I10", # Hypertension
            "procedure_codes": "P006", # Surgery (mismatch)
            "submitted_amount": "48500.00", # amount clustering
            "is_weekend": "False",
            "is_fraud": "True",
            "fraud_type": "NONE"
        }]
        results = self.detector.analyze_claims(claims)
        r = results[0]
        flags = [f["rule"] for f in r["flags"]]
        self.assertIn("diagnosis_procedure_mismatch", flags)
        self.assertIn("amount_clustering", flags)
        
        # Mismatch weight = 3, clustering weight = 2. Total = 5.
        # Score = (5 / 10.0) * 100 = 50
        self.assertEqual(r["risk_score"], 50)

if __name__ == "__main__":
    unittest.main()
