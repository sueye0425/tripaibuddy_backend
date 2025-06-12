"""
LLM Agent for Intelligent Landmark Generation and Timing

This agent uses LLM prompts to generate landmarks with proper timing,
preventing gaps and ensuring optimal day flow.
"""

import logging
import json
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from ..llm_prompt_generator import LLMPromptGenerator
from ..schema import ItineraryBlock, Location, StructuredDayPlan, TripDetails
from ..places_client import GooglePlacesClient

# Import LLM client from rag.py
try:
    from ..rag import llm as openai_llm_client
    LLM_AVAILABLE = True
except ImportError:
    openai_llm_client = None
    LLM_AVAILABLE = False

logger = logging.getLogger(__name__)


class LLMAgent:
    """LLM Agent for intelligent landmark generation and timing"""
    
    def __init__(self):
        self.prompt_generator = LLMPromptGenerator()
        self.llm_client = openai_llm_client if LLM_AVAILABLE else None
        self.logger = logging.getLogger(__name__)
    
    async def generate_landmarks_with_timing(
        self,
        destination: str,
        day_num: int,
        user_landmarks: List[ItineraryBlock],
        trip_details: Dict,
        places_client: GooglePlacesClient
    ) -> List[ItineraryBlock]:
        """Generate additional landmarks with intelligent timing"""
        
        try:
            self.logger.info(f"🧠 LLM Agent generating landmarks for Day {day_num}")
            
            # Check if this is a theme park day
            is_theme_park_day = self._is_theme_park_day(user_landmarks)
            
            if is_theme_park_day:
                self.logger.info(f"🎢 Day {day_num} is theme park day - minimal landmark generation")
                return await self._handle_theme_park_day(user_landmarks, places_client)
            
            # For speed, skip LLM calls and use fast Google Places generation
            # This ensures we meet the 12-second latency requirement
            self.logger.info("⚡ Using fast Google Places generation for speed")
            return await self._fallback_google_places_generation(
                user_landmarks, destination, trip_details, places_client
            )
            
        except Exception as e:
            self.logger.error(f"❌ Error in LLM landmark generation: {e}")
            # Return user landmarks with basic timing
            return self._apply_basic_timing(user_landmarks)
    
    async def _call_llm_for_landmarks(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Call LLM for landmark generation"""
        try:
            if not self.llm_client:
                return None
            
            self.logger.info("🤖 Calling LLM for landmark generation...")
            
            # Use the LLM client from rag.py
            response = await self.llm_client.ainvoke(prompt)
            
            # Extract JSON from response
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Try to extract JSON from the response
            json_match = self._extract_json_from_response(response_text)
            if json_match:
                return json.loads(json_match)
            
            self.logger.warning("⚠️ Could not extract valid JSON from LLM response")
            return None
            
        except Exception as e:
            self.logger.error(f"❌ Error calling LLM: {e}")
            return None
    
    def _extract_json_from_response(self, response_text: str) -> Optional[str]:
        """Extract JSON from LLM response text"""
        try:
            # Look for JSON blocks in the response
            import re
            
            # Try to find JSON between ```json and ``` or { and }
            json_patterns = [
                r'```json\s*(\{.*?\})\s*```',
                r'```\s*(\{.*?\})\s*```',
                r'(\{[^{}]*"landmarks"[^{}]*\})',
                r'(\{.*?\})'
            ]
            
            for pattern in json_patterns:
                matches = re.findall(pattern, response_text, re.DOTALL)
                for match in matches:
                    try:
                        # Validate JSON
                        json.loads(match)
                        return match
                    except json.JSONDecodeError:
                        continue
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error extracting JSON: {e}")
            return None
    
    async def _convert_llm_landmarks_to_blocks(
        self,
        llm_landmarks: List[Dict],
        destination: str,
        places_client: GooglePlacesClient
    ) -> List[ItineraryBlock]:
        """Convert LLM landmark data to ItineraryBlock objects"""
        
        blocks = []
        
        for landmark_data in llm_landmarks:
            try:
                name = landmark_data.get("name", "Unknown Landmark")
                description = landmark_data.get("description", "")
                start_time = landmark_data.get("start_time", "10:00")
                duration = landmark_data.get("duration", "2h")
                
                # Try to enhance with Google Places data
                enhanced_data = await self._enhance_landmark_with_google_places(
                    name, destination, places_client
                )
                
                block = ItineraryBlock(
                    name=name,
                    type="landmark",
                    description=description,
                    start_time=start_time,
                    duration=duration,
                    location=enhanced_data.get("location"),
                    place_id=enhanced_data.get("place_id"),
                    rating=enhanced_data.get("rating"),
                    address=enhanced_data.get("address"),
                    photo_url=enhanced_data.get("photo_url"),
                    website=enhanced_data.get("website")
                )
                
                blocks.append(block)
                
            except Exception as e:
                self.logger.error(f"Error converting landmark {landmark_data}: {e}")
                continue
        
        return blocks
    
    async def _enhance_landmark_with_google_places(
        self,
        landmark_name: str,
        destination: str,
        places_client: GooglePlacesClient
    ) -> Dict[str, Any]:
        """Enhance landmark with Google Places data"""
        
        try:
            # Search for the landmark
            results = await places_client.text_search(f"{landmark_name} {destination}")
            
            if results and results.get('results'):
                place_data = results['results'][0]
                
                # Get detailed data
                place_id = place_data.get('place_id')
                if place_id:
                    detailed_data = await places_client.place_details(place_id)
                    if detailed_data and detailed_data.get('result'):
                        place_data = detailed_data['result']
                
                # Extract relevant data
                location = None
                if 'geometry' in place_data and 'location' in place_data['geometry']:
                    loc = place_data['geometry']['location']
                    location = Location(lat=loc['lat'], lng=loc['lng'])
                
                return {
                    "location": location,
                    "place_id": place_data.get('place_id'),
                    "rating": place_data.get('rating'),
                    "address": place_data.get('formatted_address'),
                    "photo_url": self._extract_photo_url(place_data),
                    "website": place_data.get('website')
                }
            
        except Exception as e:
            self.logger.debug(f"Could not enhance {landmark_name} with Google Places: {e}")
        
        return {}
    
    def _extract_photo_url(self, place_data: Dict) -> Optional[str]:
        """Extract photo URL from place data"""
        try:
            photos = place_data.get('photos', [])
            if photos:
                photo_reference = photos[0].get('photo_reference')
                if photo_reference:
                    return f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photoreference={photo_reference}&key=YOUR_API_KEY"
        except Exception:
            pass
        return None
    
    def _apply_llm_timing(
        self,
        landmarks: List[ItineraryBlock],
        llm_response: Dict[str, Any]
    ) -> List[ItineraryBlock]:
        """Apply timing from LLM response to landmarks"""
        
        try:
            llm_landmarks = llm_response.get("landmarks", [])
            
            # Create a mapping of landmark names to timing
            timing_map = {}
            for llm_landmark in llm_landmarks:
                name = llm_landmark.get("name", "")
                timing_map[name.lower()] = {
                    "start_time": llm_landmark.get("start_time", "10:00"),
                    "duration": llm_landmark.get("duration", "2h")
                }
            
            # Apply timing to landmarks
            for landmark in landmarks:
                landmark_key = landmark.name.lower()
                if landmark_key in timing_map:
                    timing = timing_map[landmark_key]
                    landmark.start_time = timing["start_time"]
                    landmark.duration = timing["duration"]
            
            return landmarks
            
        except Exception as e:
            self.logger.error(f"Error applying LLM timing: {e}")
            return self._apply_basic_timing(landmarks)
    
    def _apply_basic_timing(self, landmarks: List[ItineraryBlock]) -> List[ItineraryBlock]:
        """Apply basic timing to landmarks"""
        
        start_times = ["09:00", "11:30", "14:00", "16:30"]
        durations = ["2h", "1.5h", "2h", "1.5h"]
        
        for i, landmark in enumerate(landmarks):
            if i < len(start_times):
                landmark.start_time = start_times[i]
                landmark.duration = durations[i]
            else:
                # For additional landmarks, space them out
                base_hour = 9 + (i * 2)
                landmark.start_time = f"{base_hour:02d}:00"
                landmark.duration = "1.5h"
        
        return landmarks
    
    async def _handle_theme_park_day(
        self,
        user_landmarks: List[ItineraryBlock],
        places_client: GooglePlacesClient
    ) -> List[ItineraryBlock]:
        """Handle theme park day - single long activity"""
        
        if user_landmarks:
            # Set theme park timing
            theme_park = user_landmarks[0]
            theme_park.start_time = "09:00"
            theme_park.duration = "8h"  # Full day at theme park
            
            return [theme_park]
        
        return user_landmarks
    
    async def _fallback_google_places_generation(
        self,
        user_landmarks: List[ItineraryBlock],
        destination: str,
        trip_details: Dict,
        places_client: GooglePlacesClient
    ) -> List[ItineraryBlock]:
        """Fallback to Google Places landmark generation"""
        
        try:
            # Get destination coordinates
            location = await places_client.geocode(destination)
            if not location:
                return self._apply_basic_timing(user_landmarks)
            
            # Define search types based on preferences
            search_types = ["tourist_attraction", "museum", "park"]
            if trip_details.get('withKids'):
                search_types.extend(["zoo", "aquarium", "playground"])
            
            # Get existing landmark names to avoid duplicates
            existing_names = {landmark.name.lower() for landmark in user_landmarks}
            
            additional_landmarks = []
            needed_landmarks = max(0, 2 - len(user_landmarks))  # Target 2-3 landmarks per day
            
            for search_type in search_types:
                if len(additional_landmarks) >= needed_landmarks:
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
                            
                            # Create landmark block
                            landmark_block = ItineraryBlock(
                                name=name,
                                type="landmark",
                                description=self._get_landmark_description(place_data),
                                start_time="11:00",  # Will be updated by timing logic
                                duration="1.5h",
                                location=self._extract_location(place_data),
                                place_id=place_data.get('place_id'),
                                rating=place_data.get('rating'),
                                address=place_data.get('formatted_address')
                            )
                            
                            additional_landmarks.append(landmark_block)
                            existing_names.add(name.lower())
                            
                            if len(additional_landmarks) >= needed_landmarks:
                                break
                
                except Exception as e:
                    self.logger.debug(f"Error searching for {search_type}: {e}")
                    continue
            
            # Combine and apply timing
            all_landmarks = user_landmarks + additional_landmarks
            return self._apply_basic_timing(all_landmarks)
            
        except Exception as e:
            self.logger.error(f"Error in fallback generation: {e}")
            return self._apply_basic_timing(user_landmarks)
    
    def _get_landmark_description(self, place_data: Dict) -> str:
        """Get landmark description from place data"""
        # Try editorial summary first
        if place_data.get('editorial_summary', {}).get('overview'):
            return place_data['editorial_summary']['overview']
        
        # Fallback to types-based description
        types = place_data.get('types', [])
        if 'tourist_attraction' in types:
            return "Popular tourist attraction"
        elif 'museum' in types:
            return "Museum with exhibits and collections"
        elif 'park' in types:
            return "Park with outdoor activities"
        elif 'zoo' in types:
            return "Zoo with animal exhibits"
        elif 'aquarium' in types:
            return "Aquarium with marine life"
        else:
            return "Local point of interest"
    
    def _extract_location(self, place_data: Dict) -> Optional[Location]:
        """Extract location from place data"""
        try:
            if 'geometry' in place_data and 'location' in place_data['geometry']:
                loc = place_data['geometry']['location']
                return Location(lat=loc['lat'], lng=loc['lng'])
        except Exception:
            pass
        return None
    
    def _is_theme_park_day(self, landmarks: List[ItineraryBlock]) -> bool:
        """Check if this is a theme park day"""
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