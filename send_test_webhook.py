import hmac
import hashlib
import json
import urllib.request
import urllib.error
import time

# Config
WEBHOOK_URL = "http://127.0.0.1:8000/webhook"
TEST_SECRET = "my_super_secret_webhook_key"

def generate_signature(payload: bytes, secret: str) -> str:
    return hmac.new(
        key=secret.encode("utf-8"),
        msg=payload,
        digestmod=hashlib.sha256
    ).hexdigest()

def send_webhook(event_type: str, payment_id: str, amount: int, email: str = None, error_code: str = None, error_description: str = None):
    # Construct base entity depending on whether it's failed or captured
    payload_data = {
        "event": event_type,
        "payload": {
            "payment": {
                "entity": {
                    "id": payment_id,
                    "amount": amount,
                    "currency": "INR",
                }
            }
        }
    }
    
    entity = payload_data["payload"]["payment"]["entity"]
    
    if event_type == "payment.failed":
        entity["status"] = "failed"
        entity["error_code"] = error_code if error_code else "BAD_REQUEST_PAYMENT_DECLINED_BY_BANK"
        entity["error_description"] = error_description if error_description else "Insufficient funds"
        entity["email"] = email if email else "customer@example.com"
        entity["contact"] = "+919999999999"
    elif event_type == "payment.captured":
        entity["status"] = "captured"
        
    payload_bytes = json.dumps(payload_data).encode("utf-8")
    sig = generate_signature(payload_bytes, TEST_SECRET)
    
    headers = {
        "Content-Type": "application/json",
        "x-razorpay-signature": sig
    }
    
    req = urllib.request.Request(WEBHOOK_URL, data=payload_bytes, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as response:
            status_code = response.getcode()
            response_body = response.read().decode("utf-8")
            print(f"👉 Sent Event: {event_type} | ID={payment_id} | Amount=Rs.{amount/100:.2f}")
            print(f"   Response HTTP {status_code}: {response_body}")
    except urllib.error.HTTPError as e:
        status_code = e.getcode()
        response_body = e.read().decode("utf-8")
        print(f"👉 Sent Event: {event_type} | ID={payment_id} | Amount=Rs.{amount/100:.2f}")
        print(f"   Response HTTP {status_code}: {response_body}")

# Run the test suite
if __name__ == "__main__":
    print("=================== STARTING FIREWALL TEST SUITE ===================")
    
    # Test 1: Safe amount, consented user -> EXPECT: ALLOW & Outreach Generated
    print("\n--- Test 1: Normal payment failure (Should result in ALLOW & Outreach) ---")
    send_webhook("payment.failed", "pay_allow_001", 25000, email="customer@example.com") # Rs 250.00
    
    # Test 2: Amount is too low (Rs. 5) -> EXPECT: BLOCK (Too Low)
    print("\n--- Test 2: Micro payment failure (Should result in BLOCK - Too Low) ---")
    send_webhook("payment.failed", "pay_block_low", 500, email="customer@example.com") # Rs 5.00
    
    # Test 3: Customer email has 'no-consent' -> EXPECT: BLOCK (No Consent)
    print("\n--- Test 3: Non-consenting customer (Should result in BLOCK - No Consent) ---")
    send_webhook("payment.failed", "pay_block_consent", 35000, email="no-consent-user@example.com") # Rs 350.00
    
    # Test 4: High amount (Rs. 60,000) -> EXPECT: REVIEW (Human-in-the-loop)
    print("\n--- Test 4: High-value payment failure (Should result in REVIEW) ---")
    send_webhook("payment.failed", "pay_review_high", 6000000, email="wealthy-user@example.com") # Rs 60,000.00
    
    # Test 5: Anti-Spam Check
    print("\n--- Test 5: Anti-Spam Check ---")
    print("We will register outreach for 'spam-check@example.com' by inserting a mock log.")
    import sqlite3
    conn = sqlite3.connect("recovery_system.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO audit_logs (payment_id, action_type, decision, details, created_at)
        VALUES ('pay_spam_init', 'OUTBOUND_DISPATCH', 'SUCCESS', '{"email": "spam-check@example.com"}', ?)
    """, (time.strftime('%Y-%m-%dT%H:%M:%S'),))
    conn.commit()
    conn.close()
    
    # Send webhook with the same email
    send_webhook("payment.failed", "pay_spam_blocked", 25000, email="spam-check@example.com")
    
    # Test 6: Simulation of Recovery Success
    # Now we simulate the customer opening their email, clicking the link, and completing the payment!
    print("\n--- Test 6: Simulate Customer Paying the Link (Should result in RECOVERY) ---")
    print("Waiting 2 seconds for server to settle...")
    time.sleep(2)
    # We send a success event (payment.captured) for pay_allow_001 (which was the failed payment from Test 1)
    send_webhook("payment.captured", "pay_allow_001", 25000)
    
    print("\n=================== TESTS COMPLETE. CHECK DASHBOARD IN BROWSER ===================")
