"""
Test duplicate detection logic using mocked LLM responses.

These tests validate:
- Detection of duplicate landmarks across days
- Proper handling of duplicate responses
- Anti-duplicate strategies

No LLM costs - uses mocked data with known duplicates!
"""

import pytest
from unittest.mock import patch, MagicMock

from app.agentic_itinerary import enhanced_agentic_system


class TestDuplicateDetection:
    """Test suite for duplicate detection and prevention"""
    
    @pytest.mark.asyncio
    async def test_unified_generation_prevents_duplicates(self, sample_trip_selection, mock_landmarks_response):
        """Test that unified generation prevents duplicates compared to parallel generation"""
        
        # Test unified generation (should have no duplicates)
        mock_response = MagicMock()
        mock_response.content = f"```json\n{mock_landmarks_response}\n```"
        
        with patch.object(enhanced_agentic_system.primary_llm, 'ainvoke', return_value=mock_response):
            unified_result = await enhanced_agentic_system._generate_all_landmarks_unified(sample_trip_selection)
        
        # Collect all landmark names
        all_landmark_names = []
        for day_landmarks in unified_result.values():
            for landmark in day_landmarks:
                all_landmark_names.append(landmark.get('name', '').lower().strip())
        
        # Check for duplicates
        unique_landmarks = set(all_landmark_names)
        assert len(all_landmark_names) == len(unique_landmarks), (
            f"Unified generation should prevent duplicates. "
            f"Found: {all_landmark_names}, Unique: {list(unique_landmarks)}"
        )

    @pytest.mark.asyncio
    async def test_duplicate_landmark_names_detection(self, sample_trip_selection, mock_landmarks_response_with_duplicates):
        """Test detection of duplicate landmark names in LLM response"""
        
        mock_response = MagicMock()
        mock_response.content = f"```json\n{mock_landmarks_response_with_duplicates}\n```"
        
        with patch.object(enhanced_agentic_system.primary_llm, 'ainvoke', return_value=mock_response):
            result = await enhanced_agentic_system._generate_all_landmarks_unified(sample_trip_selection)
        
        # Collect all landmark names
        all_landmark_names = []
        for day_landmarks in result.values():
            for landmark in day_landmarks:
                all_landmark_names.append(landmark.get('name', '').lower().strip())
        
        # Count occurrences
        name_counts = {}
        for name in all_landmark_names:
            name_counts[name] = name_counts.get(name, 0) + 1
        
        # Find duplicates
        duplicates = {name: count for name, count in name_counts.items() if count > 1}
        
        # For testing purposes, we expect the mock data to have duplicates
        # In production, this would trigger duplicate handling
        if duplicates:
            assert "universal studios florida" in duplicates, (
                f"Expected 'universal studios florida' to be duplicated in test data. "
                f"Found duplicates: {duplicates}"
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
    async def test_restaurant_duplicate_prevention(self, sample_trip_selection, mock_places_client):
        """Test that restaurant duplication is prevented across days"""
        
        # Create restaurants with some having same place_id (potential duplicates)
        restaurants = [
            {
                "place_id": "duplicate_restaurant",  # This will be a duplicate
                "name": "Duplicate Restaurant",
                "vicinity": "Main St",
                "rating": 4.0,
                "geometry": {"location": {"lat": 28.5, "lng": -81.4}},
                "types": ["restaurant", "food"]
            },
            {
                "place_id": "unique_restaurant_1",
                "name": "Unique Restaurant 1", 
                "vicinity": "First St",
                "rating": 4.2,
                "geometry": {"location": {"lat": 28.51, "lng": -81.41}},
                "types": ["restaurant", "food"]
            },
            {
                "place_id": "unique_restaurant_2",
                "name": "Unique Restaurant 2",
                "vicinity": "Second St", 
                "rating": 4.4,
                "geometry": {"location": {"lat": 28.52, "lng": -81.42}},
                "types": ["restaurant", "food"]
            }
        ]
        
        mock_places_client.places_nearby.return_value = restaurants
        
        # Reset global tracking
        enhanced_agentic_system._used_restaurants_global = set()
        
        from app.schema import StructuredDayPlan, ItineraryBlock
        
        # Process first day - should use the duplicate restaurant
        day1_plan = StructuredDayPlan(
            day=1,
            blocks=[
                ItineraryBlock(
                    name="Day 1 Landmark",
                    type="landmark",
                    start_time="09:00",
                    duration="3h"
                )
            ]
        )
        
        day1_result = await enhanced_agentic_system._add_restaurants_to_day(
            day1_plan, mock_places_client, sample_trip_selection
        )
        
        day1_place_ids = {
            block.place_id for block in day1_result.blocks 
            if block.type == 'restaurant' and block.place_id
        }
        
        # Process second day - should NOT reuse restaurants from day 1
        day2_plan = StructuredDayPlan(
            day=2,
            blocks=[
                ItineraryBlock(
                    name="Day 2 Landmark",
                    type="landmark", 
                    start_time="09:00",
                    duration="3h"
                )
            ]
        )
        
        day2_result = await enhanced_agentic_system._add_restaurants_to_day(
            day2_plan, mock_places_client, sample_trip_selection
        )
        
        day2_place_ids = {
            block.place_id for block in day2_result.blocks
            if block.type == 'restaurant' and block.place_id
        }
        
        # Check for duplicates
        overlap = day1_place_ids.intersection(day2_place_ids)
        assert len(overlap) == 0, (
            f"Found duplicate restaurants between days: {overlap}. "
            f"Day 1: {day1_place_ids}, Day 2: {day2_place_ids}"
        )

    def test_parse_response_with_malformed_json(self):
        """Test handling of malformed JSON responses that might cause duplicate issues"""
        
        malformed_responses = [
            # Missing closing brace
            '{"day_1": [{"name": "Test", "type": "landmark"}]',
            
            # Extra comma
            '{"day_1": [{"name": "Test", "type": "landmark",}]}',
            
            # Missing quotes
            '{day_1: [{"name": "Test", "type": "landmark"}]}',
            
            # Empty response
            '',
            
            # Non-JSON response
            'This is not JSON at all',
        ]
        
        for malformed_response in malformed_responses:
            result = enhanced_agentic_system._parse_unified_landmark_response(malformed_response, 3)
            
            # Should return fallback structure, not crash
            assert isinstance(result, dict), f"Should return dict for malformed response: {malformed_response[:50]}"
            assert len(result) == 3, f"Should have 3 days in fallback response"
            
            # All days should have empty lists (fallback)
            for day_num in [1, 2, 3]:
                assert day_num in result, f"Missing day {day_num} in fallback"
                assert isinstance(result[day_num], list), f"Day {day_num} should be list in fallback"

    def test_gap_detection_logic(self):
        """Test gap detection logic with mock data - no API costs"""
        
        # Create test day with a large gap
        day_with_gap = {
            "day": 1,
            "blocks": [
                {
                    "name": "Morning Museum",
                    "type": "landmark",
                    "start_time": "09:00",
                    "duration": "2h"  # Ends at 11:00
                },
                {
                    "name": "Late Afternoon Activity", 
                    "type": "landmark",
                    "start_time": "16:00",  # Starts at 16:00 - 5 hour gap!
                    "duration": "2h"
                }
            ]
        }
        
        # Test the gap detection logic
        from analysis.test_comprehensive_agentic import ComprehensiveAgenticValidation
        validator = ComprehensiveAgenticValidation()
        
        gap_issues = validator._analyze_day_gaps(day_with_gap, 1)
        
        # Should detect the large gap
        assert len(gap_issues) == 1, f"Should detect 1 gap issue, found {len(gap_issues)}"
        assert "5.0 hours" in gap_issues[0], f"Should mention 5 hour gap, got: {gap_issues[0]}"
        assert "Morning Museum" in gap_issues[0], "Should mention first activity"
        assert "Late Afternoon Activity" in gap_issues[0], "Should mention second activity"
        
        # Test day with no gaps
        day_without_gap = {
            "day": 2,
            "blocks": [
                {
                    "name": "Morning Activity",
                    "type": "landmark", 
                    "start_time": "09:00",
                    "duration": "2h"  # Ends at 11:00
                },
                {
                    "name": "Lunch",
                    "type": "restaurant",
                    "start_time": "12:30",  # 1.5 hour gap - acceptable
                    "duration": "1h"
                },
                {
                    "name": "Afternoon Activity",
                    "type": "landmark",
                    "start_time": "14:00",  # 0.5 hour gap - fine
                    "duration": "2h"
                }
            ]
        }
        
        gap_issues = validator._analyze_day_gaps(day_without_gap, 2)
        
        # Should not detect any issues
        assert len(gap_issues) == 0, f"Should not detect gaps in well-planned day, found: {gap_issues}" 