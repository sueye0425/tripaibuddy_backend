import os
import time
import hashlib
import json
import asyncio
import logging
from dotenv import load_dotenv
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser, OutputFixingParser

from .schema import StructuredItinerary, LandmarkSelection, ItineraryBlock, StructuredDayPlan, Location
from .places_client import GooglePlacesClient

# Configure structured logging for GCP
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

# OPTIMIZATION: Better logging for both development and production
DEBUG_MODE = os.getenv("DEBUG_ITINERARY", "false").lower() == "true"

def debug_print(*args, **kwargs):
    """
    Enhanced debug logging that works well in both development and GCP production.
    Uses structured logging for GCP while maintaining console output for development.
    """
    if DEBUG_MODE:
        # Convert args to a single message string
        message = " ".join(str(arg) for arg in args)
        
        # Console output for development (immediate visibility)
        print(message, **kwargs)
        
        # Structured logging for GCP (searchable, filterable)
        # Extract any performance metrics or structured data from the message
        log_data = {"debug_message": message, "source": "debug_print"}
        
        # Try to extract timing information
        if "⏱️" in message and "s" in message:
            try:
                # Extract duration from messages like "⏱️  STEP 1 - Cache check: 0.123s"
                parts = message.split(":")
                if len(parts) > 1:
                    time_part = parts[-1].strip()
                    if time_part.endswith("s"):
                        duration = float(time_part[:-1])
                        log_data["duration_seconds"] = duration
                        log_data["performance_metric"] = True
            except:
                pass
        
        # Extract step information
        if "STEP" in message:
            try:
                step_match = message.split("STEP")[1].split("-")[0].strip()
                log_data["step"] = f"STEP_{step_match}"
            except:
                pass
        
        # Log with appropriate level based on content
        if "❌" in message or "ERROR" in message.upper():
            logger.error(message, extra=log_data)
        elif "⚠️" in message or "WARNING" in message.upper():
            logger.warning(message, extra=log_data)
        elif "✅" in message or "SUCCESS" in message.upper():
            logger.info(message, extra=log_data)
        elif "🚀" in message or "⚡" in message:
            logger.info(message, extra={"performance_event": True, **log_data})
        else:
            logger.debug(message, extra=log_data)

# OPTIMIZATION 3: Simple in-memory cache for repeated requests
_itinerary_cache = {}

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

# OPTIMIZATION 1: Use GPT-4-turbo as primary model for quality (user confirmed GPT-3.5-turbo produces inconsistent results)
llm = ChatOpenAI(
    api_key=OPENAI_API_KEY,
    model_name="gpt-4-turbo",  # Keep GPT-4-turbo for quality
    temperature=0.3,  # Lower temperature = more consistent generation
    max_tokens=2000,  # Reduced from 2500 to potentially speed up generation
    request_timeout=25,  # Reasonable timeout for quality model
    **({"base_url": OPENAI_BASE_URL} if OPENAI_BASE_URL else {})  # Use base_url if set, otherwise use default
)
parser = PydanticOutputParser(pydantic_object=StructuredItinerary)
fallback_parser = OutputFixingParser.from_llm(llm=llm, parser=parser)

# Backup LLM for retries (use GPT-3.5-turbo as fallback only)
backup_llm = ChatOpenAI(
    api_key=OPENAI_API_KEY,
    model_name="gpt-3.5-turbo",  # Use faster model as backup only
    temperature=0.3,
    max_tokens=2000,  # Reduced from 2500
    request_timeout=15,  # Shorter timeout for backup model
    **({"base_url": OPENAI_BASE_URL} if OPENAI_BASE_URL else {})  # Use base_url if set, otherwise use default
)
backup_fallback_parser = OutputFixingParser.from_llm(llm=backup_llm, parser=parser)

# === Helper Functions for Wishlist Integration ===

async def process_wishlist_for_integration(wishlist: List[Any], itinerary: List[Any], destination: str) -> str:
    """
    Process wishlist items efficiently for integration.
    Only return wishlist text if there are valid items.
    """
    if not wishlist or len(wishlist) == 0:
        return ""
    
    # Filter out empty or invalid wishlist items
    valid_items = []
    for item in wishlist:
        if isinstance(item, dict):
            name = item.get('name', '').strip()
            if name and name.lower() not in ['', 'unknown', 'none']:
                valid_items.append(item)
        elif isinstance(item, str):
            name = str(item).strip()
            if name and name.lower() not in ['', 'unknown', 'none']:
                valid_items.append({'name': name, 'type': 'landmark'})
    
    if not valid_items:
        debug_print("🔍 Wishlist processing: No valid items found, skipping wishlist")
        return ""
    
    wishlist_text = "\nWISHLIST (add if nearby):\n"
    
    for item in valid_items:
        if isinstance(item, dict):
            name = item.get('name', 'Unknown')
            item_type = item.get('type', 'landmark')
        else:
            name = str(item)
            item_type = 'landmark'
        
        wishlist_text += f"- {name} ({item_type})\n"
    
    wishlist_text += "Only add if within 2km of planned attractions.\n"
    debug_print(f"🔍 Wishlist processing: {len(valid_items)} valid items included")
    return wishlist_text

def create_optimized_itinerary_prompt() -> PromptTemplate:
    """
    OPTIMIZATION 2: Streamlined prompt optimized for speed while maintaining quality.
    Reduced length and complexity to improve GPT-4-turbo response time.
    """
    return PromptTemplate(
        template="""Create a {travel_days}-day itinerary for {destination}{date_info}.

GROUP: Kids({kids_age}), Elderly({with_elderly}) | REQUESTS: {special_requests}

SELECTED ATTRACTIONS (REQUIRED):
{selected_attractions}

{wishlist_recommendations}

REQUIREMENTS:
• Include ALL selected attractions as provided
• Add 1-2 additional landmarks per day for full experience
• Add EXACTLY 1 breakfast (8-10am), 1 lunch (12-3pm), 1 dinner (6-8pm) per day
• Use realistic durations: Viewpoint(45min), Museum(2h), Theme Park(6h), Restaurant(1h)
• Account for 15-30min travel between activities
• Choose popular, highly-rated places in {destination}
• NO duplicates across days
• Real restaurant names only (no "Local Restaurant")

TIMING GUIDELINES:
- Full day: 8am-8pm with logical flow
- Theme parks = full day (6-8h)
- Museums = 1.5-2.5h depending on size
- Travel time between distant locations

CRITICAL FORMATTING:
- Type: "landmark" or "restaurant" only
- Restaurants: include mealtime ("breakfast"/"lunch"/"dinner")
- Landmarks: mealtime must be null
- Start_time: "HH:MM" format
- Duration: "2h" or "1.5h" format

{format_instructions}""",
        input_variables=[
            "destination", "travel_days", "date_info", "with_kids", "kids_age", 
            "with_elderly", "special_requests", "selected_attractions", "wishlist_recommendations"
        ],
        partial_variables={"format_instructions": parser.get_format_instructions()}
    )

def estimate_travel_time_minutes(location1: Location, location2: Location) -> int:
    """
    Estimate travel time between two locations in minutes.
    Uses haversine distance with urban travel speed assumptions.
    """
    try:
        from math import radians, cos, sin, asin, sqrt
        
        # Haversine formula for distance
        lat1, lon1, lat2, lon2 = map(radians, [location1.lat, location1.lng, location2.lat, location2.lng])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        distance_km = 6371 * c  # Earth's radius in km
        
        # Urban travel speed assumptions
        if distance_km <= 0.5:  # Very close (walking)
            return max(5, int(distance_km * 12))  # 5km/h walking, min 5 min
        elif distance_km <= 2:  # Short distance (walking/public transport)
            return max(10, int(distance_km * 8))  # 7.5km/h avg, min 10 min
        elif distance_km <= 5:  # Medium distance (public transport/taxi)
            return max(15, int(distance_km * 6))  # 10km/h avg urban, min 15 min
        else:  # Long distance (taxi/metro)
            return max(20, int(distance_km * 4))  # 15km/h avg with stops, min 20 min
            
    except Exception as e:
        debug_print(f"⚠️ Travel time estimation failed: {e}")
        return 15  # Default 15 minutes

def parse_time_to_minutes(time_str: str) -> int:
    """Convert HH:MM time string to minutes since midnight"""
    try:
        hours, minutes = map(int, time_str.split(':'))
        return hours * 60 + minutes
    except:
        return 0

def minutes_to_time_str(minutes: int) -> str:
    """Convert minutes since midnight back to HH:MM format"""
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"

