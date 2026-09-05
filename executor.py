import os
import logging
import razorpay
from database import log_audit

logger = logging.getLogger("webhook-listener")

# Load Razorpay API Keys from environment variables
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

# Initialize Razorpay Client if keys are available
razorpay_client = None
if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET:
    try:
        razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        logger.info("Razorpay Client successfully initialized with credentials.")
    except Exception as e:
        logger.error(f"Failed to initialize Razorpay Client: {e}")
else:
    logger.warning(
        "⚠️ RAZORPAY_KEY_ID or RAZORPAY_KEY_SECRET is not set. "
        "The system will generate mock payment links for local testing."
    )

def create_razorpay_payment_link(payment_id: str, amount: int, currency: str, name: str, email: str, phone: str) -> str:
    """
    Calls the Razorpay API to generate a unique checkout link for the customer.
    Falls back to a mock URL if API keys are missing.
    """
    if not razorpay_client:
        logger.info("Using mock Razorpay payment link (no API keys set).")
        return f"https://rzp.io/i/mock_{payment_id}"
        
    try:
        logger.info(f"Contacting Razorpay API to create payment link for {payment_id}...")
        
        # Razorpay expects contact details in a specific dictionary
        customer_details = {}
        if name:
            customer_details["name"] = name
        if email:
            customer_details["email"] = email
        if phone:
            customer_details["contact"] = phone
            
        # Call the Razorpay SDK to create a Payment Link
        payment_link = razorpay_client.payment_link.create({
            "amount": amount,                      # In paisa (e.g. 50000 for Rs. 500.00)
            "currency": currency,
            "accept_partial": False,               # Do not allow split payments
            "description": f"Recovery link for failed payment {payment_id}",
            "customer": customer_details,
            "notify": {
                "sms": False,                      # Set to False because our AI drafts and sends
                "email": False                     # custom notifications instead of default Razorpay emails
            },
            "reminder": {
                "enable": False                    # Disable default reminders so our AI controls outreach
            },
            "notes": {
                "system": "AI Revenue Recovery Agent",
                "original_payment_id": payment_id
            }
        })
        
        # Extract the short URL created by Razorpay
        short_url = payment_link.get("short_url")
        logger.info(f"Razorpay Payment Link generated successfully: {short_url}")
        return short_url
        
    except Exception as e:
        logger.error(f"Error creating Razorpay payment link: {e}. Falling back to mock URL.")
        return f"https://rzp.io/i/mock_fallback_{payment_id}"

def execute_recovery_outreach(payment_id: str, amount: int, currency: str, name: str, email: str, 
                              phone: str, draft_subject: str, draft_body: str) -> bool:
    """
    Executes the recovery outreach:
    1. Generates the payment link.
    2. Injects the link into the AI draft body.
    3. Simulates sending the email by saving it locally in 'outbound_emails/' folder.
    4. Writes a record to the database audit logs.
    """
    # 1. Generate the payment link
    payment_link = create_razorpay_payment_link(payment_id, amount, currency, name, email, phone)
    
    # 2. Inject the payment link into the email body
    final_body = draft_body.format(payment_link=payment_link)
    
    # 3. Simulate sending (save to file)
    outbound_dir = "outbound_emails"
    os.makedirs(outbound_dir, exist_ok=True)
    
    file_path = os.path.join(outbound_dir, f"{payment_id}_email.txt")
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"TO: {email if email else 'No Email Provided'}\n")
            f.write(f"PHONE: {phone if phone else 'No Phone Provided'}\n")
            f.write(f"SUBJECT: {draft_subject}\n")
            f.write("="*60 + "\n")
            f.write(final_body)
            
        logger.info(f"📧 Outreach email successfully dispatched (saved to {file_path})")
    except Exception as e:
        logger.error(f"Failed to write outbound email file: {e}")
        return False
        
    # 4. Log the dispatch to the Database Audit Trail
    # This acts as our source-of-truth for spam protection
    log_audit(
        payment_id=payment_id,
        action_type="OUTBOUND_DISPATCH",
        decision="SUCCESS",
        details={
            "email": email,
            "subject": draft_subject,
            "payment_url": payment_link
        }
    )
    
    return True
