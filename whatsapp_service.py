import os
import logging
import json
from datetime import datetime
import httpx
from database import log_audit

logger = logging.getLogger("webhook-listener")

# Meta WhatsApp Business Cloud API Configuration
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_API_VERSION = os.getenv("WHATSAPP_API_VERSION", "v19.0")
WHATSAPP_TEMPLATE_NAME = os.getenv("WHATSAPP_TEMPLATE_NAME", "payment_recovery")
WHATSAPP_TEMPLATE_LANGUAGE = os.getenv("WHATSAPP_TEMPLATE_LANGUAGE", "en")
WHATSAPP_DEMO_MODE = os.getenv("WHATSAPP_DEMO_MODE", "true").lower() in ("true", "1", "yes")

def is_whatsapp_configured() -> bool:
    """
    Checks if active WhatsApp Cloud API credentials are provided.
    """
    return bool(WHATSAPP_ACCESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID and not WHATSAPP_DEMO_MODE)

def is_valid_phone(phone: str) -> bool:
    """
    Validates if a phone string has at least 10 digits and is not all zeros.
    """
    if not phone or str(phone).strip() in ("", "None", "null", "undefined", "Phone number unavailable"):
        return False
    clean = "".join(filter(str.isdigit, str(phone)))
    if len(clean) < 10:
        return False
    if set(clean) == {"0"}:
        return False
    return True

def format_phone_e164(phone: str, default_country_code: str = "91") -> str:
    """
    Normalizes a phone string to E.164 standard (e.g., '+919876543210').
    Returns '' if the number is unavailable or invalid.
    """
    if not is_valid_phone(phone):
        return ""
    clean = "".join(filter(str.isdigit, str(phone)))
    if len(clean) == 10:
        clean = default_country_code + clean
    elif len(clean) == 11 and clean.startswith("0"):
        clean = default_country_code + clean[1:]
    return f"+{clean}"

def format_phone_display(phone: str) -> str:
    """
    Formats a phone string into a human-readable display:
    e.g., '+91 98765 43210' or 'Phone number unavailable'
    """
    e164 = format_phone_e164(phone)
    if not e164:
        return "Phone number unavailable"
    digits = e164[1:] # strip '+'
    if digits.startswith("91") and len(digits) == 12:
        return f"+91 {digits[2:7]} {digits[7:]}"
    elif len(digits) == 10:
        return f"+91 {digits[:5]} {digits[5:]}"
    return e164

def construct_template_payload(
    recipient_phone: str,
    customer_name: str,
    order_id: str,
    amount_str: str,
    payment_link: str
) -> dict:
    """
    Builds the official Meta WhatsApp Business Cloud API template payload.
    """
    e164 = format_phone_e164(recipient_phone)
    clean_digits = e164.replace("+", "")

    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": clean_digits,
        "type": "template",
        "template": {
            "name": WHATSAPP_TEMPLATE_NAME,
            "language": {
                "code": WHATSAPP_TEMPLATE_LANGUAGE
            },
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": customer_name},
                        {"type": "text", "text": order_id},
                        {"type": "text", "text": amount_str},
                        {"type": "text", "text": payment_link}
                    ]
                }
            ]
        }
    }

