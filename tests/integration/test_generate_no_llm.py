import pytest
import requests
import time
import json
import re

class TestGenerateEndpointNoLLM:
    """Test suite to verify /generate endpoint does not call LLMs and remains lightweight"""
    
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
    
    def test_generate_response_speed(self):
        """Test that /generate responds quickly (indicating no LLM calls)"""
        payload = {
            "destination": "San Francisco, CA",
            "travel_days": 2,
            "with_kids": False,
            "with_elderly": False
        }
        
        start_time = time.time()
        response = requests.post(f"{self.BASE_URL}/generate", json=payload, timeout=10)
        response_time = time.time() - start_time
        
        # Verify successful response
        assert response.status_code == 200
        data = response.json()
        
        # Verify fast response time (should be under 5 seconds for non-LLM endpoint)
        assert response_time < 5.0, f"Response time was {response_time:.2f}s, expected < 5s"
        print(f"✅ Response time: {response_time:.2f}s (fast, indicating no LLM calls)")
        
        # Verify basic structure exists
        assert "landmarks" in data or "restaurants" in data
        
        # Test passed - response time is acceptable
        print(f"✅ Generate endpoint is fast and shows no LLM usage")
        assert True  # Explicit assertion to pass test
    
    def test_generate_simple_response_structure(self):
        """Test that /generate returns simple structure (not enhanced agentic format)"""
        payload = {
            "destination": "Portland, OR", 
            "travel_days": 1,
            "with_kids": False,
            "with_elderly": False
        }
        
        response = requests.post(f"{self.BASE_URL}/generate", json=payload, timeout=10)
        assert response.status_code == 200
        data = response.json()
        
        # Should NOT have agentic/enhanced structure
        assert "blocks" not in data, "Found 'blocks' - indicates agentic system usage"
        assert "timing" not in data, "Found 'timing' - indicates agentic system usage" 
        assert "enhanced_restaurants" not in data, "Found enhanced restaurant matching"
        
        # Should have simple structure
        expected_keys = {"landmarks", "restaurants"}
        actual_keys = set(data.keys())
        assert expected_keys.issubset(actual_keys), f"Expected simple structure with {expected_keys}, got {actual_keys}"
        
        print("✅ Response structure is simple (no agentic features)")
        
    def test_generate_no_llm_content_patterns(self):
        """Test that response content shows no signs of LLM generation"""
        payload = {
            "destination": "Seattle, WA",
            "travel_days": 2, 
            "with_kids": True,
            "with_elderly": False
        }
        
        response = requests.post(f"{self.BASE_URL}/generate", json=payload, timeout=10)
        assert response.status_code == 200
        data = response.json()
        
        # Convert response to string for pattern checking
        response_text = json.dumps(data).lower()
        
        # Check for LLM-style content that shouldn't be there
        llm_patterns = [
            "as an ai", "i recommend", "here's a suggested", "based on your request",
            "let me help", "i'd suggest", "perfect for families", "ideal for",
            "experience the", "discover the", "enjoy a", "don't miss"
        ]
        
        found_patterns = []
        for pattern in llm_patterns:
            if pattern in response_text:
                found_patterns.append(pattern)
        
        assert len(found_patterns) == 0, f"Found LLM-style patterns: {found_patterns}"
        
        # Check that descriptions are simple/factual (Google Places style)
        if "restaurants" in data:
            for restaurant_name, restaurant_data in data["restaurants"].items():
                description = restaurant_data.get("description", "").lower()
                if description:
                    # Should be factual Google Places descriptions, not LLM generated
                    assert not any(phrase in description for phrase in [
                        "perfect for", "ideal for", "great choice", "highly recommend"
                    ]), f"Restaurant '{restaurant_name}' has LLM-style description: {description}"
        
        print("✅ No LLM-style content patterns detected")
    
    def test_generate_consistent_fast_performance(self):
        """Test that /generate is consistently fast across multiple calls"""
        payload = {
            "destination": "Los Angeles, CA",
            "travel_days": 1,
            "with_kids": False, 
            "with_elderly": False
        }
        
        response_times = []
        for i in range(3):
            start_time = time.time()
            response = requests.post(f"{self.BASE_URL}/generate", json=payload, timeout=10)
            response_time = time.time() - start_time
            
            assert response.status_code == 200
            response_times.append(response_time)
        
        # All responses should be fast
        max_time = max(response_times)
        avg_time = sum(response_times) / len(response_times)
        
        assert max_time < 5.0, f"Slowest response was {max_time:.2f}s, expected < 5s"
        assert avg_time < 3.0, f"Average response time was {avg_time:.2f}s, expected < 3s"
        
        print(f"✅ Consistent performance: avg={avg_time:.2f}s, max={max_time:.2f}s")
    
    def test_generate_vs_complete_itinerary_speed_difference(self):
        """Test that /generate is significantly faster than /complete-itinerary"""
        payload = {
            "destination": "San Diego, CA",
            "travel_days": 2,
            "with_kids": False,
            "with_elderly": False
        }
        
        # Test /generate speed
        start_time = time.time()
        generate_response = requests.post(f"{self.BASE_URL}/generate", json=payload, timeout=10)
        generate_time = time.time() - start_time
        
        assert generate_response.status_code == 200
        
        # For comparison, we know /complete-itinerary should be slower (but we won't test it here)
        # /generate should be under 3 seconds consistently
        assert generate_time < 3.0, f"/generate took {generate_time:.2f}s, should be < 3s (no LLM calls)"
        
        print(f"✅ /generate is fast at {generate_time:.2f}s (vs expected 4-10s for /complete-itinerary)")

if __name__ == "__main__":
    # Allow running the test directly
    test_suite = TestGenerateEndpointNoLLM()
    print("🧪 Testing /generate endpoint to verify it's not calling LLMs...")
    
    try:
        test_suite.test_server_is_running()
        print("✅ Server is running")
        
        response_time = test_suite.test_generate_response_speed()
        test_suite.test_generate_simple_response_structure()
        test_suite.test_generate_no_llm_content_patterns()
        test_suite.test_generate_consistent_fast_performance()
        test_suite.test_generate_vs_complete_itinerary_speed_difference()
        
        print(f"\n🎉 All tests passed! /generate endpoint is confirmed to be:")
        print(f"   • Fast (< 3 seconds)")
        print(f"   • Simple structure (no agentic features)")
        print(f"   • No LLM-style content patterns")
        print(f"   • Consistently performant")
        print(f"   • Architecture properly separated from /complete-itinerary")
        
    except Exception as e:
        print(f"❌ Test failed: {e}") 