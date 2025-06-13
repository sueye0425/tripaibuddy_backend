#!/usr/bin/env python3
"""
Endpoint Completeness Tests
==========================

Tests to ensure all landmarks and restaurants have complete data including:
- Descriptions (non-empty)
- Photo URLs (non-null)
- Essential metadata (place_id, location, rating)

Tests both /generate and /complete-itinerary endpoints.
"""

import pytest
import asyncio
import json
import requests
import time

# Use requests directly since TestClient has compatibility issues
BASE_URL = "http://localhost:8000"

class TestEndpointCompleteness:
    """Test that both endpoints return complete data for all places"""
    
    def test_generate_endpoint_completeness(self):
        """Test that /generate endpoint returns complete data for all landmarks and restaurants"""
        # Test data
        request_data = {
            "destination": "San Francisco, CA",
            "travel_days": 2,
            "with_kids": False,
            "with_elderly": False,
            "special_requests": "Love art and culture"
        }
        
        # Make request
        response = requests.post(f"{BASE_URL}/generate", json=request_data)
        
        # Basic response validation
        assert response.status_code == 200
        data = response.json()
        assert "itinerary" in data
        assert len(data["itinerary"]) == 2  # 2 days
        
        # Track completeness stats
        total_landmarks = 0
        total_restaurants = 0
        landmarks_with_descriptions = 0
        landmarks_with_photos = 0
        restaurants_with_descriptions = 0
        restaurants_with_photos = 0
        
        # Check each day
        for day_plan in data["itinerary"]:
            assert "day" in day_plan
            assert "blocks" in day_plan
            
            # Check each block
            for block in day_plan["blocks"]:
                # Validate basic structure
                assert "type" in block
                assert "name" in block
                assert "description" in block
                assert block["type"] in ["landmark", "restaurant"]
                
                if block["type"] == "landmark":
                    total_landmarks += 1
                    
                    # Check landmark completeness
                    self._validate_landmark_completeness(block)
                    
                    # Count completeness
                    if block.get("description") and block["description"].strip():
                        landmarks_with_descriptions += 1
                    if block.get("photo_url"):
                        landmarks_with_photos += 1
                        
                elif block["type"] == "restaurant":
                    total_restaurants += 1
                    
                    # Check restaurant completeness
                    self._validate_restaurant_completeness(block)
                    
                    # Count completeness
                    if block.get("description") and block["description"].strip():
                        restaurants_with_descriptions += 1
                    if block.get("photo_url"):
                        restaurants_with_photos += 1
        
        # Assert completeness requirements
        assert total_landmarks > 0, "Should have at least some landmarks"
        assert total_restaurants > 0, "Should have at least some restaurants"
        
        # 100% description coverage required ONLY for landmarks
        assert landmarks_with_descriptions == total_landmarks, f"All {total_landmarks} landmarks should have descriptions, got {landmarks_with_descriptions}"
        # Note: Restaurant descriptions are optional for speed optimization
        
        # 100% photo coverage required for both landmarks and restaurants
        assert landmarks_with_photos == total_landmarks, f"All {total_landmarks} landmarks should have photos, got {landmarks_with_photos}"
        assert restaurants_with_photos == total_restaurants, f"All {total_restaurants} restaurants should have photos, got {restaurants_with_photos}"
        
        print(f"✅ /generate completeness: {total_landmarks} landmarks ({landmarks_with_descriptions} descriptions, {landmarks_with_photos} photos), {total_restaurants} restaurants ({restaurants_with_descriptions} descriptions, {restaurants_with_photos} photos)")
    
    def test_complete_itinerary_endpoint_completeness(self):
        """Test that /complete-itinerary endpoint returns complete data for all landmarks and restaurants"""
        # Test data
        request_data = {
            "details": {
                "destination": "San Francisco, CA",
                "travelDays": 2,
                "startDate": "2024-12-01",
                "endDate": "2024-12-02",
                "withKids": False,
                "withElders": False,
                "specialRequests": "Love art and culture"
            },
            "wishlist": [],
            "itinerary": [
                {
                    "day": 1,
                    "attractions": [
                        {
                            "name": "Golden Gate Bridge",
                            "description": "Iconic suspension bridge",
                            "location": {"lat": 37.8199, "lng": -122.4783},
                            "type": "landmark"
                        }
                    ]
                },
                {
                    "day": 2,
                    "attractions": [
                        {
                            "name": "Alcatraz Island",
                            "description": "Historic prison island",
                            "location": {"lat": 37.8267, "lng": -122.4233},
                            "type": "landmark"
                        }
                    ]
                }
            ]
        }
        
        # Make request
        response = requests.post(f"{BASE_URL}/complete-itinerary", json=request_data)
        
        # Basic response validation
        assert response.status_code == 200
        data = response.json()
        assert "itinerary" in data
        assert len(data["itinerary"]) == 2  # 2 days
        
        # Track completeness stats
        total_landmarks = 0
        total_restaurants = 0
        landmarks_with_descriptions = 0
        landmarks_with_photos = 0
        restaurants_with_descriptions = 0
        restaurants_with_photos = 0
        
        # Check each day
        for day_plan in data["itinerary"]:
            assert "day" in day_plan
            assert "blocks" in day_plan
            
            # Check each block
            for block in day_plan["blocks"]:
                # Validate basic structure
                assert "type" in block
                assert "name" in block
                assert "description" in block
                assert block["type"] in ["landmark", "restaurant"]
                
                if block["type"] == "landmark":
                    total_landmarks += 1
                    
                    # Check landmark completeness
                    self._validate_landmark_completeness(block)
                    
                    # Count completeness
                    if block.get("description") and block["description"].strip():
                        landmarks_with_descriptions += 1
                    if block.get("photo_url"):
                        landmarks_with_photos += 1
                        
                elif block["type"] == "restaurant":
                    total_restaurants += 1
                    
                    # Check restaurant completeness
                    self._validate_restaurant_completeness(block)
                    
                    # Count completeness
                    if block.get("description") and block["description"].strip():
                        restaurants_with_descriptions += 1
                    if block.get("photo_url"):
                        restaurants_with_photos += 1
        
        # Assert completeness requirements
        assert total_landmarks > 0, "Should have at least some landmarks"
        assert total_restaurants > 0, "Should have at least some restaurants"
        
        # 100% description coverage required ONLY for landmarks
        assert landmarks_with_descriptions == total_landmarks, f"All {total_landmarks} landmarks should have descriptions, got {landmarks_with_descriptions}"
        # Note: Restaurant descriptions are optional for speed optimization
        
        # 100% photo coverage required for both landmarks and restaurants
        assert landmarks_with_photos == total_landmarks, f"All {total_landmarks} landmarks should have photos, got {landmarks_with_photos}"
        assert restaurants_with_photos == total_restaurants, f"All {total_restaurants} restaurants should have photos, got {restaurants_with_photos}"
        
        print(f"✅ /complete-itinerary completeness: {total_landmarks} landmarks ({landmarks_with_descriptions} descriptions, {landmarks_with_photos} photos), {total_restaurants} restaurants ({restaurants_with_descriptions} descriptions, {restaurants_with_photos} photos)")
    
    def _validate_landmark_completeness(self, landmark_block):
        """Validate that a landmark block has complete data"""
        # Required fields
        assert landmark_block.get("name"), "Landmark must have name"
        assert landmark_block.get("description"), "Landmark must have description"
        assert landmark_block.get("start_time"), "Landmark must have start_time"
        assert landmark_block.get("duration"), "Landmark must have duration"
        
        # Description quality check
        description = landmark_block.get("description", "")
        assert len(description.strip()) >= 20, f"Landmark description too short: '{description}'"
        assert description != "Landmark", "Description should not be generic"
        
        # Optional but important fields
        if landmark_block.get("place_id"):
            assert isinstance(landmark_block["place_id"], str), "place_id should be string"
            assert len(landmark_block["place_id"]) > 10, "place_id should be meaningful"
        
        if landmark_block.get("location"):
            loc = landmark_block["location"]
            assert "lat" in loc and "lng" in loc, "Location should have lat/lng"
            assert isinstance(loc["lat"], (int, float)), "Latitude should be numeric"
            assert isinstance(loc["lng"], (int, float)), "Longitude should be numeric"
            assert -90 <= loc["lat"] <= 90, "Latitude should be valid"
            assert -180 <= loc["lng"] <= 180, "Longitude should be valid"
        
        if landmark_block.get("rating"):
            rating = landmark_block["rating"]
            assert isinstance(rating, (int, float)), "Rating should be numeric"
            assert 1.0 <= rating <= 5.0, f"Rating should be 1-5, got {rating}"
        
        if landmark_block.get("photo_url"):
            photo_url = landmark_block["photo_url"]
            assert isinstance(photo_url, str), "Photo URL should be string"
            # Accept both old and new photo proxy formats
            assert (photo_url.startswith("/photo-proxy/") or photo_url.startswith("/api/v1/image_proxy")), f"Photo URL should be proxy URL: {photo_url}"
    
    def _validate_restaurant_completeness(self, restaurant_block):
        """Validate that a restaurant block has complete data"""
        # Required fields
        assert restaurant_block.get("name"), "Restaurant must have name"
        assert restaurant_block.get("description"), "Restaurant must have description"
        assert restaurant_block.get("start_time"), "Restaurant must have start_time"
        assert restaurant_block.get("duration"), "Restaurant must have duration"
        assert restaurant_block.get("mealtime"), "Restaurant must have mealtime"
        
        # Mealtime validation
        mealtime = restaurant_block.get("mealtime")
        assert mealtime in ["breakfast", "lunch", "dinner"], f"Invalid mealtime: {mealtime}"
        
        # Description quality check
        description = restaurant_block.get("description", "")
        assert len(description.strip()) >= 15, f"Restaurant description too short: '{description}'"
        assert description != "Restaurant", "Description should not be generic"
        
        # Optional but important fields
        if restaurant_block.get("place_id"):
            assert isinstance(restaurant_block["place_id"], str), "place_id should be string"
            assert len(restaurant_block["place_id"]) > 10, "place_id should be meaningful"
        
        if restaurant_block.get("location"):
            loc = restaurant_block["location"]
            assert "lat" in loc and "lng" in loc, "Location should have lat/lng"
            assert isinstance(loc["lat"], (int, float)), "Latitude should be numeric"
            assert isinstance(loc["lng"], (int, float)), "Longitude should be numeric"
            assert -90 <= loc["lat"] <= 90, "Latitude should be valid"
            assert -180 <= loc["lng"] <= 180, "Longitude should be valid"
        
        if restaurant_block.get("rating"):
            rating = restaurant_block["rating"]
            assert isinstance(rating, (int, float)), "Rating should be numeric"
            assert 1.0 <= rating <= 5.0, f"Rating should be 1-5, got {rating}"
        
        if restaurant_block.get("photo_url"):
            photo_url = restaurant_block["photo_url"]
            assert isinstance(photo_url, str), "Photo URL should be string"
            # Accept both old and new photo proxy formats
            assert (photo_url.startswith("/photo-proxy/") or photo_url.startswith("/api/v1/image_proxy")), f"Photo URL should be proxy URL: {photo_url}"

