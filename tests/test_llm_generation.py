"""
Test actual LLM generation for landmark planning.

This test makes REAL LLM calls to validate:
- No duplicate landmarks across days
- Proper response to prompts
- Theme park detection and handling
- JSON format compliance

⚠️ This test incurs LLM costs - run sparingly for validation!
"""

import pytest
import asyncio
import json
from unittest.mock import patch
import aiohttp

from app.agentic_itinerary import enhanced_agentic_system
from app.places_client import GooglePlacesClient


@pytest.mark.asyncio
@pytest.mark.llm_cost  # Custom marker for expensive tests
async def test_unified_landmark_generation_no_duplicates(sample_trip_selection):
    """
    Test that unified landmark generation produces no duplicate landmarks.
    
    This is the KEY test that validates our anti-duplicate strategy.
    """
    
    # Test the unified landmark generation
    landmarks_by_day = await enhanced_agentic_system._generate_all_landmarks_unified(sample_trip_selection)
    
    # Collect all landmark names across all days
    all_landmark_names = []
    for day_num, landmarks in landmarks_by_day.items():
        for landmark in landmarks:
            all_landmark_names.append(landmark.get('name', '').lower().strip())
    
    # Check for duplicates
    unique_landmarks = set(all_landmark_names)
    
    assert len(all_landmark_names) == len(unique_landmarks), (
        f"Duplicate landmarks detected! "
        f"Total: {len(all_landmark_names)}, Unique: {len(unique_landmarks)}. "
        f"Landmarks: {all_landmark_names}"
    )
    
    # Validate each day has landmarks
    assert len(landmarks_by_day) == 3, "Should generate landmarks for 3 days"
    
    for day_num in [1, 2, 3]:
        assert day_num in landmarks_by_day, f"Missing landmarks for day {day_num}"
        landmarks = landmarks_by_day[day_num]
        assert len(landmarks) >= 1, f"Day {day_num} should have at least 1 landmark"


@pytest.mark.asyncio
@pytest.mark.llm_cost
async def test_theme_park_generates_single_landmark(sample_trip_selection):
    """
    Test that theme park days generate EXACTLY 1 landmark.
    """
    
    landmarks_by_day = await enhanced_agentic_system._generate_all_landmarks_unified(sample_trip_selection)
    
    # Day 1 has Universal Studios (theme park) - should have exactly 1 landmark
    day_1_landmarks = landmarks_by_day.get(1, [])
    
    assert len(day_1_landmarks) == 1, (
        f"Theme park day should have exactly 1 landmark, got {len(day_1_landmarks)}: "
        f"{[l.get('name') for l in day_1_landmarks]}"
    )
    
    # Verify it's Universal Studios
    landmark = day_1_landmarks[0]
    assert 'universal' in landmark.get('name', '').lower(), (
        f"Theme park landmark should be Universal Studios, got: {landmark.get('name')}"
    )
    
    # Verify 8-hour duration for theme park
    assert landmark.get('duration') == '8h', (
        f"Theme park should have 8h duration, got: {landmark.get('duration')}"
    )


@pytest.mark.asyncio
@pytest.mark.llm_cost
async def test_non_theme_park_days_multiple_landmarks(sample_trip_selection):
    """
    Test that non-theme park days generate multiple landmarks (2-3 per day).
    """
    
    landmarks_by_day = await enhanced_agentic_system._generate_all_landmarks_unified(sample_trip_selection)
    
    # Days 2 and 3 are non-theme park - should have multiple landmarks
    for day_num in [2, 3]:
        landmarks = landmarks_by_day.get(day_num, [])
        assert len(landmarks) >= 2, (
            f"Non-theme park day {day_num} should have 2-3 landmarks for full experience, got {len(landmarks)}. "
            f"Landmarks: {[l.get('name') for l in landmarks]}"
        )
        assert len(landmarks) <= 3, (
            f"Non-theme park day {day_num} should have at most 3 landmarks, got {len(landmarks)}. "
            f"Landmarks: {[l.get('name') for l in landmarks]}"
        )


@pytest.mark.asyncio
@pytest.mark.llm_cost
async def test_landmarks_only_no_restaurants(sample_trip_selection):
    """
    Test that LLM generates ONLY landmarks, no restaurants.
    """
    
    landmarks_by_day = await enhanced_agentic_system._generate_all_landmarks_unified(sample_trip_selection)
    
    # Check all generated items are landmarks
    for day_num, landmarks in landmarks_by_day.items():
        for landmark in landmarks:
            assert landmark.get('type') == 'landmark', (
                f"Day {day_num} contains non-landmark: {landmark.get('name')} "
                f"with type: {landmark.get('type')}"
            )
            
            # Check name doesn't contain restaurant keywords
            name = landmark.get('name', '').lower()
            restaurant_keywords = ['restaurant', 'cafe', 'diner', 'kitchen', 'bistro', 'eatery']
            for keyword in restaurant_keywords:
                assert keyword not in name, (
                    f"Landmark name contains restaurant keyword '{keyword}': {landmark.get('name')}"
                )


@pytest.mark.asyncio
@pytest.mark.llm_cost
async def test_json_format_compliance(sample_trip_selection):
    """
    Test that LLM response follows the required JSON format.
    """
    
    landmarks_by_day = await enhanced_agentic_system._generate_all_landmarks_unified(sample_trip_selection)
    
    # Validate structure
    assert isinstance(landmarks_by_day, dict), "Response should be a dictionary"
    
    for day_num, landmarks in landmarks_by_day.items():
        assert isinstance(day_num, int), f"Day number should be int, got {type(day_num)}"
        assert isinstance(landmarks, list), f"Landmarks should be list, got {type(landmarks)}"
        
        for landmark in landmarks:
            assert isinstance(landmark, dict), f"Each landmark should be dict, got {type(landmark)}"
            
            # Required fields
            required_fields = ['name', 'type', 'description', 'start_time', 'duration']
            for field in required_fields:
                assert field in landmark, f"Missing required field '{field}' in landmark: {landmark}"
            
            # Optional location field format
            if 'location' in landmark:
                location = landmark['location']
                assert isinstance(location, dict), "Location should be dict"
                assert 'lat' in location and 'lng' in location, "Location should have lat/lng"


