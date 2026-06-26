import json
from calculator import PolicyBenefitsCalculator

def run_calculator():
    # Load files
    with open("policy.json", "r", encoding="utf-8") as f:
        policy = json.load(f)
        
    with open("expenses.json", "r", encoding="utf-8") as f:
        expenses = json.load(f)
        
    # Sort expenses chronologically by date
    expenses.sort(key=lambda x: x["date"])
    
    # Initialize calculator
    calc = PolicyBenefitsCalculator(policy)
    
    results = []
    
    print("="*80)
    print("PROCESSING MEDICAL CLAIMS CHRONOLOGICALLY")
    print("="*80)
    print(f"{'ID':<9} | {'Date':<10} | {'Type':<10} | {'Amount':<10} | {'Covered':<10} | {'Decision':<18} | {'Reason'}")
    print("-"*120)
    
    for exp in expenses:
        res = calc.process_expense(exp)
        results.append(res)
        
        print(f"{res['expense_id']:<9} | {exp['date']:<10} | {exp['benefit_type']:<10} | {res['submitted_amount']:<10.0f} | {res['covered_amount']:<10.0f} | {res['decision']:<18} | {res['reason']}")
        
    # Write to output.json
    with open("output.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
        
    print("\n" + "="*80)
    print("FINAL POLICY BALANCE SUMMARY")
    print("="*80)
    summary = calc.get_summary()
    
    print(f"Remaining Global Deductible: {summary['remaining_global_deductible']:.0f} THB")
    print("\nBenefit Remaining Balances:")
    for b_type, bal in summary["remaining_annual_limits"].items():
        print(f" - {b_type:<12}: {bal:,.2f} THB")
        
    print("\nSub-benefit Remaining Limits:")
    for b_type, sub_dict in summary["remaining_sub_limits"].items():
        if sub_dict:
            print(f" - {b_type}:")
            for sub_name, limit in sub_dict.items():
                print(f"    * {sub_name:<20}: {limit:,.2f} THB")
                
    print("\nSub-benefit Remaining Visits/Days:")
    for b_type, visits_dict in summary["remaining_visits"].items():
        if visits_dict:
            print(f" - {b_type}:")
            for sub_name, visits in visits_dict.items():
                print(f"    * {sub_name:<20}: {visits} units")
                
    print("="*80)
    print("Processed list saved to 'output.json'.")

if __name__ == "__main__":
    run_calculator()
