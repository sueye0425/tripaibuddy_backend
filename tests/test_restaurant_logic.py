"""
Test restaurant logic in the agentic itinerary system.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import json

from app.agentic import complete_itinerary_from_selection
from app.schema import StructuredDayPlan, ItineraryBlock, Location


class TestRestaurantLogic:
    """Test suite for restaurant logic and integration"""

    @pytest.mark.asyncio
    async def test_restaurant_integration_in_complete_itinerary(self, sample_trip_selection, mock_places_client, mock_multiple_restaurants):
        """Test that restaurants are properly integrated into complete itinerary"""
        
        # Mock Google Places responses
        mock_places_client.places_nearby.return_value = {"results": mock_multiple_restaurants}
        mock_places_client.geocode.return_value = {"lat": 28.5383, "lng": -81.3792}
        mock_places_client.place_details.return_value = {"result": mock_multiple_restaurants[0]}
        
        result = await complete_itinerary_from_selection(sample_trip_selection, mock_places_client)
        
        # Verify each day has restaurants
        for day in result['itinerary']['itinerary']:
            restaurants = [block for block in day['blocks'] if block['type'] == 'restaurant']
            assert len(restaurants) > 0, f"Day {day['day']} should have restaurants"
            
            # Verify restaurant structure
            for restaurant in restaurants:
                assert 'name' in restaurant, "Restaurant should have name"
                assert 'start_time' in restaurant, "Restaurant should have start_time"
                assert 'duration' in restaurant, "Restaurant should have duration"
                assert restaurant['type'] == 'restaurant', "Type should be restaurant"

    @pytest.mark.asyncio
    async def test_meal_timing_logic(self, sample_trip_selection, mock_places_client, mock_google_places_restaurant_detailed):
        """Test that restaurants are scheduled at appropriate meal times"""
        
        # Mock Google Places responses
        mock_places_client.places_nearby.return_value = {"results": [mock_google_places_restaurant_detailed] * 10}
        mock_places_client.geocode.return_value = {"lat": 28.5383, "lng": -81.3792}
        mock_places_client.place_details.return_value = {"result": mock_google_places_restaurant_detailed}
        
        result = await complete_itinerary_from_selection(sample_trip_selection, mock_places_client)
        
        # Check meal timing for each day
        for day in result['itinerary']['itinerary']:
            restaurants = [block for block in day['blocks'] if block['type'] == 'restaurant']
            
            for restaurant in restaurants:
                start_time = restaurant['start_time']
                start_hour = int(start_time.split(':')[0])
                
                # Restaurants should be scheduled during reasonable meal times
                # Breakfast: 7-10, Lunch: 11-15, Dinner: 17-21
                assert (7 <= start_hour <= 10) or (11 <= start_hour <= 15) or (17 <= start_hour <= 21), (
                    f"Restaurant {restaurant['name']} scheduled at {start_time}, "
                    f"should be during meal times (7-10, 11-15, 17-21)"
                )

    @pytest.mark.asyncio
    async def test_restaurant_variety_across_days(self, sample_trip_selection, mock_places_client):
        """Test that different restaurants are used across different days"""
        
        # Create diverse restaurants
        restaurants = []
        for i in range(15):
            restaurants.append({
                "place_id": f"restaurant_{i}",
                "name": f"Restaurant {i}",
                "vicinity": f"Address {i}",
                "rating": 4.0 + (i % 5) / 10,
                "geometry": {"location": {"lat": 28.5 + i*0.01, "lng": -81.4 + i*0.01}},
                "types": ["restaurant", "food"]
            })
        
        mock_places_client.places_nearby.return_value = {"results": restaurants}
        mock_places_client.geocode.return_value = {"lat": 28.5383, "lng": -81.3792}
        
        result = await complete_itinerary_from_selection(sample_trip_selection, mock_places_client)
        
        # Collect all restaurant place_ids
        all_restaurant_place_ids = []
        for day in result['itinerary']['itinerary']:
            for block in day['blocks']:
                if block['type'] == 'restaurant' and block.get('place_id'):
                    all_restaurant_place_ids.append(block['place_id'])
        
        # Check for duplicates
        unique_place_ids = set(all_restaurant_place_ids)
        assert len(all_restaurant_place_ids) == len(unique_place_ids), (
            f"Found duplicate restaurants across days. "
            f"Total: {len(all_restaurant_place_ids)}, Unique: {len(unique_place_ids)}"
        )

    @pytest.mark.asyncio
    async def test_theme_park_restaurant_timing(self, mock_places_client, mock_multiple_restaurants):
        """Test that theme park days have appropriate restaurant timing"""
        
        # Create trip selection with theme park
        from app.schema import LandmarkSelection, TripDetails, DayAttraction, Attraction, Location
        
        details = TripDetails(
            destination='Orlando, FL',
            travelDays=3,
            startDate='2024-06-10',
            endDate='2024-06-12',
            withKids=True,
            kidsAge=[8, 12],
            withElders=False,
            specialRequests='Include Universal Studios theme park'
        )

        universal_studios = Attraction(
            name='Universal Studios Florida',
            type='landmark',
            description='Famous movie-themed attractions and rides',
            location=Location(lat=28.4743, lng=-81.4677)
        )

        science_center = Attraction(
            name='Orlando Science Center',
            type='landmark',
            description='Interactive science exhibits and planetarium',
            location=Location(lat=28.5721, lng=-81.3519)
        )

        eola_park = Attraction(
            name='Lake Eola Park',
            type='landmark',
            description='Beautiful downtown park with swan boats',
            location=Location(lat=28.5427, lng=-81.3709)
        )

        trip_selection = LandmarkSelection(
            details=details,
            itinerary=[
                DayAttraction(day=1, attractions=[universal_studios]),
                DayAttraction(day=2, attractions=[science_center]),
                DayAttraction(day=3, attractions=[eola_park])
            ],
            wishlist=[]
        )
        
        # Mock Google Places responses
        mock_places_client.places_nearby.return_value = {"results": mock_multiple_restaurants}
        mock_places_client.geocode.return_value = {"lat": 28.5383, "lng": -81.3792}
        mock_places_client.place_details.return_value = {"result": mock_multiple_restaurants[0]}
        
        result = await complete_itinerary_from_selection(trip_selection, mock_places_client)
        
        # Day 1 has Universal Studios (theme park)
        day_1 = next(day for day in result['itinerary']['itinerary'] if day['day'] == 1)
        restaurants = [block for block in day_1['blocks'] if block['type'] == 'restaurant']
        
        # Theme park days should have restaurants
        assert len(restaurants) > 0, "Theme park day should have restaurants"
        
        # Check for lunch timing (theme parks typically have lunch around 12:30)
        lunch_restaurants = [r for r in restaurants if 11 <= int(r['start_time'].split(':')[0]) <= 15]
        assert len(lunch_restaurants) > 0, "Theme park day should have lunch restaurant"

    @pytest.mark.asyncio
    async def test_restaurant_selection_behavior(self, sample_trip_selection, mock_places_client):
        """Test restaurant selection behavior from Google Places results"""
        
        # Create mix of restaurants (system takes first available, doesn't filter by type)
        restaurants = [
            {
                "place_id": "restaurant_1",
                "name": "Italian Bistro",
                "vicinity": "Main St",
                "rating": 4.2,
                "geometry": {"location": {"lat": 28.5, "lng": -81.4}},
                "types": ["restaurant", "food", "establishment"]
            },
            {
                "place_id": "restaurant_2", 
                "name": "Seafood Grill",
                "vicinity": "Ocean Ave",
                "rating": 4.5,
                "geometry": {"location": {"lat": 28.51, "lng": -81.41}},
                "types": ["restaurant", "food", "establishment"]
            },
            {
                "place_id": "restaurant_3",
                "name": "Pizza Place",
                "vicinity": "Downtown",
                "rating": 4.0,
                "geometry": {"location": {"lat": 28.52, "lng": -81.42}},
                "types": ["restaurant", "food"]
            }
        ]
        
        mock_places_client.places_nearby.return_value = {"results": restaurants}
        mock_places_client.geocode.return_value = {"lat": 28.5383, "lng": -81.3792}
        
        result = await complete_itinerary_from_selection(sample_trip_selection, mock_places_client)
        
        # Collect all restaurant names
        all_restaurant_names = []
        for day in result['itinerary']['itinerary']:
            for block in day['blocks']:
                if block['type'] == 'restaurant':
                    all_restaurant_names.append(block['name'].lower())
        
        # Should have restaurants from the provided list
        assert len(all_restaurant_names) > 0, "Should have restaurants"
        
        # Should include restaurants from our mock data
        expected_restaurants = ["italian bistro", "seafood grill", "pizza place"]
        found_restaurants = [name for name in all_restaurant_names if any(expected in name for expected in expected_restaurants)]
        assert len(found_restaurants) > 0, "Should include restaurants from mock data"

    @pytest.mark.asyncio
    async def test_minimum_restaurant_count(self, sample_trip_selection, mock_places_client, mock_multiple_restaurants):
        """Test that each day has a minimum number of restaurants"""
        
        # Mock Google Places responses
        mock_places_client.places_nearby.return_value = {"results": mock_multiple_restaurants}
        mock_places_client.geocode.return_value = {"lat": 28.5383, "lng": -81.3792}
        mock_places_client.place_details.return_value = {"result": mock_multiple_restaurants[0]}
        
        result = await complete_itinerary_from_selection(sample_trip_selection, mock_places_client)
        
        # Each day should have at least 1 restaurant (ideally 3 for breakfast/lunch/dinner)
        for day in result['itinerary']['itinerary']:
            restaurants = [block for block in day['blocks'] if block['type'] == 'restaurant']
            assert len(restaurants) >= 1, f"Day {day['day']} should have at least 1 restaurant"

    @pytest.mark.asyncio
    async def test_restaurant_location_data(self, sample_trip_selection, mock_places_client, mock_google_places_restaurant_detailed):
        """Test that restaurants have proper location data"""
        
        # Mock Google Places responses
        mock_places_client.places_nearby.return_value = {"results": [mock_google_places_restaurant_detailed] * 10}
        mock_places_client.geocode.return_value = {"lat": 28.5383, "lng": -81.3792}
        mock_places_client.place_details.return_value = {"result": mock_google_places_restaurant_detailed}
        
        result = await complete_itinerary_from_selection(sample_trip_selection, mock_places_client)
        
        # Check restaurant location data
        for day in result['itinerary']['itinerary']:
            restaurants = [block for block in day['blocks'] if block['type'] == 'restaurant']
            
            for restaurant in restaurants:
                # Should have location data
                if 'location' in restaurant and restaurant['location']:
                    location = restaurant['location']
                    assert 'lat' in location, "Restaurant location should have latitude"
                    assert 'lng' in location, "Restaurant location should have longitude"
                    assert isinstance(location['lat'], (int, float)), "Latitude should be numeric"
                    assert isinstance(location['lng'], (int, float)), "Longitude should be numeric" 