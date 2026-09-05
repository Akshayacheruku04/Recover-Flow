from firewall import run_firewall_checks
from database import log_audit

def evaluate_recovery_decision(payment_id: str, amount: int, email: str, phone: str = "") -> dict:
    """
    Evaluates the risk firewall checks and determines the final action:
    - ALLOW: Proceed with AI recovery outreach automatically.
    - REVIEW: High-value transaction. Draft outreach, but wait for manual approval.
    - BLOCK: Discard request due to safety/anti-spam/consent failures.
    """
    # 1. Run all firewall checks including WhatsApp opt-in
    checks = run_firewall_checks(payment_id, amount, email, phone)
    
    decision = "ALLOW"
    reason = "All safety and privacy checks passed."
    
    # 2. Check rules sequentially
    if not checks["consent_passed"] and not checks["whatsapp_opted_in"]:
        decision = "BLOCK"
        reason = "Customer has not consented to WhatsApp or Email recovery communications."
        
    elif checks["amount_status"] == "TOO_LOW":
        decision = "BLOCK"
        reason = f"Transaction amount (₹{amount / 100:.2f}) is below the minimum noise floor of ₹10.00."

    elif checks["amount_status"] == "TOO_HIGH":
        decision = "REVIEW"
        reason = f"High-value payment (₹{amount / 100:,.2f}) exceeds auto-pilot ceiling of ₹{checks['high_value_threshold']:,}. Human review required."
        
    elif not checks["anti_spam_passed"]:
        decision = "BLOCK"
        reason = "Outreach suppressed: 24-hour frequency limit reached for this customer."
        
    # 3. Write decision to Database Audit Trail
    log_audit(
        payment_id=payment_id,
        action_type="RISK_FIREWALL",
        decision=decision,
        details={
            "reason": reason,
            "firewall_results": checks
        }
    )
    
    return {
        "payment_id": payment_id,
        "decision": decision,
        "reason": reason,
        "checks": checks
    }
