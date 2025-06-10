"""
Test restaurant addition logic using mocked LLM responses.

These tests validate:
- Correct number of restaurants per day
- Proper meal timing (especially theme park lunch at 12:30)
- No duplicate restaurants across days
- Google Places integration
- Restaurant filtering and selection

No LLM costs - uses mocked data!
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import json

from app.agentic_itinerary import enhanced_agentic_system
from app.schema import StructuredDayPlan, ItineraryBlock, Location

# Import detailed fixtures from Google Places integration test
from .test_google_places_integration import mock_google_places_restaurant_detailed, mock_google_places_landmark_detailed


class TestRestaurantLogic:
    """Test suite for restaurant addition logic"""
    
    @pytest.mark.asyncio
    async def test_restaurant_count_per_day(self, sample_trip_selection, mock_places_client, mock_google_places_restaurant_detailed):
        """Test that exactly 3 restaurants are added per day"""
        
        # Mock Google Places to return restaurants using detailed fixture
        mock_places_client.places_nearby.return_value = {"results": [mock_google_places_restaurant_detailed] * 5}
        
        # Create a day plan with landmarks only
        day_plan = StructuredDayPlan(
            day=1,
            blocks=[
                ItineraryBlock(
                    name="Universal Studios Florida",
                    type="landmark",
                    start_time="09:00",
                    duration="8h"
                )
            ]
        )
        
        # Test restaurant addition
        result = await enhanced_agentic_system._add_restaurants_to_day(
            day_plan, mock_places_client, sample_trip_selection
        )
        
        # Count restaurants
        restaurants = [block for block in result.blocks if block.type == 'restaurant']
        landmarks = [block for block in result.blocks if block.type == 'landmark']
        
        assert len(restaurants) == 3, f"Expected 3 restaurants, got {len(restaurants)}"
        assert len(landmarks) == 1, f"Expected 1 landmark, got {len(landmarks)}"
        
        # Check meal types
        meal_types = {r.mealtime for r in restaurants}
        expected_meals = {'breakfast', 'lunch', 'dinner'}
        assert meal_types == expected_meals, f"Missing meal types: {expected_meals - meal_types}"

    @pytest.mark.asyncio
    async def test_theme_park_lunch_timing(self, sample_trip_selection, mock_places_client, mock_google_places_restaurant_detailed):
        """Test that theme park lunch is scheduled at exactly 12:30"""
        
        mock_places_client.places_nearby.return_value = {"results": [mock_google_places_restaurant_detailed] * 5}
        
        # Create theme park day
        day_plan = StructuredDayPlan(
            day=1,
            blocks=[
                ItineraryBlock(
                    name="Universal Studios Florida",
                    type="landmark", 
                    start_time="09:00",
                    duration="8h"
                )
            ]
        )
        
        result = await enhanced_agentic_system._add_restaurants_to_day(
            day_plan, mock_places_client, sample_trip_selection
        )
        
        # Find lunch restaurant
        lunch_restaurant = next(
            (block for block in result.blocks 
             if block.type == 'restaurant' and block.mealtime == 'lunch'),
            None
        )
        
        assert lunch_restaurant is not None, "No lunch restaurant found"
        assert lunch_restaurant.start_time == "12:30", (
            f"Theme park lunch should be at 12:30, got {lunch_restaurant.start_time}"
        )

    @pytest.mark.asyncio
    async def test_no_duplicate_restaurants_across_days(self, sample_trip_selection, mock_places_client):
        """Test that no duplicate restaurants are used across multiple days"""
        
        # Create multiple unique restaurants using detailed format
        restaurants = []
        for i in range(15):  # 5 restaurants per day * 3 days = 15 total
            restaurants.append({
                "place_id": f"ChIJtest_place_id_{i}",
                "name": f"Restaurant {i}",
                "vicinity": f"Address {i}, Orlando, FL",
                "formatted_address": f"Address {i}, Orlando, FL 32819, USA",
                "rating": 4.0 + (i % 10) / 10,
                "geometry": {
                    "location": {"lat": 28.5 + i*0.01, "lng": -81.4 + i*0.01}
                },
                "photos": [
                    {
                        "photo_reference": f"test_photo_{i}",
                        "width": 400,
                        "height": 400
                    }
                ],
                "types": ["restaurant", "food", "establishment"]
            })
        
        mock_places_client.places_nearby.return_value = {"results": restaurants}
        
        # Reset the global used restaurants
        enhanced_agentic_system._used_restaurants_global = set()
        
        # Process 3 days
        all_place_ids = set()
        for day_num in range(1, 4):
            day_plan = StructuredDayPlan(
                day=day_num,
                blocks=[
                    ItineraryBlock(
                        name=f"Landmark Day {day_num}",
                        type="landmark",
                        start_time="09:00",
                        duration="3h"
                    )
                ]
            )
            
            result = await enhanced_agentic_system._add_restaurants_to_day(
                day_plan, mock_places_client, sample_trip_selection
            )
            
            # Collect place_ids for this day
            day_restaurants = [block for block in result.blocks if block.type == 'restaurant']
            day_place_ids = {r.place_id for r in day_restaurants if r.place_id}
            
            # Check no duplicates within this day
            assert len(day_place_ids) == len(day_restaurants), f"Duplicate restaurants within day {day_num}"
            
            # Check no overlap with previous days
            overlap = all_place_ids.intersection(day_place_ids)
            assert len(overlap) == 0, f"Day {day_num} has duplicate restaurants from previous days: {overlap}"
            
            all_place_ids.update(day_place_ids)

    @pytest.mark.asyncio
    async def test_google_places_integration(self, sample_trip_selection, mock_places_client, mock_google_places_restaurant_detailed):
        """Test that restaurants get proper Google Places data"""
        
        mock_places_client.places_nearby.return_value = {"results": [mock_google_places_restaurant_detailed] * 5}
        
        day_plan = StructuredDayPlan(
            day=1,
            blocks=[
                ItineraryBlock(
                    name="Test Landmark",
                    type="landmark",
                    start_time="09:00",
                    duration="3h"
                )
            ]
        )
        
        result = await enhanced_agentic_system._add_restaurants_to_day(
            day_plan, mock_places_client, sample_trip_selection
        )
        
        restaurants = [block for block in result.blocks if block.type == 'restaurant']
        
        for restaurant in restaurants:
            assert restaurant.place_id == "ChIJtest_restaurant_123", f"Missing place_id: {restaurant.name}"
            assert restaurant.address == "123 Test Street, Orlando, FL 32819, USA", f"Missing address: {restaurant.name}"
            assert restaurant.rating == 4.5, f"Missing rating: {restaurant.name}"
            assert restaurant.location is not None, f"Missing location: {restaurant.name}"

    @pytest.mark.asyncio
    async def test_regular_day_meal_timing(self, sample_trip_selection, mock_places_client, mock_google_places_restaurant):
        """Test that regular (non-theme park) days have proper meal timing"""
        
        mock_places_client.places_nearby.return_value = [mock_google_places_restaurant] * 5
        
        # Create regular day (not theme park)
        day_plan = StructuredDayPlan(
            day=2,
            blocks=[
                ItineraryBlock(
                    name="Orlando Science Center",
                    type="landmark",
                    start_time="09:00", 
                    duration="3h"
                )
            ]
        )
        
        result = await enhanced_agentic_system._add_restaurants_to_day(
            day_plan, mock_places_client, sample_trip_selection
        )
        
        restaurants = [block for block in result.blocks if block.type == 'restaurant']
        meal_times = {r.mealtime: r.start_time for r in restaurants}
        
        # Regular day meal times (not theme park)
        expected_times = {
            'breakfast': '08:00',
            'lunch': '12:00', 
            'dinner': '19:00'
        }
        
        for meal, expected_time in expected_times.items():
            assert meal in meal_times, f"Missing {meal} on regular day"
            assert meal_times[meal] == expected_time, (
                f"Regular day {meal} should be at {expected_time}, got {meal_times[meal]}"
            )

    @pytest.mark.asyncio 
    async def test_restaurant_filtering_by_type(self, sample_trip_selection, mock_places_client):
        """Test that only appropriate restaurants are selected"""
        
        # Mix of restaurants and non-restaurants
        places_data = [
            {
                "place_id": "restaurant1",
                "name": "Good Restaurant",
                "types": ["restaurant", "food", "establishment"],
                "rating": 4.2,
                "vicinity": "Main St",
                "geometry": {"location": {"lat": 28.5, "lng": -81.4}}
            },
            {
                "place_id": "gas_station",
                "name": "Gas Station",
                "types": ["gas_station", "convenience_store"],
                "rating": 3.0,
                "vicinity": "Highway",
                "geometry": {"location": {"lat": 28.5, "lng": -81.4}}
            },
            {
                "place_id": "restaurant2", 
                "name": "Another Restaurant",
                "types": ["restaurant", "bar", "establishment"],
                "rating": 4.8,
                "vicinity": "Downtown",
                "geometry": {"location": {"lat": 28.5, "lng": -81.4}}
            }
        ]
        
        mock_places_client.places_nearby.return_value = places_data
        
        day_plan = StructuredDayPlan(
            day=1,
            blocks=[
                ItineraryBlock(
                    name="Test Landmark",
                    type="landmark",
                    start_time="09:00",
                    duration="3h"
                )
            ]
        )
        
        result = await enhanced_agentic_system._add_restaurants_to_day(
            day_plan, mock_places_client, sample_trip_selection
        )
        
        restaurants = [block for block in result.blocks if block.type == 'restaurant']
        restaurant_names = {r.name for r in restaurants}
        
        # Should only include actual restaurants, not gas station
        assert "Good Restaurant" in restaurant_names or "Another Restaurant" in restaurant_names
        assert "Gas Station" not in restaurant_names, "Gas station should not be selected as restaurant" 