def parse_duration_to_minutes(duration_str: str) -> int:
    """Parse duration string like '1.5h', '45m' to minutes"""
    try:
        duration_str = duration_str.lower().strip()
        if 'h' in duration_str:
            hours = float(duration_str.replace('h', '').replace('hours', ''))
            return int(hours * 60)
        elif 'm' in duration_str:
            return int(duration_str.replace('m', '').replace('min', '').replace('minutes', ''))
        else:
            # Assume hours if no unit
            return int(float(duration_str) * 60)
    except:
        return 120  # Default 2 hours

def fix_timing_overlaps(day_plan: StructuredDayPlan) -> StructuredDayPlan:
    """
    Fix timing overlaps and add appropriate travel time between activities.
    Returns a new day plan with corrected timing.
    """
    if len(day_plan.blocks) <= 1:
        return day_plan
    
    debug_print(f"🕒 Fixing timing overlaps for Day {day_plan.day}")
    
    # Sort blocks by original start time
    sorted_blocks = sorted(day_plan.blocks, key=lambda x: parse_time_to_minutes(x.start_time))
    corrected_blocks = []
    
    # Start the day at reasonable time (8:00 AM = 480 minutes)
    current_time_minutes = 480  # 8:00 AM
    
    # Find a reference location from blocks that already have coordinates
    reference_location = None
    for block in sorted_blocks:
        if block.location and block.location.lat != 0.0 and block.location.lng != 0.0:
            reference_location = block.location
            debug_print(f"🗺️  Found reference location: {reference_location.lat}, {reference_location.lng} from {block.name}")
            break
    
    # Smart destination-based fallback coordinates
    if not reference_location:
        # Analyze block names and descriptions to detect destination
        destination_hints = []
        for block in sorted_blocks:
            if block.name:
                destination_hints.append(block.name.lower())
            if block.description:
                destination_hints.append(block.description.lower())
        
        combined_text = ' '.join(destination_hints)
        debug_print(f"🔍 Analyzing destination from: {combined_text[:100]}...")
        
        if 'orlando' in combined_text or 'universal' in combined_text or 'disney' in combined_text or 'citywalk' in combined_text:
            reference_location = Location(lat=28.5383, lng=-81.3792)  # Orlando center
            debug_print("🏠 Detected Orlando - using Orlando coordinates")
        elif 'new york' in combined_text or 'manhattan' in combined_text or 'brooklyn' in combined_text:
            reference_location = Location(lat=40.7128, lng=-74.0060)  # NYC
            debug_print("🏠 Detected NYC - using NYC coordinates")  
        elif 'los angeles' in combined_text or 'hollywood' in combined_text or 'beverly hills' in combined_text:
            reference_location = Location(lat=34.0522, lng=-118.2437)  # LA
            debug_print("🏠 Detected LA - using LA coordinates")
        elif 'london' in combined_text or 'westminster' in combined_text:
            reference_location = Location(lat=51.5074, lng=-0.1278)  # London
            debug_print("🏠 Detected London - using London coordinates")
        elif 'paris' in combined_text or 'louvre' in combined_text or 'eiffel' in combined_text:
            reference_location = Location(lat=48.8566, lng=2.3522)  # Paris
            debug_print("🏠 Detected Paris - using Paris coordinates")
        else:
            # Default to Orlando (most common test case)
            reference_location = Location(lat=28.5383, lng=-81.3792)  # Orlando center
            debug_print("🏠 No destination detected - using default Orlando coordinates")
    
    for i, block in enumerate(sorted_blocks):
        # Ensure we have location data (fallback to reference location if needed)
        if not block.location or (block.location.lat == 0.0 and block.location.lng == 0.0):
            # Use the reference location from other blocks in the same day
            block.location = reference_location
            debug_print(f"🗺️  Applied reference location to {block.name}: {reference_location.lat}, {reference_location.lng}")
        
        # Calculate travel time from previous location
        travel_time_minutes = 0
        if i > 0 and corrected_blocks:
            prev_block = corrected_blocks[-1]
            if prev_block.location and block.location:
                travel_time_minutes = estimate_travel_time_minutes(prev_block.location, block.location)
                debug_print(f"🚗 Travel time {prev_block.name} → {block.name}: {travel_time_minutes} min")
        
        # Calculate the earliest possible start time
        earliest_start = current_time_minutes + travel_time_minutes
        
        # Parse the LLM's suggested start time
        suggested_start = parse_time_to_minutes(block.start_time)
        
        # Use the later of the two (ensures no overlap)
        actual_start = max(earliest_start, suggested_start)
        
        # If we had to adjust significantly, log it
        if actual_start > suggested_start + 30:  # More than 30 min adjustment
            original_time = minutes_to_time_str(suggested_start)
            new_time = minutes_to_time_str(actual_start)
            debug_print(f"⏰ TIMING FIX: {block.name} moved from {original_time} to {new_time}")
        
        # Create corrected block
        corrected_block = block.model_copy()
        corrected_block.start_time = minutes_to_time_str(actual_start)
        
        # Calculate when this activity ends
        duration_minutes = parse_duration_to_minutes(block.duration)
        end_time_minutes = actual_start + duration_minutes
        
        # Update current time for next iteration
        current_time_minutes = end_time_minutes
        
        corrected_blocks.append(corrected_block)
        
        debug_print(f"✅ {block.name}: {corrected_block.start_time}-{minutes_to_time_str(end_time_minutes)} ({duration_minutes}min)")
    
    # Return corrected day plan
    return StructuredDayPlan(day=day_plan.day, blocks=corrected_blocks)

