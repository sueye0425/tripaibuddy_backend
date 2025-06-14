from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator, model_validator
from typing import Dict, List, Optional, AsyncGenerator, Any
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import aiohttp
from .recommendations import RecommendationGenerator
from .places_client import GooglePlacesClient
from .schema import LandmarkSelection, StructuredItinerary
from .complete_itinerary import complete_itinerary_from_selection
from .redis_client import redis_client
from decorators.rate_limit import rate_limit
import os
import logging
import asyncio

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Shared resources
app_state: Dict[str, Any] = {}

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage startup and shutdown events for the application."""
    logging.info("Application lifespan: Startup sequence starting...")
    client_session = None
    try:
        client_session = aiohttp.ClientSession()
        places_client = GooglePlacesClient(session=client_session, redis_client=redis_client)
        recommendation_generator = RecommendationGenerator(places_client=places_client)
        
        app_state["client_session"] = client_session
        app_state["places_client"] = places_client
        app_state["redis_client"] = redis_client
        app_state["recommendation_generator"] = recommendation_generator
        
        logging.info("Application lifespan: Startup sequence completed. Clients initialized.")
        yield
    except Exception as e:
        logging.exception("Application lifespan: CRITICAL_ERROR during startup sequence.")
        raise
    finally:
        logging.info("Application lifespan: Shutdown sequence starting...")
        if "places_client" in app_state and app_state["places_client"]:
            try:
                await app_state["places_client"].close()
                logging.info("Application lifespan: GooglePlacesClient closed.")
            except Exception as e:
                logging.exception("Application lifespan: Error closing GooglePlacesClient.")
        
        if "redis_client" in app_state and app_state["redis_client"]:
            # Close Redis client
            try:
                await app_state["redis_client"].close()
                logging.info("Application lifespan: Redis client closed.")
            except Exception as e:
                logging.exception("Application lifespan: Error closing Redis client.")
        
        if client_session and not client_session.closed:
            try:
                await client_session.close()
                logging.info("Application lifespan: Main aiohttp.ClientSession closed.")
            except Exception as e:
                logging.exception("Application lifespan: Error closing main aiohttp.ClientSession.")
        logging.info("Application lifespan: Shutdown sequence completed.")

app = FastAPI(
    title="TripAIBuddy Backend",
    description="Smart travel planning API with Google Places integration",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
allowed_origins = [
    "http://localhost:5173",
    "http://localhost:5174", 
    "http://localhost:5175",
    "http://localhost:5176",
    "http://localhost:5177",
    "http://localhost:5184",  # Added localhost format
    "http://localhost:8000",  # Backend URL
    "http://localhost:3000",  # Common React dev port
    "http://localhost:3001",  # Alternative React dev port
    "http://127.0.0.1:5173",  # Alternative localhost format
    "http://127.0.0.1:5174",
    "http://127.0.0.1:5175",
    "http://127.0.0.1:5176",
    "http://127.0.0.1:5177",
    "http://127.0.0.1:5181",
    "http://127.0.0.1:5182",
    "http://127.0.0.1:5183",
    "http://127.0.0.1:5184",
    "http://127.0.0.1:8000",  # Backend URL alternative format
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
]

# Add production origins from environment variable
env_origins = os.getenv("ALLOWED_ORIGINS", "https://tripaibuddy.app")
if env_origins:
    allowed_origins.extend(env_origins.split(","))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600
)

class ItineraryRequest(BaseModel):
    destination: str
    travel_days: Optional[int] = None
    start_date: Optional[str] = None  # YYYY-MM-DD format
    end_date: Optional[str] = None    # YYYY-MM-DD format
    with_kids: bool = False
    with_elderly: bool = False
    kids_age: Optional[List[int]] = None
    special_requests: Optional[str] = None

    @field_validator('start_date', 'end_date')
    @classmethod
    def validate_date_format(cls, v):
        if v is not None:
            try:
                datetime.strptime(v, '%Y-%m-%d')
                return v
            except ValueError:
                raise ValueError('Date must be in YYYY-MM-DD format')
        return v

    @model_validator(mode='after')
    def compute_travel_days(self):
        if self.travel_days is not None:
            return self
        
        # If travel_days not provided, calculate from start_date and end_date
        if self.start_date and self.end_date:
            start_date = datetime.strptime(self.start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(self.end_date, '%Y-%m-%d').date()
            days = (end_date - start_date).days + 1
            if days <= 0:
                raise ValueError('End date must be after start date')
            self.travel_days = days
            return self
        
        raise ValueError('Either travel_days or both start_date and end_date must be provided')

@app.post("/generate")
@rate_limit(endpoint="generate", limit=50)
async def generate(request: ItineraryRequest):
    try:
        recommendation_generator = app_state["recommendation_generator"]
        result = await recommendation_generator.generate_recommendations(
            destination=request.destination,
            travel_days=request.travel_days,
            with_kids=request.with_kids,
            kids_age=request.kids_age,
            with_elderly=request.with_elderly,
            special_requests=request.special_requests,
            start_date=request.start_date,
            end_date=request.end_date
        )
        
        if not result.get("landmarks") and not result.get("restaurants"):
            raise HTTPException(
                status_code=500,
                detail="Could not generate recommendations"
            )
            
        return result
    except Exception as e:
        logging.exception("Error during /generate")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/complete-itinerary", response_model=StructuredItinerary)
@rate_limit(endpoint="complete_itinerary", limit=50)
async def complete_itinerary(data: LandmarkSelection):
    try:
        logging.info(f"Received complete-itinerary request: {data.model_dump()}")
        
        # Get places_client from app_state for Google API enhancement
        places_client = app_state.get("places_client")
        
        # Check if enhanced agentic system should be used
        use_agentic = os.getenv("ENABLE_AGENTIC_SYSTEM", "false").lower() == "true"
        
        if use_agentic:
            logging.info("🤖 Using Enhanced Agentic Itinerary System")
            from .agentic_itinerary import complete_itinerary_agentic
            result = await complete_itinerary_agentic(data, places_client)
        else:
            logging.info("🔧 Using Standard Itinerary System")
            from .complete_itinerary import complete_itinerary_from_selection
            result = await complete_itinerary_from_selection(data, places_client)
        
        logging.info(f"Complete itinerary result: {result}")
        
        if isinstance(result, dict) and "error" in result:
            logging.error(f"Error in itinerary generation: {result['error']}")
            raise HTTPException(status_code=500, detail=result["error"])
        
        return StructuredItinerary(**result)
    except Exception as e:
        logging.exception(f"Error in complete-itinerary endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to complete itinerary: {str(e)}")

@app.get("/api/v1/image_proxy")
async def image_proxy(photoreference: str, maxwidth: int = 800, maxheight: Optional[int] = None):
    """
    Proxies requests to the Google Places Photo API.
    Caches results in Redis.
    """
    if "places_client" not in app_state or not app_state["places_client"] or \
       "client_session" not in app_state or not app_state["client_session"]:
        logging.error("Image proxy: places_client or client_session not initialized in app_state.")
        raise HTTPException(status_code=503, detail="Image proxy service is not available.")

    places_client: GooglePlacesClient = app_state["places_client"]
    client_session: aiohttp.ClientSession = app_state["client_session"]
    
    # Validate photoreference
    if not photoreference or len(photoreference) < 10:  # Basic validation
        raise HTTPException(status_code=400, detail="Invalid photo reference")
    
    # Construct cache key using the method from RedisCache
    cache_key_params = {'photoreference': photoreference, 'maxwidth': maxwidth}
    if maxheight:
        cache_key_params['maxheight'] = maxheight
    
    cache_key = places_client.cache.get_key('image_proxy', **cache_key_params)
    
    try:
        # Try to get from cache with a short timeout
        try:
            cached_image = await asyncio.wait_for(
                places_client.cache.redis_client.get(cache_key),
                timeout=1.0  # 1 second timeout for cache
            )
            if cached_image:
                return Response(
                    content=cached_image,
                    media_type="image/jpeg",
                    headers={
                        "Cache-Control": "public, max-age=604800",  # 1 week cache
                        "X-Cache": "HIT"
                    }
                )
        except (asyncio.TimeoutError, Exception) as e:
            logging.warning(f"Image proxy: Cache error for {photoreference}: {str(e)}")
            # Continue to Google API if cache fails

        # Fetch from Google with a reasonable timeout
        google_photo_url = "https://maps.googleapis.com/maps/api/place/photo"
        params = {
            "maxwidth": str(maxwidth),
            "photoreference": photoreference,
            "key": places_client.api_key
        }
        if maxheight:
            params["maxheight"] = str(maxheight)

        async with client_session.get(google_photo_url, params=params, timeout=3) as res:
            if res.status == 200:
                img_data = await res.read()
                content_type = res.headers.get("Content-Type", "image/jpeg")
                
                # Only cache if we got valid image data
                if len(img_data) > 100:  # Basic check for valid image data
                    try:
                        # Try to cache but don't wait too long
                        await asyncio.wait_for(
                            places_client.cache.redis_client.set(
                                cache_key,
                                img_data,
                                places_client.cache.ttl['image_proxy']
                            ),
                            timeout=1.0  # 1 second timeout for cache set
                        )
                    except (asyncio.TimeoutError, Exception) as e_cache:
                        logging.warning(f"Image proxy: Cache set error: {e_cache}")
                        # Continue without caching if it fails
                
                return Response(
                    content=img_data,
                    media_type=content_type,
                    headers={
                        "Cache-Control": "public, max-age=604800",  # 1 week cache
                        "Content-Type": content_type,
                        "X-Cache": "MISS"
                    }
                )
            else:
                error_text = await res.text()
                logging.error(f"Image proxy: Google Places Photo API failed. Status: {res.status}")
                raise HTTPException(
                    status_code=res.status if res.status >= 400 else 500,
                    detail="Failed to fetch image from provider"
                )

    except aiohttp.ClientError as e_aiohttp:
        logging.error(f"Image proxy: Network error: {e_aiohttp}")
        raise HTTPException(status_code=504, detail="Network error while fetching image")
    except asyncio.TimeoutError:
        logging.error(f"Image proxy: Timeout for {photoreference}")
        raise HTTPException(status_code=504, detail="Request timed out")
    except Exception as e:
        logging.error(f"Image proxy: Error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/_ah/health")
async def health_check():
    """Health check endpoint for GCP"""
    return {"status": "healthy"}

@app.get("/")
async def home():
    return {
        "message": "🎒 Welcome to TripAIBuddy API!",
        "docs_url": "/docs",
        "openapi_url": "/openapi.json"
    }

@app.get("/photo-proxy/{photo_reference}")
async def photo_proxy(photo_reference: str, maxwidth: int = 400, maxheight: int = 400):
    """Proxy Google Places photos with caching"""
    try:
        places_client = app_state.get("places_client")
        if not places_client:
            raise HTTPException(status_code=500, detail="Places client not available")
            
        photo_data = await places_client.get_photo_data(photo_reference, maxwidth, maxheight)
        
        if not photo_data:
            raise HTTPException(status_code=404, detail="Photo not found")
            
        # Return the image with appropriate headers
        return Response(
            content=photo_data,
            media_type="image/jpeg",
            headers={
                "Cache-Control": "public, max-age=86400",  # Cache for 24 hours
                "Content-Length": str(len(photo_data))
            }
        )
    except Exception as e:
        logging.exception(f"Error in photo proxy: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching photo: {str(e)}")