async def send_whatsapp_recovery_message(
    payment_id: str,
    recipient_phone: str,
    customer_name: str,
    amount_in_paisa: int,
    payment_link: str,
    order_id: str = None
) -> dict:
    """
    Dispatches a recovery message via official WhatsApp Business Cloud API.
    In DEMO_MODE or when credentials are not present, simulates the send accurately.
    Prevents sending if phone number is unavailable.
    """
    if not is_valid_phone(recipient_phone):
        logger.warning(f"WhatsApp dispatch prevented for {payment_id}: Phone number is unavailable or invalid ({recipient_phone}).")
        log_audit(
            payment_id=payment_id,
            action_type="WHATSAPP_DISPATCH",
            decision="BLOCKED",
            details={
                "channel": "WhatsApp Business Cloud API",
                "reason": "Phone number unavailable",
                "recipient": "Phone number unavailable",
                "status": "BLOCKED",
                "is_simulated": WHATSAPP_DEMO_MODE
            }
        )
        return {
            "status": "BLOCKED",
            "reason": "Phone number unavailable",
            "is_simulated": WHATSAPP_DEMO_MODE
        }

    formatted_display = format_phone_display(recipient_phone)
    order_ref = order_id or f"ORD-{payment_id[-6:]}"
    amount_formatted = f"₹{amount_in_paisa / 100:,.2f}"
    name = customer_name or "Valued Customer"

    # 1. Build Payload
    payload = construct_template_payload(
        recipient_phone=recipient_phone,
        customer_name=name,
        order_id=order_ref,
        amount_str=amount_formatted,
        payment_link=payment_link
    )

    # 2. Check if running in REAL MODE vs DEMO/SIMULATION MODE
    if is_whatsapp_configured():
        logger.info(f"Connecting to official Meta WhatsApp Cloud API ({WHATSAPP_API_VERSION}) for {payment_id}...")
        url = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
        headers = {
            "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                res_data = response.json()

                if response.status_code in (200, 201):
                    msg_id = res_data.get("messages", [{}])[0].get("id", f"wamid_{payment_id}")
                    logger.info(f"WhatsApp message dispatched successfully to {recipient_phone}! Message ID: {msg_id}")
                    
                    log_audit(
                        payment_id=payment_id,
                        action_type="WHATSAPP_DISPATCH",
                        decision="SENT",
                        details={
                            "channel": "WhatsApp Business Cloud API",
                            "recipient": recipient_phone,
                            "message_id": msg_id,
                            "template": WHATSAPP_TEMPLATE_NAME,
                            "payment_link": payment_link,
                            "status": "SENT",
                            "is_simulated": False
                        }
                    )
                    return {
                        "status": "SENT",
                        "message_id": msg_id,
                        "is_simulated": False,
                        "recipient": recipient_phone
                    }
                else:
                    error_msg = res_data.get("error", {}).get("message", "Unknown Meta Graph API error")
                    logger.error(f"WhatsApp API Error ({response.status_code}): {error_msg}")
                    
                    log_audit(
                        payment_id=payment_id,
                        action_type="WHATSAPP_DISPATCH",
                        decision="FAILED",
                        details={
                            "channel": "WhatsApp Business Cloud API",
                            "error": error_msg,
                            "status_code": response.status_code,
                            "status": "FAILED",
                            "is_simulated": False
                        }
                    )
                    return {
                        "status": "FAILED",
                        "error": error_msg,
                        "is_simulated": False
                    }
        except Exception as e:
            logger.error(f"Network error calling WhatsApp API: {e}")
            return {
                "status": "FAILED",
                "error": str(e),
                "is_simulated": False
            }
    else:
        # DEMO / SIMULATION MODE
        logger.info(f"WhatsApp Cloud API credentials not active. Executing safe DEMO simulation for {payment_id}...")
        simulated_msg_id = f"wamid_sim_{payment_id[-8:]}"
        
        log_audit(
            payment_id=payment_id,
            action_type="WHATSAPP_DISPATCH",
            decision="SIMULATED",
            details={
                "channel": "WhatsApp Business Cloud API (Simulated)",
                "recipient": recipient_phone,
                "message_id": simulated_msg_id,
                "template": WHATSAPP_TEMPLATE_NAME,
                "payment_link": payment_link,
                "status": "SIMULATED",
                "is_simulated": True,
                "note": "Message prepared and formatted for WhatsApp template delivery."
            }
        )
        
        return {
            "status": "SIMULATED",
            "message_id": simulated_msg_id,
            "is_simulated": True,
            "recipient": recipient_phone,
            "message": "Simulated WhatsApp message formatted and logged."
        }