class TestEndpointPerformance:
    """Test that both endpoints maintain good performance"""
    
    def test_generate_endpoint_performance(self):
        """Test that /generate endpoint responds within acceptable time"""
        request_data = {
            "destination": "San Francisco, CA",
            "travel_days": 2,
            "with_kids": False,
            "with_elderly": False
        }
        
        start_time = time.time()
        response = requests.post(f"{BASE_URL}/generate", json=request_data)
        end_time = time.time()
        
        response_time = end_time - start_time
        
        assert response.status_code == 200
        assert response_time < 3.0, f"Generate endpoint too slow: {response_time:.2f}s (should be < 3s)"
        
        print(f"✅ /generate performance: {response_time:.2f}s")
    
    def test_complete_itinerary_endpoint_performance(self):
        """Test that /complete-itinerary endpoint responds within acceptable time"""
        request_data = {
            "details": {
                "destination": "San Francisco, CA",
                "travelDays": 2,
                "startDate": "2024-12-01",
                "endDate": "2024-12-02",
                "withKids": False,
                "withElders": False
            },
            "wishlist": [],
            "itinerary": [
                {
                    "day": 1,
                    "attractions": [
                        {
                            "name": "Golden Gate Bridge",
                            "description": "Iconic bridge",
                            "location": {"lat": 37.8199, "lng": -122.4783},
                            "type": "landmark"
                        }
                    ]
                }
            ]
        }
        
        start_time = time.time()
        response = requests.post(f"{BASE_URL}/complete-itinerary", json=request_data)
        end_time = time.time()
        
        response_time = end_time - start_time
        
        assert response.status_code == 200
        assert response_time < 40.0, f"Complete-itinerary endpoint too slow: {response_time:.2f}s (should be < 40s)"
        
        print(f"✅ /complete-itinerary performance: {response_time:.2f}s")

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"]) 