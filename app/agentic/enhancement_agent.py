"""
Enhancement Agent for restaurant integration and landmark enhancement.
Handles Google Places integration.
"""
import logging
import time
from typing import Dict, List, Optional, Set, Any

from ..schema import StructuredDayPlan, ItineraryBlock, Location
from ..places_client import GooglePlacesClient
from .restaurant_system import RestaurantSystem

logger = logging.getLogger(__name__)

class EnhancementAgent:
    """Agent responsible for restaurant integration and landmark enhancement"""
    
    def __init__(self):
        self.restaurant_system = RestaurantSystem()
    
    async def _enhance_day_with_restaurants(
        self, 
        day_plan: StructuredDayPlan, 
        places_client: GooglePlacesClient,
        destination: str,
        used_restaurants: set
    ) -> StructuredDayPlan:
        """Enhance a day with restaurant integration and landmark enhancement"""
        
        try:
            # First enhance landmarks with Google Places data using the destination
            enhanced_landmarks_day = await self._enhance_landmarks_basic(day_plan, places_client, destination)
            
            # Then add restaurants
            enhanced_with_restaurants = await self.restaurant_system.add_restaurants_to_day(
                enhanced_landmarks_day, places_client, destination, used_restaurants
            )
            
            return enhanced_with_restaurants
            
        except Exception as e:
            logger.error(f"❌ Day {day_plan.day} enhancement failed: {e}")
            return day_plan
    
    async def _enhance_landmarks_basic(self, day_plan: StructuredDayPlan, places_client: GooglePlacesClient, destination: str) -> StructuredDayPlan:
        """Basic landmark enhancement - add Google Places data"""
        try:
            enhanced_blocks = []
            
            for block in day_plan.blocks:
                if block.type == 'landmark':
                    # Try to enhance this landmark using destination
                    enhanced_block = await self._enhance_single_landmark_basic(block, places_client, destination)
                    enhanced_blocks.append(enhanced_block)
                else:
                    # Keep non-landmarks as-is
                    enhanced_blocks.append(block)
            
            return StructuredDayPlan(day=day_plan.day, blocks=enhanced_blocks)
            
        except Exception as e:
            logger.warning(f"⚠️ Basic enhancement failed for Day {day_plan.day}: {e}")
            return day_plan
    
    async def _enhance_single_landmark_basic(self, block: ItineraryBlock, places_client: GooglePlacesClient, destination: str) -> ItineraryBlock:
        """Basic enhancement for a single landmark - uses destination coordinates"""
        try:
            # Get destination coordinates for proper search
            location = await places_client.geocode(destination)
            if not location:
                logger.warning(f"Could not geocode destination {destination}, using landmark name only")
                # Fallback to text search without location bias
                search_queries = [block.name]
                search_location = None
            else:
                # Use destination-based search queries and location
                search_queries = [
                    f"{block.name} {destination}",
                    block.name
                ]
                search_location = {"lat": location["lat"], "lng": location["lng"]}
            
            for query in search_queries:
                try:
                    if search_location:
                        # Use nearby search with destination coordinates
                        results = await places_client.places_nearby(
                            location=search_location,
                            radius=25000,  # 25km radius
                            place_type="tourist_attraction",
                            keyword=query
                        )
                    else:
                        # Use text search if no location available
                        results = await places_client.text_search(query)
                    
                    if results and results.get('results'):
                        place_data = results['results'][0]  # Take first result
                        
                        # Apply basic place data
                        enhanced_block = block.model_copy()
                        if place_data.get('place_id'):
                            enhanced_block.place_id = place_data['place_id']
                            
                        if place_data.get('rating'):
                            enhanced_block.rating = place_data['rating']
                            
                        if 'geometry' in place_data and 'location' in place_data['geometry']:
                            enhanced_block.location = Location(
                                lat=place_data['geometry']['location']['lat'],
                                lng=place_data['geometry']['location']['lng']
                            )
                        
                        if place_data.get('formatted_address'):
                            enhanced_block.address = place_data['formatted_address']
                        elif place_data.get('vicinity'):
                            enhanced_block.address = place_data['vicinity']
                        
                        # Add photo URL extraction
                        if place_data.get('photos'):
                            photo_reference = place_data['photos'][0].get('photo_reference')
                            if photo_reference:
                                enhanced_block.photo_url = f"/photo-proxy/{photo_reference}?maxwidth=400&maxheight=400"
                        
                        logger.info(f"✅ Enhanced landmark: {block.name} in {destination} -> place_id: {enhanced_block.place_id}")
                        return enhanced_block
                        
                except Exception as e:
                    logger.debug(f"Search failed for '{query}' in {destination}: {e}")
                    continue
            
            # No enhancement found
            logger.warning(f"⚠️ No enhancement found for landmark {block.name} in {destination}")
            return block
            
        except Exception as e:
            logger.warning(f"⚠️ Failed to enhance landmark {block.name}: {e}")
            return block 