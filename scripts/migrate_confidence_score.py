import sqlite3

db_path = "invoices.db"

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Add confidence_score to invoices table
    cursor.execute("ALTER TABLE invoices ADD COLUMN confidence_score FLOAT;")
    conn.commit()
    print("Successfully added confidence_score column to invoices table.")
except sqlite3.OperationalError as e:
    print(f"OperationalError: {e}. (The column might already exist)")
except Exception as e:
    print(f"Error: {e}")
finally:
    if 'conn' in locals():
        conn.close()
