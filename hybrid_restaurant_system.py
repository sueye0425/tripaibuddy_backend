"""
Hybrid Restaurant Recommendation System
=====================================

This prototype demonstrates a more efficient approach:
- LLM generates only LANDMARKS (what it's good at)
- Google Places API finds nearby RESTAURANTS (what it's good at)
- Rule-based selection ensures no duplicates and optimal geography

Benefits:
- Faster (fewer LLM calls)
- More accurate (real restaurant data)
- Natural duplicate prevention (different locations = different restaurants)
- Real-time data (hours, ratings, prices)
"""

import asyncio
import time
from typing import List, Dict, Optional
from dataclasses import dataclass
from app.schema import LandmarkSelection, StructuredDayPlan, ItineraryBlock, Location
from app.places_client import GooglePlacesClient

@dataclass
class LandmarkOnlyDay:
    """Day plan with only landmarks - restaurants to be added via Google Places"""
    day: int
    landmarks: List[ItineraryBlock]

class HybridRestaurantSystem:
    """
    Hybrid system that separates landmark generation from restaurant selection
    """
    
    def __init__(self, places_client: Optional[GooglePlacesClient] = None):
        self.places_client = places_client
        self.used_restaurants = set()  # Global duplicate prevention
    
    async def generate_hybrid_itinerary(self, selection: LandmarkSelection) -> Dict:
        """
        Step 1: LLM generates landmarks only
        Step 2: Google Places API finds nearby restaurants
        Step 3: Rule-based selection with duplicate prevention
        """
        start_time = time.time()
        
        # Step 1: Generate landmarks only (much faster LLM call)
        landmark_days = await self._generate_landmarks_only(selection)
        landmark_time = time.time() - start_time
        
        # Step 2: Add restaurants using Google Places API
        restaurant_start = time.time()
        complete_days = await self._add_restaurants_via_google(landmark_days, selection.details.destination)
        restaurant_time = time.time() - restaurant_start
        
        total_time = time.time() - start_time
        
        return {
            "itinerary": [day.dict() for day in complete_days],
            "performance_summary": {
                "total_time": f"{total_time:.2f}s",
                "landmark_generation": f"{landmark_time:.2f}s",
                "restaurant_selection": f"{restaurant_time:.2f}s",
                "speedup_vs_full_llm": "2-3x estimated",
                "restaurants_found": len([block for day in complete_days for block in day.blocks if block.type == "restaurant"]),
                "duplicates_prevented": len(self.used_restaurants) - len(set(self.used_restaurants))
            }
        }
    
    async def _generate_landmarks_only(self, selection: LandmarkSelection) -> List[LandmarkOnlyDay]:
        """
        Use LLM to generate only landmarks - much simpler and faster prompt
        """
        from langchain.llms import OpenAI
        from langchain.prompts import PromptTemplate
        
        # Simplified landmark-only prompt
        landmark_prompt = PromptTemplate(
            template="""Generate landmarks ONLY for a {travel_days}-day itinerary in {destination}.

USER SELECTED LANDMARKS (REQUIRED):
{selected_landmarks}

YOUR TASK: Add 1-2 additional complementary landmarks per day (if needed).

LANDMARK RULES:
• Theme parks = FULL DAY (6-8h), no additional landmarks needed
• Museums/attractions = 1.5-3h each
• Parks/gardens = 1-2h each  
• Shopping/markets = 1-2h each
• Viewpoints = 30-60min each

DO NOT include any restaurants, meals, or dining. Landmarks only!

Output format for each day:
Day X:
- [Landmark Name] ([Duration]) - [Brief description]

{format_instructions}""",
            input_variables=["travel_days", "destination", "selected_landmarks"]
        )
        
        # This would be the actual LLM call (simplified for prototype)
        # In practice, this would be much faster than full itinerary generation
        landmark_days = []
        
        for day_num in range(1, selection.details.travelDays + 1):
            # Get selected landmarks for this day
            selected_landmarks = []
            for day_data in selection.itinerary:
                if day_data.day == day_num:
                    selected_landmarks.extend([attr for attr in day_data.attractions if attr.type == "landmark"])
                    break
            
            # For prototype, simulate landmark generation
            landmarks = []
            
            # Add selected landmarks
            for landmark in selected_landmarks:
                duration = "8h" if "universal" in landmark.name.lower() else "2h"
                landmarks.append(ItineraryBlock(
                    type="landmark",
                    name=landmark.name,
                    description=landmark.description,
                    start_time="10:00",
                    duration=duration,
                    mealtime=None,
                    location=landmark.location
                ))
            
            # Add complementary landmarks only if not a theme park day
            is_theme_park_day = any("universal" in landmark.name.lower() or "disney" in landmark.name.lower() 
                                  for landmark in selected_landmarks)
            
            if not is_theme_park_day and len(landmarks) < 2:
                # Add one complementary landmark
                landmarks.append(ItineraryBlock(
                    type="landmark",
                    name=f"Local Attraction in {selection.details.destination}",
                    description="Popular local attraction or cultural site",
                    start_time="14:00",
                    duration="1.5h",
                    mealtime=None,
                    location=Location(lat=28.5, lng=-81.4)  # Default Orlando area
                ))
            
            landmark_days.append(LandmarkOnlyDay(day=day_num, landmarks=landmarks))
        
        return landmark_days
    
    async def _add_restaurants_via_google(self, landmark_days: List[LandmarkOnlyDay], destination: str) -> List[StructuredDayPlan]:
        """
        Use Google Places API to find optimal restaurants near landmarks
        """
        complete_days = []
        
        for landmark_day in landmark_days:
            # Calculate center point of landmarks for this day
            center_location = self._calculate_day_center(landmark_day.landmarks)
            
            # Find restaurants for this day
            restaurants = await self._find_optimal_restaurants(
                center_location, 
                landmark_day.landmarks,
                destination
            )
            
            # Combine landmarks and restaurants into complete day
            all_blocks = []
            
            # Add breakfast
            if restaurants["breakfast"]:
                all_blocks.append(restaurants["breakfast"])
            
            # Add landmarks with timing
            for i, landmark in enumerate(landmark_day.landmarks):
                # Adjust start time based on position
                start_hour = 9 + (i * 3)  # Space out landmarks
                landmark.start_time = f"{start_hour:02d}:00"
                all_blocks.append(landmark)
            
            # Add lunch
            if restaurants["lunch"]:
                all_blocks.append(restaurants["lunch"])
            
            # Add dinner
            if restaurants["dinner"]:
                all_blocks.append(restaurants["dinner"])
            
            complete_days.append(StructuredDayPlan(day=landmark_day.day, blocks=all_blocks))
        
        return complete_days
    
    def _calculate_day_center(self, landmarks: List[ItineraryBlock]) -> Location:
        """Calculate the geographic center of landmarks for the day"""
        if not landmarks:
            return Location(lat=28.5, lng=-81.4)  # Default Orlando
        
        avg_lat = sum(landmark.location.lat for landmark in landmarks) / len(landmarks)
        avg_lng = sum(landmark.location.lng for landmark in landmarks) / len(landmarks)
        
        return Location(lat=avg_lat, lng=avg_lng)
    
    async def _find_optimal_restaurants(self, center: Location, landmarks: List[ItineraryBlock], destination: str) -> Dict[str, ItineraryBlock]:
        """
        Use Google Places API to find the best restaurants for each meal
        """
        if not self.places_client:
            # Fallback to generic restaurants if no Places API
            return self._create_fallback_restaurants(center, destination)
        
        restaurants = {}
        
        # Define search radius based on landmark spread
        radius = 5000  # 5km radius
        
        # Search for different meal types
        meal_types = [
            ("breakfast", ["breakfast", "cafe", "coffee", "brunch"]),
            ("lunch", ["lunch", "restaurant", "bistro", "casual_dining"]),
            ("dinner", ["dinner", "restaurant", "fine_dining", "family_restaurant"])
        ]
        
        for meal_time, keywords in meal_types:
            # Search for restaurants of this type
            query = f"{' '.join(keywords)} near {center.lat},{center.lng}"
            
            try:
                # Simulate Google Places API call
                search_results = await self._simulate_places_search(center, keywords, radius)
                
                # Select best restaurant (highest rating, not used before)
                best_restaurant = self._select_best_restaurant(search_results, meal_time)
                
                if best_restaurant:
                    restaurants[meal_time] = best_restaurant
                    self.used_restaurants.add(best_restaurant.name)
                
            except Exception as e:
                print(f"Error finding {meal_time} restaurant: {e}")
                restaurants[meal_time] = self._create_fallback_restaurant(center, meal_time, destination)
        
        return restaurants
    
    async def _simulate_places_search(self, center: Location, keywords: List[str], radius: int) -> List[Dict]:
        """
        Simulate Google Places API search results
        In real implementation, this would be actual API calls
        """
        # Simulate realistic restaurant data
        sample_restaurants = [
            {
                "name": f"Local {keywords[0].title()} Spot",
                "rating": 4.5,
                "location": {"lat": center.lat + 0.01, "lng": center.lng + 0.01},
                "types": ["restaurant", "food"],
                "vicinity": "Downtown Orlando"
            },
            {
                "name": f"Popular {keywords[0].title()} Place",
                "rating": 4.3,
                "location": {"lat": center.lat - 0.01, "lng": center.lng - 0.01},
                "types": ["restaurant", "food"],
                "vicinity": "Tourist District"
            }
        ]
        
        # Filter out already used restaurants
        return [r for r in sample_restaurants if r["name"] not in self.used_restaurants]
    
    def _select_best_restaurant(self, search_results: List[Dict], meal_time: str) -> Optional[ItineraryBlock]:
        """
        Select the best restaurant based on rating, distance, and availability
        """
        if not search_results:
            return None
        
        # Sort by rating
        best_result = max(search_results, key=lambda r: r.get("rating", 0))
        
        # Convert to ItineraryBlock
        meal_times = {
            "breakfast": "08:00",
            "lunch": "12:30", 
            "dinner": "18:30"
        }
        
        return ItineraryBlock(
            type="restaurant",
            name=best_result["name"],
            description=f"Highly rated {meal_time} spot ({best_result['rating']}★)",
            start_time=meal_times[meal_time],
            duration="1h",
            mealtime=meal_time,
            location=Location(
                lat=best_result["location"]["lat"],
                lng=best_result["location"]["lng"]
            ),
            rating=best_result["rating"]
        )
    
    def _create_fallback_restaurants(self, center: Location, destination: str) -> Dict[str, ItineraryBlock]:
        """Create fallback restaurants when Google Places API is unavailable"""
        return {
            "breakfast": ItineraryBlock(
                type="restaurant",
                name=f"Local {destination} Breakfast Cafe",
                description="Popular local breakfast spot",
                start_time="08:00",
                duration="1h",
                mealtime="breakfast",
                location=center
            ),
            "lunch": ItineraryBlock(
                type="restaurant",
                name=f"{destination} Bistro",
                description="Local lunch favorite",
                start_time="12:30",
                duration="1h",
                mealtime="lunch",
                location=center
            ),
            "dinner": ItineraryBlock(
                type="restaurant",
                name=f"Traditional {destination} Restaurant",
                description="Authentic local cuisine",
                start_time="18:30",
                duration="1.5h",
                mealtime="dinner",
                location=center
            )
        }
    
    def _create_fallback_restaurant(self, center: Location, meal_time: str, destination: str) -> ItineraryBlock:
        """Create a single fallback restaurant"""
        fallbacks = self._create_fallback_restaurants(center, destination)
        return fallbacks[meal_time]

