"""
Test complete itinerary requirements to prevent regressions.

These tests verify:
1. Each non-theme park day has 2-3 landmarks (not just 1)
2. Each day has exactly 3 restaurants (breakfast, lunch, dinner)
3. No missing restaurants on any day
4. Additional landmarks are properly added when needed
"""

import pytest
import requests
import json
import time

class TestCompleteItineraryRequirements:
    """Test suite to enforce complete itinerary requirements"""
    
    BASE_URL = "http://127.0.0.1:8000"
    
    def test_server_is_running(self):
        """Verify the server is running before running tests"""
        try:
            response = requests.get(f"{self.BASE_URL}/", timeout=5)
            assert response.status_code == 200
            data = response.json()
            assert "TripAIBuddy" in data["message"]
        except requests.exceptions.RequestException:
            pytest.skip("Server not running - start with: python -m uvicorn app.main:app --reload --port 8000")
    
    def test_multiple_landmarks_per_day(self):
        """Test that non-theme park days have 2-3 landmarks (not just 1)"""
        
        # Test payload with only 1 landmark per day (should be expanded to 2-3)
        payload = {
            "details": {
                "destination": "San Diego, CA",
                "travelDays": 3,
                "startDate": "2025-06-10",
                "endDate": "2025-06-12",
                "withKids": False,
                "withElders": False,
                "kidsAge": [],
                "specialRequests": ""
            },
            "wishlist": [],
            "itinerary": [
                {
                    "day": 1,
                    "attractions": [
                        {
                            "name": "Balboa Park",
                            "description": "Large cultural park",
                            "location": {"lat": 32.7341479, "lng": -117.1498161},
                            "type": "landmark"
                        }
                    ]
                },
                {
                    "day": 2,
                    "attractions": [
                        {
                            "name": "La Jolla Cove",
                            "description": "Beautiful beach area",
                            "location": {"lat": 32.8508, "lng": -117.2713},
                            "type": "landmark"
                        }
                    ]
                },
                {
                    "day": 3,
                    "attractions": [
                        {
                            "name": "Sunset Cliffs",
                            "description": "Scenic coastal park",
                            "location": {"lat": 32.7157, "lng": -117.2544},
                            "type": "landmark"
                        }
                    ]
                }
            ]
        }
        
        start_time = time.time()
        response = requests.post(f"{self.BASE_URL}/complete-itinerary", json=payload, timeout=30)
        response_time = time.time() - start_time
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        print(f"⏱️  Response time: {response_time:.2f}s")
        
        # Validate structure
        assert "itinerary" in data, "Response should contain itinerary"
        itinerary = data["itinerary"]
        
        # Handle nested structure
        if "itinerary" in itinerary:
            days = itinerary["itinerary"]
        else:
            days = itinerary
        
        assert len(days) == 3, f"Expected 3 days, got {len(days)}"
        
        # Check each day
        for day in days:
            day_num = day["day"]
            blocks = day.get("blocks", [])
            landmarks = [b for b in blocks if b.get("type") == "landmark"]
            
            print(f"🏛️  Day {day_num}: {len(landmarks)} landmarks")
            for landmark in landmarks:
                print(f"   - {landmark.get('name', 'Unknown')}")
            
            # Each non-theme park day should have 2-3 landmarks
            # (not just the 1 landmark from user input)
            assert len(landmarks) >= 2, f"Day {day_num} should have at least 2 landmarks, got {len(landmarks)}"
            assert len(landmarks) <= 3, f"Day {day_num} should have at most 3 landmarks, got {len(landmarks)}"
        
        print("✅ All days have proper landmark count (2-3 per day)")
    
    def test_three_restaurants_per_day(self):
        """Test that every day has exactly 3 restaurants (breakfast, lunch, dinner)"""
        
        # Test payload
        payload = {
            "details": {
                "destination": "San Diego, CA",
                "travelDays": 3,
                "startDate": "2025-06-10",
                "endDate": "2025-06-12",
                "withKids": False,
                "withElders": False,
                "kidsAge": [],
                "specialRequests": ""
            },
            "wishlist": [],
            "itinerary": [
                {
                    "day": 1,
                    "attractions": [
                        {
                            "name": "Balboa Park",
                            "description": "Large cultural park",
                            "location": {"lat": 32.7341479, "lng": -117.1498161},
                            "type": "landmark"
                        }
                    ]
                },
                {
                    "day": 2,
                    "attractions": [
                        {
                            "name": "La Jolla Cove",
                            "description": "Beautiful beach area",
                            "location": {"lat": 32.8508, "lng": -117.2713},
                            "type": "landmark"
                        }
                    ]
                },
                {
                    "day": 3,
                    "attractions": [
                        {
                            "name": "Animal World & Snake Farm Zoo",
                            "description": "Roadside attraction with snakes",
                            "location": {"lat": 29.6550009, "lng": -98.1459910},
                            "type": "landmark"
                        }
                    ]
                }
            ]
        }
        
        start_time = time.time()
        response = requests.post(f"{self.BASE_URL}/complete-itinerary", json=payload, timeout=30)
        response_time = time.time() - start_time
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        print(f"⏱️  Response time: {response_time:.2f}s")
        
        # Validate structure
        assert "itinerary" in data, "Response should contain itinerary"
        itinerary = data["itinerary"]
        
        # Handle nested structure
        if "itinerary" in itinerary:
            days = itinerary["itinerary"]
        else:
            days = itinerary
        
        assert len(days) == 3, f"Expected 3 days, got {len(days)}"
        
        # Check each day for restaurant requirements
        for day in days:
            day_num = day["day"]
            blocks = day.get("blocks", [])
            restaurants = [b for b in blocks if b.get("type") == "restaurant"]
            
            print(f"🍽️  Day {day_num}: {len(restaurants)} restaurants")
            
            # CRITICAL: Each day must have exactly 3 restaurants
            assert len(restaurants) == 3, f"Day {day_num} must have exactly 3 restaurants, got {len(restaurants)}"
            
            # Check meal types
            meal_types = {r.get("mealtime") for r in restaurants if r.get("mealtime")}
            expected_meals = {"breakfast", "lunch", "dinner"}
            
            print(f"   Meal types: {meal_types}")
            for restaurant in restaurants:
                name = restaurant.get('name', 'Unknown')
                mealtime = restaurant.get('mealtime', 'None')
                description = restaurant.get('description', 'No description')[:50] + "..."
                print(f"   - {name} ({mealtime}): {description}")
            
            # CRITICAL: Must have all 3 meal types
            assert meal_types == expected_meals, f"Day {day_num} missing meal types. Expected {expected_meals}, got {meal_types}"
            
            # Verify restaurants have proper data
            for restaurant in restaurants:
                assert restaurant.get("name"), f"Day {day_num} restaurant missing name"
                assert restaurant.get("mealtime") in expected_meals, f"Day {day_num} restaurant has invalid mealtime: {restaurant.get('mealtime')}"
                # Note: description might be empty if Google Places doesn't provide one, that's OK
        
        print("✅ All days have exactly 3 restaurants with proper meal types")
    
    def test_no_missing_restaurants_on_day_3(self):
        """Specific test to ensure Day 3 never has missing restaurants"""
        
        # This is the exact scenario that was failing before
        payload = {
            "details": {
                "destination": "San Antonio, TX",
                "travelDays": 3,
                "startDate": "2025-06-10",
                "endDate": "2025-06-12",
                "withKids": True,
                "withElders": False,
                "kidsAge": [8, 12],
                "specialRequests": "prefer waterfront activities"
            },
            "wishlist": [],
            "itinerary": [
                {
                    "day": 1,
                    "attractions": [
                        {
                            "name": "San Antonio Zoo",
                            "description": "Zoo featuring various animal exhibits",
                            "location": {"lat": 29.4871014, "lng": -98.4871014},
                            "type": "landmark"
                        }
                    ]
                },
                {
                    "day": 2,
                    "attractions": [
                        {
                            "name": "San Antonio Riverwalk",
                            "description": "Historic river walk",
                            "location": {"lat": 29.4241219, "lng": -98.4936282},
                            "type": "landmark"
                        }
                    ]
                },
                {
                    "day": 3,
                    "attractions": [
                        {
                            "name": "Animal World & Snake Farm Zoo",
                            "description": "Roadside attraction with snakes",
                            "location": {"lat": 29.6550009, "lng": -98.1459910},
                            "type": "landmark"
                        }
                    ]
                }
            ]
        }
        
        start_time = time.time()
        response = requests.post(f"{self.BASE_URL}/complete-itinerary", json=payload, timeout=30)
        response_time = time.time() - start_time
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        print(f"⏱️  Response time: {response_time:.2f}s")
        
        # Focus specifically on Day 3
        itinerary = data["itinerary"]
        if "itinerary" in itinerary:
            days = itinerary["itinerary"]
        else:
            days = itinerary
        
        day_3 = next((day for day in days if day["day"] == 3), None)
        assert day_3 is not None, "Day 3 not found in response"
        
        blocks = day_3.get("blocks", [])
        restaurants = [b for b in blocks if b.get("type") == "restaurant"]
        landmarks = [b for b in blocks if b.get("type") == "landmark"]
        
        print(f"🐍 Day 3 Analysis:")
        print(f"   Landmarks: {len(landmarks)}")
        for landmark in landmarks:
            print(f"   - {landmark.get('name', 'Unknown')}")
        
        print(f"   Restaurants: {len(restaurants)}")
        for restaurant in restaurants:
            name = restaurant.get('name', 'Unknown')
            mealtime = restaurant.get('mealtime', 'None')
            print(f"   - {name} ({mealtime})")
        
        # CRITICAL: Day 3 must not be missing restaurants
        assert len(restaurants) == 3, f"Day 3 is missing restaurants! Expected 3, got {len(restaurants)}"
        
        # Check meal coverage
        meal_types = {r.get("mealtime") for r in restaurants if r.get("mealtime")}
        expected_meals = {"breakfast", "lunch", "dinner"}
        assert meal_types == expected_meals, f"Day 3 missing meal types: {expected_meals - meal_types}"
        
        print("✅ Day 3 has proper restaurant coverage")
    
    def test_landmark_expansion_logic(self):
        """Test that landmark expansion works correctly for different scenarios"""
        
        # Test with kids preferences to ensure proper landmark types
        payload = {
            "details": {
                "destination": "San Diego, CA",
                "travelDays": 2,
                "startDate": "2025-06-10",
                "endDate": "2025-06-11",
                "withKids": True,
                "withElders": False,
                "kidsAge": [6, 10],
                "specialRequests": "family-friendly activities"
            },
            "wishlist": [],
            "itinerary": [
                {
                    "day": 1,
                    "attractions": [
                        {
                            "name": "San Diego Zoo",
                            "description": "Zoo with animal exhibits",
                            "location": {"lat": 32.7360353, "lng": -117.1509849},
                            "type": "landmark"
                        }
                    ]
                },
                {
                    "day": 2,
                    "attractions": [
                        {
                            "name": "Balboa Park",
                            "description": "Large cultural park",
                            "location": {"lat": 32.7341479, "lng": -117.1498161},
                            "type": "landmark"
                        }
                    ]
                }
            ]
        }
        
        response = requests.post(f"{self.BASE_URL}/complete-itinerary", json=payload, timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        itinerary = data["itinerary"]
        if "itinerary" in itinerary:
            days = itinerary["itinerary"]
        else:
            days = itinerary
        
        # Analyze landmark expansion
        for day in days:
            day_num = day["day"]
            blocks = day.get("blocks", [])
            landmarks = [b for b in blocks if b.get("type") == "landmark"]
            
            print(f"🎠 Day {day_num} landmark analysis:")
            print(f"   Total landmarks: {len(landmarks)}")
            
            # Should have original + additional landmarks
            user_landmark_found = False
            additional_landmarks_found = 0
            
            for landmark in landmarks:
                name = landmark.get('name', '')
                place_id = landmark.get('place_id')
                
                print(f"   - {name} (place_id: {place_id is not None})")
                
                # Check if this is the user's original landmark
                if day_num == 1 and "zoo" in name.lower():
                    user_landmark_found = True
                elif day_num == 2 and "balboa" in name.lower():
                    user_landmark_found = True
                else:
                    additional_landmarks_found += 1
            
            # Verify expansion worked
            assert user_landmark_found, f"Day {day_num} missing user's original landmark"
            assert additional_landmarks_found >= 1, f"Day {day_num} should have additional landmarks, got {additional_landmarks_found}"
            assert len(landmarks) >= 2, f"Day {day_num} should have at least 2 landmarks total"
        
        print("✅ Landmark expansion logic working correctly")

if __name__ == "__main__":
    # Run tests directly
    test_suite = TestCompleteItineraryRequirements()
    
    print("🧪 Running Complete Itinerary Requirements Tests")
    print("=" * 60)
    
    test_suite.test_server_is_running()
    print("✅ Server connectivity verified\n")
    
    test_suite.test_multiple_landmarks_per_day()
    print("✅ Multiple landmarks per day test passed\n")
    
    test_suite.test_three_restaurants_per_day()
    print("✅ Three restaurants per day test passed\n")
    
    test_suite.test_no_missing_restaurants_on_day_3()
    print("✅ Day 3 restaurant test passed\n")
    
    test_suite.test_landmark_expansion_logic()
    print("✅ Landmark expansion test passed\n")
    
    print("🎉 All tests passed! Requirements are properly enforced.") 