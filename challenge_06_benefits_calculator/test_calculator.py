import unittest
import json
from calculator import PolicyBenefitsCalculator

# A minimal test policy
TEST_POLICY = {
  "policy_number": "POL-TEST-001",
  "global_deductible": 2000,
  "plan": {
    "name": "Test Plan",
    "tier": "Gold",
    "effective_date": "2024-01-01",
    "expiry_date": "2024-12-31",
    "currency": "THB"
  },
  "benefits": [
    {
      "type": "OUTPATIENT",
      "annual_limit": 10000,
      "sub_benefits": [
        { "name": "Doctor Visit", "limit_per_visit": 2000, "visits_per_year": 3 }
      ]
    },
    {
      "type": "DENTAL",
      "annual_limit": 5000,
      "waiting_period_days": 90,
      "sub_benefits": [
        { "name": "Basic Dental", "limit_per_year": 3000 }
      ]
    }
  ],
  "exclusions": [
    "Cosmetic surgery"
  ],
  "copay": {
    "outpatient": { "percentage": 10, "max_per_visit": 200 }
  }
}

class TestPolicyBenefitsCalculator(unittest.TestCase):
    
    def setUp(self):
        self.calc = PolicyBenefitsCalculator(TEST_POLICY)

    def test_policy_period(self):
        # Date before effective date
        expense = {
            "expense_id": "EXP-01",
            "date": "2023-12-31",
            "benefit_type": "OUTPATIENT",
            "sub_benefit": "Doctor Visit",
            "amount": 500,
            "diagnosis": "Fever"
        }
        res = self.calc.process_expense(expense)
        self.assertEqual(res["decision"], "DENIED")
        self.assertIn("outside policy coverage period", res["reason"])

    def test_exclusions(self):
        # Excluded diagnosis
        expense = {
            "expense_id": "EXP-02",
            "date": "2024-02-15",
            "benefit_type": "OUTPATIENT",
            "sub_benefit": "Doctor Visit",
            "amount": 500,
            "diagnosis": "Cosmetic surgery"
        }
        res = self.calc.process_expense(expense)
        self.assertEqual(res["decision"], "DENIED")
        self.assertIn("exclusion", res["reason"])

    def test_waiting_period_denial(self):
        # Dental has 90 days waiting period.
        # Date 2024-02-01 is 31 days. Should be denied.
        expense = {
            "expense_id": "EXP-03",
            "date": "2024-02-01",
            "benefit_type": "DENTAL",
            "sub_benefit": "Basic Dental",
            "amount": 1000,
            "diagnosis": "Teeth cleaning"
        }
        res = self.calc.process_expense(expense)
        self.assertEqual(res["decision"], "DENIED")
        self.assertIn("Waiting period", res["reason"])

    def test_waiting_period_passed(self):
        # 2024-05-01 is 121 days (waiting period is 90 days). Should be processed.
        # Note: deductible is 2000. Under testing policy, global deductible applies.
        # Since it goes to deductible first, covered_amount will be 0, but deductible_applied will be 1000.
        expense = {
            "expense_id": "EXP-04",
            "date": "2024-05-01",
            "benefit_type": "DENTAL",
            "sub_benefit": "Basic Dental",
            "amount": 1000,
            "diagnosis": "Teeth cleaning"
        }
        res = self.calc.process_expense(expense)
        self.assertEqual(res["deductible_applied"], 1000.0)
        self.assertEqual(res["decision"], "DENIED")  # Denied because it went to deductible
        self.assertIn("deductible", res["reason"])

    def test_deductible_satisfaction_and_copay(self):
        # 1st expense: 1500 (goes to deductible. Covered=0, remaining deductible = 500)
        exp1 = {
            "expense_id": "EXP-05a",
            "date": "2024-01-10",
            "benefit_type": "OUTPATIENT",
            "sub_benefit": "Doctor Visit",
            "amount": 1500,
            "diagnosis": "Flu"
        }
        res1 = self.calc.process_expense(exp1)
        self.assertEqual(res1["deductible_applied"], 1500.0)
        self.assertEqual(res1["covered_amount"], 0.0)
        
        # 2nd expense: 1000 (limited by visit sub-limit of 1000)
        # Deductible remaining is 500. So 500 goes to deductible.
        # Remaining base for copay is 500.
        # Outpatient has 10% copay. Copay on 500 = 50 THB.
        # Final covered = 450.
        # Member pays: 500 (deductible) + 50 (copay) = 550.
        exp2 = {
            "expense_id": "EXP-05b",
            "date": "2024-01-15",
            "benefit_type": "OUTPATIENT",
            "sub_benefit": "Doctor Visit",
            "amount": 1000,
            "diagnosis": "Flu follow-up"
        }
        res2 = self.calc.process_expense(exp2)
        self.assertEqual(res2["deductible_applied"], 500.0)
        self.assertEqual(res2["copay_amount"], 50.0)
        self.assertEqual(res2["covered_amount"], 450.0)
        self.assertEqual(res2["member_pays"], 550.0)

    def test_copay_capping(self):
        # Satisfy deductible first
        self.calc.remaining_deductible = 0.0
        
        # Expense: 2000. Visit limit is 2000.
        # Outpatient copay is 10%. 10% of 2000 = 200.
        # Max per visit is 200 (hit, 200 = 200).
        # Covered: 1800.
        expense = {
            "expense_id": "EXP-06",
            "date": "2024-01-15",
            "benefit_type": "OUTPATIENT",
            "sub_benefit": "Doctor Visit",
            "amount": 2000,
            "diagnosis": "Fever"
        }
        res = self.calc.process_expense(expense)
        self.assertEqual(res["copay_amount"], 200.0)
        self.assertEqual(res["covered_amount"], 1800.0)

    def test_visit_limits_exhaustion(self):
        self.calc.remaining_deductible = 0.0
        
        # Max visits is 3
        expense = {
            "expense_id": "EXP-07",
            "date": "2024-01-15",
            "benefit_type": "OUTPATIENT",
            "sub_benefit": "Doctor Visit",
            "amount": 500,
            "diagnosis": "Flu"
        }
        
        # Visit 1
        res1 = self.calc.process_expense(expense)
        self.assertEqual(res1["decision"], "PARTIALLY_COVERED")  # Copay applied (500 - 50 = 450)
        self.assertEqual(res1["remaining_visit_limit"], 2)
        
        # Visit 2
        res2 = self.calc.process_expense(expense)
        self.assertEqual(res2["remaining_visit_limit"], 1)
        
        # Visit 3
        res3 = self.calc.process_expense(expense)
        self.assertEqual(res3["remaining_visit_limit"], 0)
        
        # Visit 4 (exhausted)
        res4 = self.calc.process_expense(expense)
        self.assertEqual(res4["decision"], "DENIED")
        self.assertIn("exhausted", res4["reason"])

    def test_annual_limit_exhaustion(self):
        self.calc.remaining_deductible = 0.0
        # Reduce remaining annual limit for outpatient to 1200 THB
        self.calc.remaining_annual_limits["OUTPATIENT"] = 1200.0
        
        # Expense is 1000. Outpatient copay is 10% (100). Remaining limit is 1200.
        # Covered: 900.
        expense = {
            "expense_id": "EXP-08a",
            "date": "2024-01-15",
            "benefit_type": "OUTPATIENT",
            "sub_benefit": "Doctor Visit",
            "amount": 1000,
            "diagnosis": "Flu"
        }
        res1 = self.calc.process_expense(expense)
        self.assertEqual(res1["covered_amount"], 900.0)
        self.assertEqual(self.calc.remaining_annual_limits["OUTPATIENT"], 300.0)
        
        # Next expense: 1000. Cap of visit is 1000. Copay is 10% (100).
        # Base covered is 900. But remaining annual limit is 300.
        # So covered is capped at 300.
        res2 = self.calc.process_expense(expense)
        self.assertEqual(res2["covered_amount"], 300.0)
        self.assertEqual(self.calc.remaining_annual_limits["OUTPATIENT"], 0.0)

    def test_uncovered_benefit_type(self):
        expense = {
            "expense_id": "EXP-09",
            "date": "2024-01-15",
            "benefit_type": "MATERNITY",
            "sub_benefit": "Normal Delivery",
            "amount": 50000,
            "diagnosis": "Pregnancy"
        }
        res = self.calc.process_expense(expense)
        self.assertEqual(res["decision"], "DENIED")
        self.assertIn("not covered under this policy", res["reason"])

if __name__ == "__main__":
    unittest.main()
