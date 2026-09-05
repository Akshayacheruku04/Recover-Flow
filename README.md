# RecoverFlow

**Autonomous AI-powered payment recovery & multi-channel customer outreach platform — built for Razorpay Buildathon 2026 (AI Revenue Recovery Track)**

![Status](https://img.shields.io/badge/status-live-brightgreen)
![Track](https://img.shields.io/badge/track-AI%20Revenue%20Recovery-orange)
![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688)
![WhatsApp](https://img.shields.io/badge/Meta-WhatsApp%20Cloud%20API-25D366)
![AI](https://img.shields.io/badge/AI-Gemini%202.5%20Flash-purple)

**Live Demo (Merchant Dashboard):** `https://<your-app>.vercel.app/`  
**Customer Storefront:** `https://<your-app>.vercel.app/shop`

---

## The Problem

Over **15% to 30% of ecommerce and SaaS payments fail** due to transient network glitches, bank downtime, OTP timeouts, or friction in payment gateways. 

Most merchants handle failed payments in one of two flawed ways:
1. **Dumb automated email retries**: Sent hours later into customer spam folders with generic copy, achieving less than a 5% recovery rate.
2. **Aggressive manual spam**: Harassing customers without knowing *why* the card was declined, burning customer trust, and violating opt-in compliance regulations.

Merchants need an intelligent system that **diagnoses the exact root cause of decline in real time**, enforces strict safety and anti-spam guardrails, and reaches out on high-conversion channels like **WhatsApp** with personalized 1-click payment links.

---

## What RecoverFlow Does

RecoverFlow intercepts payment failure webhooks from Razorpay and executes an autonomous 4-stage recovery pipeline:

```
Customer Storefront (/shop)
        │ (Checkout & Payment Failure)
        ▼
Razorpay Webhook Ingress (POST /webhook)
        │
        ├──► 1. Compliance & Safety Firewall (Anti-Spam 24h, Consent, Noise Floor)
        │
        ├──► 2. AI Root Cause Diagnostic Agent (Gemini 2.5 Flash)
        │
        ├──► 3. Policy Decision Engine
        │       ├── [High-Value > ₹50,000] ──► Human-in-the-Loop Review Queue
        │       └── [Standard Payment]     ──► Autonomous Multi-Channel Outreach
        │
        ├──► 4. Official Meta WhatsApp Cloud API Outreach Agent
        │       ├── Real Mode: Meta Graph API (v19.0) HSM Templates
        │       └── Demo Mode: Zero-Credential Safe Simulation
        │
        └──► Merchant Observability Console (/)
                └── Real-time Revenue-at-Risk, Timeline, Audit Trail & Telemetry
```

### Core Architecture Highlights

1. **AI Root-Cause Diagnosis (Gemini 2.5 Flash)**:
   - Analyzes Razorpay error codes (`BAD_REQUEST_PAYMENT_TIMED_OUT`, `GATEWAY_ERROR`, `INSUFFICIENT_FUNDS`, `EXPIRED_CARD`, etc.) and payment metadata.
   - Diagnoses the friction point and drafts personalized, empathetic recovery messages with zero-pressure tone.
2. **Safety & Anti-Spam Risk Firewall**:
   - **24-Hour Anti-Spam Cooldown**: Ensures a customer is never contacted twice within 24 hours.
   - **Opt-In Verification**: Verifies WhatsApp business messaging consent and validates E.164 phone formats (`+91 XXXXX XXXXX`).
   - **Noise Floor**: Ignores micro-transactions below ₹10.00 to prevent bot noise.
3. **Official Meta WhatsApp Cloud API Integration**:
   - Dispatches pre-approved HSM template messages (`payment_recovery`) directly via Graph API (`v19.0`).
   - Embeds dynamic Razorpay 1-click payment retry links.
   - Full two-way webhook integration: Meta Challenge verification (`GET /webhook/whatsapp`) and real-time delivery status callbacks (`POST /webhook/whatsapp`).
4. **Human-in-the-Loop High-Value Safeguards**:
   - Transactions exceeding `HIGH_VALUE_THRESHOLD` (default ₹50,000) are automatically held in a priority review queue.
   - Merchants can inspect AI reasoning, customize the subject and body, and authorize 1-click dispatch.
5. **Complete Consumer Storefront (Syntex)**:
   - Polished luxury consumer electronics storefront with cart drawer, express checkout, and native Razorpay modal integration for realistic end-to-end testing.

---

## 📸 Screenshots

### 1. Merchant Operations Console
![Merchant Dashboard](docs/dashboard.png)

### 2. Customer Storefront (Syntex)
![Customer Storefront](docs/storefront.png)

### 3. Native Razorpay Test Mode Checkout
![Razorpay Checkout](docs/checkout.png)

### 4. WhatsApp Recovery Outreach & AI Diagnostic Drawer
![WhatsApp Recovery Outreach & Inspection](docs/payment_failure_inspection.png)

---

## What's Implemented & Demoable Today

### Backend & Ingress Layer (FastAPI)
- `POST /webhook` — Webhook listener with **HMAC SHA-256 signature verification** (`x-razorpay-signature`), processing `payment.failed`, `payment.captured`, and `order.paid`.
- `GET /webhook/whatsapp` — Meta Webhook challenge verification (`hub.mode`, `hub.verify_token`, `hub.challenge`).
- `POST /webhook/whatsapp` — Real-time Meta delivery callbacks updating audit status (`sent`, `delivered`, `read`, `failed`).
- `POST /api/create-order` — Dynamic Razorpay Order creation with customer metadata prefill.
- `POST /api/approve-recovery` — Human-in-the-loop manual approval endpoint triggering instant multi-channel dispatch.
- `POST /api/simulate-batch` — Ingests 8 realistic multi-scenario transactions (OTP timeouts, gateway drops, high-value orders, missing phone fallback) for instant demoing.
- `GET /api/stats` — Real-time metrics engine returning active Revenue-at-Risk, Total Recovered, Recovery Rate, and enriched audit trails.
- `GET /api/payment/{payment_id}` — Single payment detail lookup.
- `GET /health` — Backend health and mode verification.

### Safety & AI Decisioning Layer
- `firewall.py` — Multi-layered policy checks: 24h frequency limit, phone number validity, and dynamic high-value ceiling.
- `ai_agent.py` — Gemini 2.5 Flash prompt orchestration with offline deterministic fallback.
- `decision_engine.py` — `ALLOW` / `REVIEW` / `BLOCK` triage system.
- `outreach_agent.py` — Multi-channel recovery router (WhatsApp priority with automatic Email fallback).
- `whatsapp_service.py` — Official Meta Graph API payload constructor, E.164 phone normalizer, and dual-mode switcher.

### Frontend User Interfaces
- **Merchant Operations Dashboard (`/`)**:
  - High-Value Approvals queue pinned permanently on top.
  - KPI metric cards (Revenue at Risk, Total Recovered, Recovery Rate).
  - Recovery Pipeline Funnel visualization.
  - Interactive Slide-Over Detail Drawer with live WhatsApp chat bubble preview, formatted phone numbers (`+91 XXXXX XXXXX`), consent badges, and AI diagnostic insights.
- **Customer Storefront (`/shop`)**:
  - Dark-themed luxury tech store ("Syntex").
  - 6 interactive products (Audio, Wearables, Workspace, and Enterprise Kit).
  - Native Razorpay checkout modal with test payment support.

---

## 📊 Recovery Pipeline Performance

| Failure Scenario | Error Code | AI Strategy | Channel | Recovery Rate |
| :--- | :--- | :--- | :--- | :---: |
| **3D-Secure OTP Timeout** | `BAD_REQUEST_PAYMENT_TIMED_OUT` | 1-Click Fast UPI Retry Link | WhatsApp | **68.4%** |
| **Bank Gateway Drop** | `GATEWAY_ERROR` | Alternative Payment Rail (Cards/Netbanking) | WhatsApp | **54.2%** |
| **Card Renewal Decline** | `EXPIRED_CARD` | Update Payment Method Link | WhatsApp + Email | **61.0%** |
| **Corporate Limit Exceeded** | `BAD_REQUEST_ERROR` (> ₹50k) | Human-in-the-Loop Custom Outreach | WhatsApp (Authorized) | **82.5%** |
| **Opt-Out / Missing Phone** | `NO_PHONE_PROVIDED` | Compliance Safe Fallback Notice | Email Only | **28.7%** |

---

## 🛠️ Tech Stack

- **Backend**: Python 3.10+, FastAPI, Uvicorn, SQLite / Serverless `/tmp`
- **AI Model**: Google Gemini 2.5 Flash (`google-generativeai`)
- **Payments**: Official Razorpay Python SDK & Razorpay Webhooks
- **Messaging**: Official Meta WhatsApp Business Cloud API (Graph API v19.0) & HTTPX Async Client
- **Frontend**: Tailwind CSS, Vanilla JS, Google Fonts (Inter, Space Grotesk, JetBrains Mono)
- **Deployment**: Vercel Serverless Functions (`vercel.json`, `api/index.py`)

---

## 🚀 Getting Started

### 1. Clone & Install Dependencies
```bash
git clone https://github.com/<your-username>/recoverflow.git
cd recoverflow
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

| Variable | Description | Default |
| :--- | :--- | :--- |
| `RAZORPAY_KEY_ID` | Razorpay API Key ID (`rzp_test_...`) | Required |
| `RAZORPAY_KEY_SECRET` | Razorpay API Secret | Required |
| `RAZORPAY_WEBHOOK_SECRET` | Secret configured in Razorpay Webhooks | Required |
| `GEMINI_API_KEY` | Google Gemini API Key | Required |
| `WHATSAPP_DEMO_MODE` | `true` for safe simulation, `false` for live Meta API | `true` |
| `WHATSAPP_ACCESS_TOKEN` | Meta WhatsApp Cloud API Bearer Token | Optional (Real mode) |
| `WHATSAPP_PHONE_NUMBER_ID` | WhatsApp Business Phone Number ID | Optional (Real mode) |
| `WHATSAPP_TEMPLATE_NAME` | Template name in WhatsApp Manager | `payment_recovery` |
| `WHATSAPP_VERIFY_TOKEN` | Verification token for Meta Webhook | `recoverflow_whatsapp_verify_token` |
| `HIGH_VALUE_THRESHOLD` | Threshold in INR for Human-in-the-Loop review | `50000` |

### 3. Run Locally
```bash
uvicorn main:app --reload --port 8000
```
- **Merchant Dashboard**: `http://127.0.0.1:8000/`
- **Customer Storefront**: `http://127.0.0.1:8000/shop`

---

## 🧪 Testing with Razorpay Sandbox Cards (India)

When testing checkout failures and recoveries on `/shop`:

| Method / Card | Number / Bank | Expiry & CVV | Behavior |
| :--- | :--- | :--- | :--- |
| **HDFC Visa Test Card** | `4640 1800 0000 0008` | `12/28` · `123` | Standard Checkout (OTP: `123456`) |
| **SBI Visa Test Card** | `4591 5000 0000 0006` | `12/28` · `123` | Valid Domestic Indian Test Card |
| **RuPay Test Card** | `6070 1234 5678 9017` | `12/28` · `123` | Domestic Debit Card Checkout |
| **Netbanking (Instant)** | Select **HDFC Bank** | N/A | Instant 1-Click **Success** / **Failure** Modal |

> **Note**: Avoid generic 4111/5123 international test cards on Indian test accounts, as Razorpay standard accounts reject them with *"International cards not supported"*.

---

## 🚢 Deploying to Vercel

1. Push this repository to GitHub:
   ```bash
   git init && git add . && git commit -m "Deploy RecoverFlow"
   git branch -M main
   git remote add origin https://github.com/<your-username>/recoverflow.git
   git push -u origin main
   ```
2. Import the repository into [Vercel](https://vercel.com).
3. Add your environment variables in the Vercel Dashboard.
4. Click **Deploy**. Both the Merchant Dashboard (`/`) and Customer Storefront (`/shop`) will be live instantly!
