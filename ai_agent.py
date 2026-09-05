import os
import json
import logging
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger("webhook-listener")

# Retrieve API key from environment variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

genai_client = None
if GEMINI_API_KEY and GEMINI_API_KEY.startswith("AIzaSy"):
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        genai_client = genai
        logger.info("Google Gemini AI Client successfully configured with active API key.")
    except Exception as e:
        logger.warning(f"Could not initialize Google GenAI SDK: {e}")
else:
    logger.info("Using Advanced Multi-Signal Local AI Reasoning Engine for recovery generation.")


def generate_intelligent_local_reasoning(
    customer_name: str, 
    error_code: str, 
    error_description: str, 
    amount_in_paisa: int,
    plan_name: str = "Pro Plan"
) -> dict:
    """
    Advanced Multi-Signal AI Reasoning Engine that diagnoses payment failures,
    determines the optimal recovery rail, and generates customized multi-channel messaging.
    """
    name = customer_name if customer_name else "Valued Customer"
    amount_rupees = f"₹{amount_in_paisa / 100:,.2f}"
    err_lower = f"{error_code} {error_description}".lower()
    
    # 1. Root Cause Diagnosis & Strategic Intervention Selector
    if "insufficient" in err_lower or "balance" in err_lower:
        diagnosis = "Transaction declined due to insufficient account balance or preset card spending limit."
        strategy = "Non-intrusive reminder; suggest instant UPI or alternate bank card; offer grace period."
        subject = f"Quick update regarding your {plan_name} payment ({amount_rupees})"
        body = (
            f"Hi {name},\n\n"
            f"We noticed that your recent payment of {amount_rupees} for {plan_name} was declined by your bank due to account limits or insufficient balance.\n\n"
            f"To ensure your service continues without any interruption, we've set up a fast, secure payment link where you can retry using UPI (Google Pay, PhonePe), net banking, or another card:\n\n"
            f"👉 {{payment_link}}\n\n"
            f"If you need more time or have questions, simply reply directly to this email.\n\n"
            f"Best regards,\n"
            f"Synthex Customer Success Team"
        )
        whatsapp_copy = (
            f"Hey {name}! 👋 Your {plan_name} renewal ({amount_rupees}) was declined by your bank. "
            f"No worries—you can resume instantly via UPI/GPay here: {{payment_link}}"
        )

    elif "expired" in err_lower or "expire" in err_lower:
        diagnosis = "Card on file has reached its expiration date and was rejected by the issuing bank."
        strategy = "Card updater flow; emphasize uninterrupted service and zero downtime."
        subject = f"Action Required: Please update your payment card for {plan_name}"
        body = (
            f"Hi {name},\n\n"
            f"Your bank declined the recent {amount_rupees} invoice for {plan_name} because your card appears to have expired.\n\n"
            f"Please update your card details or select an alternative payment method using your secure link below:\n\n"
            f"👉 {{payment_link}}\n\n"
            f"Once updated, your active cluster will remain online with zero downtime.\n\n"
            f"Warm regards,\n"
            f"Synthex Billing Operations"
        )
        whatsapp_copy = (
            f"Hi {name}, your card on file for {plan_name} has expired. "
            f"Update your payment details here to keep your cluster active: {{payment_link}}"
        )

    elif "timeout" in err_lower or "network" in err_lower or "bank" in err_lower or "bad_request" in err_lower:
        diagnosis = "Temporary 3D-Secure authentication timeout or bank server network latency."
        strategy = "Reassure customer; explain bank outage; recommend UPI QR code as reliable bypass."
        subject = f"Temporary bank network timeout on your {plan_name} order"
        body = (
            f"Hi {name},\n\n"
            f"It looks like your bank experienced a temporary connection timeout while authenticating your {amount_rupees} payment for {plan_name}.\n\n"
            f"You don't need to enter your card numbers again. You can complete the checkout in 10 seconds via UPI (GPay/PhonePe/Paytm) or Netbanking here:\n\n"
            f"👉 {{payment_link}}\n\n"
            f"We're keeping your order active in the meantime.\n\n"
            f"Thank you,\n"
            f"Synthex Autonomous Cloud"
        )
        whatsapp_copy = (
            f"Hey {name}! Aapka bank server timeout ho gaya tha. "
            f"Aap 1-click UPI se yahan easily complete kar sakte hain: {{payment_link}}"
        )
    else:
        diagnosis = f"Bank returned generic decline code ({error_code}): {error_description}"
        strategy = "Helpful multi-rail payment fallback with standard support escalation."
        subject = f"Assistance with your recent {plan_name} payment ({amount_rupees})"
        body = (
            f"Hi {name},\n\n"
            f"We encountered a bank processing error while completing your recent transaction of {amount_rupees} for {plan_name}.\n\n"
            f"You can securely retry your payment using your preferred payment method (UPI, Cards, or Netbanking) at this link:\n\n"
            f"👉 {{payment_link}}\n\n"
            f"If you need any assistance, our priority engineering support is on standby.\n\n"
            f"Best regards,\n"
            f"Synthex Operations"
        )
        whatsapp_copy = (
            f"Hello {name}, your {plan_name} payment could not be processed. "
            f"Please complete your invoice securely here: {{payment_link}}"
        )

    return {
        "root_cause_diagnosis": diagnosis,
        "recommended_strategy": strategy,
        "subject": subject,
        "body": body,
        "whatsapp_sms_copy": whatsapp_copy
    }


