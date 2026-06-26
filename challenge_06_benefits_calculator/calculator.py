import json
from datetime import datetime

class PolicyBenefitsCalculator:
    def __init__(self, policy_json):
        if isinstance(policy_json, str):
            self.policy = json.loads(policy_json)
        else:
            self.policy = policy_json
            
        # Parse policy effective/expiry dates
        self.effective_date = datetime.strptime(self.policy["plan"]["effective_date"], "%Y-%m-%d").date()
        self.expiry_date = datetime.strptime(self.policy["plan"]["expiry_date"], "%Y-%m-%d").date()
        
        # Track limits
        self.remaining_annual_limits = {}
        self.remaining_visits = {}
        self.remaining_sub_limits = {}
        
        # Initialize global deductible if present, else 0
        self.remaining_deductible = float(self.policy.get("global_deductible", 0.0))
        
        # Initialize benefit limits
        for benefit in self.policy["benefits"]:
            b_type = benefit["type"]
            # Some benefits have annual_limit, some have lifetime_limit
            limit = benefit.get("annual_limit") or benefit.get("lifetime_limit") or 0
            self.remaining_annual_limits[b_type] = float(limit)
            
            self.remaining_visits[b_type] = {}
            self.remaining_sub_limits[b_type] = {}
            
            for sub in benefit.get("sub_benefits", []):
                name = sub["name"]
                # Track max days / visits
                if "max_days" in sub:
                    self.remaining_visits[b_type][name] = sub["max_days"]
                elif "visits_per_year" in sub:
                    self.remaining_visits[b_type][name] = sub["visits_per_year"]
                    
                # Track sub-limits per year/pregnancy/event if applicable
                if "limit_per_year" in sub:
                    self.remaining_sub_limits[b_type][name] = float(sub["limit_per_year"])
                elif "limit_per_pregnancy" in sub:
                    self.remaining_sub_limits[b_type][name] = float(sub["limit_per_pregnancy"])

    def process_expense(self, expense):
        exp_id = expense["expense_id"]
        submitted_amount = float(expense["amount"])
        b_type = expense["benefit_type"]
        sub_name = expense["sub_benefit"]
        diag = expense.get("diagnosis", "")
        provider = expense.get("provider", "")
        
        # Parse expense date
        exp_date = datetime.strptime(expense["date"], "%Y-%m-%d").date()
        
        # Initialize response template
        result = {
            "expense_id": exp_id,
            "submitted_amount": submitted_amount,
            "covered_amount": 0.0,
            "copay_amount": 0.0,
            "deductible_applied": 0.0,
            "member_pays": submitted_amount,
            "decision": "DENIED",
            "reason": ""
        }
        
        # 1. Check policy period
        if exp_date < self.effective_date or exp_date > self.expiry_date:
            result["reason"] = f"Expense date {exp_date} is outside policy coverage period ({self.effective_date} to {self.expiry_date})."
            return result
            
        # 2. Check exclusions
        exclusions = self.policy.get("exclusions", [])
        for excl in exclusions:
            excl_lower = excl.lower()
            if diag.lower() in excl_lower or sub_name.lower() in excl_lower:
                result["reason"] = f"Claim denied. Diagnosis '{diag}' / Benefit '{sub_name}' matches policy exclusion: '{excl}'."
                return result
                
        # 3. Find matching benefit
        benefit = None
        for b in self.policy["benefits"]:
            if b["type"] == b_type:
                benefit = b
                break
                
        if not benefit:
            result["reason"] = f"Benefit type {b_type} is not covered under this policy."
            return result
            
        # 4. Check waiting period
        waiting_days = benefit.get("waiting_period_days", 0)
        if waiting_days > 0:
            days_enrolled = (exp_date - self.effective_date).days
            if days_enrolled < waiting_days:
                result["reason"] = f"Claim denied. Waiting period of {waiting_days} days not met. Member enrolled for {days_enrolled} days."
                return result
                
        # 5. Check sub-benefit config
        sub_benefit = None
        for sb in benefit.get("sub_benefits", []):
            if sb["name"] == sub_name:
                sub_benefit = sb
                break
                
        if not sub_benefit:
            result["reason"] = f"Sub-benefit '{sub_name}' is not covered under benefit type '{b_type}'."
            return result
            
        # 6. Check max visits / max days limit
        if sub_name in self.remaining_visits[b_type]:
            rem_visits = self.remaining_visits[b_type][sub_name]
            if rem_visits == 0:
                result["reason"] = f"Claim denied. Limit of visits/days exhausted for '{sub_name}'."
                return result
            # Note: -1 means unlimited
            
        # Determine maximum base amount covered before copay / deductible / limits
        limit_per_unit = (
            sub_benefit.get("limit_per_visit") or 
            sub_benefit.get("limit_per_day") or 
            sub_benefit.get("limit_per_event") or 
            sub_benefit.get("limit_per_pregnancy") or 
            sub_benefit.get("limit_per_year") or 
            submitted_amount
        )
        
        # If the limit per unit is unlimited (-1), use submitted amount
        if limit_per_unit == -1:
            limit_per_unit = submitted_amount
            
        base_covered = min(submitted_amount, float(limit_per_unit))
        
        # If there's a year/pregnancy sub-limit limit remaining, apply it
        if sub_name in self.remaining_sub_limits[b_type]:
            rem_sub_lim = self.remaining_sub_limits[b_type][sub_name]
            if base_covered > rem_sub_lim:
                base_covered = rem_sub_lim
                if base_covered <= 0:
                    result["reason"] = f"Claim denied. Sub-benefit annual/pregnancy limit for '{sub_name}' has been exhausted."
                    return result
                    
        # Apply global Deductible
        deductible_applied = 0.0
        if self.remaining_deductible > 0:
            deductible_applied = min(base_covered, self.remaining_deductible)
            base_covered -= deductible_applied
            self.remaining_deductible -= deductible_applied
            
        # Apply Copay (if any)
        copay_amount = 0.0
        copay_percentage = 0.0
        
        copay_config = self.policy.get("copay", {})
        benefit_copay_key = b_type.lower()
        if benefit_copay_key in copay_config:
            copay_percentage = float(copay_config[benefit_copay_key].get("percentage", 0.0))
            max_copay = copay_config[benefit_copay_key].get("max_per_visit")
            
            if copay_percentage > 0 and base_covered > 0:
                copay_amount = base_covered * (copay_percentage / 100.0)
                if max_copay is not None:
                    copay_amount = min(copay_amount, float(max_copay))
                base_covered -= copay_amount
                
        # Apply benefit annual/lifetime limit
        rem_annual = self.remaining_annual_limits[b_type]
        final_covered = min(base_covered, rem_annual)
        
        # Check if limited by annual limit
        is_limited_by_annual = base_covered > rem_annual
        
        # Update remaining limits
        self.remaining_annual_limits[b_type] -= final_covered
        
        if sub_name in self.remaining_sub_limits[b_type]:
            self.remaining_sub_limits[b_type][sub_name] -= final_covered
            
        if sub_name in self.remaining_visits[b_type] and self.remaining_visits[b_type][sub_name] > 0:
            self.remaining_visits[b_type][sub_name] -= 1
            
        # Compute final amounts
        result["covered_amount"] = final_covered
        result["copay_amount"] = copay_amount
        result["deductible_applied"] = deductible_applied
        result["member_pays"] = submitted_amount - final_covered
        
        # Determine decision and detailed reasoning
        if final_covered == submitted_amount:
            result["decision"] = "FULLY_COVERED"
            result["reason"] = f"Claim fully covered. Approved amount: {final_covered:.0f} THB."
        elif final_covered > 0:
            result["decision"] = "PARTIALLY_COVERED"
            reasons = []
            if submitted_amount > float(limit_per_unit):
                reasons.append(f"Sub-limit per visit/day of {limit_per_unit:.0f} THB applied")
            if deductible_applied > 0:
                reasons.append(f"Deductible applied: {deductible_applied:.0f} THB")
            if copay_amount > 0:
                reasons.append(f"{copay_percentage:.0f}% copay applied ({copay_amount:.0f} THB)")
            if is_limited_by_annual:
                reasons.append(f"Limited by remaining benefit balance of {rem_annual:.0f} THB")
            result["reason"] = ", ".join(reasons) + "."
        else:
            result["decision"] = "DENIED"
            reasons = []
            if deductible_applied > 0 and base_covered == 0:
                reasons.append(f"Submitted amount went fully towards remaining deductible ({deductible_applied:.0f} THB)")
            if is_limited_by_annual and rem_annual <= 0:
                reasons.append("Benefit annual limit is fully exhausted")
            if not reasons:
                reasons.append("Claim denied due to limit restrictions")
            result["reason"] = ", ".join(reasons) + "."
            
        # Add remaining trackers for context
        result["remaining_annual_limit"] = self.remaining_annual_limits[b_type]
        if sub_name in self.remaining_visits[b_type]:
            result["remaining_visit_limit"] = self.remaining_visits[b_type][sub_name]
            
        return result
        
    def get_summary(self):
        summary = {
            "remaining_global_deductible": self.remaining_deductible,
            "remaining_annual_limits": self.remaining_annual_limits,
            "remaining_sub_limits": self.remaining_sub_limits,
            "remaining_visits": self.remaining_visits
        }
        return summary
