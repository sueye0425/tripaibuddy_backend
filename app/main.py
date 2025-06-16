import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, Any, Optional, List
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, field_validator, model_validator
import aiohttp

from .complete_itinerary import complete_itinerary_from_selection
from .schema import LandmarkSelection, StructuredItinerary, StructuredDayPlan, ItineraryBlock, Location, CompleteItineraryResponse
from .recommendations import RecommendationGenerator
from .places_client import GooglePlacesClient
from .redis_client import redis_client
from decorators.rate_limit import rate_limit

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
    "http://localhost:5178",
    "http://localhost:5179",  # Added missing localhost:5179
    "http://localhost:5180",
    "http://localhost:5181",
    "http://localhost:5182",  # Added missing localhost:5182
    "http://localhost:5183",
    "http://localhost:5184",
    "http://localhost:8000",  # Backend URL
    "http://localhost:3000",  # Common React dev port
    "http://localhost:3001",  # Alternative React dev port
    "http://127.0.0.1:5173",  # Alternative localhost format
    "http://127.0.0.1:5174",
    "http://127.0.0.1:5175",
    "http://127.0.0.1:5176",
    "http://127.0.0.1:5177",
    "http://127.0.0.1:5178",
    "http://127.0.0.1:5179",  # Added missing 127.0.0.1:5179
    "http://127.0.0.1:5180",
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

