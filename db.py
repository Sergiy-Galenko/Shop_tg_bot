import asyncpg
from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

pool: asyncpg.Pool | None = None

async def init_pool():
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
        )
        async with pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    game_id TEXT NOT NULL,
                    balance NUMERIC DEFAULT 0
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS payments (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                    amount NUMERIC NOT NULL,
                    invoice_id BIGINT UNIQUE
                )
                """
            )

async def get_user(user_id: int):
    if pool is None:
        raise RuntimeError("Pool is not initialized")
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT game_id, balance FROM users WHERE user_id=$1", user_id
        )
        if not user:
            return None
        payments = await conn.fetch(
            "SELECT amount, invoice_id FROM payments WHERE user_id=$1", user_id
        )
        return {
            "game_id": user["game_id"],
            "balance": float(user["balance"]),
            "payments": [dict(p) for p in payments],
        }

async def create_user(user_id: int, game_id: str):
    if pool is None:
        raise RuntimeError("Pool is not initialized")
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users(user_id, game_id) VALUES ($1, $2)
            ON CONFLICT (user_id) DO NOTHING
            """,
            user_id,
            game_id,
        )

async def update_game_id(user_id: int, game_id: str):
    if pool is None:
        raise RuntimeError("Pool is not initialized")
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET game_id=$2 WHERE user_id=$1",
            user_id,
            game_id,
        )

async def add_payment(user_id: int, amount: float, invoice_id: int):
    if pool is None:
        raise RuntimeError("Pool is not initialized")
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                INSERT INTO payments(user_id, amount, invoice_id)
                VALUES ($1, $2, $3)
                ON CONFLICT (invoice_id) DO NOTHING
                """,
                user_id,
                amount,
                invoice_id,
            )
            await conn.execute(
                "UPDATE users SET balance = balance + $2 WHERE user_id=$1",
                user_id,
                amount,
            )


