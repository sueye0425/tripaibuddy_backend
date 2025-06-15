import os
import time
import hashlib
import json
import asyncio
import logging
import random
from dotenv import load_dotenv
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser, OutputFixingParser

from .schema import StructuredItinerary, LandmarkSelection, ItineraryBlock, StructuredDayPlan, Location
from .places_client import GooglePlacesClient
from .llm_descriptions import LLMDescriptionService
from .llm_prompt_generator import LLMPromptGenerator

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Try to import Google Cloud Logging for better GCP integration
try:
    import google.cloud.logging
    gcp_client = google.cloud.logging.Client()
    gcp_client.setup_logging()
    logger.info("✅ Google Cloud Logging configured")
except ImportError:
    logger.info("⚠️  Google Cloud Logging not available, using standard logging")
except Exception as e:
    logger.warning(f"⚠️  Could not configure Google Cloud Logging: {e}")

# Debug mode configuration
DEBUG_MODE = os.getenv("DEBUG_ITINERARY", "false").lower() == "true"

# Cache for storing generated itineraries
_itinerary_cache = {}

# Initialize LLM description service globally
_llm_description_service = None

async def get_llm_description_service():
    """Get or create LLM description service instance"""
    global _llm_description_service
    if _llm_description_service is None:
        _llm_description_service = LLMDescriptionService()
    return _llm_description_service

def debug_print(*args, **kwargs):
    """Print debug messages with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}]", *args, **kwargs)

def get_cache_key(selection: LandmarkSelection) -> str:
    """Generate a cache key based on core parameters"""
    key_data = {
        'destination': selection.details.destination,
        'travel_days': selection.details.travelDays,
        'with_kids': selection.details.withKids,
        'kids_age': selection.details.kidsAge,
        'special_requests': selection.details.specialRequests,
        'attractions': [(a.name, a.type) for day in selection.itinerary for a in day.attractions],
        'wishlist': [(w.get('name'), w.get('type')) if isinstance(w, dict) else str(w) for w in (selection.wishlist or [])]
    }
    return hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")

# Use GPT-4-turbo as primary model for quality
llm = ChatOpenAI(
    api_key=OPENAI_API_KEY,
    model_name="gpt-4-turbo",
    temperature=0.3,
    max_tokens=2000,
    request_timeout=25,
    **({"base_url": OPENAI_BASE_URL} if OPENAI_BASE_URL else {})  # Use base_url if set, otherwise use default
)
parser = PydanticOutputParser(pydantic_object=StructuredItinerary)
prompt_generator = LLMPromptGenerator()

# Backup LLM for retries
backup_llm = ChatOpenAI(
    api_key=OPENAI_API_KEY,
    model_name="gpt-3.5-turbo",
    temperature=0.3,
    max_tokens=2000,
    request_timeout=15,
    **({"base_url": OPENAI_BASE_URL} if OPENAI_BASE_URL else {})  # Use base_url if set, otherwise use default
)
backup_fallback_parser = OutputFixingParser.from_llm(llm=backup_llm, parser=parser)

def create_itinerary_prompt() -> PromptTemplate:
    """Create prompt for generating complete itinerary with landmarks"""
    return PromptTemplate(
        template="""Create a {travel_days}-day itinerary for {destination}{date_info}.

GROUP: Kids({kids_age}), Elderly({with_elderly}) | REQUESTS: {special_requests}

SELECTED ATTRACTIONS (REQUIRED):
{selected_attractions}

{wishlist_recommendations}

REQUIREMENTS:
• Include ALL selected attractions as provided
• Add 1-2 additional landmarks per day for full experience
• Choose MAIN LANDMARKS, not sub-attractions (e.g., "ICON Park" not "The Wheel at ICON Park")
• Use realistic, specific durations based on attraction type:
  - Theme Parks: 6h-8h (Universal Studios, Disney World)
  - Major Museums: 2h-3h (Science centers, art museums)
  - Observation Points: 1h-1.5h (Observation wheels, viewpoints)
  - Parks/Gardens: 1.5h-2h (City parks, botanical gardens)
  - Historic Sites: 1h-2h (Historic districts, monuments)
  - Entertainment Districts: 2h-3h (Shopping areas, entertainment complexes)
• Account for 15-30min travel between activities
• Choose popular, highly-rated places in {destination}

CRITICAL: NO DUPLICATE LANDMARKS
• Each landmark must be COMPLETELY UNIQUE across ALL {travel_days} days
• Do NOT use the same landmark name on multiple days
• Do NOT use variations of the same landmark (e.g., "SeaWorld" on Day 1 and "SeaWorld San Diego" on Day 2)
• Verify each landmark appears only ONCE in the entire itinerary
• If you're unsure, choose a different landmark entirely

LANDMARK SELECTION PRIORITY:
• Choose the MAIN ATTRACTION, not individual rides or sub-attractions
• Example: "Universal Studios Florida" not "The Wizarding World of Harry Potter"
• Example: "ICON Park" not "The Wheel at ICON Park"
• Example: "Balboa Park" not "San Diego Zoo" (unless zoo is the main focus)
• Focus on the primary destination that encompasses multiple activities

TIMING STRATEGY:
- FOCUS ON LANDMARKS ONLY - do not schedule meals/restaurants
- Fill the entire day from 9:00 AM to 6:00 PM with engaging landmarks
- Create a continuous flow of activities with minimal gaps
- Restaurants will be added later along your planned route
- For non-theme park days: Plan 3-4 landmarks to fill the day completely
- Ensure logical geographic flow between landmarks

CRITICAL GAP PREVENTION:
- Plan landmarks to span the full day (9:00 AM to 6:00 PM)
- Maximum 30-minute gaps between landmarks for travel time
- If a landmark is short (under 1 hour), extend it or add nearby activities
- Create a packed but enjoyable day that leaves no large empty periods

EXAMPLE OF GOOD MULTI-DAY PLANNING:
Day 1: Balboa Park (9:00, 3h), USS Midway Museum (13:00, 2h), Sunset Cliffs (16:00, 1h)
Day 2: La Jolla Cove (9:00, 2h), Torrey Pines (12:00, 2h), Gaslamp Quarter (15:00, 2h)
Day 3: San Diego Zoo (9:00, 4h), Little Italy (14:00, 1.5h), Embarcadero (16:00, 1.5h)

CRITICAL FORMATTING:
- Type: "landmark" only (restaurants will be added later)
- Start_time: "HH:MM" format
- Duration: Use specific durations like "1h", "1.5h", "2h", "3h", "6h" (not "2-3 hours")

