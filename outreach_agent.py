import os
import logging
from firewall import run_firewall_checks
from database import log_audit
from executor import create_razorpay_payment_link
from whatsapp_service import send_whatsapp_recovery_message

logger = logging.getLogger("webhook-listener")

def evaluate_outreach_strategy(payment_id: str, amount: int, email: str, phone: str, error_code: str) -> dict:
    """
    Outreach Agent Decision Layer:
    Determines optimal communication channel, consent validity, and approval status.
    """
    firewall = run_firewall_checks(payment_id, amount, email, phone)
    
    # 1. Check Spam Cooldown
    if not firewall["anti_spam_passed"]:
        return {
            "decision": "BLOCK",
            "channel": "NONE",
            "reason": "Outreach suppressed: 24-hour anti-spam cooldown active for this customer.",
            "status": "FAILED",
            "firewall": firewall
        }
        
    # 2. Check Noise Floor
    if firewall["amount_status"] == "TOO_LOW":
        return {
            "decision": "BLOCK",
            "channel": "NONE",
            "reason": f"Amount (₹{amount/100:.2f}) is below minimum threshold of ₹10.00.",
            "status": "FAILED",
            "firewall": firewall
        }
        
    # 3. Check High-Value Threshold (Human Approval required)
    if firewall["amount_status"] == "TOO_HIGH":
        return {
            "decision": "REVIEW",
            "channel": "WHATSAPP_EMAIL",
            "reason": f"High-value transaction (₹{amount/100:,.2f}) exceeds auto-pilot threshold (₹{firewall['high_value_threshold']:,}). Human review required.",
            "status": "APPROVAL_REQUIRED",
            "firewall": firewall
        }
        
    # 4. Determine Channel based on Phone Availability & Opt-In
    if firewall["whatsapp_opted_in"] and phone and str(phone).strip() not in ("", "Phone number unavailable"):
        preferred_channel = "WHATSAPP"
        reason = f"Customer verified with active phone ({phone}); 1-click UPI WhatsApp recovery selected."
    elif firewall["consent_passed"]:
        preferred_channel = "EMAIL"
        reason = "Phone number unavailable or not opted in; falling back to authorized email channel."
    else:
        return {
            "decision": "BLOCK",
            "channel": "NONE",
            "reason": "Customer has neither a valid phone number nor email consent for recovery outreach.",
            "status": "FAILED",
            "firewall": firewall
        }
        
    return {
        "decision": "ALLOW",
        "channel": preferred_channel,
        "reason": reason,
        "status": "READY",
        "firewall": firewall
    }

async def execute_agent_outreach(
    payment_id: str,
    amount: int,
    currency: str,
    name: str,
    email: str,
    phone: str,
    draft_subject: str,
    draft_body: str,
    whatsapp_copy: str = None
) -> dict:
    """
    Executes the Outreach Agent plan across verified communication channels:
    - Generates Razorpay payment link
    - Dispatches WhatsApp Business message (Real or Simulated)
    - Records audit trails with authentic lifecycle status (SENT, SIMULATED, FAILED)
    """
    # 1. Generate Secure Payment Retry Link
    payment_link = create_razorpay_payment_link(payment_id, amount, currency, name, email, phone)
    
    # 2. Evaluate Strategy
    strategy = evaluate_outreach_strategy(payment_id, amount, email, phone, "PAYMENT_FAILED")
    
    results = {
        "payment_id": payment_id,
        "payment_link": payment_link,
        "strategy": strategy,
        "whatsapp_result": None,
        "email_result": None
    }
    
    # If High-Value Review or Blocked
    if strategy["decision"] != "ALLOW":
        logger.info(f"Outreach execution deferred for {payment_id}: Decision={strategy['decision']} ({strategy['reason']})")
        return results

    # 3. Execute WhatsApp Outreach if selected
    if strategy["channel"] in ("WHATSAPP", "WHATSAPP_EMAIL"):
        logger.info(f"Outreach Agent dispatching WhatsApp recovery message for {payment_id} to {phone}...")
        wa_res = await send_whatsapp_recovery_message(
            payment_id=payment_id,
            recipient_phone=phone,
            customer_name=name,
            amount_in_paisa=amount,
            payment_link=payment_link
        )
        results["whatsapp_result"] = wa_res

    # 4. Save Local Outbound Email record
    outbound_dir = "outbound_emails"
    os.makedirs(outbound_dir, exist_ok=True)
    file_path = os.path.join(outbound_dir, f"{payment_id}_email.txt")
    final_email_body = draft_body.format(payment_link=payment_link) if draft_body else f"Payment Link: {payment_link}"
    
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"TO: {email if email else 'No Email'}\n")
            f.write(f"PHONE: {phone if phone else 'No Phone'}\n")
            f.write(f"SUBJECT: {draft_subject}\n")
            f.write("="*60 + "\n")
            f.write(final_email_body)
        results["email_result"] = {"status": "SAVED", "path": file_path}
    except Exception as e:
        logger.error(f"Failed to write outbound email copy: {e}")

    # 5. Log Outreach Agent overall dispatch step
    log_audit(
        payment_id=payment_id,
        action_type="OUTBOUND_DISPATCH",
        decision="SUCCESS",
        details={
            "channel": strategy["channel"],
            "recipient_email": email,
            "recipient_phone": phone,
            "payment_url": payment_link,
            "whatsapp_status": results.get("whatsapp_result", {}).get("status", "NOT_CONFIGURED")
        }
    )
    
    return results