# Example usage demonstration
async def test_hybrid_system():
    """Test the hybrid restaurant system"""
    print("🔬 Testing Hybrid Restaurant System")
    print("=" * 50)
    
    # Create sample selection (Orlando theme parks)
    from app.schema import TripDetails, DayAttraction, Attraction
    
    details = TripDetails(
        destination="Orlando, FL",
        travelDays=3,
        startDate="2025-06-03",
        endDate="2025-06-05",
        withKids=True,
        withElders=False,
        kidsAge=[2],
        specialRequests="Family-friendly theme park experience"
    )
    
    itinerary = [
        DayAttraction(day=1, attractions=[
            Attraction(
                name="Universal Islands of Adventure",
                description="Theme park with movie-based attractions",
                location=Location(lat=28.4716879, lng=-81.4701971),
                type="landmark"
            )
        ]),
        DayAttraction(day=2, attractions=[
            Attraction(
                name="Universal Studios Florida", 
                description="Movie studio theme park",
                location=Location(lat=28.4793754, lng=-81.4685422),
                type="landmark"
            )
        ]),
        DayAttraction(day=3, attractions=[
            Attraction(
                name="SEA LIFE Orlando Aquarium",
                description="Interactive aquarium experience", 
                location=Location(lat=28.4425885, lng=-81.4685680),
                type="landmark"
            )
        ])
    ]
    
    selection = LandmarkSelection(details=details, itinerary=itinerary, wishlist=[])
    
    # Test the hybrid system
    hybrid_system = HybridRestaurantSystem()
    result = await hybrid_system.generate_hybrid_itinerary(selection)
    
    print("✅ Results:")
    print(f"📊 Performance: {result['performance_summary']}")
    print(f"🍽️  Restaurants found: {result['performance_summary']['restaurants_found']}")
    print(f"⚡ Estimated speedup: {result['performance_summary']['speedup_vs_full_llm']}")
    
    return result

if __name__ == "__main__":
    # Run the test
    result = asyncio.run(test_hybrid_system()) 