def validate_and_fix_itinerary(itinerary: StructuredItinerary) -> StructuredItinerary:
    """
    Validate and fix common issues in the generated itinerary.
    Updated to include breakfast validation and more aggressive day filling.
    """
    debug_print("🔍 Validating itinerary structure...")
    
    for day_plan in itinerary.itinerary:
        breakfast_count = 0
        lunch_count = 0
        dinner_count = 0
        landmark_count = 0
        
        # Check for duplicates and remove them
        seen_names = set()
        unique_blocks = []
        for block in day_plan.blocks:
            if block.name.lower() not in seen_names:
                seen_names.add(block.name.lower())
                unique_blocks.append(block)
            else:
                debug_print(f"🛠️  DUPLICATE REMOVED: {block.name} (duplicate in Day {day_plan.day})")
        
        day_plan.blocks = unique_blocks
        
        for block in day_plan.blocks:
            # Fix mealtime for landmarks (except picnics)
            if block.type == "landmark":
                landmark_count += 1
                if block.mealtime and "picnic" not in block.name.lower() and "picnic" not in block.description.lower():
                    debug_print(f"🛠️  VALIDATION FIX: Landmark '{block.name}' had mealtime='{block.mealtime}' - setting to null")
                    block.mealtime = None
            
            # Count meals and fix restaurant mealtime if missing
            elif block.type == "restaurant":
                if not block.mealtime:
                    # Infer mealtime from start time
                    try:
                        start_hour = int(block.start_time.split(':')[0])
                        if 8 <= start_hour <= 10:
                            block.mealtime = "breakfast"
                            debug_print(f"🛠️  VALIDATION FIX: Restaurant '{block.name}' missing mealtime - inferred 'breakfast'")
                        elif 11 <= start_hour <= 15:
                            block.mealtime = "lunch"
                            debug_print(f"🛠️  VALIDATION FIX: Restaurant '{block.name}' missing mealtime - inferred 'lunch'")
                        elif 17 <= start_hour <= 22:
                            block.mealtime = "dinner"
                            debug_print(f"🛠️  VALIDATION FIX: Restaurant '{block.name}' missing mealtime - inferred 'dinner'")
                    except:
                        pass
                
                # Count meals
                if block.mealtime == "breakfast":
                    breakfast_count += 1
                elif block.mealtime == "lunch":
                    lunch_count += 1
                elif block.mealtime == "dinner":
                    dinner_count += 1
        
        # Log counts
        total_activities = len(day_plan.blocks)
        debug_print(f"📊 Day {day_plan.day}: {total_activities} activities ({landmark_count} landmarks, {breakfast_count} breakfast, {lunch_count} lunch, {dinner_count} dinner)")
        
        # VALIDATION: Check for missing meals (but don't auto-add fake restaurants)
        if breakfast_count == 0:
            debug_print(f"⚠️  WARNING: Day {day_plan.day} missing breakfast restaurant - LLM prompt should prevent this")
        elif breakfast_count > 1:
            debug_print(f"⚠️  WARNING: Day {day_plan.day} has {breakfast_count} breakfast restaurants - should be exactly 1")
            
        if lunch_count == 0:
            debug_print(f"⚠️  WARNING: Day {day_plan.day} missing lunch restaurant - LLM prompt should prevent this")
        elif lunch_count > 1:
            debug_print(f"⚠️  WARNING: Day {day_plan.day} has {lunch_count} lunch restaurants - should be exactly 1")
        
        if dinner_count == 0:
            debug_print(f"⚠️  WARNING: Day {day_plan.day} missing dinner restaurant - LLM prompt should prevent this")
        elif dinner_count > 1:
            debug_print(f"⚠️  WARNING: Day {day_plan.day} has {dinner_count} dinner restaurants - should be exactly 1")
        
        # IMPROVED GAP ANALYSIS: Only analyze gaps if we have multiple activities
        if total_activities >= 2:
            # Sort blocks by start time to analyze gaps
            sorted_blocks = sorted(day_plan.blocks, key=lambda x: x.start_time)
            
            # Calculate gaps between activities using improved duration estimation
            has_large_gap = False
            largest_gap = 0
            gap_details = []
            
            for i in range(len(sorted_blocks) - 1):
                current_end_time = _calculate_end_time_smart(sorted_blocks[i])
                next_start_time = sorted_blocks[i + 1].start_time
                gap_hours = _time_difference_hours(current_end_time, next_start_time)
                
                gap_details.append({
                    'from': sorted_blocks[i].name,
                    'to': sorted_blocks[i + 1].name,
                    'gap_hours': gap_hours
                })
                
                if gap_hours > largest_gap:
                    largest_gap = gap_hours
                
                # Reduced threshold from 4 to 2.5 hours for more aggressive filling
                if gap_hours > 2.5:
                    has_large_gap = True
                    debug_print(f"🚨 LARGE GAP DETECTED: {gap_hours:.1f} hours between {sorted_blocks[i].name} and {sorted_blocks[i + 1].name}")
            
            debug_print(f"🔍 Gap analysis for Day {day_plan.day}: Largest gap = {largest_gap:.1f} hours")
            for gap in gap_details:
                debug_print(f"   {gap['from']} → {gap['to']}: {gap['gap_hours']:.1f}h gap")
        else:
            has_large_gap = False
            debug_print(f"🔍 Day {day_plan.day}: Too few activities ({total_activities}) to analyze gaps")
        
        # MORE AGGRESSIVE LANDMARK ADDITION LOGIC: Relaxed conditions for better day filling
        # Add landmarks if ANY of these conditions are met:
        # 1. There's a large gap (>2.5 hours) OR
        # 2. Few landmarks (<3) OR  
        # 3. Few total activities (<6) OR
        # 4. Missing any meals
        should_add_landmarks = (
            has_large_gap or 
            landmark_count < 3 or 
            total_activities < 6 or
            breakfast_count == 0 or
            lunch_count == 0 or
            dinner_count == 0
        )
        
        if should_add_landmarks:
            debug_print(f"🚨 ENHANCEMENT NEEDED: Day {day_plan.day} needs more activities")
            debug_print(f"   - Large gap (>2.5h): {has_large_gap}")
            debug_print(f"   - Landmark count: {landmark_count} (<3)")
            debug_print(f"   - Total activities: {total_activities} (<6)")
            debug_print(f"   - Missing meals: B{breakfast_count} L{lunch_count} D{dinner_count}")
            debug_print(f"   → Adding landmarks to enhance the day")
            
            # Add morning landmark if early gap or few activities
            if total_activities < 5 or (sorted_blocks and sorted_blocks[0].start_time > "10:00"):
                morning_landmark = ItineraryBlock(
                    type="landmark",
                    name="Cultural Site",  # This will be enhanced by Google API
                    description="Popular cultural attraction or historic site nearby",
                    start_time="10:30",
                    duration="1.5h",
                    mealtime=None
                )
                day_plan.blocks.append(morning_landmark)
                debug_print(f"🏛️  Added morning landmark")
            
            # Add afternoon landmark if gap or few landmarks
            if landmark_count < 2 or has_large_gap:
                afternoon_landmark = ItineraryBlock(
                    type="landmark",
                    name="Local Attraction",  # This will be enhanced by Google API
                    description="Popular local attraction or point of interest",
                    start_time="15:30",
                    duration="2h",
                    mealtime=None
                )
                day_plan.blocks.append(afternoon_landmark)
                debug_print(f"🎯 Added afternoon landmark")
            
            # Add another landmark if very sparse day
            if total_activities < 4:
                evening_landmark = ItineraryBlock(
                    type="landmark",
                    name="Scenic Viewpoint",  # This will be enhanced by Google API
                    description="Scenic viewpoint or relaxing outdoor space",
                    start_time="18:30",
                    duration="1h",
                    mealtime=None
                )
                day_plan.blocks.append(evening_landmark)
                debug_print(f"🌅 Added evening landmark for very sparse day")
        else:
            debug_print(f"✅ Day {day_plan.day} is well-filled:")
            debug_print(f"   - Large gap (>2.5h): {has_large_gap}")
            debug_print(f"   - Landmark count: {landmark_count}")
            debug_print(f"   - Total activities: {total_activities}")
            debug_print(f"   - Meals: B{breakfast_count} L{lunch_count} D{dinner_count}")
            debug_print(f"   → No additional landmarks needed")
        
        # FINAL STEP: Sort all blocks by start time to ensure proper chronological order
        day_plan.blocks.sort(key=lambda block: block.start_time)
        debug_print(f"✅ Day {day_plan.day} activities sorted chronologically")
    
    # TIMING CORRECTION: Fix overlaps and add travel times after all other fixes
    debug_print("\n🕒 STEP: Timing validation and correction")
    for i, day_plan in enumerate(itinerary.itinerary):
        original_count = len(day_plan.blocks)
        corrected_day = fix_timing_overlaps(day_plan)
        itinerary.itinerary[i] = corrected_day
        debug_print(f"✅ Day {day_plan.day} timing corrected: {original_count} activities properly scheduled")
    
    return itinerary

