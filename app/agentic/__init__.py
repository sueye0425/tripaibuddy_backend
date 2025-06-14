"""
Agentic itinerary generation system.
This module provides enhanced recommendation generation with proper geocoding.
"""

from typing import Dict, List, Optional, Any
from ..places_client import GooglePlacesClient
from ..schema import ItineraryBlock, Location, StructuredDayPlan
import logging

logger = logging.getLogger(__name__)

async def generate_recommendations_agentic(
    destination: str,
    travel_days: int,
    with_kids: bool = False,
    kids_age: Optional[List[int]] = None,
    with_elderly: bool = False,
    special_requests: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    places_client: Optional[GooglePlacesClient] = None
) -> Dict[str, Any]:
    """
    Generate landmark and restaurant recommendations using agentic system.
    This uses proper geocoding (no hardcoded coordinates) and enhanced descriptions.
    """
    
    if not places_client:
        logger.error("Places client is required for agentic recommendation generation")
        return {
            "error": "Places client not available",
            "landmarks": {},
            "restaurants": {}
        }
    
    try:
        logger.info(f"🤖 Agentic recommendation generation for {destination}")
        
        # 1. Geocode destination properly (no hardcoded coordinates)
        location = await places_client.geocode(destination)
        if not location:
            logger.error(f"Could not geocode destination: {destination}")
            return {
                "error": f"Could not geocode destination: {destination}",
                "landmarks": {},
                "restaurants": {}
            }
        
        logger.info(f"✅ Geocoded {destination} to coordinates: {location['lat']}, {location['lng']}")
        
        # 2. Generate landmark recommendations
        landmarks = await _generate_landmark_recommendations(
            destination, location, with_kids, kids_age, with_elderly, special_requests, places_client
        )
        
        # 3. Generate restaurant recommendations  
        restaurants = await _generate_restaurant_recommendations(
            destination, location, with_kids, kids_age, with_elderly, special_requests, places_client
        )
        
        logger.info(f"✅ Generated {len(landmarks)} landmarks and {len(restaurants)} restaurants")
        
        return {
            "landmarks": landmarks,
            "restaurants": restaurants
        }
        
    except Exception as e:
        logger.exception(f"Error in agentic recommendation generation: {e}")
        return {
            "error": f"Failed to generate recommendations: {str(e)}",
            "landmarks": {},
            "restaurants": {}
        }

async def _generate_landmark_recommendations(
    destination: str,
    location: Dict[str, float],
    with_kids: bool,
    kids_age: Optional[List[int]],
    with_elderly: bool,
    special_requests: Optional[str],
    places_client: GooglePlacesClient
) -> Dict[str, Any]:
    """Generate landmark recommendations with proper descriptions"""
    
    # Define landmark types based on user preferences
    landmark_types = ["tourist_attraction", "museum", "park", "zoo", "aquarium"]
    
    if with_kids:
        landmark_types.extend(["amusement_park", "playground"])
    
    landmarks = {}
    
    for place_type in landmark_types:
        try:
            # Search for landmarks near the destination coordinates (NOT hardcoded Orlando!)
            results = await places_client.places_nearby(
                location={"lat": location["lat"], "lng": location["lng"]},
                radius=25000,  # 25km radius
                place_type=place_type,
                keyword=f"{place_type.replace('_', ' ')} {destination}"
            )
            
            if results and results.get('results'):
                for place_data in results['results'][:3]:  # Top 3 per type
                    name = place_data.get('name')
                    if name and name not in landmarks:
                        
                        # Get detailed place data for better descriptions
                        detailed_data = await _get_detailed_place_data(place_data, places_client)
                        
                        # Format landmark with proper description (NOT address!)
                        formatted_landmark = await _format_landmark_place(detailed_data, places_client)
                        landmarks[name] = formatted_landmark
                        
        except Exception as e:
            logger.debug(f"Error searching for {place_type}: {e}")
            continue
    
    return landmarks

