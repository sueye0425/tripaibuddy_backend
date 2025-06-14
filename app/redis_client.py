import os
import logging
import asyncio
from typing import Optional
import redis.asyncio as aioredis
from dotenv import load_dotenv

load_dotenv()

class RedisClient:
    """Redis client connection manager with async support"""
    
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or os.getenv('REDIS_URL')
        self.client: Optional[aioredis.Redis] = None
        self.logger = logging.getLogger(__name__)
        self._connection_lock = asyncio.Lock()

    async def get_client(self) -> aioredis.Redis:
        """Get Redis client instance, create new connection if not exists"""
        if self.client is None:
            async with self._connection_lock:
                # Double-checked locking pattern
                if self.client is None:
                    await self._create_connection()
        return self.client

    async def _create_connection(self):
        """Create Redis connection"""
        try:
            self.client = aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=False,
                retry_on_timeout=True,
                socket_timeout=2,  # Reduce timeout to fail fast
                socket_connect_timeout=2,
                socket_keepalive=True,
                health_check_interval=30,
                max_connections=10  # Limit connections to prevent overwhelming Redis
            )
            self.logger.info("Redis connection created successfully")
        except Exception as e:
            self.logger.error(f"Failed to create Redis connection: {str(e)}")
            raise

    async def is_connected(self, timeout: float = 2.0) -> bool:
        """Check if Redis connection is healthy"""
        if self.client is None:
            return False
        
        try:
            await asyncio.wait_for(self.client.ping(), timeout=timeout)
            return True
        except Exception as e:
            self.logger.warning(f"Redis connection check failed: {str(e)}")
            return False

    async def get(self, key: str, timeout: float = 2.0) -> Optional[bytes]:
        """Get raw value from Redis with timeout and error handling"""
        client = await self.get_client()
        try:
            # Add timeout to Redis get operation
            data = await asyncio.wait_for(
                client.get(key),
                timeout=timeout
            )
            return data
                
        except asyncio.TimeoutError:
            self.logger.warning(f"Redis get timeout for key {key} (timeout: {timeout}s)")
            return None
        except Exception as e:
            self.logger.error(f"Redis get error for key {key}: {str(e)}")
            return None

    async def set(self, key: str, value: bytes, ttl: int, timeout: float = 2.0):
        """Set raw value in Redis with TTL and error handling"""
        client = await self.get_client()
        try:
            # Add timeout to Redis set operation
            await asyncio.wait_for(
                client.setex(key, ttl, value),
                timeout=timeout
            )
            self.logger.debug(f"Successfully stored data in Redis with key: {key}, ttl: {ttl}")
        except asyncio.TimeoutError:
            self.logger.warning(f"Redis set timeout for key {key} (timeout: {timeout}s)")
        except Exception as e:
            self.logger.error(f"Redis set error for key {key}: {str(e)}")

    async def delete(self, key: str, timeout: float = 2.0) -> bool:
        """Delete key from Redis"""
        client = await self.get_client()
        try:
            result = await asyncio.wait_for(
                client.delete(key),
                timeout=timeout
            )
            self.logger.debug(f"Deleted key from Redis: {key}")
            return bool(result)
        except asyncio.TimeoutError:
            self.logger.warning(f"Redis delete timeout for key {key} (timeout: {timeout}s)")
            return False
        except Exception as e:
            self.logger.error(f"Redis delete error for key {key}: {str(e)}")
            return False

    async def exists(self, key: str, timeout: float = 2.0) -> bool:
        """Check if key exists in Redis"""
        client = await self.get_client()
        try:
            result = await asyncio.wait_for(
                client.exists(key),
                timeout=timeout
            )
            return bool(result)
        except asyncio.TimeoutError:
            self.logger.warning(f"Redis exists timeout for key {key} (timeout: {timeout}s)")
            return False
        except Exception as e:
            self.logger.error(f"Redis exists error for key {key}: {str(e)}")
            return False

    async def expire(self, key: str, seconds: int, timeout: float = 2.0) -> bool:
        """Set expiration time for a key in Redis"""
        client = await self.get_client()
        try:
            result = await asyncio.wait_for(
                client.expire(key, seconds),
                timeout=timeout
            )
            self.logger.debug(f"Set expiration for Redis key: {key}, seconds: {seconds}")
            return bool(result)
        except asyncio.TimeoutError:
            self.logger.warning(f"Redis expire timeout for key {key} (timeout: {timeout}s)")
            return False
        except Exception as e:
            self.logger.error(f"Redis expire error for key {key}: {str(e)}")
            return False

    async def decr(self, key: str, timeout: float = 2.0) -> Optional[int]:
        """Decrement the value of a key in Redis"""
        client = await self.get_client()
        try:
            result = await asyncio.wait_for(
                client.decr(key),
                timeout=timeout
            )
            self.logger.debug(f"Decremented Redis key: {key}, new value: {result}")
            return result
        except asyncio.TimeoutError:
            self.logger.warning(f"Redis decr timeout for key {key} (timeout: {timeout}s)")
            return None
        except Exception as e:
            self.logger.error(f"Redis decr error for key {key}: {str(e)}")
            return None

    async def close(self):
        """Close Redis connection"""
        if self.client:
            try:
                await self.client.close()
                await self.client.connection_pool.disconnect()
                self.client = None
                self.logger.info("Redis connection and pool closed")
            except Exception as e:
                self.logger.error(f"Error closing Redis connection: {str(e)}")

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()

# globally shared Redis client instance
redis_client = RedisClient(os.getenv('REDIS_URL'))
