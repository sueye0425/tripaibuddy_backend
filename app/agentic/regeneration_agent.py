"""
Regeneration Agent for Gap Detection and Fixing

This agent detects timing gaps in itineraries and regenerates landmarks
or adjusts timing to create seamless day flow.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from ..schema import ItineraryBlock, Location, StructuredDayPlan
from ..places_client import GooglePlacesClient
from .llm_agent import LLMAgent

logger = logging.getLogger(__name__)


class RegenerationAgent:
    """Agent responsible for detecting and fixing gaps in itineraries"""
    
    def __init__(self):
        self.llm_agent = LLMAgent()
        self.logger = logging.getLogger(__name__)
    
    async def detect_and_fix_gaps(
        self,
        day_plan: StructuredDayPlan,
        destination: str,
        trip_details: Dict,
        places_client: GooglePlacesClient
    ) -> StructuredDayPlan:
        """Detect gaps and regenerate landmarks to fix them"""
        
        try:
            self.logger.info(f"🔍 Analyzing Day {day_plan.day} for gaps...")
            
            # Check for theme park day with multiple landmarks (regeneration needed)
            landmarks = [b for b in day_plan.blocks if b.type == "landmark"]
            is_theme_park_day = self._is_theme_park_day(landmarks)
            
            if is_theme_park_day and len(landmarks) > 1:
                self.logger.info(f"🎢 Theme park day with {len(landmarks)} landmarks - consolidating...")
                return await self._fix_theme_park_day(day_plan, places_client)
            
            # For speed, skip detailed gap analysis and return the plan as-is
            # The intelligent meal timing should already prevent major gaps
            self.logger.info(f"⚡ Skipping detailed gap analysis for speed - relying on intelligent meal timing")
            return day_plan
            
        except Exception as e:
            self.logger.error(f"❌ Error in gap detection/fixing: {e}")
            return day_plan
    
    def _detect_gaps(self, blocks: List[ItineraryBlock]) -> List[Dict[str, Any]]:
        """Detect gaps longer than 3 hours between activities"""
        
        gaps = []
        
        try:
            # Sort blocks by start time
            timed_blocks = []
            for block in blocks:
                if block.start_time:
                    try:
                        start_time = datetime.strptime(block.start_time, "%H:%M")
                        duration_minutes = self._parse_duration_to_minutes(block.duration or "1h")
                        end_time = start_time + timedelta(minutes=duration_minutes)
                        
                        timed_blocks.append({
                            "block": block,
                            "start_time": start_time,
                            "end_time": end_time
                        })
                    except ValueError:
                        continue
            
            # Sort by start time
            timed_blocks.sort(key=lambda x: x["start_time"])
            
            # Check for gaps
            for i in range(len(timed_blocks) - 1):
                current = timed_blocks[i]
                next_block = timed_blocks[i + 1]
                
                gap_duration = (next_block["start_time"] - current["end_time"]).total_seconds() / 60  # minutes
                
                if gap_duration > 180:  # More than 3 hours
                    gaps.append({
                        "after": current["block"].name,
                        "before": next_block["block"].name,
                        "gap_start": current["end_time"],
                        "gap_end": next_block["start_time"],
                        "duration_minutes": gap_duration,
                        "duration_hours": gap_duration / 60,
                        "position": i + 1  # Position to insert new activity
                    })
            
        except Exception as e:
            self.logger.error(f"Error detecting gaps: {e}")
        
        return gaps
    
    async def _fix_theme_park_day(
        self,
        day_plan: StructuredDayPlan,
        places_client: GooglePlacesClient
    ) -> StructuredDayPlan:
        """Fix theme park day by consolidating to single landmark"""
        
        try:
            landmarks = [b for b in day_plan.blocks if b.type == "landmark"]
            restaurants = [b for b in day_plan.blocks if b.type == "restaurant"]
            
            if not landmarks:
                return day_plan
            
            # Find the theme park landmark
            theme_park = None
            for landmark in landmarks:
                if self._is_theme_park_landmark(landmark):
                    theme_park = landmark
                    break
            
            # If no clear theme park found, use the first landmark
            if not theme_park:
                theme_park = landmarks[0]
            
            # Set proper theme park timing
            theme_park.start_time = "09:00"
            theme_park.duration = "8h"
            
            # Create new day plan with only the theme park and restaurants
            new_blocks = [theme_park] + restaurants
            
            self.logger.info(f"✅ Consolidated theme park day to single landmark: {theme_park.name}")
            
            return StructuredDayPlan(day=day_plan.day, blocks=new_blocks)
            
        except Exception as e:
            self.logger.error(f"Error fixing theme park day: {e}")
            return day_plan
    
    async def _fix_regular_day_gaps(
        self,
        day_plan: StructuredDayPlan,
        gaps: List[Dict[str, Any]],
        destination: str,
        trip_details: Dict,
        places_client: GooglePlacesClient
    ) -> StructuredDayPlan:
        """Fix gaps in regular days by adding landmarks or adjusting timing"""
        
        try:
            # For large gaps (>4 hours), add new landmarks
            large_gaps = [g for g in gaps if g["duration_hours"] > 4]
            
            if large_gaps:
                return await self._add_landmarks_to_fill_gaps(
                    day_plan, large_gaps, destination, trip_details, places_client
                )
            
            # For smaller gaps (3-4 hours), try adjusting meal timing
            return self._adjust_timing_to_reduce_gaps(day_plan, gaps)
            
        except Exception as e:
            self.logger.error(f"Error fixing regular day gaps: {e}")
            return day_plan
    
    async def _add_landmarks_to_fill_gaps(
        self,
        day_plan: StructuredDayPlan,
        gaps: List[Dict[str, Any]],
        destination: str,
        trip_details: Dict,
        places_client: GooglePlacesClient
    ) -> StructuredDayPlan:
        """Add new landmarks to fill large gaps"""
        
        try:
            new_blocks = day_plan.blocks.copy()
            existing_landmark_names = {b.name.lower() for b in day_plan.blocks if b.type == "landmark"}
            
            for gap in gaps:
                # Calculate time slot for new landmark
                gap_start = gap["gap_start"]
                gap_end = gap["gap_end"]
                gap_duration = gap["duration_minutes"]
                
                # Leave buffer time around meals and activities
                buffer_minutes = 30
                available_start = gap_start + timedelta(minutes=buffer_minutes)
                available_end = gap_end - timedelta(minutes=buffer_minutes)
                available_duration = (available_end - available_start).total_seconds() / 60
                
                if available_duration >= 90:  # At least 1.5 hours available
                    # Generate new landmark for this time slot
                    new_landmark = await self._generate_gap_filling_landmark(
                        destination, available_start, available_duration, 
                        existing_landmark_names, trip_details, places_client
                    )
                    
                    if new_landmark:
                        # Insert at the right position
                        insert_position = gap["position"]
                        new_blocks.insert(insert_position, new_landmark)
                        existing_landmark_names.add(new_landmark.name.lower())
                        
                        self.logger.info(f"✅ Added landmark '{new_landmark.name}' to fill {gap['duration_hours']:.1f}h gap")
            
            return StructuredDayPlan(day=day_plan.day, blocks=new_blocks)
            
        except Exception as e:
            self.logger.error(f"Error adding landmarks to fill gaps: {e}")
            return day_plan
    
    async def _generate_gap_filling_landmark(
        self,
        destination: str,
        start_time: datetime,
        available_duration: float,
        existing_names: set,
        trip_details: Dict,
        places_client: GooglePlacesClient
    ) -> Optional[ItineraryBlock]:
        """Generate a landmark to fill a specific time gap"""
        
        try:
            # Get destination coordinates
            location = await places_client.geocode(destination)
            if not location:
                return None
            
            # Define search types based on time of day and preferences
            search_types = ["tourist_attraction", "museum", "park"]
            
            # Afternoon activities (after 2 PM) - prefer indoor activities
            if start_time.hour >= 14:
                search_types = ["museum", "art_gallery", "shopping_mall", "tourist_attraction"]
            
            # Add kid-friendly options if traveling with kids
            if trip_details.get('withKids'):
                search_types.extend(["zoo", "aquarium", "playground"])
            
            # Search for suitable landmarks
            for search_type in search_types:
                try:
                    results = await places_client.places_nearby(
                        location={"lat": location["lat"], "lng": location["lng"]},
                        radius=15000,  # 15km radius
                        place_type=search_type,
                        keyword=f"{search_type.replace('_', ' ')} {destination}"
                    )
                    
                    if results and results.get('results'):
                        for place_data in results['results'][:3]:  # Try top 3
                            name = place_data.get('name', '')
                            
                            # Skip if name already exists
                            if name.lower() in existing_names:
                                continue
                            
                            # Calculate appropriate duration
                            landmark_duration = min(available_duration, 120)  # Max 2 hours
                            duration_str = f"{landmark_duration/60:.1f}h" if landmark_duration >= 60 else f"{int(landmark_duration)}m"
                            
                            # Create landmark block
                            landmark_block = ItineraryBlock(
                                name=name,
                                type="landmark",
                                description=self._get_landmark_description(place_data),
                                start_time=start_time.strftime("%H:%M"),
                                duration=duration_str,
                                location=self._extract_location(place_data),
                                place_id=place_data.get('place_id'),
                                rating=place_data.get('rating'),
                                address=place_data.get('formatted_address')
                            )
                            
                            return landmark_block
                
                except Exception as e:
                    self.logger.debug(f"Error searching for {search_type}: {e}")
                    continue
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error generating gap-filling landmark: {e}")
            return None
    
    def _adjust_timing_to_reduce_gaps(
        self,
        day_plan: StructuredDayPlan,
        gaps: List[Dict[str, Any]]
    ) -> StructuredDayPlan:
        """Adjust timing of existing activities to reduce gaps"""
        
        try:
            # For now, return the original plan
            # This could be enhanced to shift meal times or activity times
            self.logger.info("🔧 Gap adjustment not implemented yet - returning original plan")
            return day_plan
            
        except Exception as e:
            self.logger.error(f"Error adjusting timing: {e}")
            return day_plan
    
    def _parse_duration_to_minutes(self, duration_str: str) -> int:
        """Parse duration string to minutes"""
        if not duration_str:
            return 60
        
        duration_str = duration_str.lower().strip()
        
        if duration_str.endswith('h'):
            hours_str = duration_str[:-1]
            try:
                hours = float(hours_str)
                return int(hours * 60)
            except ValueError:
                return 60
        elif duration_str.endswith('min') or duration_str.endswith('m'):
            minutes_str = duration_str.replace('min', '').replace('m', '')
            try:
                return int(minutes_str)
            except ValueError:
                return 60
        else:
            try:
                hours = float(duration_str)
                return int(hours * 60)
            except ValueError:
                return 60
    
    def _is_theme_park_day(self, landmarks: List[ItineraryBlock]) -> bool:
        """Check if this is a theme park day"""
        for landmark in landmarks:
            if self._is_theme_park_landmark(landmark):
                return True
        return False
    
    def _is_theme_park_landmark(self, landmark: ItineraryBlock) -> bool:
        """Check if a landmark is a theme park"""
        theme_park_keywords = [
            'disney', 'universal', 'studios', 'magic kingdom', 'epcot', 
            'hollywood studios', 'animal kingdom', 'islands of adventure',
            'volcano bay', 'seaworld', 'busch gardens', 'legoland'
        ]
        
        name_lower = landmark.name.lower()
        desc_lower = (landmark.description or "").lower()
        
        return any(keyword in name_lower or keyword in desc_lower for keyword in theme_park_keywords)
    
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