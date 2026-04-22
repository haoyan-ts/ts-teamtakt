import asyncio
from sqlalchemy import text
from app.db.engine import engine

async def check():
    async with engine.connect() as conn:
        result = await conn.execute(text("""
            SELECT constraint_name, check_clause
            FROM information_schema.check_constraints
            WHERE constraint_schema = 'public'
        """))
        for row in result:
            print(row)

asyncio.run(check())
