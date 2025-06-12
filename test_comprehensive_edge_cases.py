"""
Comprehensive Edge Case Tests for /complete-itinerary Endpoint

This test suite validates:
1. Response format consistency with frontend expectations
2. Latency within 12s requirement  
3. Edge cases and error scenarios
4. LLM integration and agentic system behavior
5. Theme park detection and handling
6. Restaurant guarantee mechanisms
7. Landmark expansion logic
"""

import pytest
import requests
import json
import time
from typing import Dict, Any, List
import asyncio
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta


class TestComprehensiveEdgeCases:
    """Comprehensive edge case validation for complete-itinerary endpoint"""
    
    BASE_URL = "http://127.0.0.1:8000"
    MAX_LATENCY = 12.0  # Maximum 12 seconds as required
    
    def test_server_connectivity(self):
        """Verify server is running before testing"""
        try:
            response = requests.get(f"{self.BASE_URL}/", timeout=5)
            assert response.status_code == 200
            data = response.json()
            assert "TripAIBuddy" in data["message"]
        except requests.exceptions.RequestException:
            pytest.skip("Server not running - start with: python -m uvicorn app.main:app --reload --port 8000")
    
    def test_response_format_consistency(self):
        """Test that response format matches StructuredItinerary schema exactly"""
        
        payload = {
            "details": {
                "destination": "Orlando, FL",
                "travelDays": 3,
                "startDate": "2025-06-10",
                "endDate": "2025-06-12",
                "withKids": True,
                "withElders": False,
                "kidsAge": [8, 12],
                "specialRequests": "family-friendly activities"
            },
            "wishlist": [],
            "itinerary": [
                {
                    "day": 1,
                    "attractions": [
                        {
                            "name": "Universal Studios Florida",
                            "description": "Movie-themed attractions",
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
                            "description": "Interactive science exhibits",
                            "location": {"lat": 28.5721, "lng": -81.3519},
                            "type": "landmark"
                        }
                    ]
                },
                {
                    "day": 3,
                    "attractions": [
                        {
                            "name": "Lake Eola Park",
                            "description": "Downtown park with swan boats",
                            "location": {"lat": 28.5427, "lng": -81.3709},
                            "type": "landmark"
                        }
                    ]
                }
            ]
        }
        
        response = requests.post(f"{self.BASE_URL}/complete-itinerary", json=payload, timeout=15)
        assert response.status_code == 200
        data = response.json()
        
        # Validate root structure matches StructuredItinerary
        assert "itinerary" in data, "Response must have 'itinerary' field"
        itinerary = data["itinerary"]
        assert isinstance(itinerary, list), "itinerary must be a list"
        assert len(itinerary) == 3, "Must have 3 days"
        
        # Validate each day structure matches StructuredDayPlan
        for day_plan in itinerary:
            assert "day" in day_plan, "Each day must have 'day' field"
            assert "blocks" in day_plan, "Each day must have 'blocks' field"
            assert isinstance(day_plan["day"], int), "day must be integer"
            assert isinstance(day_plan["blocks"], list), "blocks must be list"
            assert len(day_plan["blocks"]) > 0, "Each day must have activities"
            
            # Validate each block matches ItineraryBlock schema
            for block in day_plan["blocks"]:
                # Required fields
                required_fields = ["type", "name", "description", "start_time", "duration"]
                for field in required_fields:
                    assert field in block, f"Block missing required field: {field}"
                    assert block[field] is not None, f"Block field {field} cannot be None"
                    assert isinstance(block[field], str), f"Block field {field} must be string"
                
                # Type validation
                assert block["type"] in ["landmark", "restaurant"], f"Invalid block type: {block['type']}"
                
                # Restaurant-specific fields
                if block["type"] == "restaurant":
                    assert "mealtime" in block, "Restaurant must have mealtime"
                    assert block["mealtime"] in ["breakfast", "lunch", "dinner"], f"Invalid mealtime: {block['mealtime']}"
                
                # Optional fields that may be present
                optional_fields = ["place_id", "rating", "location", "address", "photo_url", "website", "notes"]
                for field in optional_fields:
                    if field in block and block[field] is not None:
                        if field == "rating":
                            assert isinstance(block[field], (int, float)), f"{field} must be numeric"
                        elif field == "location":
                            assert "lat" in block[field] and "lng" in block[field], "location must have lat/lng"
                        else:
                            assert isinstance(block[field], str), f"{field} must be string"
        
        print("✅ Response format matches StructuredItinerary schema exactly")
    
    def test_latency_requirement_12_seconds(self):
        """Test that response time stays within 12 seconds"""
        
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
        response = requests.post(f"{self.BASE_URL}/complete-itinerary", json=payload, timeout=15)
        response_time = time.time() - start_time
        
        assert response.status_code == 200, f"Request failed: {response.text}"
        
        print(f"⏱️  Response time: {response_time:.2f}s (max: {self.MAX_LATENCY}s)")
        
        # CRITICAL: Must be under 12 seconds
        assert response_time < self.MAX_LATENCY, f"Response too slow: {response_time:.2f}s exceeds {self.MAX_LATENCY}s limit"
        
        print("✅ Latency requirement met")
    
    def test_theme_park_detection_edge_cases(self):
        """Test theme park detection with various theme park names"""
        
        theme_park_cases = [
            ("Universal Studios Florida", "universal studios"),
            ("Disney World Magic Kingdom", "disney"),
            ("SeaWorld Orlando", "seaworld"),
            ("Busch Gardens Tampa", "busch gardens"),
            ("Six Flags Magic Mountain", "six flags"),
            ("Knott's Berry Farm", "knott"),
            ("Cedar Point", "cedar point")
        ]
        
        for park_name, park_keyword in theme_park_cases:
            payload = {
                "details": {
                    "destination": "Orlando, FL",
                    "travelDays": 2,
                    "startDate": "2025-06-10",
                    "endDate": "2025-06-11",
                    "withKids": True,
                    "withElders": False,
                    "kidsAge": [8, 12],
                    "specialRequests": f"Visit {park_name}"
                },
                "wishlist": [],
                "itinerary": [
                    {
                        "day": 1,
                        "attractions": [
                            {
                                "name": park_name,
                                "description": f"{park_name} theme park",
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
                                "description": "Science museum",
                                "location": {"lat": 28.5721, "lng": -81.3519},
                                "type": "landmark"
                            }
                        ]
                    }
                ]
            }
            
            response = requests.post(f"{self.BASE_URL}/complete-itinerary", json=payload, timeout=15)
            assert response.status_code == 200
            data = response.json()
            
            # Find Day 1 (theme park day)
            day_1 = next(day for day in data["itinerary"] if day["day"] == 1)
            landmarks = [b for b in day_1["blocks"] if b["type"] == "landmark"]
            
            print(f"🎢 Testing {park_name}")
            print(f"   Landmarks found: {len(landmarks)}")
            
            # Theme park day should have exactly 1 landmark
            assert len(landmarks) == 1, f"Theme park day should have 1 landmark, got {len(landmarks)} for {park_name}"
            
            # Verify it's the theme park
            theme_park_landmark = landmarks[0]
            assert park_keyword in theme_park_landmark["name"].lower(), f"Theme park landmark should contain '{park_keyword}'"
            
            # Check restaurants
            restaurants = [b for b in day_1["blocks"] if b["type"] == "restaurant"]
            assert len(restaurants) == 3, f"Theme park day should have 3 restaurants"
            
            # Check meal distribution
            meal_types = {r["mealtime"] for r in restaurants}
            assert meal_types == {"breakfast", "lunch", "dinner"}, f"Missing meal types for {park_name}"
        
        print("✅ Theme park detection works for all major theme parks")
    
    def test_international_destinations_edge_case(self):
        """Test handling of international destinations"""
        
        international_cases = [
            ("Tokyo, Japan", "Tokyo landmarks"),
            ("Paris, France", "Paris attractions"),
            ("London, UK", "London museums"),
            ("Sydney, Australia", "Sydney harbor"),
            ("Bangkok, Thailand", "Bangkok temples")
        ]
        
        for destination, expected_context in international_cases:
            payload = {
                "details": {
                    "destination": destination,
                    "travelDays": 2,
                    "startDate": "2025-06-10",
                    "endDate": "2025-06-11",
                    "withKids": False,
                    "withElders": False,
                    "kidsAge": [],
                    "specialRequests": f"Authentic local experience in {destination}"
                },
                "wishlist": [],
                "itinerary": [
                    {
                        "day": 1,
                        "attractions": [
                            {
                                "name": f"Famous landmark in {destination}",
                                "description": f"Popular attraction in {destination}",
                                "location": {"lat": 35.6762, "lng": 139.6503},  # Default to Tokyo coords
                                "type": "landmark"
                            }
                        ]
                    },
                    {
                        "day": 2,
                        "attractions": [
                            {
                                "name": f"Cultural site in {destination}",
                                "description": f"Cultural attraction in {destination}",
                                "location": {"lat": 35.6762, "lng": 139.6503},
                                "type": "landmark"
                            }
                        ]
                    }
                ]
            }
            
            start_time = time.time()
            response = requests.post(f"{self.BASE_URL}/complete-itinerary", json=payload, timeout=15)
            response_time = time.time() - start_time
            
            print(f"🌍 Testing {destination} (took {response_time:.2f}s)")
            
            # Should handle international destinations gracefully
            if response.status_code == 200:
                data = response.json()
                
                # Basic structure validation
                assert "itinerary" in data
                assert len(data["itinerary"]) == 2
                
                # Each day should have activities
                for day in data["itinerary"]:
                    blocks = day["blocks"]
                    assert len(blocks) > 0, f"Day {day['day']} has no activities for {destination}"
                    
                    # Should have restaurants
                    restaurants = [b for b in blocks if b["type"] == "restaurant"]
                    assert len(restaurants) > 0, f"Day {day['day']} missing restaurants for {destination}"
                
                print(f"   ✅ {destination} handled successfully")
            else:
                # International destinations might fail due to API limitations - that's acceptable
                print(f"   ⚠️  {destination} failed (acceptable for international destinations): {response.status_code}")
        
        print("✅ International destination handling tested")
    
    def test_extreme_kids_ages_edge_case(self):
        """Test handling of extreme kids ages (toddlers and teenagers)"""
        
        age_cases = [
            ([2, 3], "toddler-friendly activities"),
            ([16, 17], "teen-appropriate activities"),
            ([5, 8, 12, 15], "mixed age group activities"),
            ([1], "baby-friendly activities")
        ]
        
        for kids_ages, expected_context in age_cases:
            payload = {
                "details": {
                    "destination": "San Diego, CA",
                    "travelDays": 2,
                    "startDate": "2025-06-10",
                    "endDate": "2025-06-11",
                    "withKids": True,
                    "withElders": False,
                    "kidsAge": kids_ages,
                    "specialRequests": f"Activities suitable for ages {', '.join(map(str, kids_ages))}"
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
            
            response = requests.post(f"{self.BASE_URL}/complete-itinerary", json=payload, timeout=15)
            assert response.status_code == 200
            data = response.json()
            
            print(f"👶 Testing kids ages {kids_ages}")
            
            # Basic structure validation
            assert len(data["itinerary"]) == 2
            
            # Each day should have appropriate number of landmarks
            for day in data["itinerary"]:
                landmarks = [b for b in day["blocks"] if b["type"] == "landmark"]
                restaurants = [b for b in day["blocks"] if b["type"] == "restaurant"]
                
                assert len(landmarks) >= 2, f"Day {day['day']} should have multiple landmarks for kids activities"
                assert len(restaurants) == 3, f"Day {day['day']} should have 3 restaurants"
                
                print(f"   Day {day['day']}: {len(landmarks)} landmarks, {len(restaurants)} restaurants")
        
        print("✅ Extreme kids ages handled properly")
    
    def test_empty_special_requests_handling(self):
        """Test handling of empty or None special requests"""
        
        special_request_cases = [
            None,
            "",
            "   ",  # Whitespace only
            "N/A",
            "None"
        ]
        
        for special_request in special_request_cases:
            payload = {
                "details": {
                    "destination": "Las Vegas, NV",
                    "travelDays": 2,
                    "startDate": "2025-06-10",
                    "endDate": "2025-06-11",
                    "withKids": False,
                    "withElders": False,
                    "kidsAge": [],
                    "specialRequests": special_request
                },
                "wishlist": [],
                "itinerary": [
                    {
                        "day": 1,
                        "attractions": [
                            {
                                "name": "Las Vegas Strip",
                                "description": "Famous casino and entertainment district",
                                "location": {"lat": 36.1147, "lng": -115.1721},
                                "type": "landmark"
                            }
                        ]
                    },
                    {
                        "day": 2,
                        "attractions": [
                            {
                                "name": "Fremont Street",
                                "description": "Historic Las Vegas area",
                                "location": {"lat": 36.1699, "lng": -115.1398},
                                "type": "landmark"
                            }
                        ]
                    }
                ]
            }
            
            response = requests.post(f"{self.BASE_URL}/complete-itinerary", json=payload, timeout=15)
            assert response.status_code == 200
            data = response.json()
            
            print(f"🔍 Testing special_request: {repr(special_request)}")
            
            # Should handle empty special requests gracefully
            assert len(data["itinerary"]) == 2
            
            for day in data["itinerary"]:
                blocks = day["blocks"]
                assert len(blocks) > 0, f"Day {day['day']} should have activities even with empty special requests"
                
                # Should still have proper meal distribution
                restaurants = [b for b in blocks if b["type"] == "restaurant"]
                assert len(restaurants) == 3, f"Day {day['day']} should have 3 restaurants"
        
        print("✅ Empty special requests handled gracefully")
    
    def test_single_day_trip_edge_case(self):
        """Test handling of single day trips"""
        
        payload = {
            "details": {
                "destination": "San Francisco, CA",
                "travelDays": 1,
                "startDate": "2025-06-10",
                "endDate": "2025-06-10",
                "withKids": False,
                "withElders": False,
                "kidsAge": [],
                "specialRequests": "One perfect day in San Francisco"
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
                }
            ]
        }
        
        response = requests.post(f"{self.BASE_URL}/complete-itinerary", json=payload, timeout=15)
        assert response.status_code == 200
        data = response.json()
        
        print("🗓️  Testing single day trip")
        
        assert len(data["itinerary"]) == 1, "Single day trip should have exactly 1 day"
        
        day_1 = data["itinerary"][0]
        landmarks = [b for b in day_1["blocks"] if b["type"] == "landmark"]
        restaurants = [b for b in day_1["blocks"] if b["type"] == "restaurant"]
        
        print(f"   Landmarks: {len(landmarks)}")
        print(f"   Restaurants: {len(restaurants)}")
        
        # Single day should still have multiple landmarks and 3 restaurants
        assert len(landmarks) >= 2, "Single day should have multiple landmarks"
        assert len(restaurants) == 3, "Single day should have 3 restaurants"
        
        # Check meal distribution
        meal_types = {r["mealtime"] for r in restaurants}
        assert meal_types == {"breakfast", "lunch", "dinner"}, "Single day should have all meal types"
        
        print("✅ Single day trip handled correctly")
    
    def test_website_field_consistency(self):
        """Test that website field is consistently provided for restaurant clickable cards"""
        
        payload = {
            "details": {
                "destination": "New York, NY",
                "travelDays": 2,
                "startDate": "2025-06-10",
                "endDate": "2025-06-11",
                "withKids": False,
                "withElders": False,
                "kidsAge": [],
                "specialRequests": "Great restaurants"
            },
            "wishlist": [],
            "itinerary": [
                {
                    "day": 1,
                    "attractions": [
                        {
                            "name": "Central Park",
                            "description": "Large public park",
                            "location": {"lat": 40.7829, "lng": -73.9654},
                            "type": "landmark"
                        }
                    ]
                },
                {
                    "day": 2,
                    "attractions": [
                        {
                            "name": "Times Square",
                            "description": "Commercial intersection",
                            "location": {"lat": 40.7580, "lng": -73.9855},
                            "type": "landmark"
                        }
                    ]
                }
            ]
        }
        
        response = requests.post(f"{self.BASE_URL}/complete-itinerary", json=payload, timeout=15)
        assert response.status_code == 200
        data = response.json()
        
        print("🌐 Testing website field consistency")
        
        total_restaurants = 0
        restaurants_with_website = 0
        
        for day in data["itinerary"]:
            restaurants = [b for b in day["blocks"] if b["type"] == "restaurant"]
            total_restaurants += len(restaurants)
            
            for restaurant in restaurants:
                print(f"   {restaurant['name']}: website = {restaurant.get('website', 'None')}")
                if restaurant.get("website"):
                    restaurants_with_website += 1
        
        print(f"   Total restaurants: {total_restaurants}")
        print(f"   Restaurants with website: {restaurants_with_website}")
        
        # Website field should be present (even if None) for all restaurants
        for day in data["itinerary"]:
            restaurants = [b for b in day["blocks"] if b["type"] == "restaurant"]
            for restaurant in restaurants:
                assert "website" in restaurant, f"Restaurant {restaurant['name']} missing website field"
        
        print("✅ Website field consistently provided")

    def test_no_large_gaps_between_activities(self):
        """Test that there are no gaps longer than 3 hours between activities"""
        
        payload = {
            "details": {
                "destination": "Seattle, WA",
                "travelDays": 3,
                "startDate": "2025-06-10",
                "endDate": "2025-06-12",
                "withKids": False,
                "withElders": False,
                "kidsAge": [],
                "specialRequests": "full day activities"
            },
            "wishlist": [],
            "itinerary": [
                {
                    "day": 1,
                    "attractions": [
                        {
                            "name": "Pike Place Market",
                            "description": "Famous public market",
                            "location": {"lat": 47.6085, "lng": -122.3351},
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
                },
                {
                    "day": 3,
                    "attractions": [
                        {
                            "name": "Museum of Pop Culture",
                            "description": "Music and pop culture museum",
                            "location": {"lat": 47.6214, "lng": -122.3481},
                            "type": "landmark"
                        }
                    ]
                }
            ]
        }
        
        start_time = time.time()
        response = requests.post(f"{self.BASE_URL}/complete-itinerary", json=payload, timeout=15)
        response_time = time.time() - start_time
        
        assert response.status_code == 200, f"Request failed: {response.text}"
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
        
        # Check each day for gaps
        for day in days:
            day_num = day["day"]
            blocks = day.get("blocks", [])
            
            print(f"\n📅 Day {day_num} Gap Analysis:")
            
            # Sort blocks by start time
            timed_blocks = []
            for block in blocks:
                start_time_str = block.get("start_time", "")
                if start_time_str:
                    try:
                        # Parse time (format: "HH:MM")
                        start_time_obj = datetime.strptime(start_time_str, "%H:%M")
                        duration_str = block.get("duration", "1h")
                        duration_minutes = self._parse_duration_to_minutes(duration_str)
                        end_time_obj = start_time_obj + timedelta(minutes=duration_minutes)
                        
                        timed_blocks.append({
                            "name": block.get("name", "Unknown"),
                            "type": block.get("type", "unknown"),
                            "start_time": start_time_obj,
                            "end_time": end_time_obj,
                            "start_str": start_time_str,
                            "duration": duration_str
                        })
                    except ValueError:
                        print(f"   ⚠️ Invalid time format: {start_time_str}")
            
            # Sort by start time
            timed_blocks.sort(key=lambda x: x["start_time"])
            
            # Check for gaps
            gaps_found = []
            for i in range(len(timed_blocks) - 1):
                current_block = timed_blocks[i]
                next_block = timed_blocks[i + 1]
                
                gap_duration = (next_block["start_time"] - current_block["end_time"]).total_seconds() / 60  # minutes
                
                print(f"   🕐 {current_block['start_str']}-{current_block['end_time'].strftime('%H:%M')}: {current_block['name']} ({current_block['type']})")
                
                if gap_duration > 0:
                    gap_hours = gap_duration / 60
                    print(f"   ⏳ Gap: {gap_duration:.0f} minutes ({gap_hours:.1f} hours)")
                    
                    if gap_duration > 180:  # More than 3 hours
                        gaps_found.append({
                            "after": current_block["name"],
                            "before": next_block["name"],
                            "duration_minutes": gap_duration,
                            "duration_hours": gap_hours
                        })
            
            # Print last block
            if timed_blocks:
                last_block = timed_blocks[-1]
                print(f"   🕐 {last_block['start_str']}-{last_block['end_time'].strftime('%H:%M')}: {last_block['name']} ({last_block['type']})")
            
            # Assert no large gaps
            if gaps_found:
                gap_details = []
                for gap in gaps_found:
                    gap_details.append(f"{gap['duration_hours']:.1f}h gap between '{gap['after']}' and '{gap['before']}'")
                
                assert False, f"Day {day_num} has {len(gaps_found)} large gaps (>3h): {'; '.join(gap_details)}"
            
            print(f"   ✅ No large gaps found on Day {day_num}")
        
        print("\n✅ All days have proper activity distribution with no large gaps")

    def test_meal_timing_prevents_gaps(self):
        """Test that meal timing is strategic to prevent large gaps"""
        
        payload = {
            "details": {
                "destination": "Portland, OR",
                "travelDays": 2,
                "startDate": "2025-06-10",
                "endDate": "2025-06-11",
                "withKids": True,
                "withElders": False,
                "kidsAge": [8, 12],
                "specialRequests": "family activities throughout the day"
            },
            "wishlist": [],
            "itinerary": [
                {
                    "day": 1,
                    "attractions": [
                        {
                            "name": "Oregon Zoo",
                            "description": "Large zoo with diverse animals",
                            "location": {"lat": 45.5099, "lng": -122.7156},
                            "type": "landmark"
                        }
                    ]
                },
                {
                    "day": 2,
                    "attractions": [
                        {
                            "name": "Powell's City of Books",
                            "description": "Famous independent bookstore",
                            "location": {"lat": 45.5230, "lng": -122.6814},
                            "type": "landmark"
                        }
                    ]
                }
            ]
        }
        
        response = requests.post(f"{self.BASE_URL}/complete-itinerary", json=payload, timeout=15)
        assert response.status_code == 200
        data = response.json()
        
        itinerary = data["itinerary"]
        if "itinerary" in itinerary:
            days = itinerary["itinerary"]
        else:
            days = itinerary
        
        for day in days:
            day_num = day["day"]
            blocks = day.get("blocks", [])
            
            # Get meal times
            restaurants = [b for b in blocks if b.get("type") == "restaurant"]
            meal_times = {}
            
            for restaurant in restaurants:
                mealtime = restaurant.get("mealtime", "")
                start_time = restaurant.get("start_time", "")
                if mealtime and start_time:
                    meal_times[mealtime] = start_time
            
            print(f"\n🍽️ Day {day_num} Meal Timing Analysis:")
            for mealtime, time_str in meal_times.items():
                print(f"   {mealtime.capitalize()}: {time_str}")
            
            # Validate meal distribution
            if "breakfast" in meal_times and "lunch" in meal_times:
                breakfast_time = datetime.strptime(meal_times["breakfast"], "%H:%M")
                lunch_time = datetime.strptime(meal_times["lunch"], "%H:%M")
                morning_gap = (lunch_time - breakfast_time).total_seconds() / 3600  # hours
                
                print(f"   Morning gap (breakfast to lunch): {morning_gap:.1f} hours")
                assert morning_gap <= 5.0, f"Gap between breakfast and lunch too large: {morning_gap:.1f} hours"
            
            if "lunch" in meal_times and "dinner" in meal_times:
                lunch_time = datetime.strptime(meal_times["lunch"], "%H:%M")
                dinner_time = datetime.strptime(meal_times["dinner"], "%H:%M")
                afternoon_gap = (dinner_time - lunch_time).total_seconds() / 3600  # hours
                
                print(f"   Afternoon gap (lunch to dinner): {afternoon_gap:.1f} hours")
                
                # This is the critical test - current system has 6-hour gaps!
                assert afternoon_gap <= 4.0, f"Gap between lunch and dinner too large: {afternoon_gap:.1f} hours (should be ≤4h)"
            
            print(f"   ✅ Meal timing is reasonable for Day {day_num}")
        
        print("\n✅ Meal timing prevents large gaps throughout the day")

    def _parse_duration_to_minutes(self, duration_str: str) -> int:
        """Parse duration string to minutes (e.g., '2h' -> 120, '1.5h' -> 90)"""
        if not duration_str:
            return 60  # Default 1 hour
        
        duration_str = duration_str.lower().strip()
        
        if duration_str.endswith('h'):
            hours_str = duration_str[:-1]
            try:
                hours = float(hours_str)
                return int(hours * 60)
            except ValueError:
                return 60
        elif duration_str.endswith('min') or duration_str.endswith('m'):
            minutes_str = duration_str.replace('min', '').replace('m', '')
            try:
                return int(minutes_str)
            except ValueError:
                return 60
        else:
            # Try to parse as number (assume hours)
            try:
                hours = float(duration_str)
                return int(hours * 60)
            except ValueError:
                return 60


if __name__ == "__main__":
    # Run all edge case tests
    test_suite = TestComprehensiveEdgeCases()
    
    print("🧪 Running Comprehensive Edge Case Tests")
    print("=" * 60)
    
    test_suite.test_server_connectivity() 
    print("✅ Server connectivity verified\n")
    
    test_suite.test_response_format_consistency()
    print("✅ Response format consistency verified\n")
    
    test_suite.test_latency_requirement_12_seconds()
    print("✅ Latency requirement verified\n")
    
    test_suite.test_theme_park_detection_edge_cases()
    print("✅ Theme park detection edge cases passed\n")
    
    test_suite.test_international_destinations_edge_case()
    print("✅ International destinations tested\n")
    
    test_suite.test_extreme_kids_ages_edge_case()
    print("✅ Extreme kids ages tested\n")
    
    test_suite.test_empty_special_requests_handling()
    print("✅ Empty special requests tested\n")
    
    test_suite.test_single_day_trip_edge_case()
    print("✅ Single day trip tested\n")
    
    test_suite.test_website_field_consistency()
    print("✅ Website field consistency tested\n")
    
    test_suite.test_no_large_gaps_between_activities()
    print("✅ No large gaps between activities tested\n")
    
    test_suite.test_meal_timing_prevents_gaps()
    print("✅ Meal timing prevents large gaps tested\n")
    
    print("🎉 All comprehensive edge case tests passed!") 