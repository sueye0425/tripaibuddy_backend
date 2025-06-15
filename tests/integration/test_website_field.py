import requests
import json

def test_website_field_inclusion():
    """Test that restaurants in /complete-itinerary response include website field"""
    
    # Test payload
    payload = {
        "details": {
            "destination": "San Diego, CA",
            "travelDays": 1,
            "startDate": "2025-06-10",
            "endDate": "2025-06-10",
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
                        "name": "Balboa Park",
                        "description": "Large cultural park",
                        "location": {"lat": 32.7341479, "lng": -117.1498161},
                        "type": "landmark"
                    }
                ]
            }
        ]
    }
    
    # Make API request
    response = requests.post(
        'http://127.0.0.1:8000/complete-itinerary',
        json=payload,
        timeout=30
    )
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    data = response.json()
    
    # Extract restaurants
    restaurants_found = 0
    restaurants_with_websites = 0
    
    # Handle the nested response structure
    itinerary_data = data.get("itinerary", {})
    if isinstance(itinerary_data, dict) and "itinerary" in itinerary_data:
        days_list = itinerary_data["itinerary"]
    else:
        days_list = itinerary_data if isinstance(itinerary_data, list) else []
    
    for day in days_list:
        for block in day.get("blocks", []):
            if block.get("type") == "restaurant":
                restaurants_found += 1
                name = block.get("name", "Unknown")
                website = block.get("website")
                
                print(f"🍽️  Restaurant: {name}")
                print(f"   Website: {website}")
                print(f"   Description: {block.get('description', 'No description')[:60]}...")
                
                # Check if website field exists (can be None for restaurants without websites)
                assert "website" in block, f"Restaurant {name} missing website field"
                
                # Count restaurants with actual website URLs
                if website and website.startswith(('http://', 'https://')):
                    restaurants_with_websites += 1
                    print(f"   ✅ Has valid website URL")
                else:
                    print(f"   ⚪ No website URL available")
                print()
    
    # Assertions
    assert restaurants_found > 0, "Should find at least one restaurant"
    print(f"🎯 Test Results:")
    print(f"   • Total restaurants found: {restaurants_found}")
    print(f"   • Restaurants with website URLs: {restaurants_with_websites}")
    print(f"   • All restaurants have 'website' field: ✅")
    
    if restaurants_with_websites > 0:
        print(f"   • At least one restaurant has clickable website: ✅")
    else:
        print(f"   • No restaurants have website URLs (this is okay if Google Places doesn't provide them)")
    
    print("\n✅ Website field test passed!")
    return True

if __name__ == "__main__":
    test_website_field_inclusion() 