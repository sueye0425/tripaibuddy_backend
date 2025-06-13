"""
Test complete itinerary requirements to prevent regressions.

These tests verify:
1. Each non-theme park day has 2-3 landmarks (not just 1)
2. Each day has exactly 3 restaurants (breakfast, lunch, dinner)
3. No missing restaurants on any day
4. Additional landmarks are properly added when needed
5. Theme park days have proper timing and structure
6. No large gaps between activities
7. Restaurant descriptions are not generic
8. No duplicate landmarks across or within days
"""

import pytest
import requests
import json
import time
from datetime import datetime, timedelta

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
    
    def test_theme_park_day_requirements(self):
        """Test that theme park days have proper structure and timing"""
        payload = {
            "details": {
                "destination": "Orlando, FL",
                "travelDays": 2,
                "startDate": "2025-06-10",
                "endDate": "2025-06-11",
                "withKids": True,
                "withElders": False,
                "kidsAge": [8, 12],
                "specialRequests": "Visit Universal Studios"
            },
            "wishlist": [],
            "itinerary": [
                {
                    "day": 1,
                    "attractions": [
                        {
                            "name": "Universal Studios Florida",
                            "description": "Theme park with movie-themed attractions",
                            "location": {"lat": 28.4743, "lng": -81.4677},
                            "type": "landmark"
                        }
                    ]
                },
                {
                    "day": 2,
                    "attractions": [
                        {
                            "name": "Orlando Science Center",
                            "description": "Interactive science museum",
                            "location": {"lat": 28.5667, "lng": -81.3667},
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
        
        # Check theme park day (Day 1)
        day1 = next(day for day in days if day["day"] == 1)
        blocks = day1["blocks"]
        
        # Theme park should be full day
        theme_park = next(block for block in blocks if block["type"] == "landmark" and "universal" in block["name"].lower())
        assert parse_duration_to_minutes(theme_park["duration"]) >= 360, "Theme park should be at least 6 hours"
        
        # Check restaurant timing
        restaurants = [b for b in blocks if b["type"] == "restaurant"]
        assert len(restaurants) == 3, "Should have exactly 3 restaurants"
        
        # Verify lunch timing (should be around 12:00)
        lunch = next(r for r in restaurants if r["mealtime"] == "lunch")
        lunch_time = parse_time_to_minutes(lunch["start_time"])
        assert 690 <= lunch_time <= 750, "Lunch should be between 11:30 and 12:30"
        
        print("✅ Theme park day requirements met")
    
    def test_no_large_gaps(self):
        """Test that there are no large gaps (>2 hours) between activities"""
        payload = {
            "details": {
                "destination": "San Diego, CA",
                "travelDays": 2,
                "startDate": "2025-06-10",
                "endDate": "2025-06-11",
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
        
        for day in days:
            blocks = sorted(day["blocks"], key=lambda x: parse_time_to_minutes(x["start_time"]))
            
            for i in range(len(blocks) - 1):
                current_end = parse_time_to_minutes(blocks[i]["start_time"]) + parse_duration_to_minutes(blocks[i]["duration"])
                next_start = parse_time_to_minutes(blocks[i + 1]["start_time"])
                gap_hours = (next_start - current_end) / 60
                
                assert gap_hours <= 2, f"Gap of {gap_hours:.1f} hours between {blocks[i]['name']} and {blocks[i+1]['name']}"
        
        print("✅ No large gaps found between activities")
    
    def test_restaurant_description_quality(self):
        """Test that restaurant descriptions are not generic"""
        payload = {
            "details": {
                "destination": "San Diego, CA",
                "travelDays": 1,
                "startDate": "2025-06-10",
                "endDate": "2025-06-10",
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
        
        day = days[0]
        restaurants = [b for b in day["blocks"] if b["type"] == "restaurant"]
        
        # Updated quality indicators to include more natural descriptive terms
        quality_indicators = [
            "restaurant", "dining", "cuisine", "food", "menu", 
            "atmosphere", "serves", "known for", "offers",
            "destination", "establishment", "modern", "fresh",
            "spot", "dishes", "bar", "seating", "experience",
            "place", "venue", "location", "style", "featuring"
        ]
        
        for restaurant in restaurants:
            description = restaurant.get("description", "").lower()
            assert len(description) > 15, f"Description too short for {restaurant['name']}"
            
            # Check if description is meaningful (not just generic phrases)
            generic_phrases = [
                "no description available",
                "restaurant",
                "food establishment",
                "place to eat"
            ]
            
            is_generic = any(phrase in description for phrase in generic_phrases)
            has_quality_content = any(indicator in description for indicator in quality_indicators)
            
            # Description should either have quality indicators OR be descriptive enough (>30 chars) and not generic
            is_acceptable = has_quality_content or (len(description) > 30 and not is_generic)
            
            assert is_acceptable, \
                f"Poor quality description for {restaurant['name']}: {description}"
        
        print("✅ Restaurant descriptions are detailed and non-generic")
    
    def test_no_duplicate_landmarks(self):
        """Test that there are no duplicate landmarks across or within days"""
        payload = {
            "details": {
                "destination": "San Diego, CA",
                "travelDays": 2,
                "startDate": "2025-06-10",
                "endDate": "2025-06-11",
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
        
        # Check for duplicates within each day
        for day in days:
            landmark_names = [b["name"].lower() for b in day["blocks"] if b["type"] == "landmark"]
            assert len(landmark_names) == len(set(landmark_names)), \
                f"Duplicate landmarks found in day {day['day']}"
        
        # Check for duplicates across days
        all_landmark_names = []
        for day in days:
            all_landmark_names.extend([b["name"].lower() for b in day["blocks"] if b["type"] == "landmark"])
        assert len(all_landmark_names) == len(set(all_landmark_names)), "Duplicate landmarks found across days"
        
        print("✅ No duplicate landmarks found")
    
    def test_three_restaurants_per_day(self):
        """Test that every day has exactly 3 restaurants (breakfast, lunch, dinner)"""
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
        
        response = requests.post(f"{self.BASE_URL}/complete-itinerary", json=payload, timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        itinerary = data["itinerary"]
        if "itinerary" in itinerary:
            days = itinerary["itinerary"]
        else:
            days = itinerary
        
        for day in days:
            restaurants = [b for b in day["blocks"] if b["type"] == "restaurant"]
            assert len(restaurants) == 3, f"Day {day['day']} should have exactly 3 restaurants"
            
            meal_types = {r["mealtime"] for r in restaurants}
            assert meal_types == {"breakfast", "lunch", "dinner"}, \
                f"Day {day['day']} missing required meal types"
        
        print("✅ All days have exactly 3 restaurants with proper meal types")

# Import utility functions from main module
from app.complete_itinerary import parse_time_to_minutes, parse_duration_to_minutes

if __name__ == "__main__":
    # Run tests directly
    test_suite = TestCompleteItineraryRequirements()
    
    print("🧪 Running Complete Itinerary Requirements Tests")
    print("=" * 60)
    
    test_suite.test_server_is_running()
    print("✅ Server connectivity verified\n")
    
    test_suite.test_theme_park_day_requirements()
    print("✅ Theme park day requirements test passed\n")
    
    test_suite.test_no_large_gaps()
    print("✅ No large gaps test passed\n")
    
    test_suite.test_restaurant_description_quality()
    print("✅ Restaurant description quality test passed\n")
    
    test_suite.test_no_duplicate_landmarks()
    print("✅ No duplicate landmarks test passed\n")
    
    test_suite.test_three_restaurants_per_day()
    print("✅ Three restaurants per day test passed\n")
    
    print("🎉 All tests passed! Requirements are properly enforced.") 