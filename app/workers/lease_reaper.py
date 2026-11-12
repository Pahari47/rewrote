
import asyncio
from app.core.redis import redis_client
from app.database import AsyncSessionLocal
from app.services.job import reap_expired_leases


async def lease_reaper_loop():
    print("Lease reaper loop started")
    while True:
        try:
            async with AsyncSessionLocal() as db:
                n = await reap_expired_leases(db, redis_client)

            if n:
                print(f"Reaped {n} expired leases")
        except Exception as e:
            print(f"Error in lease reaper loop: {e}")
        await asyncio.sleep(5)


async def main():
    await redis_client.ping()
    try:
        await lease_reaper_loop()
    finally:
        await redis_client.aclose()

if __name__ == "__main__":
    asyncio.run(main())