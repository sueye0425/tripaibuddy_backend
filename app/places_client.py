import os
import time
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import aiohttp
import redis.asyncio as aioredis # Updated import
import json
import asyncio # Added asyncio for TimeoutError
from dateutil import parser as date_parser
from .routes_client import GoogleRoutesClient # Ensure this is the new async version
from .redis_client import RedisClient

class RateLimit:
    def __init__(self, limit: int, window: int):
        self.limit = limit
        self.window = window
        self.tokens = limit
        self.last_update = time.time()

    def can_proceed(self) -> bool:
        now = time.time()
        time_passed = now - self.last_update
        
        # Replenish tokens based on time passed
        self.tokens = min(
            self.limit,
            self.tokens + int((time_passed * self.limit) / self.window)
        )
        
        if self.tokens > 0:
            self.tokens -= 1
            self.last_update = now
            return True
        return False

class RedisCache:
    def __init__(self, redis_client: Optional[RedisClient] = None):
        self.redis_client = redis_client or RedisClient()
        self.client: Optional[aioredis.Redis] = None # Updated type hint
        # 🎯 COST OPTIMIZATION: Longer TTLs to improve cache hit rates and reduce API costs
        self.ttl = {
            'geocode': 14 * 24 * 60 * 60,  # 2 weeks (locations rarely change)
            'places': 48 * 60 * 60,        # 48 hours (good balance between freshness and cost savings)
            'photos': 14 * 24 * 60 * 60,   # 2 weeks (photos are stable)
            'image_proxy': 30 * 24 * 60 * 60 # 30 days for proxied images (very stable)
        }
        self.logger = logging.getLogger(__name__)

    def get_key(self, key_type: str, **kwargs) -> str:
        # Use a more efficient cache key format
        # 🎯 COST OPTIMIZATION: Normalize location to increase cache hits
        if 'destination' in kwargs:
            dest = kwargs['destination']
            if ',' in dest:
                # Round coordinates to 2 decimal places to increase cache hits
                try:
                    lat_str, lng_str = dest.split(',')
                    lat = round(float(lat_str), 2)
                    lng = round(float(lng_str), 2)
                    kwargs['destination'] = f"{lat},{lng}"
                except:
                    pass  # Keep original if parsing fails
        
        # Normalize keywords to increase cache hits
        if 'keywords' in kwargs and kwargs['keywords']:
            keywords = kwargs['keywords'].split(',') if isinstance(kwargs['keywords'], str) else kwargs['keywords']
            # Sort and clean keywords for better cache hits
            normalized_keywords = sorted([kw.strip().lower() for kw in keywords if kw.strip()])
            kwargs['keywords'] = ','.join(normalized_keywords)
        
        # Sort kwargs for consistent key generation
        sorted_items = sorted(kwargs.items())
        key_parts = [key_type] + [f"{k}:{v}" for k, v in sorted_items if v is not None]
        return ":".join(key_parts)

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache using RedisClient"""
        data = await self.redis_client.get(key)
        
        if not data:
            return None
            
        # If key starts with image_proxy prefix, return raw bytes
        if key.startswith('image_proxy:'):
            self.logger.debug(f"Retrieved image from cache for key: {key}")
            return data
            
        # For other data types, try to decode JSON
        try:
            return json.loads(data.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            self.logger.error(f"Error decoding data for key {key}: {str(e)}")
            return None

    async def set(self, key: str, value: Any, ttl_type: str):
        """Set value to cache using RedisClient"""
        # Handle binary data for images
        if ttl_type == 'image_proxy':
            if not isinstance(value, bytes):
                self.logger.error(f"Image proxy value must be bytes, got {type(value)}")
                return
            data_to_store = value
        else:
            # For non-image data, store as JSON
            data_to_store = json.dumps(value).encode('utf-8') if isinstance(value, (dict, list)) else str(value).encode('utf-8')

        # Get TTL value, default to 1 hour if not found
        ttl = self.ttl.get(ttl_type, 3600)
        await self.redis_client.set(key, data_to_store, ttl)
        self.logger.debug(f"Successfully stored data in cache with key: {key}, ttl_type: {ttl_type}")

    async def _do_set(self, client: aioredis.Redis, key: str, value: Any, ttl_type: str):
        """Helper method to perform the actual Redis set operation"""
        # Handle binary data for images
        if ttl_type == 'image_proxy':
            if not isinstance(value, bytes):
                self.logger.error(f"Image proxy value must be bytes, got {type(value)}")
                return
            data_to_store = value
        else:
            # For non-image data, store as JSON
            data_to_store = json.dumps(value).encode('utf-8') if isinstance(value, (dict, list)) else str(value).encode('utf-8')

        # Get TTL value, default to 1 hour if not found
        ttl = self.ttl.get(ttl_type, 3600)
        await client.setex(key, ttl, data_to_store)
        self.logger.debug(f"Successfully stored data in cache with key: {key}, ttl_type: {ttl_type}")

class GooglePlacesClient:
    def __init__(self, session: aiohttp.ClientSession, redis_client: Optional[RedisClient] = None):
        self.api_key = os.getenv('GOOGLE_PLACES_API_KEY')
        # Initialize GoogleRoutesClient with the same session
        self.routes_client = GoogleRoutesClient(session=session)
        self.rate_limits = {
            'nearby_search': RateLimit(600, 60),
            'place_details': RateLimit(600, 60),
            'photos': RateLimit(600, 60)
        }
        self.cache = RedisCache(redis_client)
        self.logger = logging.getLogger(__name__)
        self._session = session # This client also uses the passed-in session
        # self._should_close_session should be False if session is always passed in via lifespan
        # If GooglePlacesClient can still be instantiated without a session (e.g. in tests),
        # then _should_close_session logic is needed. Assuming session is always provided from main.py lifespan.
        self._should_close_session = False 

    async def get_session(self) -> aiohttp.ClientSession:
        # If session is always provided by __init__, this method might be simplified
        # or just return self._session directly. The original logic was for cases where
        # the session might be created by this class.
        if self._session is None:
            # This path should ideally not be taken if main.py always provides a session.
            self.logger.warning("GooglePlacesClient creating its own aiohttp.ClientSession. This should be managed by lifespan.")
            self._session = aiohttp.ClientSession()
            self._should_close_session = True 
        return self._session

    async def places_nearby(self, location: Dict[str, float], radius: int, place_type: str, keyword: Optional[str] = None) -> Dict:
        """Async version of places_nearby using aiohttp"""
        session = await self.get_session()
        url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        params = {
            'location': f"{location['lat']},{location['lng']}",
            'radius': radius,
            'type': place_type,
            'key': self.api_key
        }
        if keyword:
            params['keyword'] = keyword

        print(f"\n🌐 DEBUG: Places Nearby API Call")
        print(f"📍 URL: {url}")
        print(f"📋 Params: {json.dumps(params, indent=2)}")
        print(f"🔑 API Key: {self.api_key[:10]}..." if self.api_key else "❌ No API Key")
        
        try:
            async with session.get(url, params=params, timeout=10) as response:
                print(f"📡 Response Status: {response.status}")
                result = await response.json()
                print(f"📥 Full API Response: {json.dumps(result, indent=2)}")
                
                if result.get('status') == 'OK':
                    print(f"✅ Places API SUCCESS - found {len(result.get('results', []))} places")
                    if result.get('results'):
                        for i, place in enumerate(result['results'][:3]):  # Show first 3 results
                            print(f"📍 Result {i+1}: {place.get('name')} - {place.get('place_id')}")
                    return result
                elif result.get('status') == 'ZERO_RESULTS':
                    print(f"🔍 Places API: No results found for query")
                    return {'results': []}
                else:
                    print(f"❌ Places API ERROR: {result.get('status')}")
                    print(f"❌ Error message: {result.get('error_message', 'No error message')}")
                    return {'results': []}
        except Exception as e:
            print(f"⚠️ Exception in places_nearby: {str(e)}")
            return {'results': []}

    async def place_details(self, place_id: str, include_opening_hours: bool = True) -> Optional[Dict]:
        """Async version of place using aiohttp with optional opening_hours for speed optimization"""
        session = await self.get_session()
        url = "https://maps.googleapis.com/maps/api/place/details/json"
        
        # 🚀 SPEED OPTIMIZATION: Conditional opening_hours field
        # Removing opening_hours can improve API response time by 15-25%
        base_fields = 'place_id,name,rating,user_ratings_total,formatted_address,geometry/location,photo,price_level,website,formatted_phone_number,wheelchair_accessible_entrance,types,editorial_summary,reviews,business_status'
        
        fields = base_fields
        if include_opening_hours:
            fields += ',opening_hours'
        
        params = {
            'place_id': place_id,
            'key': self.api_key,
            'fields': fields
        }

        print(f"\n🔍 DEBUG: Place Details API Call")
        print(f"📍 URL: {url}")
        print(f"📋 Params: {json.dumps(params, indent=2)}")
        print(f"🔑 API Key: {self.api_key[:10]}..." if self.api_key else "❌ No API Key")
        print(f"⚡ Opening hours included: {include_opening_hours}")
        
        try:
            async with session.get(url, params=params, timeout=10) as response:
                print(f"📡 Response Status: {response.status}")
                result = await response.json()
                print(f"📥 Full API Response: {json.dumps(result, indent=2)}")
                
                if result.get('status') == 'OK':
                    place_name = result['result'].get('name', 'Unknown')
                    print(f"✅ Place Details SUCCESS for {place_name}")
                    
                    # Log key fields
                    place_data = result['result']
                    print(f"🏷️  Name: {place_data.get('name')}")
                    print(f"🔑 Place ID: {place_data.get('place_id')}")
                    print(f"⭐ Rating: {place_data.get('rating')}")
                    print(f"📍 Address: {place_data.get('formatted_address')}")
                    print(f"📸 Photos: {len(place_data.get('photos', []))} photos")
                    if place_data.get('photos'):
                        print(f"📸 First photo ref: {place_data['photos'][0].get('photo_reference', 'No ref')}")
                    
                    return result
                else:
                    print(f"❌ Place Details ERROR: {result.get('status')}")
                    print(f"❌ Error message: {result.get('error_message', 'No error message')}")
                    return None
        except Exception as e:
            print(f"⚠️ Exception in place_details: {str(e)}")
            return None

    async def calculate_radius(self, location: Dict[str, float]) -> int:
        """Calculate dynamic search radius based on city bounds. Now async."""
        try:
            # Get city bounds from geocoding - now awaits the async call
            geocode_result = await self.routes_client.reverse_geocode(location)
            if not geocode_result:
                self.logger.warning("No geocoding results, using default radius")
                return 10000  # Default 10km radius
                
            # Extract bounds from the first result if available
            for result in geocode_result:
                if 'address_components' in result:
                    # Check for San Antonio specifically
                    is_san_antonio = False
                    for component in result['address_components']:
                        if 'long_name' in component and 'San Antonio' in component['long_name']:
                            is_san_antonio = True
                            self.logger.info("Location identified as San Antonio, using larger radius")
                            return 40000  # 40km radius for San Antonio
                    
                    # Check the type of area to determine appropriate radius
                    for component in result['address_components']:
                        if 'types' in component:
                            # Major cities get largest radius
                            if 'locality' in component['types'] or 'administrative_area_level_1' in component['types']:
                                self.logger.info(f"Found major city/region, using larger radius")
                                return 30000  # 30km radius
                            # Smaller cities/towns get medium radius
                            elif 'sublocality' in component['types'] or 'administrative_area_level_2' in component['types']:
                                self.logger.info(f"Found smaller city/town, using medium radius")
                                return 20000  # 20km radius
                            
            self.logger.info("No specific area type found, using default radius")
            return 10000  # Default 10km radius
        except Exception as e:
            self.logger.error(f"Error calculating radius: {str(e)}")
            return 10000  # Default to 10km on error

    async def get_distance_matrix(self, origins: List[Dict[str, float]], destinations: List[Dict[str, float]], mode: str = "driving") -> List[List[Dict[str, Any]]]:
        """Get distance matrix using async Routes API client"""
        # Convert mode to Routes API format (DRIVE, WALK, BICYCLE, TRANSIT)
        # Note: The actual GoogleRoutesClient.calculate_distance_matrix expects mode like "DRIVE"
        mode_mapping = {
            "driving": "DRIVE",
            "walking": "WALK",
            "bicycling": "BICYCLE",
            "transit": "TRANSIT" # Assuming GoogleRoutesClient can handle this if it makes sense for the API
        }
        routes_mode = mode_mapping.get(mode.lower(), "DRIVE")
        
        self.logger.debug(f"Calling async calculate_distance_matrix with mode: {routes_mode}")
        return await self.routes_client.calculate_distance_matrix(origins, destinations, mode=routes_mode)

    async def get_places(
        self,
        location: Dict[str, float],
        place_type: str,
        keywords: Optional[List[str]] = None,
        max_results: int = 20,
        special_requests: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get places based on location and type, using async calculate_radius."""
        cache_key = self.cache.get_key(
            'places',
            destination=f"{location['lat']},{location['lng']}",
            place_type=place_type,
            keywords=','.join(keywords) if keywords else '',
            special_requests=special_requests
        )
        
        if place_type == 'restaurant':
            self.logger.info(f"Attempting to fetch restaurants for location: {location}, keywords: {keywords}")
            self.logger.info(f"Restaurant cache key: {cache_key}")

        cached = await self.cache.get(cache_key)
        if cached:
            self.logger.info(f"Found {len(cached)} cached places for {place_type} (keywords: {keywords})")
            if place_type == 'restaurant':
                self.logger.info(f"Returning {len(cached)} cached restaurants")
            return cached

        if place_type == 'restaurant':
            self.logger.info(f"No cached restaurants found for key: {cache_key}. Fetching from API.")

        if not self.rate_limits['nearby_search'].can_proceed():
            self.logger.warning("Rate limit reached for nearby search")
            return []

        try:
            # Calculate search radius based on location
            radius = await self.calculate_radius(location)
            
            # For restaurants, use specialized search regardless of keywords
            if place_type == 'restaurant':
                detailed_results = await self._search_restaurants_with_fallback(
                    location, radius, keywords or [], max_results, special_requests
                )
            else:
                # For non-restaurant searches, use the cost-optimized approach
                keyword = ' '.join(keywords) if keywords else None
                
                self.logger.info(f"Searching for places of type {place_type} with keywords: {keyword}")
                
                results = await self.places_nearby(
                    location=location,
                    radius=radius,
                    place_type=place_type,
                    keyword=keyword
                )
                
                total_results = len(results.get('results', []))
                self.logger.info(f"Found {total_results} places for {place_type} from Nearby Search API")

                # 🎯 COST OPTIMIZATION: Smart place details fetching
                # Only fetch details for high-quality places to reduce API costs
                
                # Filter and prioritize places before getting details
                candidate_places = results.get('results', [])
                high_priority_places = []
                
                for place in candidate_places:
                    # Score places based on available data from nearby search
                    score = 0
                    
                    # Higher rating gets priority
                    rating = place.get('rating', 0)
                    if rating >= 4.5:
                        score += 10
                    elif rating >= 4.0:
                        score += 7
                    elif rating >= 3.5:
                        score += 4
                    elif rating >= 3.0:
                        score += 2
                    
                    # More reviews indicate popularity
                    review_count = place.get('user_ratings_total', 0)
                    if review_count >= 1000:
                        score += 8
                    elif review_count >= 500:
                        score += 6
                    elif review_count >= 100:
                        score += 4
                    elif review_count >= 50:
                        score += 2
                    
                    # Price level preference (avoid empty or very expensive)
                    price_level = place.get('price_level')
                    if price_level in [1, 2, 3]:  # Affordable to moderate
                        score += 3
                    elif price_level == 4:  # Expensive but might be worth it
                        score += 1
                    
                    # Boost score if place has photos
                    if place.get('photos'):
                        score += 2
                    
                    # Add score to place for sorting
                    place['_priority_score'] = score
                    high_priority_places.append(place)
                
                # Sort by priority score and limit API calls
                high_priority_places.sort(key=lambda x: x.get('_priority_score', 0), reverse=True)
                
                # 🎯 COST REDUCTION: Limit place details calls based on type
                if place_type in ['tourist_attraction', 'museum', 'park', 'amusement_park', 'art_gallery', 'zoo', 'aquarium']:
                    # For landmarks, get more results per type to create a larger pool for popularity ranking
                    places_to_detail = min(12, max_results, len(high_priority_places))
                elif place_type == 'restaurant':
                    # For restaurants, allow up to 10 results
                    places_to_detail = min(10, max_results, len(high_priority_places))
                else:
                    # For other types, limit to top 5
                    places_to_detail = min(5, max_results, len(high_priority_places))
                
                self.logger.info(f"💰 Cost optimization: Fetching details for top {places_to_detail} out of {len(high_priority_places)} places")

                # Get details for selected places in parallel
                # 🚀 SPEED OPTIMIZATION: Skip opening_hours for faster /generate endpoint
                detail_tasks = []
                for place in high_priority_places[:places_to_detail]:
                    if self.rate_limits['place_details'].can_proceed():
                        detail_tasks.append(self.place_details(place['place_id'], include_opening_hours=False))

                detailed_results = []
                if detail_tasks:
                    details_list = await asyncio.gather(*detail_tasks, return_exceptions=True)
                    for details in details_list:
                        if isinstance(details, dict) and details.get('result'):
                            detailed_results.append(details['result'])
                        elif isinstance(details, Exception):
                            self.logger.error(f"Error fetching place detail: {details}")

            self.logger.info(f"Successfully fetched details for {len(detailed_results)} places")
            if place_type == 'restaurant':
                self.logger.info(f"Fetched details for {len(detailed_results)} restaurants")

            # Cache results with longer TTL for cost efficiency
            if detailed_results: # Only cache if we have results
                await self.cache.set(cache_key, detailed_results, 'places')
                if place_type == 'restaurant':
                    self.logger.info(f"Cached {len(detailed_results)} restaurants under key: {cache_key}")
            elif place_type == 'restaurant':
                 self.logger.info(f"Not caching restaurants as no detailed results were fetched for key: {cache_key}")
            return detailed_results

        except Exception as e:
            self.logger.error(f"Error in get_places: {str(e)}")
            return []

    async def _search_restaurants_with_fallback(
        self,
        location: Dict[str, float],
        radius: int,
        keywords: List[str],
        max_results: int,
        special_requests: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Simple restaurant search to avoid timeouts."""
        
        # Just do one search call to avoid hanging
        self.logger.info(f"🍽️ Simple restaurant search for {max_results} restaurants")
        
        results = await self.places_nearby(
            location=location,
            radius=radius,
            place_type='restaurant',
            keyword=None  # No keyword for broader results
        )
        
        if results.get('results'):
            self.logger.info(f"Found {len(results['results'])} restaurants from Google Places API")
            detailed_restaurants = await self._get_restaurant_details_optimized(results['results'], max_results)
            self.logger.info(f"Returning {len(detailed_restaurants)} detailed restaurants")
            return detailed_restaurants
        
        return []

    async def _get_restaurant_details_optimized(self, restaurant_results: List[Dict], max_results: int) -> List[Dict[str, Any]]:
        """Get detailed information for restaurants with cost optimization."""
        
        # 🎯 COST OPTIMIZATION: Smart restaurant prioritization
        # Score and prioritize restaurants before fetching expensive details
        
        scored_restaurants = []
        hotel_restaurants_filtered = 0
        for place in restaurant_results:
            # Skip hotel restaurants and other non-restaurant establishments
            place_types = place.get('types', [])
            place_name_lower = place.get('name', '').lower()
            
            # Check for lodging/hotel types
            if 'lodging' in place_types or 'hotel' in place_types:
                hotel_restaurants_filtered += 1
                self.logger.debug(f"Skipping hotel restaurant: {place.get('name')}")
                continue
            
            # Check for club/athletic establishments that might not be proper restaurants
            if ('club' in place_name_lower and ('athletic' in place_name_lower or 'country' in place_name_lower or 'golf' in place_name_lower)):
                hotel_restaurants_filtered += 1
                self.logger.debug(f"Skipping club establishment: {place.get('name')}")
                continue
            
            score = 0
            
            # Prioritize by rating
            rating = place.get('rating', 0)
            if rating >= 4.5:
                score += 15
            elif rating >= 4.0:
                score += 12
            elif rating >= 3.5:
                score += 8
            elif rating >= 3.0:
                score += 4
            
            # Prioritize by review count (popularity)
            review_count = place.get('user_ratings_total', 0)
            if review_count >= 1000:
                score += 10
            elif review_count >= 500:
                score += 8
            elif review_count >= 200:
                score += 6
            elif review_count >= 100:
                score += 4
            elif review_count >= 50:
                score += 2
            
            # Price level preference (avoid missing price data)
            price_level = place.get('price_level')
            if price_level in [1, 2, 3]:  # Has price data and reasonable
                score += 5
            elif price_level == 4:  # Expensive but has data
                score += 2
            
            # Boost if has photos (indicates established business)
            if place.get('photos'):
                score += 3
            
            # 🚀 SPEED OPTIMIZATION: Skip opening_hours check for faster scoring
            # Note: opening_hours.open_now boost removed for speed optimization
            # This provides minimal impact since we're already scoring by rating & reviews
            
            place['_score'] = score
            scored_restaurants.append(place)
        
        # Sort by score and limit to reduce API costs
        scored_restaurants.sort(key=lambda x: x.get('_score', 0), reverse=True)
        
        self.logger.info(f"Restaurant filtering: {len(restaurant_results)} total → {hotel_restaurants_filtered} hotel restaurants filtered → {len(scored_restaurants)} remaining")
        
        # 💰 COST OPTIMIZATION: Restaurant limit increased to 10 per user request
        # Previous limit was 10, keeping same for now to assess cost impact
        cost_optimized_limit = min(10, max_results, len(scored_restaurants))
        self.logger.info(f"💰 Restaurant cost optimization: Fetching details for top {cost_optimized_limit} out of {len(scored_restaurants)} restaurants")
        
        detail_tasks = []
        for place in scored_restaurants[:cost_optimized_limit]:
            if self.rate_limits['place_details'].can_proceed():
                # 🚀 SPEED OPTIMIZATION: Skip opening_hours for faster /generate endpoint  
                detail_tasks.append(self.place_details(place['place_id'], include_opening_hours=False))

        detailed_results = []
        if detail_tasks:
            details_list = await asyncio.gather(*detail_tasks, return_exceptions=True)
            for details in details_list:
                if isinstance(details, dict) and details.get('result'):
                    detailed_results.append(details['result'])
                elif isinstance(details, Exception):
                    self.logger.error(f"Error fetching restaurant detail: {details}")

        return detailed_results

    def is_place_open_during_dates(
        self,
        place: Dict,
        start_date: Optional[str],
        end_date: Optional[str]
    ) -> bool:
        """Check if place will be open during the travel dates"""
        if not start_date or not end_date:
            return True  # If no dates provided, assume it's open
            
        try:
            if 'opening_hours' not in place:
                return True  # If no hours info, assume it's open
                
            start = date_parser.parse(start_date)
            end = date_parser.parse(end_date)
            
            # Check if the place is permanently closed
            if place.get('business_status') == 'CLOSED_PERMANENTLY':
                return False
                
            # If we have detailed opening hours, check them
            opening_hours = place['opening_hours']
            
            # If the place is currently open, it's likely operational
            if opening_hours.get('open_now') is True:
                return True
                
            # Check periods if available
            if 'periods' in opening_hours:
                # Get all days between start and end date
                days_to_check = set()
                current = start
                while current <= end:
                    days_to_check.add(current.weekday())
                    current = current + timedelta(days=1)
                
                # Check if the place is open on any of the required days
                for period in opening_hours['periods']:
                    open_day = period['open']['day']
                    close_day = period.get('close', {}).get('day', open_day)
                    
                    # Handle overnight periods (close day < open day)
                    if close_day < open_day:
                        close_day += 7
                    
                    # Check if any day in our range falls within this period
                    for day in days_to_check:
                        # Normalize day to handle overnight periods
                        check_day = day
                        if check_day < open_day:
                            check_day += 7
                            
                        if open_day <= check_day <= close_day:
                            return True
                
                # If we have periods but none match our days, place is closed
                return False
                
            # If we have weekday_text but no periods, check if any mention "Closed"
            if 'weekday_text' in opening_hours:
                days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                days_to_check = set()
                current = start
                while current <= end:
                    days_to_check.add(days[current.weekday()])
                    current = current + timedelta(days=1)
                
                for day in days_to_check:
                    day_text = next((text for text in opening_hours['weekday_text'] if text.startswith(day)), '')
                    if day_text and 'Closed' in day_text:
                        return False
                
            # If we can't determine definitively, assume it's open
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking opening hours: {str(e)}, place data: {json.dumps(place, indent=2)}")
            return True  # If we can't determine, assume it's open 

    async def geocode(self, destination: str) -> Optional[Dict[str, Any]]:
        """Geocode a destination string to coordinates. Uses self.routes_client.reverse_geocode for consistency if preferred, 
           or can directly use the Geocoding API via self._session if geocode is a distinct capability.
           Current implementation uses a direct call similar to before but via the shared session.
        """
        session = await self.get_session() # Ensures session is available
        url = "https://maps.googleapis.com/maps/api/geocode/json" # Geocoding API URL
        params = {
            'address': destination,
            'key': self.api_key
        }
        self.logger.debug(f"Geocoding (GooglePlacesClient) destination: {destination}")
        try:
            async with session.get(url, params=params, timeout=10) as response:
                response.raise_for_status()
                result = await response.json()
                if result.get('status') == 'OK' and result.get('results'):
                    self.logger.debug(f"Geocoding (GooglePlacesClient) successful for {destination}")
                    return result['results'][0]['geometry']['location']
                self.logger.error(f"Geocoding (GooglePlacesClient) API error for {destination}: {result.get('status')}, message: {result.get('error_message', 'No error message')}")
                return None
        except aiohttp.ClientResponseError as e:
            self.logger.error(f"Geocoding (GooglePlacesClient) HTTP error for {destination}: {e.status} {e.message}")
            return None
        except asyncio.TimeoutError: # Explicitly catch asyncio.TimeoutError
            self.logger.error(f"Geocoding (GooglePlacesClient) Timeout for {destination}")
            return None
        except Exception as e:
            self.logger.error(f"Geocoding (GooglePlacesClient) Unexpected error for {destination}: {str(e)}")
            return None

    async def close(self):
        """Close the aiohttp session if it was created by this instance, the Redis cache, and the Routes client."""
        # Session closing logic depends on whether PlacesClient *ever* creates its own session.
        # If session is *always* passed from main.py, then main.py is responsible for closing it.
        # PlacesClient should then not attempt to close a session it didn't create.
        # For now, retaining the _should_close_session logic for safety, but it might be redundant.
        if self._session and self._should_close_session and not self._session.closed:
            await self._session.close()
            self.logger.info("aiohttp ClientSession closed by GooglePlacesClient (because it created it).")
        
        # Close RedisCache and GoogleRoutesClient
        # GoogleRoutesClient.close() is currently a pass-through, as its session is managed externally.
        # If GoogleRoutesClient had other resources, its close method would handle them.
        await self.routes_client.close() # This will call the new async close in GoogleRoutesClient
        self.logger.info("GoogleRoutesClient connections managed for closure by GooglePlacesClient.")

    async def get_photo_url(self, photo_reference: str, max_width: int = 400, max_height: int = 400) -> Optional[str]:
        """Get photo URL from Google Places Photo API"""
        if not photo_reference:
            return None
            
        session = await self.get_session()
        url = "https://maps.googleapis.com/maps/api/place/photo"
        params = {
            'photoreference': photo_reference,
            'maxwidth': max_width,
            'maxheight': max_height,
            'key': self.api_key
        }
        
        try:
            async with session.get(url, params=params, timeout=10, allow_redirects=False) as response:
                if response.status == 302:  # Redirect to actual image
                    return str(response.headers.get('Location'))
                else:
                    self.logger.error(f"Unexpected status code for photo: {response.status}")
                    return None
        except Exception as e:
            self.logger.error(f"Error getting photo URL: {str(e)}")
            return None

    async def get_photo_data(self, photo_reference: str, max_width: int = 400, max_height: int = 400) -> Optional[bytes]:
        """Get photo data from Google Places Photo API for caching"""
        if not photo_reference:
            return None
            
        cache_key = self.cache.get_key(
            'image_proxy',
            photoreference=photo_reference,
            maxwidth=max_width,
            maxheight=max_height
        )
        
        # Check cache first
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            self.logger.info(f"Photo cache hit for {photo_reference}")
            return cached_data
            
        session = await self.get_session()
        url = "https://maps.googleapis.com/maps/api/place/photo"
        params = {
            'photoreference': photo_reference,
            'maxwidth': max_width,
            'maxheight': max_height,
            'key': self.api_key
        }
        
        try:
            async with session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    photo_data = await response.read()
                    # Cache the photo data
                    await self.cache.set(cache_key, photo_data, 'image_proxy')
                    self.logger.info(f"Photo cached for {photo_reference}")
                    return photo_data
                else:
                    self.logger.error(f"Error fetching photo: {response.status}")
                    return None
        except Exception as e:
            self.logger.error(f"Error getting photo data: {str(e)}")
            return None

# Make sure all async methods in GooglePlacesClient use `await self.get_session()`
# For example, in places_nearby:
# async def places_nearby(self, ...)
#     session = await self.get_session()
#     ...
#
# And in place_details:
# async def place_details(self, ...)
#     session = await self.get_session()
#     ...

# ... (rest of the existing methods) ... 