import json
import csv
from generator import generate_fraud_dataset
from detector import FraudDetector

def run_fraud_analysis():
    print("1. Generating dataset with 10% embedded fraud...")
    generate_fraud_dataset()
    
    # Load dataset
    claims = []
    with open("claims.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            claims.append(row)
            
    print(f"2. Loaded {len(claims)} claims. Running analysis...")
    
    detector = FraudDetector()
    scored_results = detector.analyze_claims(claims)
    
    # Write to scored_claims.json
    with open("scored_claims.json", "w", encoding="utf-8") as f:
        json.dump(scored_results, f, indent=2)
        
    print("3. Saved results to 'scored_claims.json'. Calculating metrics...")
    
    # Risk threshold to classify as "Flagged Fraud"
    # A single triggered rule will have a minimum weight of 2, which gives risk_score = 20
    RISK_THRESHOLD = 20
    
    tp = 0
    fp = 0
    fn = 0
    tn = 0
    
    fraud_by_type = {}  # type -> (detected, total)
    
    for r in scored_results:
        is_actual_fraud = r["is_fraud_label"]
        fraud_type = r["fraud_type_label"]
        is_predicted_fraud = r["risk_score"] >= RISK_THRESHOLD
        
        # Track by type
        if is_actual_fraud:
            if fraud_type not in fraud_by_type:
                fraud_by_type[fraud_type] = [0, 0]
            fraud_by_type[fraud_type][1] += 1
            if is_predicted_fraud:
                fraud_by_type[fraud_type][0] += 1
                
        # Metrics confusion matrix
        if is_predicted_fraud and is_actual_fraud:
            tp += 1
        elif is_predicted_fraud and not is_actual_fraud:
            fp += 1
        elif not is_predicted_fraud and is_actual_fraud:
            fn += 1
        else:
            tn += 1
            
    # Computations
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    accuracy = (tp + tn) / len(scored_results)
    
    print("\n" + "="*80)
    print("FRAUD DETECTION METRICS REPORT")
    print("="*80)
    print(f"Total Claims Evaluated: {len(scored_results)}")
    print(f"True Positives (TP)   : {tp}")
    print(f"False Positives (FP)  : {fp}")
    print(f"False Negatives (FN)  : {fn}")
    print(f"True Negatives (TN)   : {tn}")
    print("-"*50)
    print(f"Recall (Sensitivity)  : {recall*100:.2f}%  (Target: >= 70%)")
    print(f"Precision             : {precision*100:.2f}%")
    print(f"False Positive Rate   : {fpr*100:.2f}%  (Target: <= 20%)")
    print(f"Overall Accuracy      : {accuracy*100:.2f}%")
    print("="*80)
    
    print("\nRECALL BY FRAUD PATTERN:")
    print("-" * 50)
    print(f"{'Fraud Pattern':<30} | {'Detected':<8} | {'Total':<5} | {'Recall':<6}")
    print("-" * 50)
    for f_type, counts in sorted(fraud_by_type.items()):
        det, tot = counts
        rec = (det / tot) if tot > 0 else 0.0
        print(f"{f_type:<30} | {det:<8} | {tot:<5} | {rec*100:.1f}%")
    print("="*80)

    # Output top 10 highest risk claims
    top_risky = sorted(scored_results, key=lambda x: x["risk_score"], reverse=True)[:10]
    print("\nTOP 10 HIGHEST RISK CLAIMS IDENTIFIED:")
    print("-" * 120)
    print(f"{'Claim ID':<15} | {'Member ID':<10} | {'Amount':<10} | {'Risk':<5} | {'Triggered Rules (Flags)'}")
    print("-" * 120)
    for r in top_risky:
        rules_triggered = ", ".join([f["rule"] for f in r["flags"]])
        print(f"{r['claim_id']:<15} | {r['member_id']:<10} | {r['submitted_amount']:<10.2f} | {r['risk_score']:<5} | {rules_triggered}")
    print("="*80)

if __name__ == "__main__":
    run_fraud_analysis()
