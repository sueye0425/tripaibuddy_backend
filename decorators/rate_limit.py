# decorators/rate_limit.py
import functools
import datetime
from fastapi import HTTPException
from app.redis_client import redis_client

def rate_limit(endpoint: str, limit: int):
    """
    Decorator to globally limit an API endpoint's requests per day using a decrementing counter.
    
    This decorator initializes a daily limit in Redis and decrements it on each request.
    When the counter reaches zero or below, further requests are blocked until the next day.

    Args:
        endpoint (str): Redis key identifier for the specific endpoint.
        limit (int): Maximum allowed requests per day (shared globally across all users).
    
    Raises:
        HTTPException: When daily limit is exceeded (HTTP 429 - Too Many Requests).
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            
            # Create a unique daily key for this endpoint
            redis_key = f"rate_limit:api:{endpoint}"

            # Get current remaining count, initialize with limit if key doesn't exist
            current_count = await redis_client.get(redis_key)
            
            if current_count is None:
                # First request of the day: initialize counter with the limit
                await redis_client.set(redis_key, str(limit).encode(), ttl=86400)  # 24 hours TTL
                current_count = limit
                
                # Set expiration to midnight of next day
                tomorrow = datetime.datetime.now() + datetime.timedelta(days=1)
                midnight = datetime.datetime.combine(tomorrow.date(), datetime.time.min)
                expire_seconds = int((midnight - datetime.datetime.now()).total_seconds())
                await redis_client.expire(redis_key, expire_seconds)
            else:
                current_count = int(current_count.decode())

            # Check if we have remaining requests
            if current_count <= 0:
                raise HTTPException(
                    status_code=429,
                    detail=f"Daily limit of {limit} requests exceeded for this endpoint. Try again tomorrow."
                )

            # Decrement the counter for this request
            await redis_client.decr(redis_key)

            # Execute the original function
            return await func(*args, **kwargs)
        return wrapper
    return decorator