async def _generate_restaurant_recommendations(
    destination: str,
    location: Dict[str, float],
    with_kids: bool,
    kids_age: Optional[List[int]],
    with_elderly: bool,
    special_requests: Optional[str],
    places_client: GooglePlacesClient
) -> Dict[str, Any]:
    """Generate restaurant recommendations with enhanced descriptions"""
    
    # Import restaurant system for enhanced descriptions
    from .restaurant_system import RestaurantSystem
    restaurant_system = RestaurantSystem()
    
    restaurants = {}
    
    # Search for restaurants near destination coordinates (NOT hardcoded Orlando!)
    try:
        results = await places_client.places_nearby(
            location={"lat": location["lat"], "lng": location["lng"]},
            radius=10000,  # 10km radius
            place_type="restaurant"
        )
        
        if results and results.get('results'):
            for place_data in results['results'][:15]:  # Top 15 restaurants
                name = place_data.get('name')
                if name:
                    # Get detailed place data
                    detailed_data = await _get_detailed_place_data(place_data, places_client)
                    
                    # Get enhanced description using restaurant system
                    description = restaurant_system._get_enhanced_restaurant_description(detailed_data)
                    
                    # Format restaurant
                    formatted_restaurant = {
                        "name": name,
                        "description": description,  # This will be Google API description or empty string
                        "place_id": detailed_data.get('place_id'),
                        "rating": detailed_data.get('rating', 0.0),
                        "user_ratings_total": detailed_data.get('user_ratings_total', 0),
                        "location": {
                            "lat": detailed_data['geometry']['location']['lat'],
                            "lng": detailed_data['geometry']['location']['lng']
                        } if detailed_data.get('geometry', {}).get('location') else {},
                        "photos": _format_photos(detailed_data.get('photos', [])),
                        "opening_hours": detailed_data.get('opening_hours', {}),
                        "types": detailed_data.get('types', [])
                    }
                    
                    restaurants[name] = formatted_restaurant
                    
    except Exception as e:
        logger.error(f"Error generating restaurant recommendations: {e}")
    
    return restaurants

async def _get_detailed_place_data(basic_place_data: Dict, places_client: GooglePlacesClient) -> Dict:
    """Get detailed place data including enhanced description fields"""
    
    place_id = basic_place_data.get('place_id')
    if not place_id:
        return basic_place_data
    
    try:
        detailed_data = await places_client.place_details(place_id)
        if detailed_data and detailed_data.get('result'):
            return {**basic_place_data, **detailed_data['result']}
    except Exception as e:
        logger.debug(f"Failed to get detailed place data: {e}")
    
    return basic_place_data

async def _format_landmark_place(place_data: Dict, places_client: GooglePlacesClient) -> Dict[str, Any]:
    """Format landmark place with proper description from Google Places"""
    
    # Try to get meaningful description from Google Places
    description_sources = [
        place_data.get('editorial_summary', {}).get('overview'),
        _extract_landmark_description_from_reviews(place_data.get('reviews', [])),
        _create_landmark_description_from_types(place_data)
    ]
    
    # Use first non-empty description
    description = ""
    for desc in description_sources:
        if desc and desc.strip():
            description = desc.strip()
            break
    
    return {
        "name": place_data.get('name'),
        "description": description,
        "place_id": place_data.get('place_id'),
        "rating": place_data.get('rating', 0.0),
        "user_ratings_total": place_data.get('user_ratings_total', 0),
        "location": {
            "lat": place_data['geometry']['location']['lat'],
            "lng": place_data['geometry']['location']['lng']
        } if place_data.get('geometry', {}).get('location') else {},
        "photos": _format_photos(place_data.get('photos', [])),
        "opening_hours": place_data.get('opening_hours', {}),
        "types": place_data.get('types', [])
    }

def _extract_landmark_description_from_reviews(reviews: List[Dict]) -> Optional[str]:
    """Extract descriptive information from landmark reviews"""
    if not reviews:
        return None
    
    for review in reviews[:3]:  # Check top 3 reviews
        rating = review.get('rating', 0)
        text = review.get('text', '')
        
        if rating >= 4 and len(text) > 30:  # Positive, substantial reviews
            # Extract first sentence if it's descriptive
            sentences = text.split('.')
            first_sentence = sentences[0].strip()
            if len(first_sentence) > 20 and len(first_sentence) <= 200:
                return first_sentence + '.'
    
    return None

