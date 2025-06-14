"""
Pytest configuration and shared fixtures for agentic itinerary testing.

This file contains:
- Mock LLM responses for rule-based testing
- Test fixtures for common test data
- Environment setup for tests
"""

import pytest
import json
import os
from unittest.mock import AsyncMock, MagicMock
from typing import Dict, Any

# Test environment setup
@pytest.fixture(autouse=True)
def setup_test_environment():
    """Automatically set up test environment for all tests"""
    os.environ["ENABLE_AGENTIC_SYSTEM"] = "true"
    
    # Only set test keys if real keys aren't already available
    if not os.environ.get("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = "test-key"
    if not os.environ.get("GOOGLE_PLACES_API_KEY"):
        os.environ["GOOGLE_PLACES_API_KEY"] = "test-key"

# Mock LLM responses
@pytest.fixture
def mock_landmarks_response():
    """Mock LLM response for unified landmark generation - realistic Orlando trip with proper time distribution to avoid gaps"""
    return {
        "itinerary": [
            {
                "day": 1,
                "blocks": [
                    {
                        "name": "Universal Studios Florida",
                        "type": "landmark",
                        "description": "Famous movie-themed attractions and rides",
                        "start_time": "09:00",
                        "duration": "8h",
                        "location": {"lat": 28.4743, "lng": -81.4677}
                    }
                ]
            },
            {
                "day": 2,
                "blocks": [
                    {
                        "name": "Orlando Science Center",
                        "type": "landmark",
                        "description": "Interactive science exhibits and planetarium",
                        "start_time": "09:00",
                        "duration": "2h",
                        "location": {"lat": 28.5721, "lng": -81.3519}
                    },
                    {
                        "name": "Harry P. Leu Gardens",
                        "type": "landmark", 
                        "description": "Beautiful botanical gardens",
                        "start_time": "13:00",
                        "duration": "2h",
                        "location": {"lat": 28.5721, "lng": -81.3519}
                    },
                    {
                        "name": "Orlando Museum of Art",
                        "type": "landmark",
                        "description": "Contemporary and classical art collections",
                        "start_time": "16:00",
                        "duration": "1.5h",
                        "location": {"lat": 28.5427, "lng": -81.3709}
                    }
                ]
            },
            {
                "day": 3,
                "blocks": [
                    {
                        "name": "Lake Eola Park",
                        "type": "landmark",
                        "description": "Beautiful downtown lake with swan boats",
                        "start_time": "09:00",
                        "duration": "2h",
                        "location": {"lat": 28.5427, "lng": -81.3709}
                    },
                    {
                        "name": "Central Florida Zoo",
                        "type": "landmark",
                        "description": "Wildlife park with diverse animal exhibits",
                        "start_time": "13:00",
                        "duration": "2h",
                        "location": {"lat": 28.7519, "lng": -81.5158}
                    }
                ]
            }
        ]
    }

@pytest.fixture
def mock_landmarks_response_with_duplicates():
    """Mock LLM response that contains duplicate landmarks across days"""
    return {
        "itinerary": [
            {
                "day": 1,
                "blocks": [
                    {
                        "name": "Universal Studios Florida",
                        "type": "landmark",
                        "description": "Famous movie-themed attractions",
                        "start_time": "09:00",
                        "duration": "8h",
                        "location": {"lat": 28.4743, "lng": -81.4677}
                    }
                ]
            },
            {
                "day": 2,
                "blocks": [
                    {
                        "name": "Universal Studios Florida",  # DUPLICATE!
                        "type": "landmark",
                        "description": "Same attraction repeated",
                        "start_time": "09:00",
                        "duration": "3h",
                        "location": {"lat": 28.4743, "lng": -81.4677}
                    }
                ]
            },
            {
                "day": 3,
                "blocks": [
                    {
                        "name": "Orlando Science Center",
                        "type": "landmark",
                        "description": "Interactive science exhibits",
                        "start_time": "09:00",
                        "duration": "2h",
                        "location": {"lat": 28.5721, "lng": -81.3519}
                    }
                ]
            }
        ]
    }

@pytest.fixture
def mock_google_places_restaurant():
    """Mock Google Places restaurant response"""
    return {
        "place_id": "ChIJw5IA5-5654gRn9TvG8q8TNE",
        "name": "IHOP",
        "vicinity": "7700 W Sand Lake Rd, Orlando",
        "rating": 4.1,
        "geometry": {
            "location": {
                "lat": 28.4561,
                "lng": -81.4659
            }
        },
        "types": ["restaurant", "food", "establishment"]
    }


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
def mock_multiple_restaurants():
    """Multiple different restaurants for testing"""
    restaurants = []
    for i in range(15):
        restaurants.append({
            "place_id": f"ChIJtest_restaurant_{i}",
            "name": f"Test Restaurant {i}",
            "vicinity": f"{i} Test Street, Orlando, FL",
            "formatted_address": f"{i} Test Street, Orlando, FL 32819, USA",
            "rating": 4.0 + (i % 5) / 10,
            "geometry": {
                "location": {
                    "lat": 28.5383 + i * 0.001,
                    "lng": -81.3792 + i * 0.001
                }
            },
            "photos": [
                {
                    "photo_reference": f"test_photo_reference_{i}",
                    "width": 400,
                    "height": 400
                }
            ],
            "types": ["restaurant", "food", "establishment"],
            "price_level": 2,
            "user_ratings_total": 1234 + i
        })
    return restaurants

@pytest.fixture
def sample_trip_selection():
    """Sample trip selection for testing"""
    from app.schema import LandmarkSelection, TripDetails, DayAttraction, Attraction, Location
    
    details = TripDetails(
        destination='Orlando, FL',
        travelDays=3,
        startDate='2024-06-10',
        endDate='2024-06-12',
        withKids=True,
        kidsAge=[8, 12],
        withElders=False,
        specialRequests='Include Universal Studios theme park and family-friendly activities'
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

    return LandmarkSelection(
        details=details,
        itinerary=[
            DayAttraction(day=1, attractions=[universal_studios]),
            DayAttraction(day=2, attractions=[science_center]),
            DayAttraction(day=3, attractions=[eola_park])
        ],
        wishlist=[]
    )

@pytest.fixture
def mock_llm():
    """Mock LLM for testing"""
    mock = AsyncMock()
    mock.ainvoke = AsyncMock()
    return mock

@pytest.fixture
def mock_places_client():
    """Mock Google Places client for testing"""
    mock = AsyncMock()
    mock.places_nearby = AsyncMock()
    mock.get_place_details = AsyncMock()
    mock.place_details = AsyncMock()
    mock.geocode = AsyncMock()
    mock.text_search = AsyncMock()
    return mock

@pytest.fixture
def expected_itinerary_structure():
    """Expected structure of a complete itinerary"""
    return {
        "days_count": 3,
        "blocks_per_day": 4,  # 1 landmark + 3 restaurants
        "required_meal_types": {"breakfast", "lunch", "dinner"},
        "landmark_types": {"landmark"},
        "restaurant_types": {"restaurant"}
    } 