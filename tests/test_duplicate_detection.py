"""
Test duplicate detection and prevention in the agentic itinerary system.
"""

import pytest
from unittest.mock import patch, MagicMock

from app.agentic import complete_itinerary_from_selection


class TestDuplicateDetection:
    """Test suite for duplicate detection and prevention"""
    
    @pytest.mark.asyncio
    async def test_complete_itinerary_prevents_duplicates(self, sample_trip_selection, mock_places_client, mock_google_places_restaurant_detailed):
        """Test that complete itinerary generation prevents duplicates"""
        
        # Mock Google Places responses
        mock_places_client.places_nearby.return_value = {"results": [mock_google_places_restaurant_detailed] * 10}
        mock_places_client.geocode.return_value = {"lat": 28.5383, "lng": -81.3792}
        mock_places_client.place_details.return_value = {"result": mock_google_places_restaurant_detailed}
        
        result = await complete_itinerary_from_selection(sample_trip_selection, mock_places_client)
        
        # Collect all landmark names across all days
        all_landmark_names = []
        all_restaurant_names = []
        all_restaurant_place_ids = []
        
        for day in result['itinerary']['itinerary']:
            for block in day['blocks']:
                if block['type'] == 'landmark':
                    all_landmark_names.append(block['name'].lower().strip())
                elif block['type'] == 'restaurant':
                    all_restaurant_names.append(block['name'].lower().strip())
                    if block.get('place_id'):
                        all_restaurant_place_ids.append(block['place_id'])
        
        # Check for landmark duplicates
        unique_landmarks = set(all_landmark_names)
        assert len(all_landmark_names) == len(unique_landmarks), (
            f"Complete itinerary should prevent landmark duplicates. "
            f"Found: {all_landmark_names}, Unique: {list(unique_landmarks)}"
        )
        
        # Check for restaurant duplicates by place_id (more reliable than name)
        unique_restaurant_place_ids = set(all_restaurant_place_ids)
        assert len(all_restaurant_place_ids) == len(unique_restaurant_place_ids), (
            f"Complete itinerary should prevent restaurant duplicates by place_id. "
            f"Found: {all_restaurant_place_ids}, Unique: {list(unique_restaurant_place_ids)}"
        )

    def test_landmark_similarity_detection(self):
        """Test detection of similar (but not identical) landmark names"""
        
        landmarks = [
            {"name": "Universal Studios Florida", "day": 1},
            {"name": "Universal Studios", "day": 2},  # Similar name
            {"name": "Disney World", "day": 3},
            {"name": "Disney's Magic Kingdom", "day": 3},  # Similar name
        ]
        
        # This would be logic to detect similar landmarks
        # For now, we test the concept
        
        similar_pairs = []
        for i, landmark1 in enumerate(landmarks):
            for j, landmark2 in enumerate(landmarks[i+1:], i+1):
                name1 = landmark1["name"].lower()
                name2 = landmark2["name"].lower()
                
                # Simple similarity check (in production, use more sophisticated methods)
                if "universal" in name1 and "universal" in name2:
                    similar_pairs.append((landmark1["name"], landmark2["name"]))
                elif "disney" in name1 and "disney" in name2:
                    similar_pairs.append((landmark1["name"], landmark2["name"]))
        
        assert len(similar_pairs) == 2, f"Expected 2 similar pairs, found: {similar_pairs}"
        
        # Verify the pairs we found
        pair_names = [pair[0].lower() for pair in similar_pairs]
        assert any("universal" in name for name in pair_names), "Should detect Universal Studios similarity"
        assert any("disney" in name for name in pair_names), "Should detect Disney similarity"

    @pytest.mark.asyncio
    async def test_restaurant_variety_across_days(self, sample_trip_selection, mock_places_client):
        """Test that different restaurants are used across different days"""
        
        # Create diverse restaurants
        restaurants = []
        for i in range(15):
            restaurants.append({
                "place_id": f"unique_restaurant_{i}",
                "name": f"Restaurant {i}",
                "vicinity": f"Street {i}",
                "rating": 4.0 + (i % 5) / 10,
                "geometry": {"location": {"lat": 28.5 + i*0.01, "lng": -81.4 + i*0.01}},
                "types": ["restaurant", "food"]
            })
        
        mock_places_client.places_nearby.return_value = {"results": restaurants}
        mock_places_client.geocode.return_value = {"lat": 28.5383, "lng": -81.3792}
        
        result = await complete_itinerary_from_selection(sample_trip_selection, mock_places_client)
        
        # Group restaurants by day
        restaurants_by_day = {}
        for day in result['itinerary']['itinerary']:
            day_num = day['day']
            restaurants_by_day[day_num] = []
            
            for block in day['blocks']:
                if block['type'] == 'restaurant' and block.get('place_id'):
                    restaurants_by_day[day_num].append(block['place_id'])
        
        # Check that each day has different restaurants
        all_day_combinations = [(1, 2), (1, 3), (2, 3)]
        for day1, day2 in all_day_combinations:
            if day1 in restaurants_by_day and day2 in restaurants_by_day:
                day1_restaurants = set(restaurants_by_day[day1])
                day2_restaurants = set(restaurants_by_day[day2])
                
                overlap = day1_restaurants.intersection(day2_restaurants)
                assert len(overlap) == 0, (
                    f"Days {day1} and {day2} should not share restaurants. "
                    f"Overlap: {overlap}"
                )

    @pytest.mark.asyncio
    async def test_itinerary_completeness(self, sample_trip_selection, mock_places_client, mock_multiple_restaurants):
        """Test that the complete itinerary has all required components without gaps"""
        
        # Mock Google Places responses
        mock_places_client.places_nearby.return_value = {"results": mock_multiple_restaurants}
        mock_places_client.geocode.return_value = {"lat": 28.5383, "lng": -81.3792}
        mock_places_client.place_details.return_value = {"result": mock_multiple_restaurants[0]}
        
        result = await complete_itinerary_from_selection(sample_trip_selection, mock_places_client)
        
        # Verify structure
        assert 'itinerary' in result, "Result should contain itinerary"
        assert 'itinerary' in result['itinerary'], "Result should contain nested itinerary"
        
        itinerary_days = result['itinerary']['itinerary']
        assert len(itinerary_days) == 3, "Should have 3 days"
        
        for day in itinerary_days:
            assert 'day' in day, "Each day should have day number"
            assert 'blocks' in day, "Each day should have blocks"
            
            # Count landmarks and restaurants
            landmarks = [b for b in day['blocks'] if b['type'] == 'landmark']
            restaurants = [b for b in day['blocks'] if b['type'] == 'restaurant']
            
            # Each day should have at least some landmarks and restaurants
            assert len(landmarks) > 0, f"Day {day['day']} should have landmarks"
            assert len(restaurants) > 0, f"Day {day['day']} should have restaurants"
            
            # Verify block structure
            for block in day['blocks']:
                assert 'type' in block, "Each block should have type"
                assert 'name' in block, "Each block should have name"
                assert block['type'] in ['landmark', 'restaurant'], "Block type should be landmark or restaurant"

    def test_gap_detection_logic(self):
        """Test logic for detecting gaps in itinerary timing"""
        
        # Mock blocks with timing gaps
        blocks = [
            {"start_time": "09:00", "duration": "2h", "name": "Morning Activity"},
            {"start_time": "14:00", "duration": "3h", "name": "Afternoon Activity"},  # 3-hour gap
            {"start_time": "19:00", "duration": "1h", "name": "Evening Activity"},   # 2-hour gap
        ]
        
        # Simple gap detection logic
        gaps = []
        for i in range(len(blocks) - 1):
            current_block = blocks[i]
            next_block = blocks[i + 1]
            
            # Parse times (simplified)
            current_start_hour = int(current_block["start_time"].split(":")[0])
            current_duration_hours = int(current_block["duration"].replace("h", ""))
            current_end_hour = current_start_hour + current_duration_hours
            
            next_start_hour = int(next_block["start_time"].split(":")[0])
            
            gap_hours = next_start_hour - current_end_hour
            if gap_hours > 1:  # More than 1 hour gap
                gaps.append({
                    "after_block": current_block["name"],
                    "before_block": next_block["name"],
                    "gap_hours": gap_hours
                })
        
        # Should detect the gaps
        assert len(gaps) == 2, f"Should detect 2 gaps, found: {gaps}"
        assert gaps[0]["gap_hours"] == 3, "First gap should be 3 hours"
        assert gaps[1]["gap_hours"] == 2, "Second gap should be 2 hours" 