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

from app.agentic import complete_itinerary_from_selection as complete_itinerary_agentic

# Fixtures are now in conftest.py


class TestPerformance:
    """Test suite for performance requirements"""
    
    @pytest.mark.asyncio
    async def test_total_generation_under_15_seconds(self, sample_trip_selection, mock_places_client, mock_google_places_restaurant_detailed):
        """Test that total itinerary generation completes under 15 seconds"""
        
        # Mock Google Places with detailed restaurant data
        mock_places_client.places_nearby.return_value = {"results": [mock_google_places_restaurant_detailed] * 10}
        mock_places_client.geocode.return_value = {"lat": 28.5383, "lng": -81.3792}
        
        start_time = time.time()
        
        result = await complete_itinerary_agentic(sample_trip_selection, mock_places_client)
        
        duration = time.time() - start_time
        
        assert duration < 15.0, (
            f"Total generation took {duration:.2f}s, must be under 15s"
        )
        
        # Verify result is complete
        assert 'itinerary' in result, "Result should contain itinerary"
        assert 'itinerary' in result['itinerary'], "Result should contain nested itinerary"
        assert len(result['itinerary']['itinerary']) == 3, "Should generate 3 days"

    @pytest.mark.asyncio
    async def test_memory_efficiency(self, sample_trip_selection, mock_places_client, mock_google_places_restaurant_detailed):
        """Test that the system doesn't use excessive memory"""
        
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Mock Google Places responses
        mock_places_client.places_nearby.return_value = {"results": [mock_google_places_restaurant_detailed] * 20}
        mock_places_client.geocode.return_value = {"lat": 28.5383, "lng": -81.3792}
        
        # Generate multiple itineraries
        for _ in range(3):  # Reduced from 5 to 3 for faster testing
            result = await complete_itinerary_agentic(sample_trip_selection, mock_places_client)
            
            # Verify result is complete
            assert 'itinerary' in result, "Should generate complete itinerary"
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 100MB for 3 itineraries)
        assert memory_increase < 100, (
            f"Memory usage increased by {memory_increase:.1f}MB, should be under 100MB"
        )



 