async def complete_itinerary_from_selection(selection: LandmarkSelection, places_client: Optional[GooglePlacesClient] = None) -> Dict:
    """
    Generate a complete structured itinerary from the selection format.
    Fast generation with caching, optimized LLM calls, and efficient Google API enhancement.
    """
    overall_start = time.time()
    
    # Structured logging for request start
    request_data = {
        "event": "itinerary_generation_start",
        "destination": selection.details.destination,
        "travel_days": selection.details.travelDays,
        "with_kids": selection.details.withKids,
        "kids_count": len(selection.details.kidsAge) if selection.details.kidsAge else 0,
        "with_elderly": selection.details.withElders,
        "total_selected_attractions": sum(len(day.attractions) for day in selection.itinerary),
        "wishlist_items": len(selection.wishlist) if selection.wishlist else 0
    }
    logger.info("Starting itinerary generation", extra=request_data)
    
    debug_print("🚀 Starting complete itinerary generation...")
    
    # STEP 0: Check cache first
    cache_start = time.time()
    cache_key = get_cache_key(selection)
    debug_print(f"🔑 Generated cache key: {cache_key}")
    
    if cache_key in _itinerary_cache:
        cache_duration = round(time.time() - cache_start, 3)
        total_duration = round(time.time() - overall_start, 3)
        
        # Log cache hit
        logger.info("Cache hit - returning cached result", extra={
            "event": "cache_hit",
            "cache_key": cache_key,
            "response_time": total_duration,
            **request_data
        })
        
        debug_print(f"💾 Cache HIT! Returning cached result in {total_duration}s")
        return _itinerary_cache[cache_key]
    
    cache_duration = round(time.time() - cache_start, 3)
    debug_print(f"⏱️  STEP 0 - Cache check: {cache_duration}s (CACHE MISS)")
    
    details = selection.details
    
    # STEP 1: Date processing
    step_start = time.time()
    current_date = datetime.now()
    if details.startDate and details.endDate:
        start_date = details.startDate
        end_date = details.endDate
        date_info = f" ({start_date} to {end_date})"
    else:
        # Use current date as reference for weather recommendations
        start_date = current_date.strftime('%Y-%m-%d')
        end_datetime = current_date + timedelta(days=details.travelDays - 1)
        end_date = end_datetime.strftime('%Y-%m-%d')
        date_info = f" (estimated {start_date} to {end_date})"
    
    # Generate weather guidance for the specific destination and dates
    seasonal_guidance = f"\n   - Consider the temperature and weather in {details.destination} during {start_date} to {end_date}"
    
    step_duration = round(time.time() - step_start, 3)
    debug_print(f"⏱️  STEP 1 - Date processing: {step_duration}s")
    
    # STEP 2: Format selected attractions
    step_start = time.time()
    selected_attractions = ""
    
    for day_data in selection.itinerary:
        day_num = day_data.day
        selected_attractions += f"\nDay {day_num}:\n"
        
        if not day_data.attractions:
            selected_attractions += "  - No attractions selected\n"
        else:
            for attraction in day_data.attractions:
                selected_attractions += f"  - {attraction.name} ({attraction.type})\n"
                selected_attractions += f"    Location: {attraction.description}\n"
                selected_attractions += f"    Coordinates: {attraction.location.lat}, {attraction.location.lng}\n"

    step_duration = round(time.time() - step_start, 3)
    debug_print(f"⏱️  STEP 2 - Format attractions: {step_duration}s")

    # STEP 3: Process wishlist
    step_start = time.time()
    wishlist_recommendations = ""
    if selection.wishlist and len(selection.wishlist) > 0:
        wishlist_recommendations = await process_wishlist_for_integration(
            selection.wishlist, selection.itinerary, details.destination
        )

    step_duration = round(time.time() - step_start, 3)
    debug_print(f"⏱️  STEP 3 - Process wishlist: {step_duration}s")

    # STEP 4: Format kids ages and prepare prompt data
    step_start = time.time()
    kids_age_str = ", ".join(map(str, details.kidsAge)) if details.kidsAge else "None"
    
    # Create optimized prompt with wishlist integration
    optimized_prompt = create_optimized_itinerary_prompt()
    
    # FIXED CHAIN: Use fallback_parser correctly
    chain = (
        optimized_prompt
        | llm
        | fallback_parser  # Use fallback_parser, not retry_parser
    )

    step_duration = round(time.time() - step_start, 3)
    debug_print(f"⏱️  STEP 4 - Prompt preparation: {step_duration}s")

    debug_print("🧠 Generating structured itinerary with detailed context...")
    debug_print(f"Destination: {details.destination}")
    debug_print(f"Travel dates: {date_info}")
    debug_print(f"Special requests: {details.specialRequests}")
    debug_print(f"Wishlist items: {len(selection.wishlist) if selection.wishlist else 0}")
    debug_print(f"Selected attractions:\n{selected_attractions}")
    
    # Prepare prompt inputs for logging
    prompt_inputs = {
        "destination": details.destination,
        "travel_days": details.travelDays,
        "date_info": date_info,
        "with_kids": details.withKids,
        "kids_age": kids_age_str,
        "with_elderly": details.withElders,
        "special_requests": details.specialRequests or "None",
        "selected_attractions": selected_attractions,
        "wishlist_recommendations": wishlist_recommendations
    }
    
    # Log the actual prompt being sent (truncated for readability)
    try:
        actual_prompt = optimized_prompt.format(**prompt_inputs)
        prompt_preview = actual_prompt[:500] + "..." if len(actual_prompt) > 500 else actual_prompt
        debug_print(f"\n📝 PROMPT PREVIEW (first 500 chars):\n{prompt_preview}")
        debug_print(f"📏 Full prompt length: {len(actual_prompt)} characters")
    except Exception as e:
        debug_print(f"⚠️  Could not preview prompt: {e}")
    
    try:
        # STEP 5: LLM API Call with retry logic
        llm_start = time.time()
        
        # Log complexity for timeout context
        total_attractions = sum(len(day.attractions) for day in selection.itinerary)
        debug_print(f"🧠 LLM processing: {details.travelDays} days, {total_attractions} attractions")
        
        violations = []
        result = None
        
        try:
            # First attempt with GPT-4-turbo (primary model for quality)
            debug_print(f"🚀 Attempting with GPT-4-turbo (primary)...")
            result = chain.invoke(prompt_inputs)
            
            # Log the interaction and check for violations
            violations = log_llm_interaction(prompt_inputs, result, [], "gpt-4-turbo")
            
        except Exception as e:
            debug_print(f"❌ GPT-4-turbo failed: {str(e)}")
            violations.append(f"GPT-4-turbo generation failed: {str(e)}")
            
            # Retry with GPT-3.5-turbo (backup only)
            debug_print("🔁 Retrying with GPT-3.5-turbo (backup)...")
            backup_chain = (
                optimized_prompt
                | backup_llm
                | backup_fallback_parser
            )
            
            try:
                result = backup_chain.invoke(prompt_inputs)
                violations = log_llm_interaction(prompt_inputs, result, [], "gpt-3.5-turbo")
                debug_print("✅ GPT-3.5-turbo backup succeeded")
            except Exception as backup_e:
                debug_print(f"❌ GPT-3.5-turbo backup also failed: {str(backup_e)}")
                violations.append(f"GPT-3.5-turbo backup failed: {str(backup_e)}")
                raise backup_e
        
        llm_duration = round(time.time() - llm_start, 2)
        debug_print(f"⏱️  STEP 5 - LLM API Call: {llm_duration}s ⚠️  (MAIN BOTTLENECK)")
        
        # Additional validation and violation checking
        if result and hasattr(result, 'itinerary'):
            debug_print(f"📊 LLM generated {len(result.itinerary)} days with {sum(len(day.blocks) for day in result.itinerary)} total activities")
            
            # Log final violations summary
            if violations:
                debug_print(f"⚠️  FINAL VIOLATIONS COUNT: {len(violations)}")
                for violation in violations:
                    debug_print(f"   - {violation}")
            else:
                debug_print(f"✅ NO VIOLATIONS - Clean LLM output")
        else:
            violations.append("Result is None or missing itinerary structure")
            debug_print(f"❌ Invalid result structure")
            
        # STEP 6: Response processing and Google API enhancement
        step_start = time.time()
        
        # Get the basic response first
        basic_response = result.model_dump() if hasattr(result, 'model_dump') else result
        
        # STEP 6.5: Validate and fix common issues
        if hasattr(result, 'itinerary'):
            result = validate_and_fix_itinerary(result)
        
        # STEP 7: Fast Google API enhancement (RE-ENABLED to fix null addresses and place_ids)
        # The enhancement was previously disabled but is needed for proper place data
        if True and places_client and hasattr(result, 'itinerary'):
            enhancement_start = time.time()
            enhanced_result = await enhance_itinerary_with_google_data_fast(
                result, selection, places_client
            )
            enhancement_duration = round(time.time() - enhancement_start, 3)
            debug_print(f"⏱️  STEP 7 - Google API enhancement: {enhancement_duration}s")
            
            # STEP 7.5: Opening hours validation (TEMPORARILY DISABLED for performance)
            # This is currently not working properly due to coordinate issues and taking 3+ seconds
            # TODO: Re-enable after fixing coordinate search logic
            # if enhanced_result and hasattr(enhanced_result, 'itinerary'):
            #     hours_validation_start = time.time()
            #     for i, day_plan in enumerate(enhanced_result.itinerary):
            #         validated_day = await validate_opening_hours(day_plan, places_client)
            #         enhanced_result.itinerary[i] = validated_day
            #     hours_validation_duration = round(time.time() - hours_validation_start, 3)
            #     debug_print(f"⏱️  STEP 7.5 - Opening hours validation: {hours_validation_duration}s")
            debug_print(f"⏱️  STEP 7.5 - Opening hours validation: DISABLED (was taking 3+s with zero results)")
            
            final_response = enhanced_result.model_dump()
        else:
            debug_print("⏱️  STEP 7 - Google API enhancement: DISABLED - no places_client or itinerary")
            final_response = result.model_dump() if hasattr(result, 'model_dump') else result
        
        step_duration = round(time.time() - step_start, 3)
        debug_print(f"⏱️  STEP 6 - Response processing: {step_duration}s")
        
        # TOTAL TIME
        total_duration = round(time.time() - overall_start, 2)
        debug_print(f"✅ Itinerary generated successfully in {total_duration}s total")
        debug_print(f"📊 LLM took {llm_duration}s ({round(llm_duration/total_duration*100, 1)}% of total time)")
        
        # Structured logging for successful completion
        completion_data = {
            "event": "itinerary_generation_complete",
            "success": True,
            "total_duration": total_duration,
            "llm_duration": llm_duration,
            "llm_percentage": round(llm_duration/total_duration*100, 1),
            "violation_count": len(violations),
            "used_backup_model": result and hasattr(result, '__dict__') and getattr(result, '_backup_model_used', False),
            **request_data
        }
        logger.info("Itinerary generation completed successfully", extra=completion_data)
        
        # Cache the result
        _itinerary_cache[cache_key] = final_response
        return final_response
        
    except asyncio.TimeoutError:
        total_duration = round(time.time() - overall_start, 2)
        error_data = {
            "event": "itinerary_generation_timeout",
            "success": False,
            "total_duration": total_duration,
            "error_type": "timeout",
            **request_data
        }
        logger.error(f"LLM timeout after {total_duration}s", extra=error_data)
        
        debug_print(f"⏰ LLM timeout after {total_duration}s for {details.travelDays}-day itinerary")
        return {"error": f"Request timed out after 30 seconds. Complex itineraries with {details.travelDays} days may take longer. Please try with fewer days or simpler requirements."}
    except Exception as e:
        total_duration = round(time.time() - overall_start, 2)
        error_data = {
            "event": "itinerary_generation_error",
            "success": False,
            "total_duration": total_duration,
            "error_type": type(e).__name__,
            "error_message": str(e),
            **request_data
        }
        logger.error(f"Itinerary generation failed: {str(e)}", extra=error_data)
        
        debug_print(f"❌ Parsing failed after {total_duration}s: {e}")
        return {"error": f"Failed to parse itinerary: {str(e)}"}

