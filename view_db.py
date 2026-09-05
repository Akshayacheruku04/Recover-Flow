import sqlite3
import json

DB_FILE = "recovery_system.db"

def print_table(table_name):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
        
        print(f"\n=================== TABLE: {table_name} ({len(rows)} rows) ===================")
        if not rows:
            print("[Empty Table]")
            return
            
        # Get column names
        col_names = rows[0].keys()
        print(" | ".join(col_names))
        print("-" * 80)
        
        for row in rows:
            row_vals = []
            for col in col_names:
                val = row[col]
                # Format JSON strings to be easier to read
                if col == "details" and val:
                    try:
                        val = json.loads(val)
                    except:
                        pass
                row_vals.append(str(val))
            print(" | ".join(row_vals))
            
    except sqlite3.OperationalError as e:
        print(f"Error reading {table_name}: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    print_table("failed_payments")
    print_table("audit_logs")
