import os
import sqlite3
import json
from datetime import datetime

# Serverless compatibility (Vercel has read-only root; writable in /tmp)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if os.getenv("VERCEL"):
    DB_FILE = "/tmp/recovery_system.db"
else:
    DB_FILE = os.getenv("DB_FILE", os.path.join(BASE_DIR, "recovery_system.db"))

def get_db_connection():
    # If the database file does not exist yet (e.g. freshly created in /tmp), initialize it
    needs_init = not os.path.exists(DB_FILE)
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    if needs_init:
        init_db_with_conn(conn)
    return conn

def init_db_with_conn(conn):
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS failed_payments (
            payment_id TEXT PRIMARY KEY,
            amount INTEGER NOT NULL,               -- Amount in paisa
            currency TEXT DEFAULT 'INR',
            status TEXT NOT NULL,                  -- 'failed' or 'recovered'
            customer_name TEXT,
            customer_email TEXT,
            customer_phone TEXT,
            error_code TEXT,
            error_description TEXT,
            created_at TEXT NOT NULL,
            recovered_at TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_id TEXT,
            action_type TEXT NOT NULL,
            decision TEXT NOT NULL,
            details TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (payment_id) REFERENCES failed_payments (payment_id)
        )
    """)
    conn.commit()

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Store information about failed payments
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS failed_payments (
            payment_id TEXT PRIMARY KEY,
            amount INTEGER NOT NULL,               -- Amount in paisa
            currency TEXT DEFAULT 'INR',
            status TEXT NOT NULL,                  -- 'failed' or 'recovered'
            customer_name TEXT,
            customer_email TEXT,
            customer_phone TEXT,
            error_code TEXT,
            error_description TEXT,
            created_at TEXT NOT NULL,
            recovered_at TEXT
        )
    """)
    
    # Store audit logs of every system action
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_id TEXT,
            action_type TEXT NOT NULL,
            decision TEXT NOT NULL,
            details TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (payment_id) REFERENCES failed_payments (payment_id)
        )
    """)
    
    conn.commit()
    conn.close()
    print("Database tables initialized successfully.")

def log_failed_payment(payment_id: str, amount: int, currency: str, error_code: str, 
                       error_description: str, name: str = None, email: str = None, phone: str = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    timestamp = datetime.now().isoformat()
    
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO failed_payments 
            (payment_id, amount, currency, status, customer_name, customer_email, customer_phone, error_code, error_description, created_at)
            VALUES (?, ?, ?, 'failed', ?, ?, ?, ?, ?, ?)
        """, (payment_id, amount, currency, name, email, phone, error_code, error_description, timestamp))
        conn.commit()
    except Exception as e:
        print(f"Error logging failed payment to DB: {e}")
    finally:
        conn.close()

def log_audit(payment_id: str, action_type: str, decision: str, details: dict):
    conn = get_db_connection()
    cursor = conn.cursor()
    timestamp = datetime.now().isoformat()
    details_str = json.dumps(details)
    
    try:
        cursor.execute("""
            INSERT INTO audit_logs (payment_id, action_type, decision, details, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (payment_id, action_type, decision, details_str, timestamp))
        conn.commit()
    except Exception as e:
        print(f"Error writing audit log to DB: {e}")
    finally:
        conn.close()

def mark_as_recovered(payment_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    timestamp = datetime.now().isoformat()
    
    try:
        cursor.execute("""
            UPDATE failed_payments 
            SET status = 'recovered', recovered_at = ? 
            WHERE payment_id = ?
        """, (timestamp, payment_id))
        conn.commit()
        print(f"Payment {payment_id} successfully marked as recovered in the database.")
    except Exception as e:
        print(f"Error updating recovery status: {e}")
    finally:
        conn.close()

def get_stats():
    conn = get_db_connection()
    cursor = conn.cursor()
    stats = {}
    
    # Active revenue still at risk (failed and not yet recovered)
    cursor.execute("SELECT SUM(amount) FROM failed_payments WHERE status = 'failed'")
    stats['total_at_risk'] = cursor.fetchone()[0] or 0
    
    # Revenue successfully recovered
    cursor.execute("SELECT SUM(amount) FROM failed_payments WHERE status = 'recovered'")
    stats['total_recovered'] = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT COUNT(*) FROM failed_payments")
    stats['count_failed'] = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT COUNT(*) FROM failed_payments WHERE status = 'recovered'")
    stats['count_recovered'] = cursor.fetchone()[0] or 0
    
    if stats['count_failed'] > 0:
        stats['recovery_rate'] = round((stats['count_recovered'] / stats['count_failed']) * 100, 2)
    else:
        stats['recovery_rate'] = 0.0
        
    conn.close()
    return stats

def get_failed_payment(payment_id: str):
    """
    Retrieves full failed payment record by payment_id.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM failed_payments WHERE payment_id = ?", (payment_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        print(f"Error fetching failed payment {payment_id}: {e}")
        return None
    finally:
        conn.close()

def get_all_logs():
    """
    Fetches the most recent audit logs enriched with customer & payment details.
    Used to populate our real-time merchant dashboard.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT 
                a.id,
                a.payment_id,
                a.action_type,
                a.decision,
                a.details,
                a.created_at,
                f.customer_name,
                f.customer_email,
                f.customer_phone,
                f.amount AS payment_amount,
                f.currency AS payment_currency,
                f.status AS payment_status,
                f.error_code AS payment_error_code,
                f.error_description AS payment_error_description
            FROM audit_logs a
            LEFT JOIN failed_payments f ON a.payment_id = f.payment_id
            ORDER BY a.created_at DESC LIMIT 60
        """)
        rows = cursor.fetchall()
        logs = [dict(row) for row in rows]
        return logs
    except Exception as e:
        print(f"Error fetching enriched audit logs from DB: {e}")
        try:
            cursor.execute("SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 50")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception:
            return []
    finally:
        conn.close()
