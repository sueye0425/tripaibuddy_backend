#!/usr/bin/env python3
import os
import sys
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, Any
from dotenv import load_dotenv
from test_setup import test_redis, test_openai, test_google_places, test_pinecone
from pinecone import Pinecone

class EndpointTester:
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url
        self.session = requests.Session()

    def test_health(self) -> bool:
        """Test health check endpoint"""
        print("\n🏥 Testing health check endpoint...")
        try:
            response = self.session.get(f"{self.base_url}/_ah/health")
            response.raise_for_status()
            print("✅ Health check successful")
            print(f"Response: {response.json()}")
            return True
        except Exception as e:
            print(f"❌ Health check failed: {str(e)}")
            return False

    def test_generate_recommendations(self) -> Dict[str, Any]:
        """Test /generate endpoint"""
        print("\n🎯 Testing /generate endpoint...")
        
        # Test case 1: Basic request
        payload = {
            "destination": "Sydney, Australia",
            "travel_days": 3,
            "with_kids": False,
            "with_elderly": False
        }
        
        try:
            response = self.session.post(f"{self.base_url}/generate", json=payload)
            response.raise_for_status()
            result = response.json()
            
            # Validate response structure
            self._validate_generate_response(result)
            print("✅ Basic recommendation test successful")
            return result
        except Exception as e:
            print(f"❌ Recommendation test failed: {str(e)}")
            return {}

    def test_generate_with_dates(self) -> Dict[str, Any]:
        """Test /generate endpoint with dates"""
        print("\n📅 Testing /generate with dates...")
        
        # Calculate dates for next week
        start_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        end_date = (datetime.now() + timedelta(days=10)).strftime('%Y-%m-%d')
        
        payload = {
            "destination": "Sydney, Australia",
            "travel_days": 4,  # Set travel days to match the date range
            "start_date": start_date,
            "end_date": end_date,
            "with_kids": True,
            "kids_age": [5, 8],
            "with_elderly": True,
            "special_requests": "Looking for family-friendly activities and wheelchair accessible places"
        }
        
        try:
            response = self.session.post(f"{self.base_url}/generate", json=payload)
            response.raise_for_status()
            result = response.json()
            
            self._validate_generate_response(result)
            print("✅ Date-based recommendation test successful")
            return result
        except Exception as e:
            print(f"❌ Date-based recommendation test failed: {str(e)}")
            return {}

    def test_complete_itinerary(self, landmarks: list) -> Dict[str, Any]:
        """Test /complete-itinerary endpoint"""
        print("\n📋 Testing /complete-itinerary endpoint...")
        
        payload = {
            "destination": "Sydney, Australia",
            "travel_days": 3,
            "with_kids": False,
            "with_elderly": False,
            "selected_landmarks": landmarks
        }
        
        try:
            response = self.session.post(f"{self.base_url}/complete-itinerary", json=payload)
            response.raise_for_status()
            result = response.json()
            
            self._validate_itinerary_response(result)
            print("✅ Itinerary completion test successful")
            return result
        except Exception as e:
            print(f"❌ Itinerary completion test failed: {str(e)}")
            return {}

    def _validate_generate_response(self, response: Dict[str, Any]):
        """Validate the structure of /generate response"""
        required_keys = ["landmarks", "restaurants"]
        for key in required_keys:
            if key not in response:
                raise ValueError(f"Missing required key: {key}")
            
            items = response[key]
            if not isinstance(items, dict):
                raise ValueError(f"{key} should be a dictionary")
            
            # Check first item's structure
            if items:
                first_item = next(iter(items.values()))
                required_fields = ["description", "place_id", "rating", "location", "photos"]
                for field in required_fields:
                    if field not in first_item:
                        raise ValueError(f"Missing required field in {key}: {field}")

    def _validate_itinerary_response(self, response: Dict[str, Any]):
        """Validate the structure of /complete-itinerary response"""
        if not isinstance(response, dict):
            raise ValueError("Response should be a dictionary")
            
        for day, plan in response.get("root", {}).items():
            if not isinstance(plan, dict):
                raise ValueError(f"Day plan for {day} should be a dictionary")
            
            required_fields = ["morning", "afternoon", "evening"]
            for field in required_fields:
                if field not in plan:
                    raise ValueError(f"Missing required field in day plan: {field}")

def print_response_example(response: Dict[str, Any], title: str):
    """Print a formatted example of the response"""
    print(f"\n📝 {title}")
    print("=" * (len(title) + 4))
    print(json.dumps(response, indent=2))

def main():
    # First test all API connections
    print("🔍 Testing API Connections")
    print("=========================")
    test_redis()
    test_openai()
    test_google_places()
    test_pinecone()

    # Then test endpoints
    print("\n🔍 Testing Endpoints")
    print("===================")
    
    # Get the base URL from environment or use default
    base_url = os.getenv("API_BASE_URL", "http://localhost:8080")
    tester = EndpointTester(base_url)
    
    # Run tests
    tester.test_health()
    
    # Test recommendations
    basic_result = tester.test_generate_recommendations()
    if basic_result:
        print_response_example(basic_result, "Basic Recommendation Response Example")
    
    date_result = tester.test_generate_with_dates()
    if date_result:
        print_response_example(date_result, "Date-based Recommendation Response Example")
    
    # Test itinerary completion if we have landmarks
    if basic_result and basic_result.get("landmarks"):
        landmarks = list(basic_result["landmarks"].keys())[:3]  # Take first 3 landmarks
        itinerary_result = tester.test_complete_itinerary(landmarks)
        if itinerary_result:
            print_response_example(itinerary_result, "Complete Itinerary Response Example")

if __name__ == "__main__":
    # Load environment variables
    load_dotenv()
    INDEX_NAME = os.getenv("INDEX_NAME")
    if not INDEX_NAME:
        raise ValueError("INDEX_NAME environment variable is not set")
    pc = Pinecone(api_key=os.environ.get("PINECONE_API_KEY"))
    main() 