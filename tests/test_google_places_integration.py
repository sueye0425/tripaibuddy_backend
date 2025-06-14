"""
Test Google Places API integration with the agentic itinerary system.
"""

import pytest
import aiohttp
from unittest.mock import patch, MagicMock

from app.agentic import complete_itinerary_from_selection
from app.places_client import GooglePlacesClient
from app.schema import StructuredDayPlan, ItineraryBlock, Location


class TestGooglePlacesIntegration:
    """Test suite for Google Places API integration"""

    @pytest.mark.asyncio
    async def test_complete_itinerary_with_google_places(self, sample_trip_selection, mock_places_client, mock_google_places_restaurant_detailed):
        """Test complete itinerary generation with Google Places integration"""
        
        # Mock Google Places responses
        mock_places_client.places_nearby.return_value = {"results": [mock_google_places_restaurant_detailed] * 10}
        mock_places_client.geocode.return_value = {"lat": 28.5383, "lng": -81.3792}
        
        result = await complete_itinerary_from_selection(sample_trip_selection, mock_places_client)
        
        # Verify basic structure
        assert 'itinerary' in result, "Result should contain itinerary"
        assert 'itinerary' in result['itinerary'], "Result should contain nested itinerary"
        
        itinerary_days = result['itinerary']['itinerary']
        assert len(itinerary_days) == 3, "Should generate 3 days"
        
        # Verify Google Places data integration
        for day in itinerary_days:
            restaurants = [block for block in day['blocks'] if block['type'] == 'restaurant']
            landmarks = [block for block in day['blocks'] if block['type'] == 'landmark']
            
            # Restaurants should have Google Places data
            for restaurant in restaurants:
                assert 'name' in restaurant, "Restaurant should have name"
                if 'place_id' in restaurant:
                    assert restaurant['place_id'], "Restaurant place_id should not be empty"
                if 'location' in restaurant and restaurant['location']:
                    assert 'lat' in restaurant['location'], "Restaurant should have latitude"
                    assert 'lng' in restaurant['location'], "Restaurant should have longitude"
            
            # Landmarks should have basic data
            for landmark in landmarks:
                assert 'name' in landmark, "Landmark should have name"
                assert 'description' in landmark, "Landmark should have description"

    @pytest.mark.asyncio
    async def test_geocoding_integration(self, sample_trip_selection, mock_places_client, mock_google_places_restaurant_detailed):
        """Test that destination geocoding works properly"""
        
        # Mock successful geocoding
        mock_places_client.geocode.return_value = {"lat": 28.5383, "lng": -81.3792}
        mock_places_client.places_nearby.return_value = {"results": [mock_google_places_restaurant_detailed] * 5}
        
        result = await complete_itinerary_from_selection(sample_trip_selection, mock_places_client)
        
        # Should succeed with proper geocoding
        assert 'itinerary' in result, "Should generate itinerary with successful geocoding"
        assert 'error' not in result, "Should not have errors with successful geocoding"
        
        # Verify geocode was called (may be called multiple times by different agents)
        assert mock_places_client.geocode.call_count >= 1, "Geocode should be called at least once"

    @pytest.mark.asyncio
    async def test_geocoding_failure_handling(self, sample_trip_selection, mock_places_client):
        """Test handling of geocoding failures"""
        
        # Mock geocoding failure
        mock_places_client.geocode.return_value = None
        
        result = await complete_itinerary_from_selection(sample_trip_selection, mock_places_client)
        
        # Should return error response
        assert 'error' in result, "Should return error when geocoding fails"
        assert "Could not geocode destination" in result['error'], "Should indicate geocoding failure"

    @pytest.mark.asyncio
    async def test_restaurant_search_integration(self, sample_trip_selection, mock_places_client):
        """Test restaurant search integration with Google Places"""
        
        # Create diverse restaurant responses
        restaurants = []
        for i in range(10):
            restaurants.append({
                "place_id": f"restaurant_place_id_{i}",
                "name": f"Restaurant {i}",
                "vicinity": f"Address {i}, Orlando, FL",
                "rating": 4.0 + (i % 5) / 10,
                "geometry": {"location": {"lat": 28.5 + i*0.01, "lng": -81.4 + i*0.01}},
                "types": ["restaurant", "food"]
            })
        
        mock_places_client.places_nearby.return_value = {"results": restaurants}
        mock_places_client.geocode.return_value = {"lat": 28.5383, "lng": -81.3792}
        
        result = await complete_itinerary_from_selection(sample_trip_selection, mock_places_client)
        
        # Verify restaurant integration
        total_restaurants = 0
        for day in result['itinerary']['itinerary']:
            day_restaurants = [block for block in day['blocks'] if block['type'] == 'restaurant']
            total_restaurants += len(day_restaurants)
            
            for restaurant in day_restaurants:
                assert 'name' in restaurant, "Restaurant should have name"
                # Should have Google Places data if available
                if 'place_id' in restaurant:
                    assert restaurant['place_id'].startswith('restaurant_place_id_'), "Should use mock place_id"
        
        assert total_restaurants > 0, "Should have restaurants from Google Places search"

    @pytest.mark.asyncio
    async def test_places_api_error_handling(self, sample_trip_selection, mock_places_client):
        """Test handling of Google Places API errors"""
        
        # Mock API error
        mock_places_client.geocode.return_value = {"lat": 28.5383, "lng": -81.3792}
        mock_places_client.places_nearby.side_effect = Exception("API Error")
        
        # Should handle API errors gracefully
        result = await complete_itinerary_from_selection(sample_trip_selection, mock_places_client)
        
        # Should still return some result (may have fewer restaurants)
        assert 'itinerary' in result or 'error' in result, "Should handle API errors gracefully"

    @pytest.mark.asyncio
    async def test_location_data_accuracy(self, sample_trip_selection, mock_places_client, mock_google_places_restaurant_detailed):
        """Test that location data from Google Places is accurate"""
        
        # Mock with specific location data
        test_restaurant = mock_google_places_restaurant_detailed.copy()
        test_restaurant["geometry"]["location"] = {"lat": 28.1234, "lng": -81.5678}
        
        mock_places_client.places_nearby.return_value = {"results": [test_restaurant] * 5}
        mock_places_client.geocode.return_value = {"lat": 28.5383, "lng": -81.3792}
        
        result = await complete_itinerary_from_selection(sample_trip_selection, mock_places_client)
        
        # Find restaurants with location data
        restaurants_with_location = []
        for day in result['itinerary']['itinerary']:
            for block in day['blocks']:
                if block['type'] == 'restaurant' and 'location' in block and block['location']:
                    restaurants_with_location.append(block)
        
        # Verify location accuracy
        for restaurant in restaurants_with_location:
            location = restaurant['location']
            assert location['lat'] == 28.1234, f"Latitude should match mock data: {location['lat']}"
            assert location['lng'] == -81.5678, f"Longitude should match mock data: {location['lng']}"

    @pytest.mark.asyncio
    async def test_restaurant_data_completeness(self, sample_trip_selection, mock_places_client, mock_google_places_restaurant_detailed):
        """Test that restaurant data from Google Places is complete"""
        
        # Mock with complete restaurant data
        complete_restaurant = {
            "place_id": "complete_restaurant_123",
            "name": "Complete Restaurant",
            "vicinity": "123 Complete St, Orlando, FL",
            "formatted_address": "123 Complete St, Orlando, FL 32819, USA",
            "rating": 4.7,
            "geometry": {"location": {"lat": 28.5383, "lng": -81.3792}},
            "photos": [{"photo_reference": "photo_123"}],
            "types": ["restaurant", "food"],
            "user_ratings_total": 1500
        }
        
        mock_places_client.places_nearby.return_value = {"results": [complete_restaurant] * 5}
        mock_places_client.geocode.return_value = {"lat": 28.5383, "lng": -81.3792}
        
        result = await complete_itinerary_from_selection(sample_trip_selection, mock_places_client)
        
        # Find restaurants and verify data completeness
        restaurants = []
        for day in result['itinerary']['itinerary']:
            for block in day['blocks']:
                if block['type'] == 'restaurant':
                    restaurants.append(block)
        
        assert len(restaurants) > 0, "Should have restaurants"
        
        # Check data completeness for restaurants that have Google Places data
        for restaurant in restaurants:
            assert 'name' in restaurant, "Restaurant should have name"
            if 'place_id' in restaurant and restaurant['place_id'] == 'complete_restaurant_123':
                # This restaurant should have complete data
                assert 'rating' in restaurant or restaurant.get('rating') is not None, "Should have rating data"


 