import sqlite3
import json

conn = sqlite3.connect("recovery_system.db")
cursor = conn.cursor()

# Query all OUTBOUND_DISPATCH logs
cursor.execute("SELECT payment_id, details, created_at FROM audit_logs WHERE action_type='OUTBOUND_DISPATCH'")
rows = cursor.fetchall()
print(f"Found {len(rows)} outreach logs:")
for r in rows:
    print(f"ID: {r[0]} | Date: {r[2]} | Details: {r[1]}")

conn.close()