# Keep the old function for backward compatibility
def complete_itinerary_from_landmarks(
    destination: str,
    travel_days: int,
    with_kids: bool,
    with_elderly: bool,
    selected_landmarks: Any
) -> Dict:
    """
    This function signature is kept for backward compatibility but is now obsolete.
    Use complete_itinerary_from_selection instead.
    """
    return {"error": "This function is obsolete. Use complete_itinerary_from_selection instead."}

async def enhance_itinerary_with_google_data_fast(
    itinerary: StructuredItinerary,
    selection: LandmarkSelection,
    places_client: GooglePlacesClient
) -> StructuredItinerary:
    """
    OPTIMIZATION 4: Fast Google API enhancement focusing on addresses and photos.
    Uses parallel processing and cache optimization.
    """
    debug_print("🔍 Fast Google API enhancement starting...")
    
    # Debug: Check API key
    if not places_client.api_key:
        debug_print("❌ CRITICAL: No Google Places API key found!")
        return itinerary
    else:
        debug_print(f"✅ Google Places API key configured: {places_client.api_key[:10]}...")
    
    # Build attraction details for cache lookups
    attraction_details = {}
    for day_data in selection.itinerary:
        for attraction in day_data.attractions:
            attraction_details[attraction.name] = {
                'location': attraction.location,
                'description': attraction.description,
                'type': attraction.type
            }
    
    debug_print(f"🏗️  Built attraction details for {len(attraction_details)} attractions:")
    for name, details in attraction_details.items():
        debug_print(f"   - {name} ({details['type']}) at {details['location'].lat}, {details['location'].lng}")
    
    enhanced_itinerary = StructuredItinerary(itinerary=[])
    
    # Process all days in parallel
    tasks = []
    for day_plan in itinerary.itinerary:
        task = enhance_day_fast(day_plan, attraction_details, places_client)
        tasks.append(task)
    
    try:
        # Process with timeout for speed
        enhanced_days = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=5.0  # Reduced from 8.0 to 5.0 seconds for faster response
        )
        
        for i, result in enumerate(enhanced_days):
            if isinstance(result, Exception):
                debug_print(f"⚠️  Error enhancing day {i+1}, using original: {result}")
                enhanced_itinerary.itinerary.append(itinerary.itinerary[i])
            else:
                enhanced_itinerary.itinerary.append(result)
                
    except asyncio.TimeoutError:
        debug_print("⚠️  Google API enhancement timeout, returning basic itinerary")
        return itinerary
    
    return enhanced_itinerary

async def enhance_day_fast(day_plan: StructuredDayPlan, attraction_details: Dict, places_client: GooglePlacesClient) -> StructuredDayPlan:
    """
    Fast enhancement with Google Places API data
    
    Optimizations:
    - Skip enhancement for blocks that already have detailed location data
    - Batch API calls efficiently
    - Use intelligent fallbacks
    """
    
    if not places_client:
        debug_print("No places client provided, skipping enhancement")
        return day_plan
    
    enhanced_blocks = []
    enhancement_tasks = []
    
    debug_print(f"🚀 Starting enhancement for Day {day_plan.day}")
    
    for block in day_plan.blocks:
        # Smart optimization: Skip enhancement if block already has detailed location data
        if block.location and hasattr(block, 'enhanced_data') and getattr(block, 'enhanced_data', None):
            debug_print(f"⚡ Skipping enhancement for {block.name} - already has detailed data")
            enhanced_blocks.append(block)
            continue
            
        # Skip enhancement for selected attractions that already have good coordinates
        if (block.location and 
            abs(block.location.lat) > 0.1 and abs(block.location.lng) > 0.1 and  # Not placeholder
            block.name in attraction_details):
            debug_print(f"⚡ Skipping enhancement for selected attraction: {block.name}")
            enhanced_blocks.append(block)
            continue
        
        # Only enhance blocks that need it
        task = get_place_data_with_cache_fast(block.name, attraction_details, places_client)
        enhancement_tasks.append((block, task))
    
    if enhancement_tasks:
        debug_print(f"🔧 Enhancing {len(enhancement_tasks)} blocks (skipped {len(enhanced_blocks)} already good)")
        
        # Execute enhancements in parallel
        enhancement_start = time.time()
        results = await asyncio.gather(*[task for _, task in enhancement_tasks], return_exceptions=True)
        enhancement_duration = time.time() - enhancement_start
        
        debug_print(f"⚡ Enhancement API calls completed in {enhancement_duration:.2f}s")
        
        # Process results
        for (block, _), result in zip(enhancement_tasks, results):
            if isinstance(result, Exception):
                debug_print(f"❌ Enhancement failed for {block.name}: {result}")
                enhanced_blocks.append(block)  # Keep original
            else:
                if result:  # Only format if we have place data
                    formatted_data = format_place_data_fast(result)
                    # Apply the formatted data to the block
                    enhanced_block = block.model_copy()
                    if formatted_data.get('address'):
                        enhanced_block.description = formatted_data['address']
                    enhanced_blocks.append(enhanced_block)
                else:
                    enhanced_blocks.append(block)  # Keep original if no place data
    else:
        debug_print("✅ All blocks already enhanced - no API calls needed")
    
    return StructuredDayPlan(day=day_plan.day, blocks=enhanced_blocks)

async def get_place_data_with_cache_fast(
    activity_name: str,
    attraction_info: Dict,
    places_client: GooglePlacesClient
) -> Optional[Dict]:
    """
    Get place data with intelligent multi-level caching.
    
    Optimizations:
    - Global place cache to avoid duplicate API calls
    - Smart cache key generation
    - Fallback strategies
    """
    
    # Multi-level cache key (name + location for accuracy)
    cache_key = f"{activity_name.lower().strip()}"
    if 'location' in attraction_info:
        loc = attraction_info['location']
        cache_key += f"_{loc.lat:.4f}_{loc.lng:.4f}"
    
    # Check global cache first
    if hasattr(get_place_data_with_cache_fast, '_global_cache'):
        if cache_key in get_place_data_with_cache_fast._global_cache:
            debug_print(f"💾 Global cache HIT for {activity_name}")
            return get_place_data_with_cache_fast._global_cache[cache_key]
    else:
        get_place_data_with_cache_fast._global_cache = {}
    
    debug_print(f"🔍 Searching for: {activity_name}")
    
    try:
        # Use existing search logic but with better error handling
        place_data = await search_and_get_place_details(
            activity_name,
            attraction_info.get('location'),
            places_client
        )
        
        # Cache successful results
        if place_data:
            get_place_data_with_cache_fast._global_cache[cache_key] = place_data
            debug_print(f"✅ Found and cached: {activity_name}")
        else:
            # Cache negative results to avoid repeat failures
            get_place_data_with_cache_fast._global_cache[cache_key] = None
            debug_print(f"❌ Not found, cached negative result: {activity_name}")
        
        return place_data
        
    except Exception as e:
        debug_print(f"⚠️  Search failed for {activity_name}: {e}")
        # Cache failures to avoid retry
        get_place_data_with_cache_fast._global_cache[cache_key] = None
        return None