def draft_recovery_message(
    customer_name: str, 
    error_code: str, 
    error_description: str, 
    amount_in_paisa: int,
    plan_name: str = "Pro Plan"
) -> dict:
    """
    Drafts a deeply personalized, empathetic outreach message using Google Gemini 1.5 Flash
    with fallback to the advanced multi-signal local reasoning engine.
    """
    amount_formatted = f"{amount_in_paisa / 100:,.2f}"
    name = customer_name if customer_name else "Valued Customer"
    
    # 1. Fallback if Gemini client is not configured
    if not genai_client:
        return generate_intelligent_local_reasoning(name, error_code, error_description, amount_in_paisa, plan_name)
        
    logger.info("Engaging Google Gemini 1.5 Flash Reasoning Engine...")
    
    system_instruction = (
        "You are an autonomous AI Revenue Recovery Agent working for a high-performance cloud platform (Synthex.io). "
        "Analyze the failed payment signals and generate an empathetic, root-cause-aware recovery strategy.\n\n"
        "Guidelines:\n"
        "- Zero dark patterns (no fake urgency, no countdowns, no threats to delete customer data).\n"
        "- High empathy, helpful tone, clear alternative payment rails (UPI, Card, Netbanking).\n"
        "- MUST include the literal string '{payment_link}' in the email body and whatsapp copy.\n"
        "- Output strictly valid JSON with keys:\n"
        "  * 'root_cause_diagnosis' (string: 1 sentence diagnosing the bank error)\n"
        "  * 'recommended_strategy' (string: strategic rationale for this intervention)\n"
        "  * 'subject' (string: tailored email subject line)\n"
        "  * 'body' (string: full empathetic email body)\n"
        "  * 'whatsapp_sms_copy' (string: conversational WhatsApp/SMS message in English or Hinglish)"
    )
    
    user_prompt = (
        f"Customer Name: {name}\n"
        f"Plan: {plan_name}\n"
        f"Failed Amount: Rs. {amount_formatted}\n"
        f"Bank Error Code: {error_code}\n"
        f"Bank Error Description: {error_description}\n\n"
        f"Diagnose root cause and draft customized multi-channel recovery communications."
    )
    
    try:
        model = genai_client.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=system_instruction
        )
        
        response = model.generate_content(
            user_prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        
        draft_json = json.loads(response.text)
        
        if "subject" in draft_json and "body" in draft_json:
            if "{payment_link}" not in draft_json["body"]:
                draft_json["body"] += "\n\n👉 Secure payment link: {payment_link}"
            return draft_json
        else:
            raise ValueError("Missing essential keys in Gemini output")
            
    except Exception as e:
        logger.error(f"Gemini API invocation failed: {e}. Switching to advanced local reasoning engine.")
        return generate_intelligent_local_reasoning(name, error_code, error_description, amount_in_paisa, plan_name)