{format_instructions}""",
        input_variables=[
            "destination", "travel_days", "date_info", "with_kids", "kids_age", 
            "with_elderly", "special_requests", "selected_attractions", "wishlist_recommendations"
        ],
        partial_variables={"format_instructions": parser.get_format_instructions()}
    )

def is_theme_park_day(day_plan: StructuredDayPlan) -> bool:
    """Check if a day is a theme park day based on keywords"""
    for block in day_plan.blocks:
        if block.type == "landmark":
            name_lower = block.name.lower()
            duration_minutes = parse_duration_to_minutes(block.duration)
            
            # Check for theme park keywords AND long duration (6+ hours)
            theme_park_keywords = [
                "disneyland", "disney", "universal", "six flags", "knott", 
                "seaworld", "busch gardens", "cedar point", "magic kingdom",
                "epcot", "hollywood studios", "animal kingdom"
            ]
            
            is_theme_park_name = any(keyword in name_lower for keyword in theme_park_keywords)
            is_long_duration = duration_minutes >= 360  # 6+ hours
            
            # Only consider it a theme park day if BOTH conditions are met
            if is_theme_park_name and is_long_duration:
                debug_print(f"🎢 Detected theme park day: {block.name} ({block.duration})")
                return True
    
    debug_print(f"🏛️ Regular day detected")
    return False

async def add_restaurants_to_day_optimized(
    day_plan: StructuredDayPlan,
    places_client: GooglePlacesClient,
    destination: str,
    used_restaurants: set,
    is_theme_park: bool
) -> StructuredDayPlan:
    """Add restaurants strategically with optimized API calls based on landmark proximity"""
    
    debug_print(f"🍽️ Adding restaurants to Day {day_plan.day} ({'theme park' if is_theme_park else 'regular'} day) - OPTIMIZED")
    
    # Get landmarks sorted by time
    landmarks = [block for block in day_plan.blocks if block.type == "landmark"]
    landmarks.sort(key=lambda x: parse_time_to_minutes(x.start_time))
    
    debug_print(f"📍 Landmarks planned by LLM:")
    for landmark in landmarks:
        debug_print(f"   🏛️ {landmark.name}: {landmark.start_time} ({landmark.duration})")
    
    restaurants = []
    
    if is_theme_park:
        # Theme park: Strategic meal times within/near the park
        debug_print(f"🎢 Theme park day - using strategic meal times")
        
        meal_schedule = [
            ("breakfast", "08:00", "45m"),
            ("lunch", "12:30", "1h"),
            ("dinner", "18:00", "1.5h")
        ]
        
        # Use theme park location for all restaurant searches (1 API call for all meals)
        theme_park_location = landmarks[0].location if landmarks else None
        
        if theme_park_location:
            debug_print(f"🎯 OPTIMIZATION: Using single location search for all theme park meals")
            # Single API call to get restaurants near theme park
            restaurant_data = await search_multiple_restaurants_near_location(
                places_client, destination, theme_park_location, ["breakfast", "lunch", "dinner"], used_restaurants
            )
            
            debug_print(f"🍽️ Found {len(restaurant_data)} restaurants for theme park day")
            
            for i, (meal_type, start_time, duration) in enumerate(meal_schedule):
                if i < len(restaurant_data):
                    restaurant_block = ItineraryBlock(
                        name=restaurant_data[i]["name"],
                        type="restaurant",
                        description=None,  # Restaurants don't need descriptions - website provides better info
                        start_time=start_time,
                        duration=duration,
                        mealtime=meal_type,
                        location=restaurant_data[i]["location"],
                        place_id=restaurant_data[i]["place_id"],
                        rating=restaurant_data[i]["rating"],
                        address=restaurant_data[i]["address"],
                        photo_url=restaurant_data[i]["photo_url"],
                        website=restaurant_data[i]["website"]
                    )
                    restaurants.append(restaurant_block)
                    used_restaurants.add(restaurant_data[i]["name"].lower())
                    debug_print(f"   🍽️ {meal_type.title()}: {restaurant_data[i]['name']} at {start_time} ({duration})")
        else:
            debug_print("⚠️ No theme park location found for restaurant search")
    
    else:
        # Regular day: Optimize based on landmark distribution
        debug_print(f"🗺️ Regular day - optimizing restaurant searches based on landmark proximity")
        
        if landmarks:
            # Analyze landmark distribution to optimize restaurant searches
            landmark_locations = [lm.location for lm in landmarks if lm.location]
            debug_print(f"📍 Found {len(landmark_locations)} landmark locations out of {len(landmarks)} landmarks")
            
            if len(landmark_locations) <= 1:
                # Single landmark or clustered landmarks - use 1 API call for all restaurants
                debug_print(f"🎯 OPTIMIZATION: Single landmark area - 1 API call for all meals")
                search_location = landmark_locations[0] if landmark_locations else None
                
                restaurant_data = await search_multiple_restaurants_near_location(
                    places_client, destination, search_location, ["breakfast", "lunch", "dinner"], used_restaurants
                )
                
                debug_print(f"🍽️ Found {len(restaurant_data)} restaurants for single landmark area")
                
                # Calculate strategic meal times
                first_landmark_start = parse_time_to_minutes(landmarks[0].start_time)
                last_landmark_end = parse_time_to_minutes(landmarks[-1].start_time) + parse_duration_to_minutes(landmarks[-1].duration)
                
                meal_times = [
                    ("breakfast", max(480, first_landmark_start - 30), "45m"),
                    ("lunch", find_optimal_meal_time(landmarks, "lunch", 720, 780), "1h"),
                    ("dinner", max(last_landmark_end + 30, 1080), "1.5h")
                ]
                
                for i, (meal_type, time_minutes, duration) in enumerate(meal_times):
                    if i < len(restaurant_data):
                        time_str = f"{time_minutes // 60:02d}:{time_minutes % 60:02d}"
                        restaurant_block = ItineraryBlock(
                            name=restaurant_data[i]["name"],
                            type="restaurant",
                            description=None,  # Restaurants don't need descriptions - website provides better info
                            start_time=time_str,
                            duration=duration,
                            mealtime=meal_type,
                            location=restaurant_data[i]["location"],
                            place_id=restaurant_data[i]["place_id"],
                            rating=restaurant_data[i]["rating"],
                            address=restaurant_data[i]["address"],
                            photo_url=restaurant_data[i]["photo_url"],
                            website=restaurant_data[i]["website"]
                        )
                        restaurants.append(restaurant_block)
                        used_restaurants.add(restaurant_data[i]["name"].lower())
                        debug_print(f"   🍽️ {meal_type.title()}: {restaurant_data[i]['name']} at {time_str} ({duration})")
            
            else:
                # Multiple landmarks spread out - group meals by proximity
                debug_print(f"🎯 OPTIMIZATION: Multiple landmarks - grouping meals by proximity")
                
                # Calculate strategic meal times first
                first_landmark_start = parse_time_to_minutes(landmarks[0].start_time)
                last_landmark_end = parse_time_to_minutes(landmarks[-1].start_time) + parse_duration_to_minutes(landmarks[-1].duration)
                
                breakfast_time = max(480, first_landmark_start - 30)
                lunch_time = find_optimal_meal_time(landmarks, "lunch", 720, 780)
                dinner_time = max(last_landmark_end + 30, 1080)
                
                meal_schedule = [
                    ("breakfast", breakfast_time, "45m"),
                    ("lunch", lunch_time, "1h"),
                    ("dinner", dinner_time, "1.5h")
                ]
                
                # Group meals by closest landmark to reduce API calls
                meal_groups = {}
                for meal_type, time_minutes, duration in meal_schedule:
                    closest_landmark = find_closest_landmark_to_time(landmarks, time_minutes)
                    if closest_landmark and closest_landmark.location:
                        location_key = f"{closest_landmark.location.lat:.3f},{closest_landmark.location.lng:.3f}"
                        if location_key not in meal_groups:
                            meal_groups[location_key] = {
                                "location": closest_landmark.location,
                                "meals": []
                            }
                        meal_groups[location_key]["meals"].append((meal_type, time_minutes, duration))
                
                debug_print(f"📍 Grouped meals into {len(meal_groups)} location clusters")
                
                # Search for restaurants for each location group (reduced API calls)
                for location_key, group in meal_groups.items():
                    meal_types = [meal[0] for meal in group["meals"]]
                    debug_print(f"🔍 Searching for {meal_types} near {location_key}")
                    
                    restaurant_data = await search_multiple_restaurants_near_location(
                        places_client, destination, group["location"], meal_types, used_restaurants
                    )
                    
                    debug_print(f"🍽️ Found {len(restaurant_data)} restaurants for location group")
                    
                    # Assign restaurants to meals
                    for i, (meal_type, time_minutes, duration) in enumerate(group["meals"]):
                        if i < len(restaurant_data):
                            time_str = f"{time_minutes // 60:02d}:{time_minutes % 60:02d}"
                            restaurant_block = ItineraryBlock(
                                name=restaurant_data[i]["name"],
                                type="restaurant",
                                description=None,  # Restaurants don't need descriptions - website provides better info
                                start_time=time_str,
                                duration=duration,
                                mealtime=meal_type,
                                location=restaurant_data[i]["location"],
                                place_id=restaurant_data[i]["place_id"],
                                rating=restaurant_data[i]["rating"],
                                address=restaurant_data[i]["address"],
                                photo_url=restaurant_data[i]["photo_url"],
                                website=restaurant_data[i]["website"]
                            )
                            restaurants.append(restaurant_block)
                            used_restaurants.add(restaurant_data[i]["name"].lower())
                            debug_print(f"   🍽️ {meal_type.title()}: {restaurant_data[i]['name']} at {time_str} ({duration})")
        
        else:
            # Fallback if no landmarks - use destination center
            debug_print("⚠️ No landmarks found, using destination center for restaurant search")
            restaurant_data = await search_multiple_restaurants_near_location(
                places_client, destination, None, ["breakfast", "lunch", "dinner"], used_restaurants
            )
            
            debug_print(f"🍽️ Found {len(restaurant_data)} restaurants for destination center")
            
            meal_times = [
                ("breakfast", "08:00", "45m"),
                ("lunch", "12:30", "1h"),
                ("dinner", "18:00", "1.5h")
            ]
            
            for i, (meal_type, start_time, duration) in enumerate(meal_times):
                if i < len(restaurant_data):
                    restaurant_block = ItineraryBlock(
                        name=restaurant_data[i]["name"],
                        type="restaurant",
                        description=None,  # Restaurants don't need descriptions - website provides better info
                        start_time=start_time,
                        duration=duration,
                        mealtime=meal_type,
                        location=restaurant_data[i]["location"],
                        place_id=restaurant_data[i]["place_id"],
                        rating=restaurant_data[i]["rating"],
                        address=restaurant_data[i]["address"],
                        photo_url=restaurant_data[i]["photo_url"],
                        website=restaurant_data[i]["website"]
                    )
                    restaurants.append(restaurant_block)
                    used_restaurants.add(restaurant_data[i]["name"].lower())
                    debug_print(f"   🍽️ {meal_type.title()}: {restaurant_data[i]['name']} at {start_time} ({duration})")
    
    # Create new day plan with restaurants added
    enhanced_day = StructuredDayPlan(
        day=day_plan.day,
        blocks=day_plan.blocks + restaurants  # Add restaurants to existing landmarks
    )
    
    debug_print(f"✅ Day {day_plan.day} enhanced: {len(day_plan.blocks)} landmarks + {len(restaurants)} restaurants = {len(enhanced_day.blocks)} total blocks")
    
    return enhanced_day


async def search_multiple_restaurants_near_location(
    places_client: GooglePlacesClient,
    destination: str,
    location: Optional[Location],
    meal_types: List[str],
    used_restaurants: set
) -> List[Dict]:
    """Search for multiple restaurants near a location with a single API call"""
    try:
        # Search parameters
        search_params = {
            "place_type": "restaurant",
            "radius": 3000  # 3km radius to get good variety
        }
        
        if location:
            search_params["location"] = {"lat": location.lat, "lng": location.lng}
            debug_print(f"🔍 Searching restaurants near location: {location.lat:.3f}, {location.lng:.3f}")
        else:
            # Geocode destination if no location provided
            debug_print(f"🔍 Geocoding destination: {destination}")
            geocode_result = await places_client.geocode(destination)
            if not geocode_result:
                debug_print("❌ Failed to geocode destination")
                return []
            search_params["location"] = geocode_result
            debug_print(f"🔍 Using geocoded location: {geocode_result}")
        
        debug_print(f"🔍 Single API call for {len(meal_types)} meals: {meal_types}")
        
        # Single search for restaurants (no keyword to get variety)
        results = await places_client.places_nearby(**search_params)
        
        if not results or not results.get("results"):
            debug_print("❌ No results from places_nearby API call")
            return []
        
        debug_print(f"📊 Places API returned {len(results['results'])} total places")
        
        # Find suitable restaurants for each meal type
        suitable_restaurants = []
        hotel_restaurants_filtered = 0
        low_rating_filtered = 0
        already_used_filtered = 0
        
        for place in results["results"]:
            name = place.get("name", "").lower()
            
            # Skip hotel restaurants and other non-restaurant establishments
            place_types = place.get('types', [])
            place_name_lower = place.get('name', '').lower()
            
            # Check for lodging/hotel types
            if 'lodging' in place_types or 'hotel' in place_types:
                hotel_restaurants_filtered += 1
                debug_print(f"🏨 Skipping hotel restaurant: {place.get('name')}")
                continue
            
            # Check for club/athletic establishments that might not be proper restaurants
            if ('club' in place_name_lower and ('athletic' in place_name_lower or 'country' in place_name_lower or 'golf' in place_name_lower)):
                hotel_restaurants_filtered += 1
                debug_print(f"🏌️ Skipping club establishment: {place.get('name')}")
                continue
            
            # Skip if already used
            if name in used_restaurants:
                already_used_filtered += 1
                continue
                
            # Skip if low rating
            rating = place.get("rating", 0)
            if rating < 4.0:
                low_rating_filtered += 1
                continue
            
            suitable_restaurants.append(place)
            if len(suitable_restaurants) >= len(meal_types) + 5:  # Get more options for diversity
                break
        
        debug_print(f"🍽️ Restaurant filtering results:")
        debug_print(f"   📊 Total places: {len(results['results'])}")
        debug_print(f"   🏨 Hotel restaurants filtered: {hotel_restaurants_filtered}")
        debug_print(f"   ⭐ Low rating filtered: {low_rating_filtered}")
        debug_print(f"   🔄 Already used filtered: {already_used_filtered}")
        debug_print(f"   ✅ Suitable restaurants: {len(suitable_restaurants)}")
        
        if not suitable_restaurants:
            debug_print("❌ No suitable restaurants found after filtering")
            return []
        
        # Select restaurants with better diversity - skip some restaurants to avoid same ones across days
        selected_restaurants = []
        
        # Add some randomization for diversity across days and meal types
        if len(suitable_restaurants) > len(meal_types):
            # Shuffle the suitable restaurants to get different ones each day
            shuffled_restaurants = suitable_restaurants.copy()
            random.shuffle(shuffled_restaurants)
            suitable_restaurants = shuffled_restaurants
            debug_print(f"🔀 Shuffled restaurants for diversity")
        
        # Try to select different types of restaurants for different meals
        for i, meal_type in enumerate(meal_types):
            if i < len(suitable_restaurants):
                place_data = suitable_restaurants[i]
            
                # 🚀 LATENCY OPTIMIZATION: Skip descriptions for restaurants entirely
                # Users get better info from website, rating, and address from Google API
                formatted_data = {
                    "name": place_data.get("name", f"Local Restaurant"),
                    "location": _extract_location_from_place_data(place_data),
                    "place_id": place_data.get("place_id"),
                    "rating": place_data.get("rating"),
                    "address": place_data.get("formatted_address") or place_data.get("vicinity"),
                    "photo_url": extract_photo_url(place_data),
                    "website": place_data.get("website")
                }
                selected_restaurants.append(formatted_data)
                used_restaurants.add(formatted_data["name"].lower())  # Store lowercase for better matching
                debug_print(f"✅ Selected {meal_type}: {formatted_data['name']} (rating: {formatted_data['rating']})")
        
        debug_print(f"🍽️ Final result: {len(selected_restaurants)} restaurants selected with 1 API call")
        return selected_restaurants
        
    except Exception as e:
        logger.error(f"Error searching for multiple restaurants: {e}")
        debug_print(f"❌ Exception in restaurant search: {e}")
        return []


async def enhance_itinerary_simultaneously(
    itinerary: StructuredItinerary,
    places_client: GooglePlacesClient,
    destination: str,
    used_restaurants: set
) -> Tuple[StructuredItinerary, Dict]:
    """Simultaneously add restaurants and enhance landmarks for maximum speed"""
    
    debug_print("🚀 SIMULTANEOUS OPTIMIZATION: Adding restaurants + enhancing landmarks in parallel")
    
    # Prepare tasks for parallel execution
    restaurant_tasks = []
    enhancement_tasks = []
    
    # Create restaurant addition tasks for each day
    for day_plan in itinerary.itinerary:
        is_theme_park = is_theme_park_day(day_plan)
        task = add_restaurants_to_day_optimized(
            day_plan,
            places_client,
            destination,
            used_restaurants,
            is_theme_park
        )
        restaurant_tasks.append(task)
    
    # Create landmark enhancement task
    enhancement_task = enhance_landmarks_cost_efficiently(itinerary, places_client, destination)
    
    # Execute all tasks simultaneously
    debug_print(f"⚡ Running {len(restaurant_tasks)} restaurant tasks + 1 enhancement task in parallel")
    
    start_time = time.time()
    
    # Run restaurant addition and landmark enhancement simultaneously
    restaurant_results, (enhanced_itinerary, api_calls) = await asyncio.gather(
        asyncio.gather(*restaurant_tasks),
        enhancement_task
    )
    
    end_time = time.time()
    
    # Update itinerary with restaurant results - FIXED MERGING LOGIC
    for i, enhanced_day_with_restaurants in enumerate(restaurant_results):
        if i < len(enhanced_itinerary.itinerary):
            # Get enhanced landmarks from the enhancement task
            enhanced_landmarks = [b for b in enhanced_itinerary.itinerary[i].blocks if b.type == "landmark"]
            # Get restaurants from the restaurant addition task
            restaurants = [b for b in enhanced_day_with_restaurants.blocks if b.type == "restaurant"]
            
            # Combine and sort all blocks by start time
            all_blocks = enhanced_landmarks + restaurants
            all_blocks.sort(key=lambda x: parse_time_to_minutes(x.start_time))
            
            # Update the enhanced itinerary with the combined blocks
            enhanced_itinerary.itinerary[i].blocks = all_blocks
            
            debug_print(f"📅 Day {i+1}: {len(enhanced_landmarks)} landmarks + {len(restaurants)} restaurants = {len(all_blocks)} total blocks")
    
    performance_metrics = {
        "restaurant_and_enhancement_time": round(end_time - start_time, 2),
        "api_calls_saved": "Significant reduction through parallel processing and smart grouping",
        "enhancement_api_calls": api_calls
    }
    
    debug_print(f"✅ Simultaneous processing completed in {end_time - start_time:.2f} seconds")
    debug_print(f"💰 API calls used for enhancement: {api_calls}")
    
    return enhanced_itinerary, performance_metrics


def find_optimal_meal_time(landmarks: List[ItineraryBlock], meal_type: str, target_start: int, target_end: int) -> int:
    """Find the optimal time for a meal between landmarks"""
    
    # Look for gaps in the landmark schedule around the target time
    for i in range(len(landmarks) - 1):
        current_end = parse_time_to_minutes(landmarks[i].start_time) + parse_duration_to_minutes(landmarks[i].duration)
        next_start = parse_time_to_minutes(landmarks[i + 1].start_time)
        
        # Check if there's a gap that overlaps with our target time
        if current_end <= target_end and next_start >= target_start:
            # Found a suitable gap, place meal in the middle
            gap_middle = (current_end + next_start) // 2
            return max(target_start, min(target_end, gap_middle))
    
    # No suitable gap found, use target time
    return (target_start + target_end) // 2


def find_closest_landmark_to_time(landmarks: List[ItineraryBlock], target_time: int) -> Optional[ItineraryBlock]:
    """Find the landmark closest to the target meal time"""
    
    if not landmarks:
        return None
    
    closest_landmark = None
    min_distance = float('inf')
    
    for landmark in landmarks:
        landmark_start = parse_time_to_minutes(landmark.start_time)
        landmark_end = landmark_start + parse_duration_to_minutes(landmark.duration)
        
        # Calculate distance to the landmark time window
        if target_time < landmark_start:
            distance = landmark_start - target_time
        elif target_time > landmark_end:
            distance = target_time - landmark_end
        else:
            distance = 0  # Target time is within the landmark window
        
        if distance < min_distance:
            min_distance = distance
            closest_landmark = landmark
    
    return closest_landmark

async def search_and_get_restaurant(
    places_client: GooglePlacesClient,
    destination: str,
    meal_type: str,
    location: Optional[Location],
    used_restaurants: set
) -> Optional[Dict]:
    """Search for a restaurant using Google Places API with LLM descriptions for cost optimization"""
    try:
        # Search parameters
        search_params = {
            "place_type": "restaurant",
            "keyword": f"{meal_type} restaurant",
            "radius": 2000  # 2km radius
        }
        
        if location:
            search_params["location"] = {"lat": location.lat, "lng": location.lng}
        else:
            # Geocode destination if no location provided
            geocode_result = await places_client.geocode(destination)
            if not geocode_result:
                return None
            search_params["location"] = geocode_result
        
        # Search for restaurants
        results = await places_client.places_nearby(**search_params)
        
        if not results or not results.get("results"):
            return None
        
        # Find suitable restaurants and generate LLM descriptions in batch
        suitable_restaurants = []
        for place in results["results"]:
            name = place.get("name", "").lower()
            if name not in used_restaurants and place.get("rating", 0) >= 4.0:
                suitable_restaurants.append(place)
                if len(suitable_restaurants) >= 3:  # Get a few options
                    break
        
        if not suitable_restaurants:
            return None
        
        # 🚀 LATENCY OPTIMIZATION: Skip descriptions for restaurants entirely
        # Users get better info from website, rating, and address from Google API
        place_data = suitable_restaurants[0]  # Take the first suitable restaurant
        
        # Format the data properly for add_restaurants_to_day
        formatted_data = {
            "name": place_data.get("name", f"Local {meal_type.title()} Spot"),
            "location": _extract_location_from_place_data(place_data),
            "place_id": place_data.get("place_id"),
            "rating": place_data.get("rating"),
            "address": place_data.get("formatted_address") or place_data.get("vicinity"),
            "photo_url": extract_photo_url(place_data),
            "website": place_data.get("website")
        }
        
        debug_print(f"🍽️ Found restaurant without LLM: {formatted_data['name']} (rating: {formatted_data['rating']})")
        return formatted_data
    except Exception as e:
        logger.error(f"Error searching for restaurant: {e}")
        return None

# Restaurant description functions removed - descriptions no longer needed
# Users get better information from restaurant websites and Google data

def _extract_location_from_place_data(place_data: Dict) -> Optional[Location]:
    """Extract Location object from Google Places data"""
    try:
        if 'geometry' in place_data and 'location' in place_data['geometry']:
            loc = place_data['geometry']['location']
            return Location(lat=loc['lat'], lng=loc['lng'])
    except Exception:
        pass
    return None

async def enhance_landmarks_cost_efficiently(
    itinerary: StructuredItinerary, 
    places_client: Optional[GooglePlacesClient] = None,
    destination: str = ""
) -> (StructuredItinerary, int):
    """
    Enhances landmarks with Google Places data and generated descriptions with a focus on cost and speed.
    
    Returns:
        A tuple containing the enhanced itinerary and the number of Google Places API calls made.
    """
    if not places_client:
        debug_print("⚠️ No places client available - skipping landmark enhancement")
        return itinerary, 0
    
    # Count total landmarks across all days
    total_landmarks = sum(
        len([b for b in day.blocks if b.type == "landmark"]) 
        for day in itinerary.itinerary
    )
    
    # INCREASED API LIMIT to ensure all days get coverage
    min_coverage = max(6, int(total_landmarks * 0.8))  # Increased to 80% coverage
    max_api_calls = min(min_coverage, 15)  # Increased cap to 15 for better coverage
    
    debug_print(f"💰 Starting cost-efficient landmark enhancement...")
    debug_print(f"📊 Total landmarks: {total_landmarks}, API limit: {max_api_calls} (targeting {min_coverage}/{total_landmarks} coverage)")
    
    api_calls_made = 0
    
    # Get destination coordinates for search center
    destination_location = None
    try:
        geocode_result = await places_client.geocode(destination)
        if geocode_result:
            destination_location = {"lat": geocode_result["lat"], "lng": geocode_result["lng"]}
            debug_print(f"📍 Destination coordinates: {destination_location}")
        else:
            debug_print("⚠️ Could not geocode destination, using default search")
    except Exception as e:
        debug_print(f"⚠️ Geocoding failed: {e}")
    
    # Collect all landmarks that need enhancement and prioritize them
    landmarks_to_enhance = []
    
    for day_plan in itinerary.itinerary:
        for i, block in enumerate(day_plan.blocks):
            if block.type == "landmark":
                # ALWAYS enhance landmarks that are missing essential data
                needs_enhancement = False
                
                # Calculate priority score (higher = more important to enhance)
                priority = 0
                if not block.place_id: 
                    priority += 3
                    needs_enhancement = True
                if not block.location: 
                    priority += 2
                    needs_enhancement = True
                if not block.address: 
                    priority += 2
                    needs_enhancement = True
                if not block.photo_url: 
                    priority += 3  # Increased priority for photos
                    needs_enhancement = True
                if not block.rating: 
                    priority += 1
                    needs_enhancement = True
                if not block.website:
                    priority += 2  # Added priority for websites
                    needs_enhancement = True
                
                # Add day-based priority to ensure all days get coverage
                day_priority_bonus = 0
                if day_plan.day == 1:
                    day_priority_bonus = 10  # Highest priority for Day 1
                elif day_plan.day == 2:
                    day_priority_bonus = 8   # High priority for Day 2
                elif day_plan.day == 3:
                    day_priority_bonus = 6   # Ensure Day 3 gets coverage too
                
                priority += day_priority_bonus
                
                if needs_enhancement:
                    landmarks_to_enhance.append({
                        'block': block,
                        'day': day_plan.day,
                        'priority': priority
                    })
                    debug_print(f"   📋 Day {day_plan.day}: {block.name} needs enhancement (priority: {priority})")
                else:
                    debug_print(f"   ⏭️ Day {day_plan.day}: {block.name} - already has complete data")
    
    # Sort by priority (highest first) to enhance most important landmarks first
    landmarks_to_enhance.sort(key=lambda x: x['priority'], reverse=True)
    
    debug_print(f"📋 Found {len(landmarks_to_enhance)} landmarks needing enhancement")
    debug_print(f"🎯 Priority order: {[(item['block'].name, item['day'], item['priority']) for item in landmarks_to_enhance[:5]]}")
    
    # Batch enhance landmarks with LLM descriptions for cost optimization
    landmarks_needing_google_data = []
    landmarks_needing_descriptions = []
    
    # Separate landmarks that need Google data vs. just descriptions
    for item in landmarks_to_enhance[:max_api_calls]:
        block = item['block']
        priority = item['priority']
        
        # All landmarks get Google API call for complete data (place_id, location, photos, websites)
        # Only skip Google API if landmark already has ALL essential data
        if not block.place_id or not block.location or not block.photo_url or not block.website:
            landmarks_needing_google_data.append(item)
        else:
            # Only use LLM for landmarks that have all Google data but need better descriptions
            landmarks_needing_descriptions.append(item)
    
    # 🚀 SPEED + COST OPTIMIZATION: Single LLM call for ALL landmarks at once
    async def generate_all_landmark_descriptions():
        """Generate descriptions for ALL landmarks in a single LLM call"""
        if not itinerary.itinerary:
            return
            
        # Collect ALL landmarks from the itinerary (both selected and recommended)
        all_landmarks = []
        landmark_blocks = []
        
        for day_plan in itinerary.itinerary:
            for block in day_plan.blocks:
                if block.type == "landmark":
                    # Prepare landmark data for LLM
                    landmark_data = {
                        'name': block.name,
                        'types': ['tourist_attraction', 'landmark'],
                        'rating': block.rating or 4.5,
                        'user_ratings_total': 100,
                        'location': {
                            'lat': block.location.lat if block.location else 37.7749,
                            'lng': block.location.lng if block.location else -122.4194
                        }
                    }
                    all_landmarks.append(landmark_data)
                    landmark_blocks.append(block)
        
        if not all_landmarks:
            return
            
        debug_print(f"💰 Generating descriptions for ALL {len(all_landmarks)} landmarks in single LLM call")
        
        try:
            # Single LLM call for all landmarks
            llm_service = await get_llm_description_service()
            user_preferences = {
                'destination': destination,
                'type': 'landmarks',
                'with_kids': False,  # Can be enhanced with actual user preferences
                'special_requests': 'Generate engaging, concise descriptions'
            }
            
            enhanced_landmarks = await llm_service.generate_place_descriptions(
                all_landmarks,
                destination,
                user_preferences,
                batch_size=len(all_landmarks)  # Single batch for all landmarks
            )
            
            # Apply descriptions to all landmark blocks
            for i, block in enumerate(landmark_blocks):
                if i < len(enhanced_landmarks) and enhanced_landmarks[i].get('description'):
                    block.description = enhanced_landmarks[i]['description']
                    debug_print(f"   ✅ Enhanced {block.name} with LLM description")
                else:
                    # Fallback description
                    block.description = f"{block.name} is a notable landmark in {destination}."
                    
        except Exception as e:
            debug_print(f"   ❌ Error generating landmark descriptions: {e}")
            # Add fallback descriptions
            for block in landmark_blocks:
                if not block.description:
                    block.description = f"{block.name} is a notable landmark in {destination}."

    # Start single LLM call for all landmarks
    llm_task = asyncio.create_task(generate_all_landmark_descriptions())

    # 🚀 SPEED OPTIMIZATION: Simplified Google API processing for photos only
    async def enhance_photos_and_data():
        """Enhance landmarks with photos and Google Places data in parallel"""
        nonlocal api_calls_made
        
        if not landmarks_needing_google_data:
            debug_print("📸 No landmarks need Google Places data enhancement")
            return
        
        debug_print(f"📸 Starting photo enhancement for {len(landmarks_needing_google_data)} landmarks")
        
        # Track enhancement results
        enhanced_count = 0
        failed_count = 0
        
        # Process landmarks in batches to avoid overwhelming the API
        batch_size = 3
        for i in range(0, len(landmarks_needing_google_data), batch_size):
            batch = landmarks_needing_google_data[i:i + batch_size]
            
            # Process batch in parallel
            tasks = []
            for item in batch:
                if api_calls_made < max_api_calls:
                    task = enhance_single_landmark_photos(item['block'])
                    tasks.append(task)
                else:
                    debug_print(f"💰 API limit reached, skipping {item['block'].name}")
                    break
            
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for j, result in enumerate(results):
                    if isinstance(result, Exception):
                        debug_print(f"❌ Error enhancing {batch[j]['block'].name}: {result}")
                        failed_count += 1
                    elif result:
                        enhanced_count += 1
                    else:
                        failed_count += 1
        
        debug_print(f"📸 Photo enhancement complete: {enhanced_count} enhanced, {failed_count} failed, {api_calls_made} API calls used")
        
        # Report which landmarks still don't have photos
        landmarks_without_photos = []
        landmarks_without_websites = []
        for day_plan in itinerary.itinerary:
            for block in day_plan.blocks:
                if block.type == "landmark":
                    if not block.photo_url:
                        landmarks_without_photos.append(f"Day {day_plan.day}: {block.name}")
                    if not block.website:
                        landmarks_without_websites.append(f"Day {day_plan.day}: {block.name}")
        
        if landmarks_without_photos:
            debug_print(f"⚠️ Landmarks still without photos: {landmarks_without_photos}")
        else:
            debug_print("✅ All landmarks now have photos!")
            
        if landmarks_without_websites:
            debug_print(f"⚠️ Landmarks still without websites: {landmarks_without_websites}")
        else:
            debug_print("✅ All landmarks now have websites!")
            
        # Summary by day
        for day_plan in itinerary.itinerary:
            landmarks = [b for b in day_plan.blocks if b.type == "landmark"]
            photos_count = sum(1 for b in landmarks if b.photo_url)
            websites_count = sum(1 for b in landmarks if b.website)
            debug_print(f"📊 Day {day_plan.day}: {len(landmarks)} landmarks, {photos_count} photos, {websites_count} websites")

    async def enhance_single_landmark_photos(block):
        """Enhance a single landmark with photos and basic data"""
        nonlocal api_calls_made
        
        if api_calls_made >= max_api_calls:
            return False
            
        try:
            # Use places_nearby to find the landmark
            search_location = destination_location or {"lat": 37.7749, "lng": -122.4194}  # Default to SF
            
            # Try multiple search strategies for better photo coverage
            search_strategies = [
                # Strategy 1: Exact name search with tourist_attraction
                {
                    "location": search_location,
                    "radius": 25000,  # 25km radius
                    "place_type": "tourist_attraction",
                    "keyword": block.name
                },
                # Strategy 2: Broader search with establishment type
                {
                    "location": search_location,
                    "radius": 30000,  # 30km radius
                    "place_type": "establishment",
                    "keyword": block.name
                }
            ]
            
            best_match = None
            
            for strategy in search_strategies:
                if api_calls_made >= max_api_calls:
                    break
                    
                results = await places_client.places_nearby(**strategy)
                api_calls_made += 1
                debug_print(f"   🔍 Search strategy for {block.name}: {len(results.get('results', []))} results")
                
                if results and results.get('results'):
                    # Find the best match with more flexible matching
                    best_score = 0
                    
                    for place_data in results['results'][:5]:  # Check top 5 results
                        place_name = place_data.get('name', '').lower()
                        landmark_name = block.name.lower()
                        
                        # Multiple matching strategies
                        score = 0
                        
                        # Exact match gets highest score
                        if landmark_name == place_name:
                            score = 100
                        # Substring match
                        elif landmark_name in place_name or place_name in landmark_name:
                            score = 80
                        # Word overlap
                        else:
                            landmark_words = set(landmark_name.split())
                            place_words = set(place_name.split())
                            common_words = landmark_words & place_words
                            if common_words:
                                score = len(common_words) * 20
                        
                        # Bonus points for having photos
                        if place_data.get('photos'):
                            score += 10
                            
                        # Bonus points for having rating
                        if place_data.get('rating'):
                            score += 5
                        
                        if score > best_score:
                            best_score = score
                            best_match = place_data
                            debug_print(f"   📸 Better match found: {place_name} (score: {score})")
                
                # If we found a good match, stop searching
                if best_match and best_score >= 80:
                    break
            
            if best_match:
                # Update only essential data
                if not block.place_id and best_match.get('place_id'):
                    block.place_id = best_match['place_id']
                    debug_print(f"   🆔 Added place_id for {block.name}")
                
                if not block.rating and best_match.get('rating'):
                    block.rating = best_match['rating']
                    debug_print(f"   ⭐ Added rating {best_match['rating']} for {block.name}")
                
                if not block.location and 'geometry' in best_match:
                    loc = best_match['geometry']['location']
                    block.location = Location(lat=loc['lat'], lng=loc['lng'])
                    debug_print(f"   📍 Added location for {block.name}")
                
                if not block.address:
                    address = best_match.get('formatted_address') or best_match.get('vicinity')
                    if address:
                        block.address = address
                        debug_print(f"   📮 Added address for {block.name}: {address}")
                
                # Most importantly - add photo URL with better error handling
                if not block.photo_url:
                    photo_url = extract_photo_url(best_match)
                    if photo_url:
                        block.photo_url = photo_url
                        debug_print(f"   📸 Added photo URL for {block.name}: {photo_url}")
                    else:
                        debug_print(f"   ⚠️ No photo available for {block.name}")
                
                # IMPROVED WEBSITE ASSIGNMENT - be more aggressive
                if not block.website:
                    website = best_match.get('website')
                    if website:
                        block.website = website
                        debug_print(f"   🌐 Added website for {block.name}: {website}")
                    else:
                        # Try to get website from place details if we have place_id
                        if best_match.get('place_id') and api_calls_made < max_api_calls:
                            try:
                                place_details = await places_client.place_details(best_match['place_id'])
                                api_calls_made += 1
                                if place_details and place_details.get('result', {}).get('website'):
                                    block.website = place_details['result']['website']
                                    debug_print(f"   🌐 Added website from place details for {block.name}: {block.website}")
                                else:
                                    debug_print(f"   ⚠️ No website found in place details for {block.name}")
                            except Exception as e:
                                debug_print(f"   ❌ Error getting place details for {block.name}: {e}")
                        else:
                            debug_print(f"   ⚠️ No website available for {block.name}")
                
                debug_print(f"   ✅ Enhanced {block.name} with Google Places data (score: {best_score})")
                return True
            else:
                debug_print(f"   ❌ No suitable match found for {block.name}")
                    
        except Exception as e:
            debug_print(f"   ❌ Error enhancing {block.name}: {e}")
        
        return False

    # Start photo enhancement in parallel with LLM
    photo_task = asyncio.create_task(enhance_photos_and_data())
    
    # Wait for both LLM and photo processing to complete
    await asyncio.gather(llm_task, photo_task)
    
    # Report final coverage
    enhanced_count = api_calls_made
    coverage_percent = (enhanced_count / total_landmarks * 100) if total_landmarks > 0 else 0
    
    debug_print(f"💰 Landmark enhancement complete:")
    debug_print(f"   📊 Enhanced: {enhanced_count}/{total_landmarks} landmarks ({coverage_percent:.1f}% coverage)")
    debug_print(f"   💸 API calls used: {api_calls_made}/{max_api_calls}")
    
    return itinerary, api_calls_made

async def complete_itinerary_from_selection(
    selection: LandmarkSelection,
    places_client: Optional[GooglePlacesClient] = None
) -> Dict:
    """Generate complete itinerary with landmarks and restaurants"""
    start_time = time.time()
    performance_metrics = {
        "timings": {},
        "costs": {
            "openai": {},
            "google_places": {}
        }
    }
    try:
        # Check cache
        cache_key = get_cache_key(selection)
        if cache_key in _itinerary_cache:
            debug_print("✅ Cache hit - returning cached itinerary")
            return _itinerary_cache[cache_key]
        
        # Extract details
        destination = selection.details.destination
        travel_days = selection.details.travelDays
        with_kids = selection.details.withKids
        kids_age = selection.details.kidsAge
        with_elderly = selection.details.withElders
        special_requests = selection.details.specialRequests
        
        # Format selected attractions
        selected_attractions = ""
        for day in selection.itinerary:
            selected_attractions += f"\nDay {day.day}:\n"
            for attraction in day.attractions:
                selected_attractions += f"- {attraction.name} ({attraction.type})\n"
        
        # Process wishlist
        wishlist_text = ""
        if selection.wishlist:
            wishlist_text = "\nWISHLIST (add if nearby):\n"
            for item in selection.wishlist:
                if isinstance(item, dict):
                    name = item.get('name', 'Unknown')
                    item_type = item.get('type', 'landmark')
                else:
                    name = str(item)
                    item_type = 'landmark'
                wishlist_text += f"- {name} ({item_type})\n"
        
        # Generate itinerary with landmarks
        prompt = create_itinerary_prompt()
        prompt_inputs = {
            "destination": destination,
            "travel_days": travel_days,
            "date_info": "",
            "with_kids": with_kids,
            "kids_age": kids_age,
            "with_elderly": with_elderly,
            "special_requests": special_requests,
            "selected_attractions": selected_attractions,
            "wishlist_recommendations": wishlist_text
        }
        
        # Clear cache for debugging
        debug_print("🧹 Clearing cache for fresh results")
        _itinerary_cache.clear()
        
        # Try with primary model first
        try:
            debug_print("🤖 Calling LLM to generate itinerary...")
            llm_start_time = time.time()
            result = await llm.ainvoke(prompt.format(**prompt_inputs))
            llm_end_time = time.time()
            
            # Log token usage
            if result.response_metadata and 'token_usage' in result.response_metadata:
                token_usage = result.response_metadata['token_usage']
                prompt_tokens = token_usage.get('prompt_tokens', 0)
                completion_tokens = token_usage.get('completion_tokens', 0)
                total_tokens = token_usage.get('total_tokens', 0)
                debug_print(f"💰 Token Usage (Primary): {total_tokens} total tokens ({prompt_tokens} prompt, {completion_tokens} completion)")
                performance_metrics["costs"]["openai"]["primary"] = {
                    "model": "gpt-4-turbo",
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens
                }
            
            debug_print(f"📝 LLM Raw Response: {result.content[:500]}...")
            itinerary = parser.parse(result.content)
            llm_end_time = time.time()
            performance_metrics["timings"]["llm_generation"] = round(llm_end_time - llm_start_time, 2)
            debug_print(f"✅ LLM Generated landmarks in {llm_end_time - llm_start_time:.2f} seconds")
            for day in itinerary.itinerary:
                landmarks = [b.name for b in day.blocks if b.type == "landmark"]
                debug_print(f"   Day {day.day}: {landmarks}")
        except Exception as e:
            debug_print(f"⚠️ Primary model failed: {e}, trying backup model")
            llm_start_time = time.time()
            result = await backup_llm.ainvoke(prompt.format(**prompt_inputs))
            llm_end_time = time.time()

            # Log token usage for backup model
            if result.response_metadata and 'token_usage' in result.response_metadata:
                token_usage = result.response_metadata['token_usage']
                prompt_tokens = token_usage.get('prompt_tokens', 0)
                completion_tokens = token_usage.get('completion_tokens', 0)
                total_tokens = token_usage.get('total_tokens', 0)
                debug_print(f"💰 Token Usage (Backup): {total_tokens} total tokens ({prompt_tokens} prompt, {completion_tokens} completion)")
                performance_metrics["costs"]["openai"]["backup"] = {
                    "model": "gpt-3.5-turbo",
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens
                }

            debug_print(f"📝 Backup LLM Raw Response: {result.content[:500]}...")
            itinerary = backup_fallback_parser.parse(result.content)
            llm_end_time = time.time()
            performance_metrics["timings"]["llm_generation_backup"] = round(llm_end_time - llm_start_time, 2)
            debug_print(f"✅ Backup LLM Generated landmarks in {llm_end_time - llm_start_time:.2f} seconds")
            for day in itinerary.itinerary:
                landmarks = [b.name for b in day.blocks if b.type == "landmark"]
                debug_print(f"   Day {day.day}: {landmarks}")
        
        # 🚀 SIMULTANEOUS OPTIMIZATION: Add restaurants and enhance landmarks in parallel
        used_restaurants = set()
        if not places_client:
            debug_print("⚠️ No places client available - skipping restaurant addition and landmark enhancement")
        else:
            debug_print("🚀 SIMULTANEOUS: Adding restaurants + enhancing landmarks in parallel...")
            simultaneous_start_time = time.time()
            
            itinerary, simultaneous_metrics = await enhance_itinerary_simultaneously(
                itinerary, places_client, destination, used_restaurants
            )
            
            simultaneous_end_time = time.time()
            performance_metrics["timings"]["restaurant_and_enhancement"] = round(simultaneous_end_time - simultaneous_start_time, 2)
            performance_metrics["costs"]["google_places"]["enhancement_api_calls"] = simultaneous_metrics.get("enhancement_api_calls", 0)
            performance_metrics["optimization"] = simultaneous_metrics.get("api_calls_saved", "")
            debug_print(f"✅ Simultaneous processing completed in {simultaneous_end_time - simultaneous_start_time:.2f} seconds")
        
        # Remove duplicate landmarks and replace with nearby alternatives
        debug_print("🔍 Checking for duplicate landmarks...")
        duplicate_start_time = time.time()
        itinerary = await remove_duplicate_landmarks(itinerary, places_client)
        duplicate_end_time = time.time()
        performance_metrics["timings"]["duplicate_removal"] = round(duplicate_end_time - duplicate_start_time, 2)
        debug_print(f"✅ Duplicate landmark check completed in {duplicate_end_time - duplicate_start_time:.2f} seconds")
        
        # Format result - fix double nesting issue
        result = {
            "itinerary": [
                {
                    "day": day.day,
                    "blocks": [
                        {
                            "type": block.type,
                            "name": block.name,
                            "description": block.description,
                            "start_time": block.start_time,
                            "duration": block.duration,
                            "mealtime": block.mealtime,
                            "place_id": block.place_id,
                            "rating": block.rating,
                            "location": {"lat": block.location.lat, "lng": block.location.lng} if block.location else None,
                            "address": block.address,
                            "photo_url": block.photo_url,
                            "website": block.website
                        }
                        for block in day.blocks
                    ]
                }
                for day in itinerary.itinerary
            ],
            "performance_metrics": performance_metrics
        }
        
        # Cache the result
        _itinerary_cache[cache_key] = result
        
        end_time = time.time()
        performance_metrics["timings"]["total_generation"] = round(end_time - start_time, 2)
        debug_print(f"✅ Total itinerary generation time: {end_time - start_time:.2f} seconds")
        return result
        
    except Exception as e:
        logger.error(f"Error in complete_itinerary_from_selection: {e}")
        return {"error": str(e)}

# Helper functions for time calculations
def parse_time_to_minutes(time_str: str) -> int:
    """Convert HH:MM time string to minutes since midnight"""
    try:
        hours, minutes = map(int, time_str.split(':'))
        return hours * 60 + minutes
    except:
        return 0

def parse_duration_to_minutes(duration_str: str) -> int:
    """Parse duration string like '1.5h', '45m' to minutes"""
    try:
        duration_str = duration_str.lower().strip()
        debug_print(f"🕐 Parsing duration: '{duration_str}'")
        
        if 'h' in duration_str:
            # Handle formats like '1h', '1.5h', '2hours'
            hours_str = duration_str.replace('h', '').replace('hours', '').replace('hour', '').strip()
            hours = float(hours_str)
            minutes = int(hours * 60)
            debug_print(f"   ✅ Parsed {duration_str} as {hours} hours = {minutes} minutes")
            return minutes
        elif 'm' in duration_str:
            # Handle formats like '45m', '90min', '120minutes'
            minutes_str = duration_str.replace('m', '').replace('min', '').replace('minutes', '').replace('minute', '').strip()
            minutes = int(float(minutes_str))
            debug_print(f"   ✅ Parsed {duration_str} as {minutes} minutes")
            return minutes
        else:
            # Fallback: assume it's hours if no unit specified
            hours = float(duration_str)
            minutes = int(hours * 60)
            debug_print(f"   ✅ Parsed {duration_str} (no unit) as {hours} hours = {minutes} minutes")
            return minutes
    except Exception as e:
        debug_print(f"   ❌ Error parsing duration '{duration_str}': {e}, defaulting to 120 minutes")
        return 120  # Default 2 hours

async def remove_duplicate_landmarks(itinerary: StructuredItinerary, places_client: Optional[GooglePlacesClient] = None) -> StructuredItinerary:
    """Remove duplicate landmarks across days and replace with nearby alternatives (cost-efficiently)"""
    if not places_client:
        debug_print("⚠️ No places client available for duplicate removal")
        return itinerary
    
    seen_landmarks = set()
    total_duplicates_found = 0
    api_calls_used = 0
    max_replacement_calls = 5  # Limit replacement API calls to control costs
    
    debug_print(f"🔍 Scanning {len(itinerary.itinerary)} days for duplicate landmarks...")
    
    for day_plan in itinerary.itinerary:
        landmarks_to_replace = []
        
        debug_print(f"📅 Day {day_plan.day}: {len([b for b in day_plan.blocks if b.type == 'landmark'])} landmarks")
        
        for i, block in enumerate(day_plan.blocks):
            if block.type == "landmark":
                landmark_name_lower = block.name.lower()
                debug_print(f"   🏛️ Checking: {block.name}")
                
                if landmark_name_lower in seen_landmarks:
                    landmarks_to_replace.append(i)
                    total_duplicates_found += 1
                    debug_print(f"🔄 DUPLICATE DETECTED: {block.name} on Day {day_plan.day}")
                else:
                    seen_landmarks.add(landmark_name_lower)
                    debug_print(f"   ✅ Unique: {block.name}")
        
        # Replace duplicate landmarks with nearby alternatives (with cost limits)
        for landmark_index in reversed(landmarks_to_replace):  # Reverse to maintain indices
            original_block = day_plan.blocks[landmark_index]
            debug_print(f"🔄 Finding replacement for: {original_block.name}")
            
            # Only try to find replacement if we haven't exceeded API call limit
            if api_calls_used < max_replacement_calls:
                replacement = await find_replacement_landmark(
                    original_block, 
                    seen_landmarks, 
                    places_client
                )
                api_calls_used += 1
                
                if replacement:
                    day_plan.blocks[landmark_index] = replacement
                    seen_landmarks.add(replacement.name.lower())
                    debug_print(f"✅ Replaced duplicate {original_block.name} with {replacement.name}")
                else:
                    # If no replacement found, remove the duplicate
                    day_plan.blocks.pop(landmark_index)
                    debug_print(f"❌ Removed duplicate {original_block.name} (no replacement found)")
            else:
                # Exceeded API call limit, just remove the duplicate
                day_plan.blocks.pop(landmark_index)
                debug_print(f"💰 Removed duplicate {original_block.name} (API call limit reached)")
    
    debug_print(f"🎯 Duplicate removal complete: {total_duplicates_found} duplicates processed, {api_calls_used} API calls used")
    return itinerary


async def find_replacement_landmark(
    original_block: ItineraryBlock, 
    seen_landmarks: set, 
    places_client: GooglePlacesClient
) -> Optional[ItineraryBlock]:
    """Find a replacement landmark near the original location (cost-efficiently)"""
    try:
        if not original_block.location:
            return None
        
        debug_print(f"💰 Finding replacement for {original_block.name} (1 API call)")
        
        # Use nearby search but limit results to save costs
        search_results = await places_client.places_nearby(
            location={"lat": original_block.location.lat, "lng": original_block.location.lng},
            radius=5000,  # Reduced radius to 5km to get fewer results
            place_type="tourist_attraction"
        )
        
        if not search_results or not search_results.get('results'):
            debug_print(f"   ❌ No nearby attractions found for replacement")
            return None
        
        # Find the first result that's not already used (limit to first 3 to save processing)
        for place_data in search_results['results'][:3]:  # Only check first 3 results
            place_name = place_data.get('name', '')
            if place_name.lower() not in seen_landmarks:
                # Create replacement block with minimal data (no additional API calls)
                replacement_block = ItineraryBlock(
                    name=place_name,
                    type="landmark",
                    description=place_data.get('editorial_summary', {}).get('overview', 'Popular tourist attraction'),
                    start_time=original_block.start_time,
                    duration=original_block.duration,
                    location=Location(
                        lat=place_data['geometry']['location']['lat'],
                        lng=place_data['geometry']['location']['lng']
                    ) if 'geometry' in place_data else original_block.location,
                    place_id=place_data.get('place_id'),
                    rating=place_data.get('rating'),
                    address=place_data.get('formatted_address') or place_data.get('vicinity'),
                    photo_url=extract_photo_url(place_data),  # No additional API call needed
                    website=place_data.get('website')
                )
                debug_print(f"   ✅ Found replacement: {place_name}")
                return replacement_block
        
        debug_print(f"   ❌ No suitable replacement found (all nearby attractions already used)")
        return None
        
    except Exception as e:
        debug_print(f"❌ Error finding replacement landmark: {e}")
        return None
    

def extract_photo_url(place_data: Dict) -> Optional[str]:
    """Extract photo URL from Google Places data"""
    try:
        photos = place_data.get('photos', [])
        if photos and photos[0].get('photo_reference'):
            photo_ref = photos[0]['photo_reference']
            # Use the correct image proxy endpoint that we know works
            return f"/api/v1/image_proxy?photoreference={photo_ref}&maxwidth=800"
    except Exception as e:
        debug_print(f"⚠️ Error extracting photo URL: {e}")
    return None

def _is_theme_park_day(day_plan: StructuredDayPlan) -> bool:
    """Check if a day is a theme park day based on keywords"""
    for block in day_plan.blocks:
        if block.type == "landmark":
            name_lower = block.name.lower()
            duration_minutes = parse_duration_to_minutes(block.duration)
            
            # Check for theme park keywords AND long duration (6+ hours)
            theme_park_keywords = [
                "disneyland", "disney", "universal", "six flags", "knott", 
                "seaworld", "busch gardens", "cedar point", "magic kingdom",
                "epcot", "hollywood studios", "animal kingdom"
            ]
            
            is_theme_park_name = any(keyword in name_lower for keyword in theme_park_keywords)
            is_long_duration = duration_minutes >= 360  # 6+ hours
            
            # Only consider it a theme park day if BOTH conditions are met
            if is_theme_park_name and is_long_duration:
                debug_print(f"🎢 Detected theme park day: {block.name} ({block.duration})")
                return True
    
    debug_print(f"🏛️ Regular day detected")
    return False 