def _create_landmark_description_from_types(place_data: Dict) -> Optional[str]:
    """Create description from landmark types"""
    types = place_data.get('types', [])
    
    type_descriptions = {
        'tourist_attraction': 'Popular tourist attraction',
        'museum': 'Museum featuring exhibits and collections',
        'zoo': 'Zoo with diverse animal exhibits',
        'aquarium': 'Aquarium with marine life displays',
        'amusement_park': 'Amusement park with rides and attractions',
        'park': 'Park with outdoor recreational facilities'
    }
    
    for place_type in types:
        if place_type in type_descriptions:
            return type_descriptions[place_type]
    
    return "Point of interest"

def _format_photos(photos: List[Dict]) -> List[str]:
    """Format photo references for frontend use"""
    formatted_photos = []
    for photo in photos[:5]:  # Limit to 5 photos
        photo_reference = photo.get('photo_reference')
        if photo_reference:
            photo_url = f"/photo-proxy/{photo_reference}?maxwidth=400&maxheight=400"
            formatted_photos.append(photo_url)
    return formatted_photos

async def complete_itinerary_from_selection(data, places_client: GooglePlacesClient):
    """
    Enhanced agentic system for complete-itinerary with LLM integration,
    intelligent meal timing, and gap detection/regeneration.
    """
    try:
        logger.info("🤖 Using enhanced agentic system for complete-itinerary")
        
        # Extract destination and other details
        destination = data.details.destination
        travel_days = data.details.travelDays
        with_kids = data.details.withKids
        kids_age = data.details.kidsAge
        with_elderly = data.details.withElders
        special_requests = data.details.specialRequests
        
        # Initialize agents
        from .enhancement_agent import EnhancementAgent
        from .llm_agent import LLMAgent
        from .regeneration_agent import RegenerationAgent
        
        enhancement_agent = EnhancementAgent()
        llm_agent = LLMAgent()
        regeneration_agent = RegenerationAgent()
        
        # Convert the input attractions to StructuredDayPlan format
        structured_days = []
        used_restaurants = set()
        used_landmarks = set()  # Track landmarks across all days to prevent duplicates
        
        # Get destination coordinates for landmark expansion
        location = await places_client.geocode(destination)
        if not location:
            logger.error(f"Could not geocode destination: {destination}")
            return {"error": f"Could not geocode destination: {destination}"}
        
        for day_data in data.itinerary:
            day_blocks = []
            
            # Convert user's attractions to landmark blocks
            for attraction in day_data.attractions:
                # Create landmark block from the user's selection
                landmark_block = ItineraryBlock(
                    name=attraction.name,
                    type="landmark",
                    description=attraction.description,
                    start_time="09:00",  # Will be updated by LLM agent
                    duration="2h",      # Will be updated by LLM agent
                    location=Location(lat=attraction.location.lat, lng=attraction.location.lng) if attraction.location else None
                )
                day_blocks.append(landmark_block)
                used_landmarks.add(attraction.name.lower())  # Track this landmark
            
            # 🧠 Use LLM Agent for intelligent landmark generation and timing
            trip_details = {
                "withKids": with_kids,
                "kidsAge": kids_age,
                "withElders": with_elderly,
                "specialRequests": special_requests,
                "travelDays": travel_days,
                "usedLandmarks": used_landmarks  # Pass used landmarks to prevent duplicates
            }
            
            enhanced_landmarks = await llm_agent.generate_landmarks_with_timing(
                destination=destination,
                day_num=day_data.day,
                user_landmarks=day_blocks,
                trip_details=trip_details,
                places_client=places_client
            )
            
            # Update used landmarks with newly generated ones
            for landmark in enhanced_landmarks:
                if landmark.type == "landmark":
                    used_landmarks.add(landmark.name.lower())
            
            # Create structured day plan with LLM-enhanced landmarks
            day_plan = StructuredDayPlan(day=day_data.day, blocks=enhanced_landmarks)
            
            # Enhance the day with landmarks using intelligent timing
            enhanced_day = await enhancement_agent.enhance_day_with_landmarks(
                day_plan, places_client, destination
            )
            
            # 🔍 Apply regeneration agent for gap detection and fixing
            regenerated_day = await regeneration_agent.detect_and_fix_gaps(
                enhanced_day, destination, trip_details, places_client
            )
            
            # 🎯 FIX: Ensure every day has exactly 3 restaurants
            restaurants_count = len([b for b in regenerated_day.blocks if b.type == 'restaurant'])
            if restaurants_count < 3:
                logger.warning(f"⚠️ Day {day_data.day} only has {restaurants_count} restaurants, adding more...")
                regenerated_day = await _ensure_minimum_restaurants(
                    regenerated_day, places_client, destination, used_restaurants, 3
                )
            
            structured_days.append(regenerated_day)
        
        # Convert back to the expected format
        itinerary_blocks = []
        for day in structured_days:
            itinerary_blocks.extend(day.blocks)
        
        # Format as expected by the endpoint
        result = {
            "itinerary": {
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
                                "website": block.website,
                                "notes": block.notes
                            }
                            for block in day.blocks
                        ]
                    }
                    for day in structured_days
                ]
            },
            "performance_metrics": {},
            "errors": [],
            "total_generation_time": 0.0
        }
        
        # Log summary
        total_landmarks = sum(len([b for b in day.blocks if b.type == 'landmark']) for day in structured_days)
        total_restaurants = sum(len([b for b in day.blocks if b.type == 'restaurant']) for day in structured_days)
        logger.info(f"✅ Complete itinerary: {total_landmarks} landmarks, {total_restaurants} restaurants across {len(structured_days)} days")
        
        return result
        
    except Exception as e:
        logger.error(f"Error in complete_itinerary_from_selection: {e}")
        return {"error": str(e)}