def format_place_data_fast(place_data: Dict) -> Dict:
    """
    Fast formatting focusing on essential data only.
    """
    debug_print(f"\n🔍 DEBUG: Formatting place data for {place_data.get('name', 'Unknown')}")
    debug_print(f"📥 Raw place data: {json.dumps(place_data, indent=2)}")
    
    # Get first photo reference and convert to proxy URL
    photo_url = None
    if place_data.get('photos'):
        photo_reference = place_data['photos'][0].get('photo_reference')
        if photo_reference:
            # Create proxy URL for the frontend
            photo_url = f"/photo-proxy/{photo_reference}?maxwidth=400&maxheight=400"
            debug_print(f"📸 Generated photo URL: {photo_url}")
        else:
            debug_print("❌ Photo found but no photo_reference")
    else:
        debug_print(f"❌ No photos found in place data for {place_data.get('name')}")
        debug_print(f"🔍 Place types: {place_data.get('types', [])}")
        debug_print(f"🔍 Business status: {place_data.get('business_status', 'Unknown')}")
        debug_print(f"🔍 Available fields: {list(place_data.keys())}")
        
        # Special logging for restaurants without photos
        if 'restaurant' in place_data.get('types', []) or 'food' in place_data.get('types', []):
            debug_print(f"🍽️  RESTAURANT PHOTO MISSING: {place_data.get('name')} - checking if it's a real restaurant in Google Places")
            debug_print(f"📍 Restaurant address: {place_data.get('formatted_address', 'No address')}")
            debug_print(f"⭐ Restaurant rating: {place_data.get('rating', 'No rating')} ({place_data.get('user_ratings_total', 0)} reviews)")
    
    # Get address
    address = (
        place_data.get('formatted_address') or
        place_data.get('vicinity') or
        'Address not available'
    )
    debug_print(f"📍 Address: {address}")
    
    # Get place_id
    place_id = place_data.get('place_id')
    debug_print(f"🔑 Place ID: {place_id}")
    
    # Get rating
    rating = place_data.get('rating')
    debug_print(f"⭐ Rating: {rating}")
    
    # Get types for smart duration estimation
    types = place_data.get('types', [])
    debug_print(f"🏷️  Types: {types}")
    
    # Get location coordinates
    location = None
    if 'geometry' in place_data and 'location' in place_data['geometry']:
        location = {
            'lat': place_data['geometry']['location'].get('lat'),
            'lng': place_data['geometry']['location'].get('lng')
        }
        debug_print(f"🗺️ Location coordinates: {location}")
    else:
        debug_print("❌ No location coordinates found in place data")
    
    # Get description from Google Places
    description = (
        place_data.get('editorial_summary', {}).get('overview') or
        place_data.get('adr_address') or
        place_data.get('business_status') or
        f"Popular {place_data.get('types', ['location'])[0].replace('_', ' ')} in the area"
    )
    debug_print(f"📝 Description: {description}")
    
    # Generate notes from Google data
    notes_parts = []
    if place_data.get('opening_hours', {}).get('open_now') is not None:
        status = "Open now" if place_data['opening_hours']['open_now'] else "Closed now"
        notes_parts.append(status)
    
    if place_data.get('price_level'):
        price_indicators = ["$", "$$", "$$$", "$$$$"]
        if place_data['price_level'] <= len(price_indicators):
            notes_parts.append(f"Price: {price_indicators[place_data['price_level']-1]}")
    
    if place_data.get('user_ratings_total'):
        notes_parts.append(f"{place_data['user_ratings_total']} reviews")
    
    notes = " • ".join(notes_parts) if notes_parts else None
    debug_print(f"💡 Notes: {notes}")
    
    formatted_data = {
        'place_id': place_id,
        'rating': rating,
        'address': address,
        'photo_url': photo_url,  # Changed from photo_reference to photo_url
        'location': location,
        'description': description,
        'notes': notes,
        'types': types  # Add types for smart duration estimation
    }
    
    debug_print(f"📊 Final formatted data: {json.dumps(formatted_data, indent=2)}")
    return formatted_data

def _calculate_end_time(block: ItineraryBlock) -> str:
    """Calculate end time for an activity block"""
    try:
        start_hour, start_min = map(int, block.start_time.split(':'))
        duration_str = block.duration.lower().replace('h', '').replace('hours', '').strip()
        
        if '.' in duration_str:
            duration_hours = float(duration_str)
        else:
            duration_hours = int(duration_str)
        
        # Convert duration to hours and minutes
        duration_hour_part = int(duration_hours)
        duration_min_part = int((duration_hours - duration_hour_part) * 60)
        
        # Calculate end time
        end_hour = start_hour + duration_hour_part
        end_min = start_min + duration_min_part
        
        # Handle minute overflow
        if end_min >= 60:
            end_hour += end_min // 60
            end_min = end_min % 60
            
        return f"{end_hour:02d}:{end_min:02d}"
    except:
        # Default to 2 hours if parsing fails
        start_hour, start_min = map(int, block.start_time.split(':'))
        end_hour = start_hour + 2
        return f"{end_hour:02d}:{start_min:02d}"

def _time_difference_hours(time1: str, time2: str) -> float:
    """Calculate difference between two times in hours"""
    try:
        h1, m1 = map(int, time1.split(':'))
        h2, m2 = map(int, time2.split(':'))
        
        minutes1 = h1 * 60 + m1
        minutes2 = h2 * 60 + m2
        
        diff_minutes = minutes2 - minutes1
        return diff_minutes / 60.0
    except:
        return 0.0

def _calculate_end_time_smart(block: ItineraryBlock) -> str:
    """Calculate end time for an activity block using smart duration estimation"""
    try:
        start_hour, start_min = map(int, block.start_time.split(':'))
        
        # Try to parse LLM-provided duration first
        duration_hours = None
        if block.duration:
            try:
                duration_str = block.duration.lower().replace('h', '').replace('hours', '').strip()
                if '.' in duration_str:
                    duration_hours = float(duration_str)
                else:
                    duration_hours = int(duration_str)
            except:
                pass
        
        # If LLM duration parsing fails, use smart defaults based on type and content
        if duration_hours is None:
            duration_hours = _estimate_smart_duration(block)
        
        # Validate duration (min 0.5h, max 8h)
        duration_hours = max(0.5, min(8.0, duration_hours))
        
        # Convert duration to hours and minutes
        duration_hour_part = int(duration_hours)
        duration_min_part = int((duration_hours - duration_hour_part) * 60)
        
        # Calculate end time
        end_hour = start_hour + duration_hour_part
        end_min = start_min + duration_min_part
        
        # Handle minute overflow
        if end_min >= 60:
            end_hour += end_min // 60
            end_min = end_min % 60
            
        return f"{end_hour:02d}:{end_min:02d}"
    except:
        # Default to 2 hours if all parsing fails
        start_hour, start_min = map(int, block.start_time.split(':'))
        end_hour = start_hour + 2
        return f"{end_hour:02d}:{start_min:02d}"

def _estimate_smart_duration(block: ItineraryBlock) -> float:
    """Estimate realistic duration based on activity type and name"""
    name_lower = block.name.lower()
    description_lower = (block.description or "").lower()
    block_type = block.type.lower()
    
    # Restaurant duration based on mealtime
    if block_type == "restaurant":
        if block.mealtime == "breakfast":
            return 0.75  # 45 minutes for breakfast
        elif block.mealtime == "lunch":
            return 1.0  # 1 hour for lunch
        elif block.mealtime == "dinner":
            return 1.5  # 1.5 hours for dinner
        else:
            return 1.0  # Default restaurant time
    
    # Landmark duration based on type indicators in name/description
    if block_type == "landmark":
        # Theme parks and major attractions (3-7 hours)
        if any(keyword in name_lower or keyword in description_lower for keyword in [
            'disney', 'universal', 'theme park', 'amusement park', 'six flags', 'busch gardens'
        ]):
            return 6.0
        
        # Museums (1-3 hours depending on size)
        if any(keyword in name_lower or keyword in description_lower for keyword in [
            'museum', 'gallery', 'exhibition', 'smithsonian', 'national museum'
        ]):
            # Large/national museums get more time
            if any(keyword in name_lower for keyword in ['national', 'smithsonian', 'metropolitan', 'moma']):
                return 3.0
            else:
                return 2.0
        
        # Zoos and aquariums (2-4 hours)
        if any(keyword in name_lower or keyword in description_lower for keyword in [
            'zoo', 'aquarium', 'safari', 'wildlife'
        ]):
            return 3.0
        
        # Gardens and parks (1-2 hours)
        if any(keyword in name_lower or keyword in description_lower for keyword in [
            'garden', 'park', 'botanical', 'arboretum'
        ]):
            return 1.5
        
        # Monuments and viewpoints (30 min - 1 hour)
        if any(keyword in name_lower or keyword in description_lower for keyword in [
            'monument', 'memorial', 'statue', 'viewpoint', 'overlook', 'tower'
        ]):
            return 1.0
        
        # Markets and shopping areas (1-2 hours)
        if any(keyword in name_lower or keyword in description_lower for keyword in [
            'market', 'bazaar', 'shopping', 'mall', 'district'
        ]):
            return 1.5
        
        # Religious sites (30 min - 1 hour)
        if any(keyword in name_lower or keyword in description_lower for keyword in [
            'church', 'cathedral', 'temple', 'mosque', 'synagogue', 'chapel'
        ]):
            return 1.0
        
        # Default landmark duration
        return 2.0
    
    # Default for unknown types
    return 2.0

