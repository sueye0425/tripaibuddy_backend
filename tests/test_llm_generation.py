"""
Test LLM generation functionality in the agentic itinerary system.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import json
import aiohttp

from app.agentic import complete_itinerary_from_selection
from app.places_client import GooglePlacesClient


class TestLLMGeneration:
    """Test suite for LLM generation functionality"""

    @pytest.mark.asyncio
    async def test_complete_itinerary_generation(self, sample_trip_selection, mock_places_client, mock_google_places_restaurant_detailed):
        """Test that complete itinerary generation works end-to-end"""
        
        # Mock Google Places responses
        mock_places_client.places_nearby.return_value = {"results": [mock_google_places_restaurant_detailed] * 10}
        mock_places_client.geocode.return_value = {"lat": 28.5383, "lng": -81.3792}
        mock_places_client.place_details.return_value = {"result": mock_google_places_restaurant_detailed}
        
        result = await complete_itinerary_from_selection(sample_trip_selection, mock_places_client)
        
        # Verify basic structure
        assert 'itinerary' in result, "Result should contain itinerary"
        assert 'itinerary' in result['itinerary'], "Result should contain nested itinerary"
        
        itinerary_days = result['itinerary']['itinerary']
        assert len(itinerary_days) == 3, "Should generate 3 days"
        
        # Verify each day has proper structure
        for day in itinerary_days:
            assert 'day' in day, "Each day should have day number"
            assert 'blocks' in day, "Each day should have blocks"
            assert len(day['blocks']) > 0, "Each day should have at least one block"
            
            # Verify block structure
            for block in day['blocks']:
                assert 'type' in block, "Each block should have type"
                assert 'name' in block, "Each block should have name"
                assert block['type'] in ['landmark', 'restaurant'], "Block type should be landmark or restaurant"

    @pytest.mark.asyncio
    async def test_landmark_enhancement(self, sample_trip_selection, mock_places_client, mock_google_places_restaurant_detailed):
        """Test that landmarks are properly enhanced with descriptions and details"""
        
        # Mock Google Places responses
        mock_places_client.places_nearby.return_value = {"results": [mock_google_places_restaurant_detailed] * 10}
        mock_places_client.geocode.return_value = {"lat": 28.5383, "lng": -81.3792}
        mock_places_client.place_details.return_value = {"result": mock_google_places_restaurant_detailed}
        
        result = await complete_itinerary_from_selection(sample_trip_selection, mock_places_client)
        
        # Find landmark blocks
        landmark_blocks = []
        for day in result['itinerary']['itinerary']:
            for block in day['blocks']:
                if block['type'] == 'landmark':
                    landmark_blocks.append(block)
        
        assert len(landmark_blocks) > 0, "Should have landmark blocks"
        
        # Verify landmark enhancement
        for landmark in landmark_blocks:
            assert 'name' in landmark, "Landmark should have name"
            assert 'description' in landmark, "Landmark should have description"
            assert landmark['description'], "Landmark description should not be empty"
            assert 'start_time' in landmark, "Landmark should have start_time"
            assert 'duration' in landmark, "Landmark should have duration"

    @pytest.mark.asyncio
    async def test_restaurant_integration(self, sample_trip_selection, mock_places_client, mock_google_places_restaurant_detailed):
        """Test that restaurants are properly integrated into the itinerary"""
        
        # Mock Google Places responses
        mock_places_client.places_nearby.return_value = {"results": [mock_google_places_restaurant_detailed] * 10}
        mock_places_client.geocode.return_value = {"lat": 28.5383, "lng": -81.3792}
        mock_places_client.place_details.return_value = {"result": mock_google_places_restaurant_detailed}
        
        result = await complete_itinerary_from_selection(sample_trip_selection, mock_places_client)
        
        # Find restaurant blocks
        restaurant_blocks = []
        for day in result['itinerary']['itinerary']:
            for block in day['blocks']:
                if block['type'] == 'restaurant':
                    restaurant_blocks.append(block)
        
        assert len(restaurant_blocks) > 0, "Should have restaurant blocks"
        
        # Verify restaurant structure
        for restaurant in restaurant_blocks:
            assert 'name' in restaurant, "Restaurant should have name"
            assert 'start_time' in restaurant, "Restaurant should have start_time"
            assert 'duration' in restaurant, "Restaurant should have duration"
            # Note: restaurants don't have descriptions in the current system
            
            # Verify meal timing
            if 'mealtime' in restaurant:
                assert restaurant['mealtime'] in ['breakfast', 'lunch', 'dinner'], "Mealtime should be valid"

    @pytest.mark.asyncio
    async def test_timing_logic(self, sample_trip_selection, mock_places_client, mock_google_places_restaurant_detailed):
        """Test that timing logic produces reasonable schedules"""
        
        # Mock Google Places responses
        mock_places_client.places_nearby.return_value = {"results": [mock_google_places_restaurant_detailed] * 10}
        mock_places_client.geocode.return_value = {"lat": 28.5383, "lng": -81.3792}
        mock_places_client.place_details.return_value = {"result": mock_google_places_restaurant_detailed}
        
        result = await complete_itinerary_from_selection(sample_trip_selection, mock_places_client)
        
        # Verify timing logic for each day
        for day in result['itinerary']['itinerary']:
            blocks = day['blocks']
            
            # Sort blocks by start time
            sorted_blocks = sorted(blocks, key=lambda b: b['start_time'])
            
            # Verify reasonable start times
            for block in sorted_blocks:
                start_hour = int(block['start_time'].split(':')[0])
                assert 6 <= start_hour <= 22, f"Start time {block['start_time']} should be between 6:00 and 22:00"
            
            # Verify no overlapping times (simplified check)
            for i in range(len(sorted_blocks) - 1):
                current_block = sorted_blocks[i]
                next_block = sorted_blocks[i + 1]
                
                current_start = int(current_block['start_time'].split(':')[0])
                next_start = int(next_block['start_time'].split(':')[0])
                
                # Next block should start after current block (allowing for duration)
                assert next_start >= current_start, f"Blocks should not overlap: {current_block['name']} -> {next_block['name']}"

    @pytest.mark.asyncio
    async def test_error_handling(self, sample_trip_selection, mock_places_client):
        """Test that the system handles errors gracefully"""
        
        # Mock geocoding failure
        mock_places_client.geocode.return_value = None
        
        result = await complete_itinerary_from_selection(sample_trip_selection, mock_places_client)
        
        # Should return error response
        assert 'error' in result, "Should return error when geocoding fails"
        assert "Could not geocode destination" in result['error'], "Should indicate geocoding failure"

    @pytest.mark.asyncio
    async def test_special_requests_handling(self, mock_places_client, mock_google_places_restaurant_detailed):
        """Test that special requests are handled appropriately"""
        
        # Create trip selection with special requests
        from app.schema import LandmarkSelection, TripDetails, DayAttraction, Attraction, Location
        
        details = TripDetails(
            destination='Orlando, FL',
            travelDays=3,
            startDate='2024-06-10',
            endDate='2024-06-12',
            withKids=True,
            kidsAge=[8, 12],
            withElders=False,
            specialRequests='vegetarian restaurants only'
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

        trip_with_special_requests = LandmarkSelection(
            details=details,
            itinerary=[
                DayAttraction(day=1, attractions=[universal_studios]),
                DayAttraction(day=2, attractions=[science_center]),
                DayAttraction(day=3, attractions=[eola_park])
            ],
            wishlist=[]
        )
        trip_with_special_requests.details.specialRequests = "vegetarian restaurants only"
        
        # Mock Google Places responses
        mock_places_client.places_nearby.return_value = {"results": [mock_google_places_restaurant_detailed] * 10}
        mock_places_client.geocode.return_value = {"lat": 28.5383, "lng": -81.3792}
        mock_places_client.place_details.return_value = {"result": mock_google_places_restaurant_detailed}
        
        result = await complete_itinerary_from_selection(trip_with_special_requests, mock_places_client)
        
        # Should still generate a complete itinerary
        assert 'itinerary' in result, "Should generate itinerary even with special requests"
        assert 'itinerary' in result['itinerary'], "Should contain nested itinerary"
        
        itinerary_days = result['itinerary']['itinerary']
        assert len(itinerary_days) == 3, "Should generate 3 days" 