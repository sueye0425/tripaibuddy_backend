"""
LLM and Agentic System Integration Tests

This test suite specifically validates:
1. That /complete-itinerary uses LLM calls for landmark generation
2. That the agentic system is properly engaged 
3. That LLM-generated landmarks are enhanced with Google Places data
4. That unified landmark generation prevents duplicates
5. That theme park detection uses proper logic
"""

import pytest
import requests
import json
import time
from typing import Dict, Any, List
import asyncio
from unittest.mock import patch, MagicMock
import os
import sys

# Add the app directory to Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestLLMAgenticIntegration:
    """Test suite to verify LLM and agentic system integration"""
    
    BASE_URL = "http://127.0.0.1:8000"
    
    def test_server_connectivity(self):
        """Verify server is running before testing"""
        try:
            response = requests.get(f"{self.BASE_URL}/", timeout=5)
            assert response.status_code == 200
            data = response.json()
            assert "TripAIBuddy" in data["message"]
        except requests.exceptions.RequestException:
            pytest.skip("Server not running - start with: python -m uvicorn app.main:app --reload --port 8000")
    
    def test_agentic_system_engagement(self):
        """Test that the agentic system is properly engaged and not just Google API calls"""
        
        payload = {
            "details": {
                "destination": "Portland, OR",
                "travelDays": 3,
                "startDate": "2025-06-10",
                "endDate": "2025-06-12",
                "withKids": False,
                "withElders": False,
                "kidsAge": [],
                "specialRequests": "unique local experiences"
            },
            "wishlist": [],
            "itinerary": [
                {
                    "day": 1,
                    "attractions": [
                        {
                            "name": "Powell's City of Books",
                            "description": "Famous independent bookstore",
                            "location": {"lat": 45.5230, "lng": -122.6814},
                            "type": "landmark"
                        }
                    ]
                },
                {
                    "day": 2,
                    "attractions": [
                        {
                            "name": "Washington Park",
                            "description": "Large urban park",
                            "location": {"lat": 45.5105, "lng": -122.7062},
                            "type": "landmark"
                        }
                    ]
                },
                {
                    "day": 3,
                    "attractions": [
                        {
                            "name": "Oregon Museum of Science and Industry",
                            "description": "Interactive science museum",
                            "location": {"lat": 45.5084, "lng": -122.6648},
                            "type": "landmark"
                        }
                    ]
                }
            ]
        }
        
        start_time = time.time()
        response = requests.post(f"{self.BASE_URL}/complete-itinerary", json=payload, timeout=20)
        response_time = time.time() - start_time
        
        assert response.status_code == 200, f"Request failed: {response.text}"
        data = response.json()
        
        print(f"🤖 Agentic system response time: {response_time:.2f}s")
        
        # Analyze the response for signs of agentic processing
        total_landmarks_found = 0
        total_supplementary_landmarks = 0
        total_enhanced_landmarks = 0
        
        for day in data["itinerary"]:
            day_num = day["day"]
            landmarks = [b for b in day["blocks"] if b.get("type") == "landmark"]
            total_landmarks_found += len(landmarks)
            
            print(f"📅 Day {day_num}: {len(landmarks)} landmarks")
            
            # Check if landmarks were expanded beyond user input (sign of agentic processing) 
            if len(landmarks) > 1:
                total_supplementary_landmarks += len(landmarks) - 1
                print(f"   🔄 {len(landmarks) - 1} supplementary landmarks added")
            
            # Check for Google Places enhancement (place_id, rating, address)
            for landmark in landmarks:
                name = landmark.get("name", "")
                has_place_id = landmark.get("place_id") is not None
                has_rating = landmark.get("rating") is not None
                has_address = landmark.get("address") is not None
                
                if has_place_id or has_rating or has_address:
                    total_enhanced_landmarks += 1
                
                print(f"   🏛️  {name[:30]}... (place_id: {has_place_id}, rating: {has_rating}, address: {has_address})")
        
        print(f"\n📊 Agentic System Analysis:")
        print(f"   Total landmarks: {total_landmarks_found}")
        print(f"   Supplementary landmarks: {total_supplementary_landmarks}")
        print(f"   Enhanced landmarks: {total_enhanced_landmarks}")
        
        # Validate agentic system behavior
        assert total_landmarks_found >= 6, f"Should have at least 6 landmarks (2 per day), got {total_landmarks_found}"
        assert total_supplementary_landmarks >= 3, f"Should have supplementary landmarks from agentic expansion, got {total_supplementary_landmarks}"
        
        # Enhanced landmarks indicate Google Places integration
        enhancement_rate = total_enhanced_landmarks / total_landmarks_found if total_landmarks_found > 0 else 0
        print(f"   Enhancement rate: {enhancement_rate:.1%}")
        
        assert enhancement_rate >= 0.5, f"At least 50% of landmarks should be enhanced with Google Places data, got {enhancement_rate:.1%}"
        
        print("✅ Agentic system properly engaged with landmark expansion and enhancement")
    
    def test_llm_landmark_generation_vs_google_only(self):
        """Test that landmarks are LLM-generated, not just Google Places API results"""
        
        payload = {
            "details": {
                "destination": "Austin, TX",
                "travelDays": 2,
                "startDate": "2025-06-10",
                "endDate": "2025-06-11",
                "withKids": False,
                "withElders": False,
                "kidsAge": [],
                "specialRequests": "live music and local culture"
            },
            "wishlist": [],
            "itinerary": [
                {
                    "day": 1,
                    "attractions": [
                        {
                            "name": "South by Southwest (SXSW) Interactive",
                            "description": "Annual music festival",
                            "location": {"lat": 30.2672, "lng": -97.7431},
                            "type": "landmark"
                        }
                    ]
                },
                {
                    "day": 2,
                    "attractions": [
                        {
                            "name": "Lady Bird Lake",
                            "description": "Lake in downtown Austin",
                            "location": {"lat": 30.2500, "lng": -97.7500},
                            "type": "landmark"
                        }
                    ]
                }
            ]
        }
        
        response = requests.post(f"{self.BASE_URL}/complete-itinerary", json=payload, timeout=20)
        assert response.status_code == 200
        data = response.json()
        
        print("🧠 Analyzing LLM vs Google Places behavior...")
        
        # Look for signs of intelligent landmark selection
        all_landmark_names = []
        all_landmark_descriptions = []
        
        for day in data["itinerary"]:
            landmarks = [b for b in day["blocks"] if b.get("type") == "landmark"]
            
            for landmark in landmarks:
                name = landmark.get("name", "")
                description = landmark.get("description", "")
                
                all_landmark_names.append(name)
                all_landmark_descriptions.append(description)
                
                print(f"🏛️  {name}")
                print(f"    Description: {description[:80]}...")
        
        # Check for variety and intelligence in landmark selection
        unique_landmark_count = len(set(all_landmark_names))
        total_landmarks = len(all_landmark_names)
        
        print(f"📊 Landmark Analysis:")
        print(f"   Total landmarks: {total_landmarks}")
        print(f"   Unique landmarks: {unique_landmark_count}")
        print(f"   Duplicate rate: {(total_landmarks - unique_landmark_count) / total_landmarks:.1%}")
        
        # LLM-generated landmarks should have no duplicates
        assert unique_landmark_count == total_landmarks, f"LLM should generate unique landmarks, found {total_landmarks - unique_landmark_count} duplicates"
        
        # Check for contextual descriptions (sign of LLM processing)
        descriptive_landmarks = sum(1 for desc in all_landmark_descriptions if len(desc) > 20)
        description_rate = descriptive_landmarks / total_landmarks if total_landmarks > 0 else 0
        
        print(f"   Descriptive landmarks: {descriptive_landmarks}/{total_landmarks} ({description_rate:.1%})")
        
        assert description_rate >= 0.8, f"At least 80% of landmarks should have descriptive text from LLM, got {description_rate:.1%}"
        
        print("✅ LLM landmark generation verified (unique, descriptive, contextual)")
    
    def test_theme_park_logic_precision(self):
        """Test that theme park detection is precise and accurate"""
        
        # Test cases: theme parks vs. similar venues
        test_cases = [
            {
                "name": "Universal Studios Florida",
                "expected_theme_park": True,
                "expected_landmarks": 1
            },
            {
                "name": "Orlando Science Center", 
                "expected_theme_park": False,
                "expected_landmarks": 2  # Should be expanded
            },
            {
                "name": "Disney World Magic Kingdom",
                "expected_theme_park": True,
                "expected_landmarks": 1
            },
            {
                "name": "National Air and Space Museum",
                "expected_theme_park": False,
                "expected_landmarks": 2  # Should be expanded
            }
        ]
        
        for test_case in test_cases:
            attraction_name = test_case["name"]
            expected_theme_park = test_case["expected_theme_park"]
            expected_landmarks = test_case["expected_landmarks"]
            
            payload = {
                "details": {
                    "destination": "Orlando, FL",
                    "travelDays": 1,
                    "startDate": "2025-06-10",
                    "endDate": "2025-06-10",
                    "withKids": True,
                    "withElders": False,
                    "kidsAge": [8, 12],
                    "specialRequests": f"Visit {attraction_name}"
                },
                "wishlist": [],
                "itinerary": [
                    {
                        "day": 1,
                        "attractions": [
                            {
                                "name": attraction_name,
                                "description": f"Visit {attraction_name}",
                                "location": {"lat": 28.4743, "lng": -81.4677},
                                "type": "landmark"
                            }
                        ]
                    }
                ]
            }
            
            response = requests.post(f"{self.BASE_URL}/complete-itinerary", json=payload, timeout=15)
            assert response.status_code == 200
            data = response.json()
            
            day_1 = data["itinerary"][0]
            landmarks = [b for b in day_1["blocks"] if b.get("type") == "landmark"]
            
            print(f"🎢 Testing: {attraction_name}")
            print(f"   Expected theme park: {expected_theme_park}")
            print(f"   Expected landmarks: {expected_landmarks}")
            print(f"   Actual landmarks: {len(landmarks)}")
            
            if expected_theme_park:
                # Theme park should have exactly 1 landmark
                assert len(landmarks) == 1, f"Theme park {attraction_name} should have 1 landmark, got {len(landmarks)}"
                
                # Should have lunch at appropriate time (around 12:30 PM)
                restaurants = [b for b in day_1["blocks"] if b.get("type") == "restaurant"]
                lunch_restaurants = [r for r in restaurants if r.get("mealtime") == "lunch"]
                
                if lunch_restaurants:
                    lunch_time = lunch_restaurants[0].get("start_time", "")
                    print(f"   Theme park lunch time: {lunch_time}")
                    # Theme park lunch should be around midday
                    assert "12:" in lunch_time or "1:" in lunch_time, f"Theme park lunch should be around 12-1 PM, got {lunch_time}"
            else:
                # Non-theme park should have multiple landmarks
                assert len(landmarks) >= 2, f"Non-theme park {attraction_name} should have multiple landmarks, got {len(landmarks)}"
            
            print(f"   ✅ {attraction_name} handled correctly")
        
        print("✅ Theme park detection logic is precise and accurate")
    
    def test_restaurant_agentic_enhancement(self):
        """Test that restaurants are properly enhanced with Google Places data"""
        
        payload = {
            "details": {
                "destination": "Seattle, WA",
                "travelDays": 2,
                "startDate": "2025-06-10",
                "endDate": "2025-06-11",
                "withKids": False,
                "withElders": False,
                "kidsAge": [],
                "specialRequests": "Great seafood restaurants"
            },
            "wishlist": [],
            "itinerary": [
                {
                    "day": 1,
                    "attractions": [
                        {
                            "name": "Pike Place Market",
                            "description": "Historic public market",
                            "location": {"lat": 47.6097, "lng": -122.3421},
                            "type": "landmark"
                        }
                    ]
                },
                {
                    "day": 2,
                    "attractions": [
                        {
                            "name": "Space Needle",
                            "description": "Iconic observation tower",
                            "location": {"lat": 47.6205, "lng": -122.3493},
                            "type": "landmark"
                        }
                    ]
                }
            ]
        }
        
        response = requests.post(f"{self.BASE_URL}/complete-itinerary", json=payload, timeout=20)
        assert response.status_code == 200
        data = response.json()
        
        print("🍽️  Analyzing restaurant enhancement...")
        
        total_restaurants = 0
        enhanced_restaurants = 0
        restaurants_with_website = 0
        restaurants_with_rating = 0
        restaurants_with_address = 0
        
        for day in data["itinerary"]:
            restaurants = [b for b in day["blocks"] if b.get("type") == "restaurant"]
            total_restaurants += len(restaurants)
            
            print(f"📅 Day {day['day']}: {len(restaurants)} restaurants")
            
            for restaurant in restaurants:
                name = restaurant.get("name", "")
                mealtime = restaurant.get("mealtime", "")
                place_id = restaurant.get("place_id")
                rating = restaurant.get("rating")
                address = restaurant.get("address")
                website = restaurant.get("website")
                
                if place_id or rating or address or website:
                    enhanced_restaurants += 1
                
                if website:
                    restaurants_with_website += 1
                if rating:
                    restaurants_with_rating += 1
                if address:
                    restaurants_with_address += 1
                
                print(f"   🍽️  {name} ({mealtime})")
                print(f"       place_id: {'✅' if place_id else '❌'}")
                print(f"       rating: {'✅' if rating else '❌'}")
                print(f"       address: {'✅' if address else '❌'}")
                print(f"       website: {'✅' if website else '❌'}")
        
        print(f"\n📊 Restaurant Enhancement Analysis:")
        print(f"   Total restaurants: {total_restaurants}")
        print(f"   Enhanced restaurants: {enhanced_restaurants}")
        print(f"   With website: {restaurants_with_website}")
        print(f"   With rating: {restaurants_with_rating}")
        print(f"   With address: {restaurants_with_address}")
        
        enhancement_rate = enhanced_restaurants / total_restaurants if total_restaurants > 0 else 0
        website_rate = restaurants_with_website / total_restaurants if total_restaurants > 0 else 0
        
        print(f"   Enhancement rate: {enhancement_rate:.1%}")
        print(f"   Website rate: {website_rate:.1%}")
        
        # Validate agentic restaurant enhancement
        assert total_restaurants >= 6, f"Should have at least 6 restaurants (3 per day), got {total_restaurants}"
        assert enhancement_rate >= 0.7, f"At least 70% of restaurants should be enhanced, got {enhancement_rate:.1%}"
        
        # Website field should be present for frontend clickable cards
        for day in data["itinerary"]:
            restaurants = [b for b in day["blocks"] if b.get("type") == "restaurant"]
            for restaurant in restaurants:
                assert "website" in restaurant, f"Restaurant missing website field: {restaurant.get('name')}"
        
        print("✅ Restaurant agentic enhancement verified")
    
    def test_duplicate_prevention_across_days(self):
        """Test that the unified landmark generation prevents duplicates across days"""
        
        payload = {
            "details": {
                "destination": "Miami, FL",
                "travelDays": 3,
                "startDate": "2025-06-10",
                "endDate": "2025-06-12",
                "withKids": False,
                "withElders": False,
                "kidsAge": [],
                "specialRequests": "beach and art scene"
            },
            "wishlist": [],
            "itinerary": [
                {
                    "day": 1,
                    "attractions": [
                        {
                            "name": "South Beach",
                            "description": "Famous beach area",
                            "location": {"lat": 25.7907, "lng": -80.1300},
                            "type": "landmark"
                        }
                    ]
                },
                {
                    "day": 2,
                    "attractions": [
                        {
                            "name": "Art Deco Historic District",
                            "description": "Historic art deco architecture",
                            "location": {"lat": 25.7813, "lng": -80.1319},
                            "type": "landmark"
                        }
                    ]
                },
                {
                    "day": 3,
                    "attractions": [
                        {
                            "name": "Wynwood Walls",
                            "description": "Outdoor street art museum",
                            "location": {"lat": 25.8010, "lng": -80.1994},
                            "type": "landmark"
                        }
                    ]
                }
            ]
        }
        
        response = requests.post(f"{self.BASE_URL}/complete-itinerary", json=payload, timeout=20)
        assert response.status_code == 200
        data = response.json()
        
        print("🔄 Testing duplicate prevention across days...")
        
        # Collect all landmark names across all days
        all_landmark_names = []
        day_landmark_counts = {}
        
        for day in data["itinerary"]:
            day_num = day["day"]
            landmarks = [b for b in day["blocks"] if b.get("type") == "landmark"]
            day_landmark_counts[day_num] = len(landmarks)
            
            print(f"📅 Day {day_num}: {len(landmarks)} landmarks")
            
            for landmark in landmarks:
                name = landmark.get("name", "").strip().lower()
                all_landmark_names.append(name)
                print(f"   🏛️  {landmark.get('name', '')}")
        
        # Check for duplicates
        unique_landmarks = set(all_landmark_names)
        total_landmarks = len(all_landmark_names)
        duplicate_count = total_landmarks - len(unique_landmarks)
        
        print(f"\n📊 Duplicate Analysis:")
        print(f"   Total landmarks: {total_landmarks}")
        print(f"   Unique landmarks: {len(unique_landmarks)}")
        print(f"   Duplicates found: {duplicate_count}")
        
        if duplicate_count > 0:
            # Find and report duplicates
            landmark_counts = {}
            for name in all_landmark_names:
                landmark_counts[name] = landmark_counts.get(name, 0) + 1
            
            duplicates = {name: count for name, count in landmark_counts.items() if count > 1}
            print(f"   Duplicate landmarks: {duplicates}")
        
        # Validate no duplicates (unified generation should prevent this)
        assert duplicate_count == 0, f"Found {duplicate_count} duplicate landmarks - unified generation should prevent duplicates"
        
        # Validate proper expansion
        for day_num, landmark_count in day_landmark_counts.items():
            assert landmark_count >= 2, f"Day {day_num} should have at least 2 landmarks, got {landmark_count}"
        
        print("✅ No duplicates found - unified landmark generation working correctly")


if __name__ == "__main__":
    # Run all LLM and agentic integration tests
    test_suite = TestLLMAgenticIntegration()
    
    print("🧪 Running LLM and Agentic System Integration Tests")
    print("=" * 60)
    
    test_suite.test_server_connectivity()
    print("✅ Server connectivity verified\n")
    
    test_suite.test_agentic_system_engagement()
    print("✅ Agentic system engagement verified\n")
    
    test_suite.test_llm_landmark_generation_vs_google_only()
    print("✅ LLM landmark generation verified\n")
    
    test_suite.test_theme_park_logic_precision()
    print("✅ Theme park logic precision verified\n")
    
    test_suite.test_restaurant_agentic_enhancement()
    print("✅ Restaurant agentic enhancement verified\n")
    
    test_suite.test_duplicate_prevention_across_days()
    print("✅ Duplicate prevention verified\n")
    
    print("🎉 All LLM and agentic integration tests passed!") 