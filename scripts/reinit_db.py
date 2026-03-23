import asyncio
import os
from pathlib import Path
from api.database import init_db

async def reinit():
    db_path = Path("invoices.db")
    if db_path.exists():
        print(f"Deleting existing database: {db_path}")
        os.remove(db_path)
    
    print("Initializing new database with latest schema...")
    await init_db()
    print("Database reinitialized successfully!")

if __name__ == "__main__":
    asyncio.run(reinit())
