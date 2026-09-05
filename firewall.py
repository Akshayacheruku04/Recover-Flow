import os
import sqlite3
from datetime import datetime, timedelta
from database import get_db_connection

# Dynamic Limits from Environment
MIN_RECOVERY_AMOUNT = int(os.getenv("MIN_RECOVERY_AMOUNT", 1000)) # 1000 paisa = Rs. 10.00
HIGH_VALUE_THRESHOLD_RUPEES = int(os.getenv("HIGH_VALUE_THRESHOLD", 50000))
MAX_AUTO_RECOVERY_AMOUNT = HIGH_VALUE_THRESHOLD_RUPEES * 100 # In paisa (e.g. 5,000,000 paisa = Rs. 50,000.00)

def check_customer_consent(email: str) -> bool:
    """
    Email Marketing / Recovery Outreach Consent Check.
    """
    if not email:
        return False
    if "no-consent" in email.lower():
        return False
    return True

def check_whatsapp_opt_in(phone: str, email: str = "") -> bool:
    """
    WhatsApp Specific Business Messaging Opt-In Verification.
    Validates whether the customer has explicitly opted-in to receive recovery alerts on WhatsApp.
    """
    if not phone:
        return False
    
    clean_phone = "".join(filter(str.isdigit, phone))
    if len(clean_phone) < 10:
        return False
        
    # Check explicit opt-out indicators in demo simulation
    if "no-optin" in phone.lower() or "no-whatsapp" in phone.lower() or (email and "no-whatsapp" in email.lower()):
        return False
        
    return True

def check_anti_spam(email: str, phone: str = "") -> bool:
    """
    Anti-Spam Check: Ensure we don't contact the same customer twice in 24 hours.
    Queries the SQLite 'audit_logs' table across both email and phone identifiers.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Calculate timestamp for 24 hours ago
    one_day_ago = (datetime.now() - timedelta(days=1)).isoformat()
    
    identifier = email if email else phone
    if not identifier:
        conn.close()
        return True

    cursor.execute("""
        SELECT COUNT(*) FROM audit_logs 
        WHERE (action_type = 'OUTBOUND_DISPATCH' OR action_type = 'WHATSAPP_DISPATCH') 
        AND created_at > ? 
        AND details LIKE ?
    """, (one_day_ago, f"%{identifier}%"))
    
    outreach_count = cursor.fetchone()[0]
    conn.close()
    
    return outreach_count == 0

def run_firewall_checks(payment_id: str, amount: int, email: str, phone: str = "") -> dict:
    """
    Runs comprehensive safety and privacy guardrail checks:
    1. Email Consent
    2. WhatsApp Opt-In
    3. 24h Anti-Spam Frequency Limit
    4. Amount Thresholds (Noise floor & High-value ceiling)
    """
    email_consent_passed = check_customer_consent(email)
    whatsapp_opted_in = check_whatsapp_opt_in(phone, email)
    anti_spam_passed = check_anti_spam(email, phone)
    
    if amount < MIN_RECOVERY_AMOUNT:
        amount_status = "TOO_LOW"
    elif amount > MAX_AUTO_RECOVERY_AMOUNT:
        amount_status = "TOO_HIGH"
    else:
        amount_status = "SAFE_RANGE"
        
    return {
        "consent_passed": email_consent_passed,
        "whatsapp_opted_in": whatsapp_opted_in,
        "anti_spam_passed": anti_spam_passed,
        "amount_status": amount_status,
        "amount": amount,
        "email": email,
        "phone": phone,
        "high_value_threshold": HIGH_VALUE_THRESHOLD_RUPEES
    }
