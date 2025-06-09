import requests
import json

# Test endpoint
url = "http://localhost:8000/generate"

# Test payloads
test_cases = [
    {
        "name": "Single kid array format",
        "payload": {
            "destination": "Dallas, TX",
            "travel_days": 3,
            "with_kids": True,
            "kids_age": [5],
            "with_elderly": False
        }
    },
    {
        "name": "Multiple kids same age",
        "payload": {
            "destination": "Dallas, TX",
            "travel_days": 3,
            "with_kids": True,
            "kids_age": [7, 7],
            "with_elderly": False
        }
    },
    {
        "name": "Multiple kids different ages",
        "payload": {
            "destination": "Dallas, TX",
            "travel_days": 3,
            "with_kids": True,
            "kids_age": [3, 8, 14],
            "with_elderly": False
        }
    },
    {
        "name": "Backward compatibility - single number",
        "payload": {
            "destination": "Dallas, TX",
            "travel_days": 3,
            "with_kids": True,
            "kids_age": 5,  # Single number instead of array
            "with_elderly": False
        }
    }
]

def test_endpoint():
    print("🧪 Testing /generate endpoint with different kids_age formats...\n")
    
    for test in test_cases:
        print(f"📋 Test: {test['name']}")
        print(f"   Payload: {json.dumps(test['payload'], indent=2)}")
        
        try:
            response = requests.post(url, json=test['payload'])
            
            if response.status_code == 200:
                print(f"   ✅ Status: {response.status_code}")
                result = response.json()
                
                # Check if itinerary was generated
                if "itinerary" in result and "Suggested_Things_to_Do" in result["itinerary"]:
                    count = len(result["itinerary"]["Suggested_Things_to_Do"])
                    print(f"   📍 Generated {count} recommendations")
                elif "error" in result.get("itinerary", {}):
                    print(f"   ⚠️  Error: {result['itinerary']['error']}")
                else:
                    print(f"   ❌ Unexpected response format")
            else:
                print(f"   ❌ Status: {response.status_code}")
                print(f"   Error: {response.text}")
                
        except Exception as e:
            print(f"   ❌ Exception: {str(e)}")
            
        print()

if __name__ == "__main__":
    test_endpoint() 