def _estimate_duration_from_google_types(types: List[str], name: str) -> Optional[float]:
    """Estimate duration based on Google Places types"""
    if not types:
        return None
    
    name_lower = name.lower()
    
    # Theme parks and amusement venues (4-8 hours)
    if any(t in types for t in ['amusement_park', 'theme_park']):
        return 6.0
    
    # Museums and galleries (1.5-4 hours)
    if any(t in types for t in ['museum', 'art_gallery']):
        # Large/national museums get more time
        if any(keyword in name_lower for keyword in ['national', 'smithsonian', 'metropolitan', 'moma', 'getty']):
            return 3.5
        else:
            return 2.5
    
    # Zoos and aquariums (2-4 hours)
    if any(t in types for t in ['zoo', 'aquarium']):
        return 3.0
    
    # Parks and gardens (1-2.5 hours)
    if any(t in types for t in ['park', 'botanical_garden']):
        # National parks and large botanical gardens get more time
        if 'national' in name_lower or 'botanical' in name_lower:
            return 2.0
        else:
            return 1.5
    
    # Shopping areas (1-3 hours)
    if any(t in types for t in ['shopping_mall', 'shopping_center', 'department_store']):
        return 2.0
    
    # Religious sites (0.5-1.5 hours)
    if any(t in types for t in ['church', 'hindu_temple', 'mosque', 'synagogue', 'place_of_worship']):
        # Large cathedrals and famous religious sites get more time
        if any(keyword in name_lower for keyword in ['cathedral', 'basilica', 'abbey', 'shrine']):
            return 1.5
        else:
            return 1.0
    
    # Entertainment venues (1-3 hours)
    if any(t in types for t in ['movie_theater', 'casino', 'bowling_alley', 'night_club']):
        return 2.0
    
    # Tourist attractions (varies widely, use name-based heuristics)
    if 'tourist_attraction' in types:
        # Large attractions and landmarks
        if any(keyword in name_lower for keyword in [
            'statue of liberty', 'empire state', 'golden gate', 'hoover dam', 
            'mount rushmore', 'space needle', 'arch', 'tower'
        ]):
            return 2.0
        # Viewpoints and small monuments
        elif any(keyword in name_lower for keyword in [
            'viewpoint', 'overlook', 'monument', 'memorial', 'bridge'
        ]):
            return 1.0
        else:
            return 1.5
    
    # Stadiums and sports venues (2-4 hours if events, 1 hour for tours)
    if any(t in types for t in ['stadium', 'sports_complex']):
        return 1.5  # Assume tour, not full event
    
    # Libraries and educational institutions (1-2 hours)
    if any(t in types for t in ['library', 'university', 'school']):
        return 1.5
    
    # Government buildings and city halls (0.5-1.5 hours)
    if any(t in types for t in ['city_hall', 'courthouse', 'embassy']):
        return 1.0
    
    # Default for other tourist attractions
    if any(t in types for t in ['establishment', 'point_of_interest']):
        return 1.5
    
    # No specific match found
    return None

def log_llm_interaction(prompt_inputs: Dict, result: Any, violations: List[str], model_name: str):
    """
    Comprehensive logging of LLM interactions for debugging and quality monitoring.
    Uses structured logging for GCP compatibility.
    """
    # Extract key metrics for structured logging
    destination = prompt_inputs.get('destination', 'Unknown')
    travel_days = prompt_inputs.get('travel_days', 'Unknown')
    kids_age = prompt_inputs.get('kids_age', 'None')
    with_elderly = prompt_inputs.get('with_elderly', 'False')
    special_requests = prompt_inputs.get('special_requests', 'None')
    
    # Analyze wishlist
    wishlist = prompt_inputs.get('wishlist_recommendations', '')
    wishlist_count = len(wishlist.split('\n')) - 2 if wishlist.strip() else 0  # Subtract header and footer
    
    # Analyze selected attractions
    selected_attractions = prompt_inputs.get('selected_attractions', '')
    attraction_count = len([line for line in selected_attractions.split('\n') if line.strip().startswith('- ')])
    
    # Structured log data for GCP
    log_data = {
        "event": "llm_interaction",
        "model_name": model_name,
        "destination": destination,
        "travel_days": travel_days,
        "group_composition": {
            "kids_age": kids_age,
            "with_elderly": with_elderly
        },
        "special_requests": special_requests,
        "input_metrics": {
            "attraction_count": attraction_count,
            "wishlist_count": wishlist_count
        }
    }
    
    # Console output for development (keep existing format)
    debug_print(f"\n📝 LLM INTERACTION LOG [{model_name}]")
    debug_print("=" * 60)
    debug_print(f"🎯 DESTINATION: {destination}")
    debug_print(f"📅 TRAVEL DAYS: {travel_days}")
    debug_print(f"👨‍👩‍👧‍👦 GROUP: Kids({kids_age}), Elderly({with_elderly})")
    debug_print(f"🎨 SPECIAL REQUESTS: {special_requests}")
    
    # Log selected attractions (truncated for console)
    attraction_lines = selected_attractions.split('\n')[:10]
    if len(attraction_lines) >= 10:
        attraction_lines.append("... (truncated)")
    debug_print(f"🏛️  SELECTED ATTRACTIONS:\n{chr(10).join(attraction_lines)}")
    
    # Log wishlist status
    if wishlist.strip():
        debug_print(f"⭐ WISHLIST: {wishlist_count} items")
    else:
        debug_print(f"⭐ WISHLIST: None (empty or filtered out)")
    
    # Analyze result and update log data
    if hasattr(result, 'itinerary'):
        total_days = len(result.itinerary)
        total_activities = sum(len(day.blocks) for day in result.itinerary)
        total_landmarks = sum(len([b for b in day.blocks if b.type == 'landmark']) for day in result.itinerary)
        total_restaurants = sum(len([b for b in day.blocks if b.type == 'restaurant']) for day in result.itinerary)
        
        log_data["result_metrics"] = {
            "total_days": total_days,
            "total_activities": total_activities,
            "total_landmarks": total_landmarks,
            "total_restaurants": total_restaurants,
            "success": True
        }
        
        debug_print(f"📊 RESULT SUMMARY:")
        debug_print(f"   - Days: {total_days}")
        debug_print(f"   - Total activities: {total_activities}")
        debug_print(f"   - Landmarks: {total_landmarks}")
        debug_print(f"   - Restaurants: {total_restaurants}")
        
        # Check for violations
        day_violations = []
        for day in result.itinerary:
            breakfast_count = sum(1 for b in day.blocks if b.type == 'restaurant' and b.mealtime == 'breakfast')
            lunch_count = sum(1 for b in day.blocks if b.type == 'restaurant' and b.mealtime == 'lunch')
            dinner_count = sum(1 for b in day.blocks if b.type == 'restaurant' and b.mealtime == 'dinner')
            
            if breakfast_count != 1:
                violation = f"Day {day.day}: {breakfast_count} breakfast restaurants (expected 1)"
                violations.append(violation)
                day_violations.append({"day": day.day, "type": "breakfast_count", "count": breakfast_count})
            if lunch_count != 1:
                violation = f"Day {day.day}: {lunch_count} lunch restaurants (expected 1)"
                violations.append(violation)
                day_violations.append({"day": day.day, "type": "lunch_count", "count": lunch_count})
            if dinner_count != 1:
                violation = f"Day {day.day}: {dinner_count} dinner restaurants (expected 1)"
                violations.append(violation)
                day_violations.append({"day": day.day, "type": "dinner_count", "count": dinner_count})
            
            # Check for duplicates within day
            names = [b.name.lower() for b in day.blocks]
            duplicates = [name for name in set(names) if names.count(name) > 1]
            if duplicates:
                violation = f"Day {day.day}: Duplicate names: {duplicates}"
                violations.append(violation)
                day_violations.append({"day": day.day, "type": "duplicates", "names": duplicates})
            
            # Check for landmarks with mealtime
            landmark_mealtimes = [b.name for b in day.blocks if b.type == 'landmark' and b.mealtime]
            if landmark_mealtimes:
                violation = f"Day {day.day}: Landmarks with mealtime: {landmark_mealtimes}"
                violations.append(violation)
                day_violations.append({"day": day.day, "type": "landmark_mealtime", "names": landmark_mealtimes})
        
        log_data["violations"] = day_violations
        
    else:
        log_data["result_metrics"] = {"success": False}
        log_data["violations"] = [{"type": "parsing_failed", "message": "Failed to parse result into StructuredItinerary"}]
        violations.append("Failed to parse result into StructuredItinerary")
        debug_print(f"❌ RESULT: Invalid structure or parsing failed")
    
    # Update log data with violation summary
    log_data["violation_count"] = len(violations)
    log_data["has_violations"] = len(violations) > 0
    
    # Console output for violations
    if violations:
        debug_print(f"⚠️  VIOLATIONS DETECTED ({len(violations)}):")
        for i, violation in enumerate(violations, 1):
            debug_print(f"   {i}. {violation}")
    else:
        debug_print(f"✅ NO VIOLATIONS DETECTED")
    
    debug_print("=" * 60)
    
    # Structured logging for GCP
    if violations:
        logger.warning("LLM interaction completed with violations", extra=log_data)
    else:
        logger.info("LLM interaction completed successfully", extra=log_data)
    
    return violations

