"""
Gap Detection Test Suite for /complete-itinerary

This test suite validates that there are no large gaps in daily itineraries
and ensures proper timing distribution throughout the day.

Key Requirements:
1. No gaps longer than 3 hours between activities
2. Activities should be distributed throughout the day (9 AM - 7 PM)
3. Meal times should be reasonable and fill gaps
4. Regeneration should occur if gaps are detected
"""

import pytest
import requests
import time
from datetime import datetime, timedelta
from typing import List, Dict, Tuple


class TestGapDetection:
    """Test suite for detecting and preventing timing gaps in itineraries"""
    
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
    # Run tests individually for debugging
    test_instance = TestGapDetection()
    
    print("🧪 Running Gap Detection Tests...")
    
    try:
        test_instance.test_server_is_running()
        print("✅ Server is running")
        
        test_instance.test_no_large_gaps_between_activities()
        print("✅ No large gaps test passed")
        
        test_instance.test_meal_timing_prevents_gaps()
        print("✅ Meal timing test passed")
        
        print("\n🎉 Gap detection tests completed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        raise 