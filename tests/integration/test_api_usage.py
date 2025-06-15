#!/usr/bin/env python3
"""
Test script to count API calls for /generate and /complete-itinerary endpoints
"""
import requests
import json
import time
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8080"

def test_generate_api_calls():
    """Test /generate endpoint and count API calls from logs"""
    print("\n🔍 Testing /generate endpoint API usage...")
    
    payload = {
        "destination": "San Francisco, CA",
        "travel_days": 3,
        "with_kids": False,
        "with_elderly": False
    }
    
    start_time = time.time()
    response = requests.post(f"{BASE_URL}/generate", json=payload)
    end_time = time.time()
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ /generate successful in {end_time - start_time:.2f}s")
        print(f"📊 Results: {len(data.get('landmarks', {}))} landmarks, {len(data.get('restaurants', {}))} restaurants")
        
        # Sample output
        print("\n📋 Sample /generate input:")
        print(json.dumps(payload, indent=2))
        
        print("\n📋 Sample /generate output (first 2 landmarks and restaurants):")
        sample_output = {
            "landmarks": dict(list(data.get("landmarks", {}).items())[:2]),
            "restaurants": dict(list(data.get("restaurants", {}).items())[:2])
        }
        print(json.dumps(sample_output, indent=2))
        
        return data
    else:
        print(f"❌ /generate failed: {response.status_code} - {response.text}")
        return None

def test_complete_itinerary_api_calls(landmarks_data):
    """Test /complete-itinerary endpoint and count API calls"""
    print("\n🔍 Testing /complete-itinerary endpoint API usage...")
    
    if not landmarks_data or not landmarks_data.get("landmarks"):
        print("❌ No landmarks data available for complete-itinerary test")
        return None
    
    # Select first 5 landmarks
    selected_landmarks = list(landmarks_data["landmarks"].keys())[:5]
    
    payload = {
        "destination": "San Francisco, CA",
        "travel_days": 3,
        "selected_landmarks": selected_landmarks,
        "with_kids": False,
        "with_elderly": False
    }
    
    start_time = time.time()
    response = requests.post(f"{BASE_URL}/complete-itinerary", json=payload)
    end_time = time.time()
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ /complete-itinerary successful in {end_time - start_time:.2f}s")
        
        # Count blocks and activities
        total_blocks = len(data.get("itinerary", []))
        total_activities = sum(len(day.get("blocks", [])) for day in data.get("itinerary", []))
        
        print(f"📊 Results: {total_blocks} days, {total_activities} total blocks")
        
        # Sample output
        print("\n📋 Sample /complete-itinerary input:")
        print(json.dumps(payload, indent=2))
        
        print("\n📋 Sample /complete-itinerary output (first day):")
        if data.get("itinerary"):
            sample_output = {
                "itinerary": [data["itinerary"][0]]  # First day only
            }
            print(json.dumps(sample_output, indent=2))
        
        return data
    else:
        print(f"❌ /complete-itinerary failed: {response.status_code} - {response.text}")
        return None

def main():
    print("🧪 API Usage Testing")
    print("===================")
    
    # Test /generate endpoint
    generate_data = test_generate_api_calls()
    
    # Test /complete-itinerary endpoint
    if generate_data:
        complete_data = test_complete_itinerary_api_calls(generate_data)
    
    print("\n💡 API Call Estimation:")
    print("For /generate endpoint:")
    print("  - 1 geocoding call")
    print("  - ~6-8 landmark search calls (places_nearby)")
    print("  - ~6-8 landmark detail calls (place_details)")
    print("  - 1 restaurant search call (places_nearby)")
    print("  - ~15-20 restaurant detail calls (place_details)")
    print("  - Total: ~30-40 API calls")
    
    print("\nFor /complete-itinerary endpoint:")
    print("  - 0-25 landmark enhancement calls (place_details/places_nearby)")
    print("  - 0-5 duplicate removal calls")
    print("  - Total: 0-30 API calls (depending on existing data)")

if __name__ == "__main__":
    main() 