def _is_theme_park_day_simple(landmarks: List[ItineraryBlock]) -> bool:
    """Simple check if any landmark is a theme park"""
    theme_park_keywords = [
        'disney', 'universal', 'studios', 'magic kingdom', 'epcot', 
        'hollywood studios', 'animal kingdom', 'islands of adventure',
        'volcano bay', 'seaworld', 'busch gardens', 'legoland'
    ]
    
    for landmark in landmarks:
        name_lower = landmark.name.lower()
        desc_lower = (landmark.description or "").lower()
        
        if any(keyword in name_lower or keyword in desc_lower for keyword in theme_park_keywords):
            return True
    
    return False

async def _add_supplementary_landmarks(
    existing_landmarks: List[ItineraryBlock],
    location: Dict[str, float],
    destination: str,
    places_client: GooglePlacesClient,
    with_kids: bool,
    with_elderly: bool,
    special_requests: Optional[str],
    max_additional: int
) -> List[ItineraryBlock]:
    """Add supplementary landmarks to reach minimum count per day"""
    
    try:
        # Get names of existing landmarks to avoid duplicates
        existing_names = {landmark.name.lower() for landmark in existing_landmarks}
        
        # Define search types based on preferences
        search_types = ["tourist_attraction", "museum", "park"]
        if with_kids:
            search_types.extend(["zoo", "aquarium", "playground"])
        
        supplementary_landmarks = []
        
        for search_type in search_types:
            if len(supplementary_landmarks) >= max_additional:
                break
                
            try:
                results = await places_client.places_nearby(
                    location={"lat": location["lat"], "lng": location["lng"]},
                    radius=15000,  # 15km radius
                    place_type=search_type,
                    keyword=f"{search_type.replace('_', ' ')} {destination}"
                )
                
                if results and results.get('results'):
                    for place_data in results['results'][:2]:  # Top 2 per type
                        name = place_data.get('name', '')
                        
                        # Skip if name already exists
                        if name.lower() in existing_names:
                            continue
                            
                        # Get detailed place data
                        detailed_data = await _get_detailed_place_data(place_data, places_client)
                        
                        # Create landmark block
                        landmark_block = ItineraryBlock(
                            name=name,
                            type="landmark",
                            description=_get_landmark_description(detailed_data),
                            start_time="11:00",  # Default time after user's landmarks
                            duration="1.5h",
                            location=Location(
                                lat=detailed_data['geometry']['location']['lat'],
                                lng=detailed_data['geometry']['location']['lng']
                            ) if detailed_data.get('geometry', {}).get('location') else None,
                            place_id=detailed_data.get('place_id'),
                            rating=detailed_data.get('rating'),
                            address=detailed_data.get('formatted_address')
                        )
                        
                        supplementary_landmarks.append(landmark_block)
                        existing_names.add(name.lower())
                        
                        if len(supplementary_landmarks) >= max_additional:
                            break
                            
            except Exception as e:
                logger.debug(f"Error searching for {search_type}: {e}")
                continue
        
        logger.info(f"✅ Added {len(supplementary_landmarks)} supplementary landmarks")
        return supplementary_landmarks
        
    except Exception as e:
        logger.error(f"Error adding supplementary landmarks: {e}")
        return []

