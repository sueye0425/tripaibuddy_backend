"""
Test comprehensive Google Places API integration.

This test makes REAL Google Places API calls to validate:
- Restaurant search and selection
- Landmark enhancement
- Place data extraction
- API response handling
- Error recovery

⚠️ This test incurs Google Places API costs - run sparingly for validation!
Use mocked versions for development testing.
"""

import pytest
import asyncio
import aiohttp
from unittest.mock import patch, MagicMock

from app.agentic_itinerary import enhanced_agentic_system
from app.places_client import GooglePlacesClient
from app.schema import StructuredDayPlan, ItineraryBlock, Location


@pytest.mark.asyncio
@pytest.mark.llm_cost  # Mark as expensive test
async def test_google_places_restaurant_search():
    """
    Test Google Places API for restaurant search and data extraction.
    
    This validates the complete restaurant pipeline:
    - Search for restaurants near a location
    - Extract place_id, rating, address, photos
    - Create proper ItineraryBlock objects
    """
    
    async with aiohttp.ClientSession() as session:
        places_client = GooglePlacesClient(session)
        
        # Test restaurant search near Universal Studios
        center = Location(lat=28.4743, lng=-81.4677)
        
        # Search for breakfast restaurants
        restaurants = await places_client.places_nearby(
            location={"lat": center.lat, "lng": center.lng},
            radius=5000,
            place_type="restaurant",
            keyword="breakfast"
        )
        
        assert restaurants is not None, "Restaurant search should return results"
        assert 'results' in restaurants, "Response should contain results"
        assert len(restaurants['results']) > 0, "Should find at least one restaurant"
        
        # Test first restaurant result
        restaurant_data = restaurants['results'][0]
        
        # Validate required fields
        assert 'place_id' in restaurant_data, "Restaurant should have place_id"
        assert 'name' in restaurant_data, "Restaurant should have name"
        assert 'geometry' in restaurant_data, "Restaurant should have geometry"
        assert 'location' in restaurant_data['geometry'], "Geometry should have location"
        
        # Test creating restaurant block
        restaurant_block = enhanced_agentic_system._create_restaurant_block_from_place_data(
            restaurant_data, "breakfast", "08:00"
        )
        
        # Validate restaurant block
        assert restaurant_block.type == "restaurant"
        assert restaurant_block.mealtime == "breakfast"
        assert restaurant_block.start_time == "08:00"
        assert restaurant_block.place_id is not None, "Restaurant should have place_id"
        assert restaurant_block.name is not None, "Restaurant should have name"
        assert restaurant_block.location is not None, "Restaurant should have location"
        
        # Validate Google Places data integration
        if restaurant_data.get('rating'):
            assert restaurant_block.rating == restaurant_data['rating']
        
        if restaurant_data.get('formatted_address') or restaurant_data.get('vicinity'):
            assert restaurant_block.address is not None, "Restaurant should have address"
        
        print(f"✅ Restaurant validation passed: {restaurant_block.name}")
        print(f"   📍 Place ID: {restaurant_block.place_id}")
        print(f"   🏠 Address: {restaurant_block.address}")
        print(f"   ⭐ Rating: {restaurant_block.rating}")


@pytest.mark.asyncio
@pytest.mark.llm_cost
async def test_google_places_landmark_enhancement():
    """
    Test Google Places API for landmark enhancement.
    
    This validates landmark enhancement pipeline:
    - Search for famous landmarks
    - Extract place data (place_id, rating, address, photos)
    - Apply data to landmark blocks
    """
    
    async with aiohttp.ClientSession() as session:
        places_client = GooglePlacesClient(session)
        
        # Test landmark enhancement for Universal Studios
        landmark_block = ItineraryBlock(
            name="Universal Studios Florida",
            type="landmark",
            start_time="09:00",
            duration="8h",
            description="Famous movie-themed attractions and rides"
        )
        
        # Test landmark enhancement
        enhanced_block = await enhanced_agentic_system._enhance_single_landmark_basic(
            landmark_block, places_client
        )
        
        # Validate enhancement
        assert enhanced_block.name == landmark_block.name, "Name should be preserved"
        assert enhanced_block.type == "landmark", "Type should remain landmark"
        
        # Should have Google Places data
        assert enhanced_block.place_id is not None, "Enhanced landmark should have place_id"
        assert enhanced_block.location is not None, "Enhanced landmark should have location"
        assert enhanced_block.address is not None, "Enhanced landmark should have address"
        
        # Optional fields that might be present
        if enhanced_block.rating:
            assert isinstance(enhanced_block.rating, (int, float)), "Rating should be numeric"
            assert 0 <= enhanced_block.rating <= 5, "Rating should be between 0-5"
        
        if enhanced_block.photo_url:
            assert enhanced_block.photo_url.startswith("/photo-proxy/"), "Photo URL should use proxy format"
        
        print(f"✅ Landmark enhancement passed: {enhanced_block.name}")
        print(f"   📍 Place ID: {enhanced_block.place_id}")
        print(f"   🏠 Address: {enhanced_block.address}")
        print(f"   ⭐ Rating: {enhanced_block.rating}")
        print(f"   📸 Photo: {'Yes' if enhanced_block.photo_url else 'No'}")


