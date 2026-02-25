"""Seed script — populate the ERP database with sample French supplier data.

Run: python -m scripts.seed_erp
"""

from mcp_erp_server.erp_database import init_database

if __name__ == "__main__":
    init_database()
    print("✅ ERP database seeded with sample suppliers, POs, and bank details.")
