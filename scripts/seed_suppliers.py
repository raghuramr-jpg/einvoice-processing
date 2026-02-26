"""Seed the database with mock supplier data to test validation logic."""

import asyncio
import os
import sys

# Add the project root to sys.path so we can import api modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from api.database import DATABASE_URL, Base

async def seed_suppliers():
    engine = create_async_engine(DATABASE_URL, echo=True)
    
    # 1. Create table if not exists (using Base.metadata)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    # 2. Insert mock data
    mock_suppliers = [
        {
            "name": "Acme Corp",
            "vat_number": "FR82123456789",
            "iban": "FR7630006000011234567890189",
            "is_valid": 1
        },
        {
            "name": "Global Tech Services",
            "vat_number": "GB123456789",
            "iban": "GB29BUKB60161331926819",
            "is_valid": 1
        },
        {
            "name": "Invalid Supplier Ltd",
            "vat_number": "FR000000000",
            "iban": "FR0000000000000000000000000",
            "is_valid": 0
        },
        {
            "name": "Oceanic Airlines",
            "vat_number": "US987654321",
            "iban": "US0000000000000000000000000",
            "is_valid": 1
        }
    ]
    
    async with engine.begin() as conn:
        for supplier in mock_suppliers:
            await conn.execute(
                text("INSERT INTO suppliers (name, vat_number, iban, is_valid) VALUES (:name, :vat_number, :iban, :is_valid)"),
                supplier
            )
            
    print("Mock supplier data inserted successfully.")
    
if __name__ == "__main__":
    asyncio.run(seed_suppliers())