async def validate_opening_hours(day_plan: StructuredDayPlan, places_client: Optional[GooglePlacesClient] = None) -> StructuredDayPlan:
    """
    Validate that activity durations fit within venue opening hours.
    Adjusts timing or duration if activities extend beyond operating hours.
    """
    if not places_client:
        debug_print("⚠️  No places client - skipping opening hours validation")
        return day_plan
    
    debug_print(f"🕒 Validating opening hours for Day {day_plan.day}")
    validated_blocks = []
    
    for block in day_plan.blocks:
        # Skip restaurants and non-landmark activities
        if block.type != "landmark":
            validated_blocks.append(block)
            continue
        
        # Get opening hours from Google Places
        opening_hours = await get_opening_hours(block, places_client)
        if not opening_hours:
            debug_print(f"⚠️  No opening hours data for {block.name} - keeping original timing")
            validated_blocks.append(block)
            continue
        
        # Validate and adjust timing
        validated_block = adjust_for_opening_hours(block, opening_hours)
        validated_blocks.append(validated_block)
    
    return StructuredDayPlan(day=day_plan.day, blocks=validated_blocks)

async def get_opening_hours(block: ItineraryBlock, places_client: GooglePlacesClient) -> Optional[Dict]:
    """Get opening hours data for a venue from Google Places"""
    try:
        # Search for the place
        location = {"lat": block.location.lat, "lng": block.location.lng} if block.location else {"lat": 0, "lng": 0}
        search_results = await places_client.places_nearby(
            location=location,
            radius=1000,
            place_type='establishment',
            keyword=block.name
        )
        
        if not search_results.get('results'):
            return None
        
        # Get details for the first match
        place_id = search_results['results'][0].get('place_id')
        if not place_id:
            return None
        
        place_details = await places_client.place_details(place_id)
        if not place_details or not place_details.get('result'):
            return None
        
        opening_hours = place_details['result'].get('opening_hours')
        if opening_hours and 'weekday_text' in opening_hours:
            debug_print(f"✅ Found opening hours for {block.name}")
            return opening_hours
        
        return None
        
    except Exception as e:
        debug_print(f"⚠️  Error getting opening hours for {block.name}: {e}")
        return None

def adjust_for_opening_hours(block: ItineraryBlock, opening_hours: Dict) -> ItineraryBlock:
    """Adjust activity timing to fit within venue opening hours"""
    try:
        # Parse today's opening hours (simplified - assumes today is a weekday)
        weekday_text = opening_hours.get('weekday_text', [])
        if not weekday_text:
            return block
        
        # For simplicity, use Monday's hours (index 0)
        today_hours = weekday_text[0] if weekday_text else ""
        
        # Extract open/close times (basic parsing)
        # Format: "Monday: 9:00 AM – 5:00 PM"
        if '–' in today_hours and ':' in today_hours:
            time_part = today_hours.split(': ')[1] if ': ' in today_hours else today_hours
            if '–' in time_part:
                open_time, close_time = time_part.split(' – ')
                
                # Convert to 24-hour format
                venue_open = parse_12hour_to_24hour(open_time.strip())
                venue_close = parse_12hour_to_24hour(close_time.strip())
                
                if venue_open and venue_close:
                    # Check if activity fits within opening hours
                    activity_start = parse_time_to_minutes(block.start_time)
                    activity_duration = parse_duration_to_minutes(block.duration)
                    activity_end = activity_start + activity_duration
                    
                    venue_open_minutes = parse_time_to_minutes(venue_open)
                    venue_close_minutes = parse_time_to_minutes(venue_close)
                    
                    # Adjust timing if needed
                    adjusted_block = block.model_copy()
                    
                    # If starts before opening, move to opening time
                    if activity_start < venue_open_minutes:
                        adjusted_block.start_time = venue_open
                        debug_print(f"🕒 ADJUSTED: {block.name} moved to opening time {venue_open}")
                    
                    # If ends after closing, reduce duration
                    elif activity_end > venue_close_minutes:
                        max_duration = venue_close_minutes - activity_start
                        if max_duration > 30:  # At least 30 minutes
                            adjusted_block.duration = f"{max_duration/60:.1f}h"
                            debug_print(f"🕒 ADJUSTED: {block.name} duration reduced to fit closing time")
                        else:
                            # Move start time earlier
                            new_start = venue_close_minutes - activity_duration
                            if new_start >= venue_open_minutes:
                                adjusted_block.start_time = minutes_to_time_str(new_start)
                                debug_print(f"🕒 ADJUSTED: {block.name} moved earlier to fit before closing")
                    
                    return adjusted_block
        
        # If parsing fails, return original
        return block
        
    except Exception as e:
        debug_print(f"⚠️  Error adjusting opening hours for {block.name}: {e}")
        return block

def parse_12hour_to_24hour(time_str: str) -> Optional[str]:
    """Convert 12-hour format to 24-hour format"""
    try:
        time_str = time_str.strip()
        if 'AM' in time_str.upper():
            time_part = time_str.replace('AM', '').replace('am', '').strip()
            hour, minute = time_part.split(':')
            hour = int(hour)
            if hour == 12:
                hour = 0
            return f"{hour:02d}:{minute}"
        elif 'PM' in time_str.upper():
            time_part = time_str.replace('PM', '').replace('pm', '').strip()
            hour, minute = time_part.split(':')
            hour = int(hour)
            if hour != 12:
                hour += 12
            return f"{hour:02d}:{minute}"
        else:
            # Already 24-hour format
            return time_str
    except:
        return None

async def search_and_get_place_details(
    activity_name: str,
    reference_location: Optional[Location],
    places_client: GooglePlacesClient
) -> Optional[Dict]:
    """
    Search for a place using Google Places API and return detailed information.
    
    Args:
        activity_name: Name of the place to search for
        reference_location: Reference location for the search
        places_client: Google Places client instance
        
    Returns:
        Dictionary with place details or None if not found
    """
    if not places_client:
        debug_print(f"⚠️  No places client provided for {activity_name}")
        return None
    
    try:
        # Prepare search location
        if reference_location:
            search_location = {"lat": reference_location.lat, "lng": reference_location.lng}
        else:
            # Default to Orlando if no reference location
            search_location = {"lat": 28.5383, "lng": -81.3792}
        
        debug_print(f"🔍 Searching for '{activity_name}' near {search_location['lat']:.4f}, {search_location['lng']:.4f}")
        
        # Search for the place using nearby search
        search_results = await places_client.places_nearby(
            location=search_location,
            radius=5000,  # 5km radius
            place_type='establishment',
            keyword=activity_name
        )
        
        if not search_results.get('results'):
            debug_print(f"❌ No search results for '{activity_name}'")
            return None
        
        # Get details for the first result
        first_result = search_results['results'][0]
        place_id = first_result.get('place_id')
        
        if not place_id:
            debug_print(f"❌ No place_id found for '{activity_name}'")
            return None
        
        # Get detailed place information
        place_details = await places_client.place_details(place_id)
        
        if place_details and place_details.get('result'):
            debug_print(f"✅ Found details for '{activity_name}': {place_details['result'].get('name')}")
            return place_details['result']
        else:
            debug_print(f"❌ No place details found for '{activity_name}'")
            return None
            
    except Exception as e:
        debug_print(f"⚠️  Error searching for '{activity_name}': {str(e)}")
        return None
