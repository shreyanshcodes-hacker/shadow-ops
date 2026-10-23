
import os
import redis
from dotenv import load_dotenv

load_dotenv()

redis_url = os.getenv("REDIS_URL")

if not redis_url:
    raise RuntimeError("REDIS_URL is missing from .env")

client = redis.Redis.from_url(
    redis_url,
    decode_responses=True,
    socket_connect_timeout=10,
    socket_timeout=10,
)

try:
    print("PING:", client.ping())

    client.set("shadowops:setup:test", "connected", ex=60)
    print("GET:", client.get("shadowops:setup:test"))

    print("Redis Cloud connection successful!")
except redis.RedisError as exc:
    print("Redis connection failed:", type(exc).__name__)
finally:
    client.close()