@pytest.mark.asyncio
@pytest.mark.llm_cost
async def test_google_places_error_handling():
    """
    Test Google Places API error handling and recovery.
    """
    
    async with aiohttp.ClientSession() as session:
        places_client = GooglePlacesClient(session)
        
        # Test enhancement with non-existent landmark
        fake_landmark = ItineraryBlock(
            name="Totally Fake Non-Existent Landmark XYZ123",
            type="landmark",
            start_time="09:00",
            duration="2h"
        )
        
        # Should gracefully handle missing landmark
        result = await enhanced_agentic_system._enhance_single_landmark_basic(
            fake_landmark, places_client
        )
        
        # Should return original block when enhancement fails
        assert result.name == fake_landmark.name, "Should preserve original landmark on failure"
        assert result.type == "landmark", "Should preserve type"
        # place_id might be None if no match found
        
        print(f"✅ Error handling passed: Gracefully handled non-existent landmark")


@pytest.mark.asyncio
@pytest.mark.llm_cost  
async def test_complete_google_places_pipeline():
    """
    Test the complete Google Places integration pipeline end-to-end.
    
    This test validates the full integration:
    - Restaurant addition with Google Places data
    - Landmark enhancement with Google Places data
    - No duplicate restaurants across days
    - All expected data fields populated
    """
    
    async with aiohttp.ClientSession() as session:
        places_client = GooglePlacesClient(session)
        
        # Create sample trip selection
        from app.schema import LandmarkSelection, TripDetails, DayAttraction, Attraction
        
        details = TripDetails(
            destination='Orlando, FL',
            travelDays=2,
            startDate='2024-06-10',
            endDate='2024-06-11',
            withKids=True,
            kidsAge=[8, 12],
            withElders=False,
            specialRequests='Family-friendly activities'
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
            description='Interactive science exhibits',
            location=Location(lat=28.5721, lng=-81.3519)
        )

        selection = LandmarkSelection(
            details=details,
            itinerary=[
                DayAttraction(day=1, attractions=[universal_studios]),
                DayAttraction(day=2, attractions=[science_center])
            ],
            wishlist=[]
        )
        
        # Reset global used restaurants
        enhanced_agentic_system._used_restaurants_global = set()
        
        # Test complete pipeline
        result = await enhanced_agentic_system.generate_itinerary(selection, places_client)
        
        assert 'itinerary' in result, "Should return itinerary"
        days = result['itinerary']
        assert len(days) == 2, "Should generate 2 days"
        
        total_restaurants = 0
        total_enhanced_landmarks = 0
        all_place_ids = set()
        
        for day in days:
            day_restaurants = [block for block in day['blocks'] if block['type'] == 'restaurant']
            day_landmarks = [block for block in day['blocks'] if block['type'] == 'landmark']
            
            # Validate restaurant count and Google Places integration
            assert len(day_restaurants) == 3, f"Day {day['day']} should have 3 restaurants"
            
            for restaurant in day_restaurants:
                assert restaurant['place_id'] is not None, f"Restaurant {restaurant['name']} should have place_id"
                assert restaurant['address'] is not None, f"Restaurant {restaurant['name']} should have address"
                assert restaurant['mealtime'] in ['breakfast', 'lunch', 'dinner'], "Should have valid mealtime"
                
                # Check for duplicates
                place_id = restaurant['place_id']
                assert place_id not in all_place_ids, f"Duplicate restaurant place_id: {place_id}"
                all_place_ids.add(place_id)
                
                total_restaurants += 1
            
            # Validate landmark enhancement
            for landmark in day_landmarks:
                if landmark.get('place_id'):
                    total_enhanced_landmarks += 1
                    assert landmark['address'] is not None, f"Enhanced landmark {landmark['name']} should have address"
        
        # Validate overall results
        assert total_restaurants == 6, "Should have 6 total restaurants (3 per day × 2 days)"
        assert len(all_place_ids) == 6, "All restaurants should have unique place_ids"
        assert total_enhanced_landmarks >= 1, "At least some landmarks should be enhanced"
        
        print(f"✅ Complete pipeline validation passed:")
        print(f"   🍽️ Total restaurants: {total_restaurants}")
        print(f"   🔍 Enhanced landmarks: {total_enhanced_landmarks}")
        print(f"   🆔 Unique place IDs: {len(all_place_ids)}")


# ==================== MOCK FIXTURES FOR OTHER TESTS ====================

@pytest.fixture
def mock_google_places_restaurant_detailed():
    """Detailed mock Google Places restaurant response with all fields"""
    return {
        "place_id": "ChIJtest_restaurant_123",
        "name": "Test Restaurant",
        "vicinity": "123 Test Street, Orlando, FL",
        "formatted_address": "123 Test Street, Orlando, FL 32819, USA",
        "rating": 4.5,
        "geometry": {
            "location": {
                "lat": 28.5383,
                "lng": -81.3792
            }
        },
        "photos": [
            {
                "photo_reference": "test_photo_reference_123",
                "width": 400,
                "height": 400
            }
        ],
        "types": ["restaurant", "food", "establishment"],
        "price_level": 2,
        "user_ratings_total": 1234
    }


@pytest.fixture
def mock_google_places_landmark_detailed():
    """Detailed mock Google Places landmark response with all fields"""
    return {
        "place_id": "ChIJtest_landmark_123",
        "name": "Test Landmark",
        "vicinity": "456 Landmark Ave, Orlando, FL",
        "formatted_address": "456 Landmark Ave, Orlando, FL 32819, USA",
        "rating": 4.8,
        "geometry": {
            "location": {
                "lat": 28.5400,
                "lng": -81.3800
            }
        },
        "photos": [
            {
                "photo_reference": "test_landmark_photo_456",
                "width": 800,
                "height": 600
            }
        ],
        "types": ["tourist_attraction", "point_of_interest", "establishment"],
        "user_ratings_total": 5678
    }


@pytest.fixture
def mock_google_places_empty_response():
    """Mock empty Google Places response"""
    return {
        "results": [],
        "status": "ZERO_RESULTS"
    } 