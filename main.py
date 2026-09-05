import os
import hmac
import hashlib
import logging
import json
import random
from datetime import datetime, timedelta

# Import dotenv to load environment variables
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request, Response, status, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse

# Import database, safety, AI, and action engine functions
from database import (
    init_db, log_failed_payment, log_audit, mark_as_recovered, 
    get_stats, get_all_logs, get_db_connection, get_failed_payment
)
from decision_engine import evaluate_recovery_decision
from ai_agent import draft_recovery_message
from executor import RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, create_razorpay_payment_link
from outreach_agent import execute_agent_outreach, evaluate_outreach_strategy
from whatsapp_service import (
    send_whatsapp_recovery_message, is_whatsapp_configured,
    is_valid_phone, format_phone_e164, format_phone_display
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook-listener")

# Initialize database tables on server startup
init_db()

# Load secrets from environment variables
WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "recoverflow_verify_token_2026")

# Initialize the FastAPI application
app = FastAPI(
    title="RecoverFlow AI Revenue Recovery",
    description="Autonomous AI Agent to recover failed subscription and order payments with bounded guardrails & WhatsApp outreach.",
    version="2.1.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Signature verification helper for Razorpay
def verify_razorpay_signature(payload: bytes, signature: str, secret: str) -> bool:
    try:
        hash_object = hmac.new(
            key=secret.encode("utf-8"),
            msg=payload,
            digestmod=hashlib.sha256
        )
        expected_signature = hash_object.hexdigest()
        return hmac.compare_digest(expected_signature, signature)
    except Exception as e:
        logger.error(f"Error during signature verification: {e}")
        return False

# 1. Health check endpoint
@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    logger.info("Health check endpoint was called")
    return {
        "status": "ok", 
        "message": "RecoverFlow backend is running",
        "whatsapp_mode": "REAL" if is_whatsapp_configured() else "DEMO/SIMULATION"
    }

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. Web Dashboard UI (Merchant View)
@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    logger.info("Serving Merchant Dashboard UI")
    tmpl_path = os.path.join(BASE_DIR, "templates", "dashboard.html")
    try:
        with open(tmpl_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content, status_code=status.HTTP_200_OK)
    except FileNotFoundError:
        return HTMLResponse(
            content="<h1>Dashboard Template Not Found</h1><p>Ensure templates/dashboard.html exists.</p>",
            status_code=status.HTTP_404_NOT_FOUND
        )

# 3. Customer Storefront (Customer Subscription View)
@app.get("/shop", response_class=HTMLResponse)
async def serve_shop():
    logger.info("Serving Customer Storefront UI")
    tmpl_path = os.path.join(BASE_DIR, "templates", "shop.html")
    try:
        with open(tmpl_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content, status_code=status.HTTP_200_OK)
    except FileNotFoundError:
        return HTMLResponse(
            content="<h1>Storefront Template Not Found</h1><p>Ensure templates/shop.html exists.</p>",
            status_code=status.HTTP_404_NOT_FOUND
        )

# 4. API Endpoint to Create a Razorpay Order dynamically for Storefront Checkout
@app.post("/api/create-order")
async def create_order(request: Request):
    try:
        body = await request.json()
        amount = int(body.get("amount", 899900)) # in paisa (e.g. 899900 = Rs. 8,999)
        item_name = str(body.get("product_name", body.get("plan_name", "Syntex Premium Product")))
        customer_name = str(body.get("customer_name", "Alex Mercer"))
        customer_email = str(body.get("customer_email", f"alex.mercer_{int(os.times().elapsed * 100) % 9000 + 1000}@example.com"))
        
        raw_phone = body.get("customer_phone")
        customer_phone = format_phone_e164(raw_phone) if is_valid_phone(raw_phone) else (str(raw_phone).strip() if raw_phone else None)
    except Exception:
        amount = 899900
        item_name = "Syntex Premium Product"
        customer_name = "Alex Mercer"
        customer_email = "alex.mercer@example.com"
        customer_phone = None

    logger.info(f"Creating Razorpay Order for '{item_name}' (Amount: Rs. {amount/100:.2f}) for customer '{customer_name}' (Phone: {customer_phone or 'Unavailable'})...")
    
    notes_dict = {
        "customer_name": customer_name,
        "customer_email": customer_email,
        "product_name": item_name,
        "plan": item_name
    }
    if customer_phone:
        notes_dict["customer_phone"] = customer_phone

    if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET:
        try:
            import razorpay
            client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
            order_data = client.order.create({
                "amount": amount,
                "currency": "INR",
                "receipt": f"rcpt_{int(os.times().elapsed * 1000)}",
                "notes": notes_dict
            })
            logger.info(f"Order created successfully: {order_data.get('id')} for {item_name}")
            return {
                "order_id": order_data.get("id"),
                "amount": amount,
                "key_id": RAZORPAY_KEY_ID,
                "product_name": item_name,
                "customer_name": customer_name,
                "customer_email": customer_email,
                "customer_phone": customer_phone
            }
        except Exception as e:
            logger.error(f"Failed to create order via Razorpay SDK: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    else:
        logger.warning("No Razorpay API Keys set. Using fallback mock order ID.")
        return {
            "order_id": f"order_mock_{int(os.times().elapsed * 1000)}",
            "amount": amount,
            "key_id": "rzp_test_placeholder",
            "product_name": item_name,
            "customer_name": customer_name,
            "customer_email": customer_email,
            "customer_phone": customer_phone
        }

# 5. API Statistics Endpoint (Used by Merchant Dashboard)
@app.get("/api/stats")
async def fetch_dashboard_stats():
    stats_data = get_stats()
    logs_data = get_all_logs()
    return {
        "stats": stats_data,
        "logs": logs_data
    }

# 5b. Single Payment Detail Endpoint
@app.get("/api/payment/{payment_id}")
async def get_payment_details(payment_id: str):
    rec = get_failed_payment(payment_id)
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment record not found")
    return rec

# 6. Batch Simulation Endpoint (Show Measured Money Recovered across Multi-Customer Batch)
@app.post("/api/simulate-batch")
async def simulate_batch_recovery():
    logger.info("Executing Batch Recovery Simulation across multi-customer batch...")
    
    sample_customers = [
        ("Rohan Sharma", "rohan.sharma@example.com", "+919876501234", 899900, "Syntex ANC Wireless Headphones", "BAD_REQUEST_PAYMENT_TIMED_OUT", "HDFC 3D-Secure timeout during OTP verification", True),
        ("Priya Patel", "priya.patel@example.com", "+919823456789", 549900, "Syntex Chrono Pro Smartwatch", "EXPIRED_CARD", "Customer credit card expired", True),
        ("Ananya Sen", "ananya.sen@example.com", "+919812345678", 249900, "Syntex GaN 65W Rapid Charger", "INSUFFICIENT_FUNDS", "Account balance below subscription threshold", True),
        ("Vikram Malhotra", "vikram.m@enterprise.com", "+919988776655", 6000000, "Syntex Enterprise Hardware Kit", "BAD_REQUEST_ERROR", "Bank transaction limit exceeded for corporate account", False),
        ("Rahul Verma", "rahul.no-consent@example.com", "+919765432100", 699900, "Syntex Studio Mechanical Keyboard", "INSUFFICIENT_FUNDS", "Customer opted out of notifications", False),
        ("Siddharth Rao", "siddharth.r@example.com", None, 219900, "Syntex Precision Ergonomic Mouse", "BAD_REQUEST_PAYMENT_TIMED_OUT", "SBI netbanking gateway unresponsive", True),
        ("Sneha Kulkarni", "sneha.k@example.com", "+919321098765", 899900, "Syntex ANC Wireless Headphones", "BAD_REQUEST_PAYMENT_TIMED_OUT", "ICICI UPI gateway connection dropped", True),
        ("Aarav Mehta", "aarav.m@example.com", "+919109876543", 549900, "Syntex Chrono Pro Smartwatch", "EXPIRED_CARD", "Card expired on renewal cycle", True),
    ]

    for name, email, phone, amount, plan, err_code, err_desc, will_recover in sample_customers:
        pid = f"pay_batch_{random.randint(100000, 999999)}"
        
        # 1. Log Payment
        log_failed_payment(pid, amount, "INR", err_code, err_desc, name, email, phone)
        log_audit(pid, "WEBHOOK_RECEIVED", "ALLOW", {"event": "payment.failed", "amount": amount, "error_code": err_code})
        
        # 2. Evaluate Firewall & Outreach Strategy
        decision = evaluate_recovery_decision(pid, amount, email, phone or "")
        
        # 3. AI Root Cause Drafting if ALLOW/REVIEW
        if decision["decision"] in ["ALLOW", "REVIEW"]:
            draft = draft_recovery_message(name, err_code, err_desc, amount, plan)
            log_audit(pid, "AI_DRAFTING", decision["decision"], {
                "diagnosis": draft.get("root_cause_diagnosis"),
                "strategy": draft.get("recommended_strategy"),
                "subject": draft["subject"],
                "body": draft["body"],
                "whatsapp_copy": draft.get("whatsapp_sms_copy")
            })
            
            if decision["decision"] == "ALLOW":
                mock_url = f"https://rzp.io/i/recov_{pid[4:]}"
                
                # Check if phone is available for WhatsApp dispatch
                if phone and is_valid_phone(phone):
                    log_audit(pid, "WHATSAPP_DISPATCH", "SIMULATED", {
                        "channel": "WhatsApp Business Cloud API (Simulated)",
                        "recipient": phone,
                        "template": "payment_recovery",
                        "payment_url": mock_url,
                        "status": "SIMULATED",
                        "is_simulated": True
                    })
                else:
                    log_audit(pid, "WHATSAPP_DISPATCH", "BLOCKED", {
                        "channel": "WhatsApp Business Cloud API",
                        "reason": "Phone number unavailable",
                        "recipient": "Phone number unavailable",
                        "status": "BLOCKED",
                        "is_simulated": True
                    })

                log_audit(pid, "OUTBOUND_DISPATCH", "SUCCESS", {
                    "email": email,
                    "phone": phone or "Phone number unavailable",
                    "subject": draft["subject"],
                    "payment_url": mock_url,
                    "channel": "WhatsApp + Email" if phone else "Email (Fallback)"
                })
                
                # 4. If marked for recovery, simulate customer paying on recovery link
                if will_recover:
                    mark_as_recovered(pid)
                    log_audit(pid, "RECOVERY_DETECTED", "SUCCESS", {"event": "payment.captured", "recovery_rail": "1-Click UPI (WhatsApp Link)" if phone else "Email Payment Link"})

    return {"status": "success", "message": f"Successfully simulated recovery across batch of {len(sample_customers)} transactions!"}

# 7. Human-in-the-Loop Manual Approval Endpoint
@app.post("/api/approve-recovery")
async def approve_recovery(request: Request):
    data = await request.json()
    payment_id = data.get("payment_id")
    edited_subject = data.get("subject")
    edited_body = data.get("body")
    
    logger.info(f"Human Merchant approved high-value outreach for payment: {payment_id}")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT amount, currency, customer_name, customer_email, customer_phone FROM failed_payments WHERE payment_id = ?", (payment_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        amount, currency, name, email, phone = row
    else:
        amount = 6000000
        currency = "INR"
        name = "Enterprise Customer"
        email = f"customer_{payment_id}@example.com"
        phone = None
    
    if not edited_subject or not edited_body:
        draft = draft_recovery_message(name or "Enterprise Customer", "MANUAL_APPROVAL", "Merchant approved recovery", amount, "Enterprise Hardware Kit")
        edited_subject = edited_subject or draft["subject"]
        edited_body = edited_body or draft["body"]
        
    payment_link = create_razorpay_payment_link(payment_id, amount, currency, name or "Customer", email or "", phone or "")
    
    # 1. Send WhatsApp Outreach (Real or Simulated) if phone is valid
    if phone and is_valid_phone(phone):
        wa_res = await send_whatsapp_recovery_message(
            payment_id=payment_id,
            recipient_phone=phone,
            customer_name=name,
            amount_in_paisa=amount,
            payment_link=payment_link
        )
        wa_status = wa_res.get("status", "SIMULATED")
    else:
        wa_status = "BLOCKED (Phone unavailable)"
        log_audit(
            payment_id=payment_id,
            action_type="WHATSAPP_DISPATCH",
            decision="BLOCKED",
            details={
                "channel": "WhatsApp Business Cloud API",
                "reason": "Phone number unavailable",
                "recipient": "Phone number unavailable",
                "status": "BLOCKED",
                "is_simulated": True
            }
        )
    
    # 2. Log Approval and Dispatch in Audit Trail
    log_audit(
        payment_id=payment_id,
        action_type="MANUAL_APPROVAL",
        decision="SUCCESS",
        details={
            "approved_by": "Merchant Admin",
            "subject": edited_subject,
            "body": edited_body,
            "channel": "WhatsApp + Email" if phone else "Email",
            "whatsapp_status": wa_status,
            "recipient_phone": phone or "Phone number unavailable",
            "note": "High-value outreach manually authorized and dispatched"
        }
    )
    
    # 3. Mark payment as recovered upon successful authorization
    mark_as_recovered(payment_id)
    log_audit(
        payment_id=payment_id,
        action_type="RECOVERY_DETECTED",
        decision="SUCCESS",
        details={
            "event": "payment.captured",
            "recovery_rail": "WhatsApp Authorized Recovery Link" if phone else "Email Payment Link",
            "note": "Payment recovered following merchant manual authorization"
        }
    )
    
    return {"status": "success", "message": f"Outreach for {payment_id} approved and marked as recovered!"}

# 8. Human-in-the-Loop Rejection Endpoint
@app.post("/api/reject-recovery")
async def reject_recovery(request: Request):
    data = await request.json()
    payment_id = data.get("payment_id")
    reason = data.get("reason", "Rejected by merchant operator.")
    
    logger.info(f"Human Merchant rejected recovery for payment: {payment_id}")
    
    log_audit(
        payment_id=payment_id,
        action_type="MANUAL_REJECTION",
        decision="BLOCK",
        details={
            "rejected_by": "Merchant Admin",
            "reason": reason
        }
    )
    
    return {"status": "success", "message": f"Recovery for {payment_id} rejected."}

# 9. Meta WhatsApp Webhook Endpoints (Challenge Verification & Status Callbacks)
@app.get("/webhook/whatsapp")
async def verify_whatsapp_webhook(
    mode: str = Query(None, alias="hub.mode"),
    token: str = Query(None, alias="hub.verify_token"),
    challenge: str = Query(None, alias="hub.challenge")
):
    """
    Verification endpoint called by Meta when configuring WhatsApp Business Webhook in Meta App Dashboard.
    """
    if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
        logger.info("WhatsApp webhook challenge verified successfully with Meta!")
        return PlainTextResponse(content=challenge, status_code=200)
    else:
        logger.warning("WhatsApp webhook verification token mismatch.")
        raise HTTPException(status_code=403, detail="Verification token mismatch")

@app.post("/webhook/whatsapp")
async def handle_whatsapp_status_webhook(request: Request):
    """
    Receives real-time delivery status callbacks from Meta (e.g. sent -> delivered -> read).
    """
    try:
        body = await request.json()
        logger.info(f"Received WhatsApp Status Webhook: {json.dumps(body)}")
        
        # Extract status event if present
        entry = body.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        statuses = value.get("statuses", [])
        
        for st in statuses:
            msg_id = st.get("id")
            recipient = st.get("recipient_id")
            delivery_status = st.get("status") # sent, delivered, read, failed
            timestamp = st.get("timestamp")
            
            logger.info(f"WhatsApp Message {msg_id} status updated to: {delivery_status.upper()}")
            
            log_audit(
                payment_id=f"wa_{msg_id[-8:]}",
                action_type="WHATSAPP_STATUS_UPDATE",
                decision=delivery_status.upper(),
                details={
                    "message_id": msg_id,
                    "recipient": recipient,
                    "status": delivery_status.upper(),
                    "timestamp": timestamp
                }
            )
            
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error handling WhatsApp status webhook: {e}")
        return {"status": "error", "message": str(e)}

# 10. Razorpay Webhook Listener Endpoint
@app.post("/webhook", status_code=status.HTTP_200_OK)
async def handle_webhook(request: Request):
    logger.info("Received a new Razorpay webhook request")

    body_bytes = await request.body()
    
    try:
        body_str = body_bytes.decode("utf-8")
    except Exception as e:
        logger.error(f"Failed to decode request body: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to decode request payload"
        )

    signature = request.headers.get("x-razorpay-signature")
    
    if WEBHOOK_SECRET:
        if not signature:
            logger.warning("Rejecting request: Missing signature header.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Missing webhook signature"
            )
        
        is_valid = verify_razorpay_signature(body_bytes, signature, WEBHOOK_SECRET)
        if not is_valid:
            logger.warning("Rejecting request: Invalid signature verification failed.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Invalid webhook signature"
            )
        logger.info("Webhook signature verified successfully!")
    else:
        logger.warning("⚠️ RAZORPAY_WEBHOOK_SECRET is not set. Skipping signature check.")

    try:
        payload = json.loads(body_str)
    except Exception as e:
        logger.error(f"Failed to parse JSON body: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )

    event_type = payload.get("event")
    logger.info(f"Processing event: {event_type}")

    payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
    payment_id = payment_entity.get("id")
    
    if not payment_id:
        logger.warning("No payment ID found in payload. Skipping.")
        return {"status": "ignored", "reason": "No payment ID"}

    # Handle scenario 1: Payment failed
    if event_type == "payment.failed":
        amount = payment_entity.get("amount", 0)
        currency = payment_entity.get("currency", "INR")
        error_code = payment_entity.get("error_code", "UNKNOWN_ERROR")
        error_description = payment_entity.get("error_description", "No details provided")
        email = payment_entity.get("email")
        
        # Safely extract contact and notes without inventing fake phone numbers
        notes = payment_entity.get("notes") or {}
        raw_contact = payment_entity.get("contact")
        if not raw_contact and isinstance(notes, dict):
            raw_contact = notes.get("customer_phone") or notes.get("contact")
            
        phone = format_phone_e164(raw_contact) if is_valid_phone(raw_contact) else None
        
        name = None
        plan_name = "Syntex Product"
        if isinstance(notes, dict):
            name = notes.get("customer_name")
            if notes.get("product_name") or notes.get("plan"):
                plan_name = notes.get("product_name") or notes.get("plan")

        # In Sandbox test mode, map void@razorpay.com to a unique virtual email per payment ID
        if email == "void@razorpay.com" or not email:
            email = f"customer_{payment_id}@example.com"

        # 1. Save to SQLite Database
        log_failed_payment(
            payment_id=payment_id,
            amount=amount,
            currency=currency,
            error_code=error_code,
            error_description=error_description,
            name=name,
            email=email,
            phone=phone
        )
        
        # 2. Log receipt in the Audit Trail
        log_audit(
            payment_id=payment_id,
            action_type="WEBHOOK_RECEIVED",
            decision="ALLOW",
            details={
                "event": event_type,
                "amount": amount,
                "error_code": error_code
            }
        )
        logger.info(f"Logged payment failure {payment_id} to database.")

        # 3. RUN RISK FIREWALL & DECISION ENGINE (Checking WhatsApp Opt-in & High-value ceiling)
        decision_result = evaluate_recovery_decision(payment_id, amount, email, phone)
        logger.info(f"Decision Engine Result: {decision_result['decision']} - Reason: {decision_result['reason']}")

        # 4. Handle recovery outreach next actions based on the decision
        if decision_result["decision"] == "ALLOW":
            logger.info("Outreach ALLOWED. Engaging AI Reasoning & Outreach Layer...")
            
            draft = draft_recovery_message(
                customer_name=name,
                error_code=error_code,
                error_description=error_description,
                amount_in_paisa=amount,
                plan_name=plan_name
            )
            
            # Log AI Diagnosis in Audit Trail
            log_audit(
                payment_id=payment_id,
                action_type="AI_DRAFTING",
                decision="SUCCESS",
                details={
                    "diagnosis": draft.get("root_cause_diagnosis"),
                    "strategy": draft.get("recommended_strategy"),
                    "subject": draft["subject"],
                    "body": draft["body"],
                    "whatsapp_copy": draft.get("whatsapp_sms_copy")
                }
            )
            
            # 5. TRIGGER OUTREACH AGENT (WhatsApp Business Cloud API + Email)
            logger.info("Dispatching recovery outreach via Outreach Agent...")
            await execute_agent_outreach(
                payment_id=payment_id,
                amount=amount,
                currency=currency,
                name=name,
                email=email,
                phone=phone,
                draft_subject=draft["subject"],
                draft_body=draft["body"],
                whatsapp_copy=draft.get("whatsapp_sms_copy")
            )
            
        elif decision_result["decision"] == "REVIEW":
            logger.warning("Outreach Flagged for REVIEW. Drafting AI response for merchant manual approval...")
            draft = draft_recovery_message(
                customer_name=name,
                error_code=error_code,
                error_description=error_description,
                amount_in_paisa=amount,
                plan_name=plan_name
            )
            log_audit(
                payment_id=payment_id,
                action_type="AI_DRAFTING",
                decision="REVIEW",
                details={
                    "diagnosis": draft.get("root_cause_diagnosis"),
                    "strategy": draft.get("recommended_strategy"),
                    "subject": draft["subject"],
                    "body": draft["body"],
                    "whatsapp_copy": draft.get("whatsapp_sms_copy"),
                    "status": "APPROVAL_REQUIRED",
                    "note": f"Transaction exceeds auto-pilot threshold. Merchant approval required before WhatsApp dispatch."
                }
            )
            
        elif decision_result["decision"] == "BLOCK":
            logger.warning("Outreach BLOCKED by safety firewall. No outreach will be triggered.")

    # Handle scenario 2: Customer paid successfully later (Closing Recovery Loop)
    elif event_type in ["payment.captured", "order.paid"]:
        mark_as_recovered(payment_id)
        
        log_audit(
            payment_id=payment_id,
            action_type="RECOVERY_DETECTED",
            decision="SUCCESS",
            details={
                "event": event_type,
                "recovery_rail": "Razorpay Completed Checkout"
            }
        )
        logger.info(f"Payment recovery {payment_id} successfully confirmed and marked as RECOVERED.")

    else:
        logger.info(f"Event type '{event_type}' received but not configured for recovery processing.")

    return {"status": "success", "message": f"Webhook processed: {event_type}"}