@pytest.mark.asyncio
@pytest.mark.llm_cost
async def test_mandatory_attractions_included(sample_trip_selection):
    """
    Test that mandatory attractions from trip selection are included.
    """
    
    landmarks_by_day = await enhanced_agentic_system._generate_all_landmarks_unified(sample_trip_selection)
    
    # Expected mandatory attractions
    mandatory_attractions = {
        1: "universal studios",
        2: "science center", 
        3: "lake eola"
    }
    
    for day_num, expected_attraction in mandatory_attractions.items():
        landmarks = landmarks_by_day.get(day_num, [])
        landmark_names = [l.get('name', '').lower() for l in landmarks]
        
        # Check if mandatory attraction is included
        found = any(expected_attraction in name for name in landmark_names)
        assert found, (
            f"Day {day_num} missing mandatory attraction '{expected_attraction}'. "
            f"Generated landmarks: {landmark_names}"
        )


@pytest.mark.asyncio
@pytest.mark.llm_cost
async def test_landmark_enhancement_with_address_and_photos(sample_trip_selection):
    """
    Test that landmarks get enhanced with Google Places data including address and photos.
    
    This test verifies the complete landmark enhancement pipeline.
    """
    import aiohttp
    from app.places_client import GooglePlacesClient
    
    async with aiohttp.ClientSession() as session:
        places_client = GooglePlacesClient(session)
        
        # Test landmark enhancement for Universal Studios
        from app.schema import ItineraryBlock
        
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
        
        # Validate basic enhancement
        assert enhanced_block.name == landmark_block.name, "Name should be preserved"
        assert enhanced_block.type == "landmark", "Type should remain landmark"
        
        # Should have Google Places data
        assert enhanced_block.place_id is not None, (
            f"Enhanced landmark should have place_id. Got: {enhanced_block.place_id}"
        )
        assert enhanced_block.location is not None, (
            f"Enhanced landmark should have location. Got: {enhanced_block.location}"
        )
        assert enhanced_block.address is not None, (
            f"Enhanced landmark should have address. Got: {enhanced_block.address}"
        )
        
        # Validate address format
        address = enhanced_block.address
        assert len(address) > 10, f"Address should be meaningful, got: {address}"
        assert any(word in address.lower() for word in ['orlando', 'fl', 'florida']), (
            f"Address should contain location info, got: {address}"
        )
        
        # Optional photo URL (might not always be available)
        if enhanced_block.photo_url:
            assert enhanced_block.photo_url.startswith("/photo-proxy/"), (
                f"Photo URL should use proxy format, got: {enhanced_block.photo_url}"
            )
        
        print(f"✅ Landmark enhancement validation passed for: {enhanced_block.name}")
        print(f"   📍 Place ID: {enhanced_block.place_id}")
        print(f"   🏠 Address: {enhanced_block.address}")
        print(f"   📸 Has Photo: {'Yes' if enhanced_block.photo_url else 'No'}")


@pytest.mark.asyncio
@pytest.mark.llm_cost
async def test_no_large_gaps_between_activities(sample_trip_selection):
    """
    Test that there are no large gaps (>3 hours) between activities in generated itinerary.
    
    This ensures good user experience with properly filled days.
    """
    import aiohttp
    from app.places_client import GooglePlacesClient
    
    async with aiohttp.ClientSession() as session:
        places_client = GooglePlacesClient(session)
        
        # Generate complete itinerary
        result = await enhanced_agentic_system.generate_itinerary(sample_trip_selection, places_client)
        itinerary = result["itinerary"]
        
        for day_data in itinerary:
            day_num = day_data["day"]
            blocks = day_data["blocks"]
            
            if len(blocks) < 2:
                continue  # Need at least 2 activities to check gaps
            
            # Sort blocks by start time
            sorted_blocks = sorted(blocks, key=lambda x: x["start_time"])
            
            # Check gaps between consecutive activities
            for i in range(len(sorted_blocks) - 1):
                current_block = sorted_blocks[i]
                next_block = sorted_blocks[i + 1]
                
                # Calculate end time of current activity
                start_time = current_block["start_time"]
                duration = current_block["duration"]
                
                # Parse times
                start_hour, start_min = map(int, start_time.split(":"))
                start_minutes = start_hour * 60 + start_min
                
                # Parse duration
                if duration.endswith("h"):
                    duration_minutes = float(duration[:-1]) * 60
                elif duration.endswith("m"):
                    duration_minutes = float(duration[:-1])
                else:
                    duration_minutes = 120  # Default
                
                end_minutes = start_minutes + duration_minutes
                
                # Parse next activity start time
                next_start = next_block["start_time"]
                next_hour, next_min = map(int, next_start.split(":"))
                next_start_minutes = next_hour * 60 + next_min
                
                # Calculate gap
                gap_minutes = next_start_minutes - end_minutes
                gap_hours = gap_minutes / 60
                
                # Assert no large gaps
                assert gap_hours <= 3.0, (
                    f"Day {day_num}: Large gap of {gap_hours:.1f} hours between "
                    f"{current_block['name']} (ends at {int(end_minutes//60):02d}:{int(end_minutes%60):02d}) "
                    f"and {next_block['name']} (starts at {next_start}). "
                    f"Gaps should be ≤3 hours for good user experience."
                ) 