def _get_landmark_description(place_data: Dict) -> str:
    """Get description for supplementary landmarks"""
    # Try editorial summary first
    if place_data.get('editorial_summary', {}).get('overview'):
        return place_data['editorial_summary']['overview']
    
    # Fallback to type-based description
    types = place_data.get('types', [])
    type_descriptions = {
        'tourist_attraction': 'Popular tourist destination and attraction',
        'museum': 'Museum featuring exhibits and collections',
        'park': 'Park with outdoor recreational facilities',
        'zoo': 'Zoo with diverse animal exhibits',
        'aquarium': 'Aquarium with marine life displays'
    }
    
    for place_type in types:
        if place_type in type_descriptions:
            return type_descriptions[place_type]
    
    return "Point of interest"

async def _ensure_minimum_restaurants(
    day_plan: StructuredDayPlan,
    places_client: GooglePlacesClient,
    destination: str,
    used_restaurants: set,
    min_restaurants: int
) -> StructuredDayPlan:
    """Ensure a day has the minimum number of restaurants"""
    
    current_restaurants = [b for b in day_plan.blocks if b.type == 'restaurant']
    if len(current_restaurants) >= min_restaurants:
        return day_plan
    
    # Calculate center location for restaurant search
    landmarks = [b for b in day_plan.blocks if b.type == 'landmark' and b.location]
    if landmarks:
        avg_lat = sum(l.location.lat for l in landmarks) / len(landmarks)
        avg_lng = sum(l.location.lng for l in landmarks) / len(landmarks)
        center_location = {"lat": avg_lat, "lng": avg_lng}
    else:
        # Fallback to destination geocoding
        center_location = await places_client.geocode(destination)
        if not center_location:
            logger.error(f"Cannot determine location for restaurant search")
            return day_plan
    
    # Find missing meal types
    existing_mealtimes = {r.mealtime for r in current_restaurants if r.mealtime}
    all_mealtimes = {'breakfast', 'lunch', 'dinner'}
    missing_mealtimes = all_mealtimes - existing_mealtimes
    
    # Add missing restaurants
    from .restaurant_system import RestaurantSystem
    restaurant_system = RestaurantSystem()
    
    meal_times = {'breakfast': '08:00', 'lunch': '13:00', 'dinner': '19:00'}
    new_blocks = list(day_plan.blocks)
    
    for meal_type in missing_mealtimes:
        if len([b for b in new_blocks if b.type == 'restaurant']) >= min_restaurants:
            break
            
        try:
            # Search for restaurants
            results = await places_client.places_nearby(
                location=center_location,
                radius=8000,  # 8km radius
                place_type="restaurant"
            )
            
            if results and results.get('results'):
                for place_data in results['results']:
                    restaurant_name = place_data.get('name', '')
                    
                    # Skip if already used
                    if restaurant_name in used_restaurants:
                        continue
                    
                    # Get detailed data and create restaurant block
                    detailed_data = await restaurant_system._get_detailed_place_data(place_data, places_client)
                    restaurant_block = restaurant_system._create_restaurant_block_from_place_data(
                        detailed_data, meal_type, meal_times[meal_type]
                    )
                    
                    new_blocks.append(restaurant_block)
                    used_restaurants.add(restaurant_name)
                    logger.info(f"   🍽️ Added fallback restaurant: {restaurant_name} ({meal_type})")
                    break
                    
        except Exception as e:
            logger.error(f"Error adding fallback restaurant for {meal_type}: {e}")
    
    # Sort blocks by time
    new_blocks.sort(key=lambda x: restaurant_system._parse_time_to_minutes(x.start_time))
    
    return StructuredDayPlan(day=day_plan.day, blocks=new_blocks) 