async def _convert_to_structured_itinerary(
    old_format_result: Dict[str, Any], 
    travel_days: int, 
    destination: str,
    places_client: Optional[GooglePlacesClient] = None
) -> Dict[str, Any]:
    """Convert old format to new structured itinerary format - FAST VERSION"""
    try:
        logging.info("🔄 Converting to structured itinerary format (fast mode)")
        
        # Extract landmarks and restaurants from old format
        landmarks_dict = old_format_result.get("landmarks", {})
        restaurants_dict = old_format_result.get("restaurants", {})
        
        landmark_list = list(landmarks_dict.values())
        restaurant_list = list(restaurants_dict.values())
        
        # Create structured itinerary WITHOUT LLM processing for speed
        itinerary_days = []
        
        # Distribute landmarks and restaurants across days
        landmarks_per_day = len(landmark_list) // travel_days if travel_days > 0 else 0
        restaurants_per_day = 3  # breakfast, lunch, dinner
        
        for day in range(1, travel_days + 1):
            blocks = []
            
            # Add landmarks for this day
            start_idx = (day - 1) * landmarks_per_day
            end_idx = start_idx + landmarks_per_day
            if day == travel_days:  # Last day gets remaining landmarks
                end_idx = len(landmark_list)
            
            day_landmarks = landmark_list[start_idx:end_idx]
            
            # Add restaurants for this day (rotate through available restaurants)
            restaurant_start_idx = ((day - 1) * restaurants_per_day) % len(restaurant_list)
            day_restaurants = []
            for i in range(restaurants_per_day):
                if restaurant_list:
                    restaurant_idx = (restaurant_start_idx + i) % len(restaurant_list)
                    day_restaurants.append(restaurant_list[restaurant_idx])
            
            # Create time schedule
            current_time = 8 * 60 + 30  # Start at 8:30 AM
            
            # Add breakfast
            if day_restaurants:
                restaurant = day_restaurants[0]
                blocks.append(_create_restaurant_block(restaurant, current_time, "breakfast"))
                current_time += 45  # 45 minutes for breakfast
            
            # Add morning landmarks
            morning_landmarks = day_landmarks[:len(day_landmarks)//2] if len(day_landmarks) > 1 else day_landmarks[:1]
            for landmark in morning_landmarks:
                current_time += 30  # Travel time
                blocks.append(_create_landmark_block(landmark, current_time))
                current_time += 120  # 2 hours for landmark
            
            # Add lunch
            if len(day_restaurants) > 1:
                restaurant = day_restaurants[1]
                blocks.append(_create_restaurant_block(restaurant, current_time, "lunch"))
                current_time += 60  # 1 hour for lunch
            
            # Add afternoon landmarks
            afternoon_landmarks = day_landmarks[len(day_landmarks)//2:] if len(day_landmarks) > 1 else []
            for landmark in afternoon_landmarks:
                current_time += 30  # Travel time
                blocks.append(_create_landmark_block(landmark, current_time))
                current_time += 120  # 2 hours for landmark
            
            # Add dinner
            if len(day_restaurants) > 2:
                restaurant = day_restaurants[2]
                current_time = max(current_time, 18 * 60)  # Ensure dinner is at least 6 PM
                blocks.append(_create_restaurant_block(restaurant, current_time, "dinner"))
            
            # Sort blocks by start_time to ensure proper chronological order
            blocks.sort(key=lambda block: block.start_time)
            
            itinerary_days.append(StructuredDayPlan(day=day, blocks=blocks))
        
        return {"itinerary": [day.model_dump() for day in itinerary_days]}
        
    except Exception as e:
        logging.exception(f"Error converting to structured itinerary: {e}")
        # Fallback to simple conversion
        return _simple_conversion_fallback(old_format_result, travel_days)

async def _convert_to_structured_itinerary_fast(
    old_format_result: Dict[str, Any], 
    travel_days: int
) -> Dict[str, Any]:
    """Convert old format to new structured itinerary format - SUPER FAST VERSION (NO LLM)"""
    try:
        logging.info("🔄 Converting to structured itinerary format (super fast mode - no LLM)")
        
        # Extract landmarks and restaurants from old format
        landmarks_dict = old_format_result.get("landmarks", {})
        restaurants_dict = old_format_result.get("restaurants", {})
        
        landmark_list = list(landmarks_dict.values())
        restaurant_list = list(restaurants_dict.values())
        
        # Create structured itinerary WITHOUT any external API calls
        itinerary_days = []
        
        # Distribute landmarks and restaurants across days
        landmarks_per_day = len(landmark_list) // travel_days if travel_days > 0 else 0
        
        for day in range(1, travel_days + 1):
            blocks = []
            
            # Add landmarks for this day
            start_idx = (day - 1) * landmarks_per_day
            end_idx = start_idx + landmarks_per_day
            if day == travel_days:  # Last day gets remaining landmarks
                end_idx = len(landmark_list)
            
            day_landmarks = landmark_list[start_idx:end_idx]
            
            # Add restaurants for this day (rotate through available restaurants)
            restaurants_per_day = 3  # breakfast, lunch, dinner
            restaurant_start_idx = ((day - 1) * restaurants_per_day) % len(restaurant_list)
            day_restaurants = []
            for i in range(restaurants_per_day):
                if restaurant_list:
                    restaurant_idx = (restaurant_start_idx + i) % len(restaurant_list)
                    day_restaurants.append(restaurant_list[restaurant_idx])
            
            # Create time schedule
            current_time = 8 * 60 + 30  # Start at 8:30 AM
            
            # Add breakfast
            if day_restaurants:
                restaurant = day_restaurants[0]
                blocks.append(_create_restaurant_block_fast(restaurant, current_time, "breakfast"))
                current_time += 45  # 45 minutes for breakfast
            
            # Add morning landmarks
            morning_landmarks = day_landmarks[:len(day_landmarks)//2] if len(day_landmarks) > 1 else day_landmarks[:1]
            for landmark in morning_landmarks:
                current_time += 30  # Travel time
                blocks.append(_create_landmark_block_fast(landmark, current_time))
                current_time += 120  # 2 hours for landmark
            
            # Add lunch
            if len(day_restaurants) > 1:
                restaurant = day_restaurants[1]
                blocks.append(_create_restaurant_block_fast(restaurant, current_time, "lunch"))
                current_time += 60  # 1 hour for lunch
            
            # Add afternoon landmarks
            afternoon_landmarks = day_landmarks[len(day_landmarks)//2:] if len(day_landmarks) > 1 else []
            for landmark in afternoon_landmarks:
                current_time += 30  # Travel time
                blocks.append(_create_landmark_block_fast(landmark, current_time))
                current_time += 120  # 2 hours for landmark
            
            # Add dinner
            if len(day_restaurants) > 2:
                restaurant = day_restaurants[2]
                current_time = max(current_time, 18 * 60)  # Ensure dinner is at least 6 PM
                blocks.append(_create_restaurant_block_fast(restaurant, current_time, "dinner"))
            
            # Sort blocks by start_time to ensure proper chronological order
            blocks.sort(key=lambda block: block.start_time)
            
            itinerary_days.append(StructuredDayPlan(day=day, blocks=blocks))
        
        return {"itinerary": [day.model_dump() for day in itinerary_days]}
        
    except Exception as e:
        logging.exception(f"Error converting to structured itinerary: {e}")
        # Fallback to simple conversion
        return _simple_conversion_fallback(old_format_result, travel_days)

def _create_landmark_block(landmark: Dict[str, Any], start_time_minutes: int) -> ItineraryBlock:
    """Create a landmark block from landmark data"""
    location = None
    if landmark.get('location') and isinstance(landmark['location'], dict):
        loc_data = landmark['location']
        if 'lat' in loc_data and 'lng' in loc_data:
            location = Location(lat=loc_data['lat'], lng=loc_data['lng'])
    
    # Extract photo URL
    photo_url = None
    photos = landmark.get('photos', [])
    if photos and len(photos) > 0:
        photo_url = photos[0]  # Take first photo
    
    return ItineraryBlock(
        type="landmark",
        name=landmark.get('name', 'Unknown Landmark'),
        description=landmark.get('description', ''),
        start_time=_minutes_to_time_string(start_time_minutes),
        duration="2h",
        place_id=landmark.get('place_id'),
        rating=landmark.get('rating'),
        location=location,
        address=landmark.get('address'),
        photo_url=photo_url,
        website=landmark.get('website')
    )

def _create_restaurant_block(restaurant: Dict[str, Any], start_time_minutes: int, mealtime: str) -> ItineraryBlock:
    """Create a restaurant block from restaurant data"""
    location = None
    if restaurant.get('location') and isinstance(restaurant['location'], dict):
        loc_data = restaurant['location']
        if 'lat' in loc_data and 'lng' in loc_data:
            location = Location(lat=loc_data['lat'], lng=loc_data['lng'])
    
    # Extract photo URL
    photo_url = None
    photos = restaurant.get('photos', [])
    if photos and len(photos) > 0:
        photo_url = photos[0]  # Take first photo
    
    # Duration based on meal type
    duration = "45m" if mealtime == "breakfast" else "1h" if mealtime == "lunch" else "1.5h"
    
    return ItineraryBlock(
        type="restaurant",
        name=restaurant.get('name', 'Unknown Restaurant'),
                    description=None,  # Restaurants don't need descriptions
        start_time=_minutes_to_time_string(start_time_minutes),
        duration=duration,
        mealtime=mealtime,
        place_id=restaurant.get('place_id'),
        rating=restaurant.get('rating'),
        location=location,
        address=restaurant.get('address'),
        photo_url=photo_url,
        website=restaurant.get('website')
    )

def _create_landmark_block_fast(landmark: Dict[str, Any], start_time_minutes: int) -> ItineraryBlock:
    """Create a landmark block from landmark data - FAST VERSION"""
    location = None
    if landmark.get('location') and isinstance(landmark['location'], dict):
        loc_data = landmark['location']
        if 'lat' in loc_data and 'lng' in loc_data:
            location = Location(lat=loc_data['lat'], lng=loc_data['lng'])
    
    # Extract photo URL
    photo_url = None
    photos = landmark.get('photos', [])
    if photos and len(photos) > 0:
        photo_url = photos[0]  # Take first photo
    
    return ItineraryBlock(
        type="landmark",
        name=landmark.get('name', 'Unknown Landmark'),
        description=landmark.get('description', f"{landmark.get('name', 'This landmark')} is a popular attraction."),  # Simple fallback
        start_time=_minutes_to_time_string(start_time_minutes),
        duration="2h",
        place_id=landmark.get('place_id'),
        rating=landmark.get('rating'),
        location=location,
        address=landmark.get('address'),
        photo_url=photo_url,
        website=landmark.get('website')
    )

def _create_restaurant_block_fast(restaurant: Dict[str, Any], start_time_minutes: int, mealtime: str) -> ItineraryBlock:
    """Create a restaurant block from restaurant data - FAST VERSION"""
    location = None
    if restaurant.get('location') and isinstance(restaurant['location'], dict):
        loc_data = restaurant['location']
        if 'lat' in loc_data and 'lng' in loc_data:
            location = Location(lat=loc_data['lat'], lng=loc_data['lng'])
    
    # Extract photo URL
    photo_url = None
    photos = restaurant.get('photos', [])
    if photos and len(photos) > 0:
        photo_url = photos[0]  # Take first photo
    
    # Duration based on meal type
    duration = "45m" if mealtime == "breakfast" else "1h" if mealtime == "lunch" else "1.5h"
    
    return ItineraryBlock(
        type="restaurant",
        name=restaurant.get('name', 'Unknown Restaurant'),
                    description=None,  # Restaurants don't need descriptions
        start_time=_minutes_to_time_string(start_time_minutes),
        duration=duration,
        mealtime=mealtime,
        place_id=restaurant.get('place_id'),
        rating=restaurant.get('rating'),
        location=location,
        address=restaurant.get('address'),
        photo_url=photo_url,
        website=restaurant.get('website')
    )

def _minutes_to_time_string(minutes: int) -> str:
    """Convert minutes since midnight to time string (e.g., 510 -> '08:30')"""
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"

def _simple_conversion_fallback(old_format_result: Dict[str, Any], travel_days: int) -> Dict[str, Any]:
    """Simple fallback conversion without LLM enhancement"""
    landmarks = list(old_format_result.get("landmarks", {}).values())
    restaurants = list(old_format_result.get("restaurants", {}).values())
    
    itinerary_days = []
    for day in range(1, travel_days + 1):
        blocks = []
        
        # Add a few landmarks and restaurants per day
        day_landmarks = landmarks[:3] if landmarks else []
        day_restaurants = restaurants[:3] if restaurants else []
        
        current_time = 8 * 60 + 30  # 8:30 AM
        
        for i, landmark in enumerate(day_landmarks):
            blocks.append(_create_landmark_block(landmark, current_time + i * 180))
        
        for i, restaurant in enumerate(day_restaurants):
            mealtime = ["breakfast", "lunch", "dinner"][i]
            meal_time = [8*60+30, 12*60, 18*60][i]  # 8:30, 12:00, 18:00
            blocks.append(_create_restaurant_block(restaurant, meal_time, mealtime))
        
        itinerary_days.append({"day": day, "blocks": [block.model_dump() for block in blocks]})
    
    return {"itinerary": itinerary_days}

@app.post("/generate")
@rate_limit(endpoint="generate", limit=50)
async def generate(request: ItineraryRequest):
    try:
        logging.info(f"🎯 Generate endpoint called for destination: {request.destination}")
        
        # Use the original fast RecommendationGenerator for speed - NO LLM PROCESSING
        logging.info("🚀 Using Fast RecommendationGenerator System (NO LLM)")
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
        
        # Convert object format to array format for frontend compatibility
        landmarks_array = list(result.get('landmarks', {}).values())
        restaurants_array = list(result.get('restaurants', {}).values())
        
        # Return the format expected by frontend (arrays, not objects)
        logging.info(f"✅ Generate completed: {len(landmarks_array)} landmarks, {len(restaurants_array)} restaurants")
        return {
            "recommendations": {
                "landmarks": landmarks_array,
                "restaurants": restaurants_array
            }
        }
    except Exception as e:
        logging.exception("Error during /generate")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/complete-itinerary", response_model=CompleteItineraryResponse)
@rate_limit(endpoint="complete_itinerary", limit=50)
async def complete_itinerary(data: LandmarkSelection):
    try:
        logging.info(f"Received complete-itinerary request: {data.model_dump()}")
        
        # Get places_client from app_state for Google API enhancement
        places_client = app_state.get("places_client")
        
        # Use the single LLM call approach from complete_itinerary.py
        logging.info("🚀 Using Single LLM Call System (complete_itinerary.py)")
        result = await complete_itinerary_from_selection(data, places_client)
        
        logging.info(f"Complete itinerary result: {result}")
        
        if isinstance(result, dict) and "error" in result:
            logging.error(f"Error in itinerary generation: {result['error']}")
            raise HTTPException(status_code=500, detail=result["error"])
        
        # Extract itinerary and performance metrics
        itinerary_data = result.get("itinerary")
        performance_metrics = result.get("performance_metrics")

        if not itinerary_data:
            raise HTTPException(status_code=500, detail="Failed to generate itinerary content.")

        # itinerary_data should now be a list of day plans
        if not isinstance(itinerary_data, list):
            raise HTTPException(status_code=500, detail="Invalid itinerary format - expected list of day plans")
        
        return CompleteItineraryResponse(
            itinerary=itinerary_data,
            performance_metrics=performance_metrics
        )
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
                places_client.cache.get(cache_key),
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
            "key": places_client.api_key  # API key used internally, not logged
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
                            places_client.cache.set(cache_key, img_data, 'image_proxy'),
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
