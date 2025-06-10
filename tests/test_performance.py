"""
Test performance requirements using mocked LLM responses.

These tests validate:
- Total generation time under 15s
- Individual component performance
- Memory usage
- Proper timeout handling

No LLM costs - uses mocked data!
"""

import pytest
import time
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from app.agentic_itinerary import enhanced_agentic_system, complete_itinerary_agentic

# Import detailed fixtures for consistent mocking
from .test_google_places_integration import mock_google_places_restaurant_detailed, mock_google_places_landmark_detailed


class TestPerformance:
    """Test suite for performance requirements"""
    
    @pytest.mark.asyncio
    async def test_total_generation_under_15_seconds(self, sample_trip_selection, mock_landmarks_response, mock_places_client, mock_google_places_restaurant_detailed):
        """Test that total itinerary generation completes under 15 seconds"""
        
        # Mock LLM response for unified generation
        mock_response = MagicMock()
        mock_response.content = f"```json\n{mock_landmarks_response}\n```"
        
        with patch.object(enhanced_agentic_system.primary_llm, 'ainvoke', return_value=mock_response):
            # Mock Google Places with detailed restaurant data
            mock_places_client.places_nearby.return_value = {"results": [mock_google_places_restaurant_detailed] * 10}
            
            start_time = time.time()
            
            result = await complete_itinerary_agentic(sample_trip_selection, mock_places_client)
            
            duration = time.time() - start_time
            
            assert duration < 15.0, (
                f"Total generation took {duration:.2f}s, must be under 15s"
            )
            
            # Verify result is complete
            assert 'itinerary' in result, "Result should contain itinerary"
            assert len(result['itinerary']) == 3, "Should generate 3 days"

    @pytest.mark.asyncio
    async def test_unified_landmark_generation_performance(self, sample_trip_selection, mock_landmarks_response):
        """Test that unified landmark generation is fast"""
        
        mock_response = MagicMock()
        mock_response.content = f"```json\n{mock_landmarks_response}\n```"
        
        with patch.object(enhanced_agentic_system.primary_llm, 'ainvoke', return_value=mock_response):
            start_time = time.time()
            
            result = await enhanced_agentic_system._generate_all_landmarks_unified(sample_trip_selection)
            
            duration = time.time() - start_time
            
            # Should be much faster than old parallel approach
            assert duration < 5.0, (
                f"Unified landmark generation took {duration:.2f}s, should be under 5s"
            )
            
            # Verify result quality
            assert len(result) == 3, "Should generate landmarks for 3 days"
            assert all(isinstance(landmarks, list) for landmarks in result.values()), "All days should have landmark lists"

    @pytest.mark.asyncio
    async def test_restaurant_addition_performance(self, sample_trip_selection, mock_places_client):
        """Test that restaurant addition is reasonably fast"""
        
        # Create mock restaurants using detailed format
        restaurants = []
        for i in range(20):
            restaurants.append({
                "place_id": f"ChIJtest_place_{i}",
                "name": f"Restaurant {i}",
                "vicinity": f"Address {i}, Orlando, FL",
                "formatted_address": f"Address {i}, Orlando, FL 32819, USA",
                "rating": 4.0 + (i % 10) / 10,
                "geometry": {"location": {"lat": 28.5, "lng": -81.4}},
                "photos": [{"photo_reference": f"test_photo_{i}"}],
                "types": ["restaurant", "food"]
            })
        
        mock_places_client.places_nearby.return_value = {"results": restaurants}
        
        # Create test day plans
        from app.schema import StructuredDayPlan, ItineraryBlock
        
        day_plans = {}
        for day_num in range(1, 4):
            day_plans[day_num] = StructuredDayPlan(
                day=day_num,
                blocks=[
                    ItineraryBlock(
                        name=f"Landmark Day {day_num}",
                        type="landmark",
                        start_time="09:00",
                        duration="3h"
                    )
                ]
            )
        
        start_time = time.time()
        
        # Add restaurants to all days
        tasks = []
        for day_plan in day_plans.values():
            task = enhanced_agentic_system._add_restaurants_to_day(
                day_plan, mock_places_client, sample_trip_selection
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        
        duration = time.time() - start_time
        
        # Restaurant addition should be fast due to parallel processing
        assert duration < 8.0, (
            f"Restaurant addition took {duration:.2f}s, should be under 8s"
        )
        
        # Verify all days got restaurants
        assert len(results) == 3, "Should process 3 days"
        for result in results:
            restaurants = [block for block in result.blocks if block.type == 'restaurant']
            assert len(restaurants) == 3, "Each day should have 3 restaurants"

    @pytest.mark.asyncio
    async def test_timeout_handling(self, sample_trip_selection):
        """Test that the system handles timeouts gracefully"""
        
        # Mock LLM that takes too long
        async def slow_llm_response(*args, **kwargs):
            await asyncio.sleep(20)  # Longer than any reasonable timeout
            mock_response = MagicMock()
            mock_response.content = "This should timeout"
            return mock_response
        
        with patch.object(enhanced_agentic_system.primary_llm, 'ainvoke', side_effect=slow_llm_response):
            start_time = time.time()
            
            # Should timeout and return fallback
            result = await enhanced_agentic_system._generate_all_landmarks_unified(sample_trip_selection)
            
            duration = time.time() - start_time
            
            # Should fail fast due to timeout, not wait 20 seconds
            assert duration < 15.0, (
                f"Timeout handling took {duration:.2f}s, should timeout much faster"
            )
            
            # Should return fallback result
            assert isinstance(result, dict), "Should return fallback result on timeout"

    @pytest.mark.asyncio
    async def test_concurrent_processing_efficiency(self, sample_trip_selection, mock_places_client):
        """Test that concurrent processing provides efficiency gains"""
        
        restaurants = []
        for i in range(50):
            restaurants.append({
                "place_id": f"place_{i}",
                "name": f"Restaurant {i}",
                "vicinity": f"Address {i}",
                "rating": 4.0,
                "geometry": {"location": {"lat": 28.5, "lng": -81.4}},
                "types": ["restaurant", "food"]
            })
        
        mock_places_client.places_nearby.return_value = restaurants
        
        from app.schema import StructuredDayPlan, ItineraryBlock
        
        # Create multiple day plans
        day_plans = []
        for i in range(5):  # Test with 5 days for more noticeable concurrency benefit
            day_plans.append(StructuredDayPlan(
                day=i+1,
                blocks=[
                    ItineraryBlock(
                        name=f"Landmark {i+1}",
                        type="landmark",
                        start_time="09:00",
                        duration="3h"
                    )
                ]
            ))
        
        # Test concurrent processing
        start_time = time.time()
        
        tasks = [
            enhanced_agentic_system._add_restaurants_to_day(day_plan, mock_places_client, sample_trip_selection)
            for day_plan in day_plans
        ]
        
        concurrent_results = await asyncio.gather(*tasks)
        concurrent_duration = time.time() - start_time
        
        # Test sequential processing
        start_time = time.time()
        
        sequential_results = []
        for day_plan in day_plans:
            result = await enhanced_agentic_system._add_restaurants_to_day(
                day_plan, mock_places_client, sample_trip_selection
            )
            sequential_results.append(result)
        
        sequential_duration = time.time() - start_time
        
        # Concurrent should be faster than sequential
        speedup = sequential_duration / concurrent_duration
        assert speedup > 1.5, (
            f"Concurrent processing should be faster. "
            f"Sequential: {sequential_duration:.2f}s, Concurrent: {concurrent_duration:.2f}s, "
            f"Speedup: {speedup:.1f}x"
        )
        
        # Results should be identical
        assert len(concurrent_results) == len(sequential_results), "Result counts should match"

    @pytest.mark.asyncio
    async def test_memory_efficiency(self, sample_trip_selection, mock_landmarks_response, mock_places_client, mock_google_places_restaurant_detailed):
        """Test that the system doesn't use excessive memory"""
        
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Mock responses
        mock_response = MagicMock()
        mock_response.content = f"```json\n{mock_landmarks_response}\n```"
        
        with patch.object(enhanced_agentic_system.primary_llm, 'ainvoke', return_value=mock_response):
            mock_places_client.places_nearby.return_value = {"results": [mock_google_places_restaurant_detailed] * 20}
            
            # Generate multiple itineraries
            for _ in range(5):
                result = await complete_itinerary_agentic(sample_trip_selection, mock_places_client)
                
                # Verify result is complete
                assert 'itinerary' in result, "Should generate complete itinerary"
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 100MB for 5 itineraries)
        assert memory_increase < 100, (
            f"Memory usage increased by {memory_increase:.1f}MB, should be under 100MB"
        ) 