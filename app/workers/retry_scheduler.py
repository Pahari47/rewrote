import asyncio
import time
from redis.asyncio import Redis

from app.core.redis import redis_client


PROMOTE_SCRIPT = """
local jobs = redis.call(
    'ZRANGEBYSCORE',
    KEYS[1],
    '-inf',
    ARGV[1],
    'LIMIT',
    0,
    ARGV[2]
)

for _, job_id in ipairs(jobs) do
    redis.call('ZREM', KEYS[1], job_id)
    redis.call('RPUSH', KEYS[2], job_id)
end

return #jobs
"""

async def retry_scheduler(redis: Redis):
    print("Retry scheduler started; blocking on Redis zset 'jobs:delayed'")
    while True:
        try:
            promoted = await redis.eval(
                PROMOTE_SCRIPT,
                2,
                "jobs:delayed",
                "jobs:queue",
                time.time(),
                100
            )

            if promoted:
                print(f"Promoted {promoted} jobs to the queue")
        except Exception as e:
            print(f"Error in retry scheduler: {e}")
            
        await asyncio.sleep(1)

async def main():
    await redis_client.ping()
    try:
        await retry_scheduler(redis_client)
    finally:
        await redis_client.aclose()

if __name__ == "__main__":
    asyncio.run(main())