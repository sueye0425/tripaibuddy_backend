import pytest
import asyncio
import time
import httpx
import requests

class TestEndpointPerformance:
    """Test suite to enforce performance requirements for API endpoints"""
    
    BASE_URL = "http://127.0.0.1:8000"
    
    def test_server_is_running(self):
        """Verify the server is running before running performance tests"""
        try:
            response = requests.get(f"{self.BASE_URL}/", timeout=5)
            assert response.status_code == 200
            data = response.json()
            assert "TripAIBuddy" in data["message"]
        except requests.exceptions.RequestException:
            pytest.skip("Server not running - start with: python -m uvicorn app.main:app --reload --port 8000")
    
    def test_generate_is_fast(self):
        """Test that /generate endpoint responds within 5 seconds and uses the simple system"""
        start_time = time.time()
        
        response = requests.post(f"{self.BASE_URL}/generate", json={
            "destination": "San Francisco, CA",
            "travel_days": 1,
            "with_kids": False,
            "with_elderly": False
        }, timeout=10)
        
        end_time = time.time()
        response_time = end_time - start_time
        
        # Assert response is successful and fast
        assert response.status_code == 200, f"Generate endpoint failed with status {response.status_code}: {response.text}"
        assert response_time < 5.0, f"Generate endpoint took {response_time:.2f}s, should be under 5s"
        
        # Assert correct response structure (simple format)
        data = response.json()
        assert "landmarks" in data, "Generate response missing landmarks"
        assert "restaurants" in data, "Generate response missing restaurants"
        assert isinstance(data["landmarks"], dict), "Landmarks should be a dict"
        assert isinstance(data["restaurants"], dict), "Restaurants should be a dict"
        
        # Assert reasonable content amounts
        assert len(data["landmarks"]) > 0, "Should return some landmarks"
        assert len(data["restaurants"]) > 0, "Should return some restaurants"
        
        print(f"✅ Generate endpoint: {response_time:.2f}s, {len(data['landmarks'])} landmarks, {len(data['restaurants'])} restaurants")
    
    def test_complete_itinerary_structure(self):
        """Test that /complete-itinerary returns the correct enhanced structure"""
        
        response = requests.post(f"{self.BASE_URL}/complete-itinerary", json={
            "details": {
                "destination": "San Francisco, CA",
                "travelDays": 1,
                "startDate": "2025-06-15",
                "endDate": "2025-06-15",
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
                            "name": "Golden Gate Bridge",
                            "description": "Iconic suspension bridge",
                            "location": {"lat": 37.8199, "lng": -122.4783},
                            "type": "landmark"
                        }
                    ]
                }
            ]
        }, timeout=15)
        
        # Assert response is successful
        assert response.status_code == 200, f"Complete-itinerary endpoint failed with status {response.status_code}: {response.text}"
        
        # Assert enhanced response structure
        data = response.json()
        assert "itinerary" in data, "Complete-itinerary response missing itinerary"
        assert isinstance(data["itinerary"], list), "Itinerary should be a list"
        assert len(data["itinerary"]) > 0, "Should return itinerary days"
        
        # Check enhanced structure (blocks with timing, restaurants, etc.)
        day_data = data["itinerary"][0]
        assert "day" in day_data, "Day data missing day number"
        assert "blocks" in day_data, "Day data missing blocks"
        assert isinstance(day_data["blocks"], list), "Blocks should be a list"
        
        # Should have enhanced with restaurants and timing
        blocks = day_data["blocks"]
        block_types = [block.get("type") for block in blocks]
        assert "restaurant" in block_types, "Should include restaurant blocks"
        
        # Check timing information
        for block in blocks:
            assert "start_time" in block, f"Block missing start_time: {block}"
            assert "duration" in block, f"Block missing duration: {block}"
        
        print(f"✅ Complete-itinerary endpoint: Enhanced structure with {len(blocks)} blocks")
    
    def test_endpoint_separation(self):
        """Test that the endpoints use different systems and have correct separation of concerns"""
        
        # Test /generate - should be fast and simple
        start = time.time()
        generate_response = requests.post(f"{self.BASE_URL}/generate", json={
            "destination": "Seattle, WA",
            "travel_days": 1,
            "with_kids": False,
            "with_elderly": False
        }, timeout=10)
        generate_time = time.time() - start
        
        assert generate_response.status_code == 200
        generate_data = generate_response.json()
        
        # Test /complete-itinerary - can be slower but enhanced
        complete_response = requests.post(f"{self.BASE_URL}/complete-itinerary", json={
            "details": {
                "destination": "Seattle, WA",
                "travelDays": 1,
                "startDate": "2025-06-15",
                "endDate": "2025-06-15",
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
                            "name": "Seattle Aquarium",
                            "description": "Marine life exhibits",
                            "location": {"lat": 47.6062, "lng": -122.3321},
                            "type": "landmark"
                        }
                    ]
                }
            ]
        }, timeout=15)
        
        assert complete_response.status_code == 200
        complete_data = complete_response.json()
        
        # Assert structural differences
        # Generate: simple dict format
        assert isinstance(generate_data["landmarks"], dict)
        assert isinstance(generate_data["restaurants"], dict)
        
        # Complete: enhanced list format with blocks and timing
        assert isinstance(complete_data["itinerary"], list)
        assert "blocks" in complete_data["itinerary"][0]
        
        # Generate should be fast
        assert generate_time < 5.0, f"Generate took {generate_time:.2f}s, should be under 5s"
        
        print(f"✅ Endpoint separation verified:")
        print(f"   - Generate: {generate_time:.2f}s, simple dict format")
        print(f"   - Complete-itinerary: enhanced list format with timing")
    
    def test_generate_no_agentic_logs(self):
        """Test that /generate doesn't use agentic system by checking it doesn't have enhanced timing data"""
        
        response = requests.post(f"{self.BASE_URL}/generate", json={
            "destination": "Portland, OR",
            "travel_days": 1,
            "with_kids": False,
            "with_elderly": False
        }, timeout=10)
        
        assert response.status_code == 200
        data = response.json()
        
        # Generate should NOT have timing, blocks, or other agentic features
        assert "blocks" not in data, "Generate should not return blocks (agentic feature)"
        assert "performance_metrics" not in data, "Generate should not return performance metrics"
        assert "start_time" not in str(data), "Generate should not have timing data"
        
        # Should have simple landmark/restaurant dict format
        for landmark_name, landmark_data in data["landmarks"].items():
            assert "name" in landmark_data
            assert "description" in landmark_data
            assert "location" in landmark_data
            # Should NOT have timing fields
            assert "start_time" not in landmark_data
            assert "duration" not in landmark_data
            assert "blocks" not in landmark_data
        
        print(f"✅ Generate endpoint confirmed using simple system (no agentic features)")
    
    def test_response_quality(self):
        """Test that both endpoints return quality responses with proper descriptions"""
        
        # Test Generate endpoint quality
        generate_response = requests.post(f"{self.BASE_URL}/generate", json={
            "destination": "New York, NY",
            "travel_days": 1,
            "with_kids": False,
            "with_elderly": False
        }, timeout=10)
        
        assert generate_response.status_code == 200
        generate_data = generate_response.json()
        
        # Check landmark quality
        for landmark_name, landmark_data in generate_data["landmarks"].items():
            desc = landmark_data.get("description", "")
            assert len(desc) > 10, f"Landmark {landmark_name} has too short description: '{desc}'"
            # Should not be just an address
            assert not desc.startswith("ChIJ"), f"Landmark {landmark_name} has place_id as description: '{desc}'"
            assert not any(addr_word in desc.lower() for addr_word in ["street", "avenue", "blvd", "road"]) or len(desc) > 50, \
                f"Landmark {landmark_name} might be using address as description: '{desc}'"
        
        # Check restaurant quality
        for restaurant_name, restaurant_data in generate_data["restaurants"].items():
            desc = restaurant_data.get("description", "")
            assert len(desc) > 10, f"Restaurant {restaurant_name} has too short description: '{desc}'"
            # Should not be just an address
            assert not desc.startswith("ChIJ"), f"Restaurant {restaurant_name} has place_id as description: '{desc}'"
            assert not any(addr_word in desc.lower() for addr_word in ["street", "avenue", "blvd", "road"]) or len(desc) > 50, \
                f"Restaurant {restaurant_name} might be using address as description: '{desc}'"
        
        print(f"✅ Response quality verified:")
        print(f"   - Generate: {len(generate_data['landmarks'])} landmarks, {len(generate_data['restaurants'])} restaurants")
        print(f"   - All descriptions are proper (not addresses or place IDs)")
    
    def test_performance_requirements(self):
        """Test overall performance requirements"""
        
        # Generate should be consistently fast (multiple runs)
        # Use real destinations that will geocode successfully
        destinations = ["San Francisco, CA", "Seattle, WA", "Portland, OR"]
        times = []
        for i in range(3):
            start = time.time()
            response = requests.post(f"{self.BASE_URL}/generate", json={
                "destination": destinations[i],
                "travel_days": 1,
                "with_kids": False,
                "with_elderly": False
            }, timeout=10)
            times.append(time.time() - start)
            assert response.status_code == 200
        
        avg_time = sum(times) / len(times)
        max_time = max(times)
        
        assert avg_time < 3.0, f"Generate average time {avg_time:.2f}s should be under 3s"
        assert max_time < 5.0, f"Generate max time {max_time:.2f}s should be under 5s"
        
        print(f"✅ Performance requirements met:")
        print(f"   - Generate times: {[f'{t:.2f}s' for t in times]}")
        print(f"   - Average: {avg_time:.2f}s, Max: {max_time:.2f}s")

if __name__ == "__main__":
    # Run tests directly
    test_instance = TestEndpointPerformance()
    print("🚀 Running endpoint performance tests...")
    
    try:
        test_instance.test_server_is_running()
        test_instance.test_generate_is_fast()
        test_instance.test_complete_itinerary_structure()
        test_instance.test_endpoint_separation()
        test_instance.test_generate_no_agentic_logs()
        test_instance.test_response_quality()
        test_instance.test_performance_requirements()
        print("\n✅ All tests passed! Endpoint separation is working correctly.")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        raise 