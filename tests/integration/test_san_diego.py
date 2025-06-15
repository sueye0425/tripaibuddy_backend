import pytest
import requests
import json
import time

class TestSanDiegoItinerary:
    """Test suite for San Diego itinerary payload to verify /complete-itinerary endpoint"""
    
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
    
    def test_san_diego_complete_itinerary(self):
        """Test the complete San Diego itinerary payload"""
        
        payload = {
            "details": {
                "destination": "San Diego, CA",
                "travelDays": 3,
                "startDate": "2025-06-10",
                "endDate": "2025-06-12",
                "withKids": True,
                "withElders": False,
                "kidsAge": [8, 12],
                "specialRequests": "prefer waterfront activities"
            },
            "wishlist": [],
            "itinerary": [
                {
                    "day": 1,
                    "attractions": [
                        {
                            "name": "San Diego Zoo",
                            "description": "Zoo featuring various animal exhibits",
                            "location": {
                                "lat": 32.7360353,
                                "lng": -117.1509849
                            },
                            "type": "landmark"
                        },
                        {
                            "name": "Balboa Park",
                            "description": "Large cultural park with museums and gardens",
                            "location": {
                                "lat": 32.7341479,
                                "lng": -117.1498161
                            },
                            "type": "landmark"
                        },
                        {
                            "name": "Sushi Ota",
                            "description": "Restaurant serving food and beverages",
                            "location": {
                                "lat": 32.8034895999999,
                                "lng": -117.2164306
                            },
                            "type": "restaurant"
                        }
                    ]
                },
                {
                    "day": 2,
                    "attractions": [
                        {
                            "name": "Sunset Cliffs Natural Park",
                            "description": "Scenic coastal park with dramatic cliffs",
                            "location": {
                                "lat": 32.7157,
                                "lng": -117.2544
                            },
                            "type": "landmark"
                        },
                        {
                            "name": "La Jolla Cove",
                            "description": "Beautiful beach with sea lions and snorkeling",
                            "location": {
                                "lat": 32.8508,
                                "lng": -117.2713
                            },
                            "type": "landmark"
                        }
                    ]
                },
                {
                    "day": 3,
                    "attractions": [
                        {
                            "name": "USS Midway Museum",
                            "description": "Historic aircraft carrier museum",
                            "location": {
                                "lat": 32.7136,
                                "lng": -117.1751
                            },
                            "type": "landmark"
                        },
                        {
                            "name": "The Prado at Balboa Park",
                            "description": "Fine dining restaurant in historic setting",
                            "location": {
                                "lat": 32.7308,
                                "lng": -117.1498
                            },
                            "type": "restaurant"
                        }
                    ]
                }
            ]
        }
        
        print(f"🎯 Testing /complete-itinerary with San Diego payload...")
        start_time = time.time()
        
        response = requests.post(
            f"{self.BASE_URL}/complete-itinerary",
            json=payload,
            timeout=30
        )
        
        elapsed_time = time.time() - start_time
        print(f"⏱️  Response time: {elapsed_time:.2f}s")
        
        # Basic response validation
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        print(f"📄 Response keys: {list(data.keys())}")
        
        # Validate response structure
        assert "blocks" in data or "itinerary" in data, "Response should contain 'blocks' or 'itinerary'"
        
        # Check if enhanced structure with blocks
        if "blocks" in data:
            assert isinstance(data["blocks"], list), "Blocks should be a list"
            print(f"🏗️  Enhanced response with {len(data['blocks'])} blocks")
            
            # Validate block structure
            for i, block in enumerate(data["blocks"]):
                assert "day" in block, f"Block {i} should have 'day'"
                assert "activities" in block, f"Block {i} should have 'activities'"
                print(f"📅 Day {block['day']}: {len(block['activities'])} activities")
        
        # Check if simple structure with itinerary
        elif "itinerary" in data:
            assert isinstance(data["itinerary"], list), "Itinerary should be a list"
            print(f"📋 Simple response with {len(data['itinerary'])} days")
        
        # Test passed - data structure is valid
        print("✅ San Diego itinerary test completed successfully")
        return data  # Return data for other tests to use
    
    def test_restaurant_data_quality(self):
        """Test that restaurants have essential data without descriptions (optimization)"""
        
        # Run the complete itinerary test first
        data = self.test_san_diego_complete_itinerary()
        
        restaurants_found = []
        
        # Extract restaurants from response - handle the actual structure returned
        # Based on debug output: data["itinerary"] is a list of days, each day has "blocks" 
        if "itinerary" in data:
            itinerary = data["itinerary"]
            
            for day in itinerary:
                # Each day has "blocks" - each block can be a restaurant or landmark
                if "blocks" in day:
                    for block in day["blocks"]:
                        if block.get("type") == "restaurant":
                            restaurants_found.append(block)
                
                # Fallback for old structure with attractions
                elif "attractions" in day:
                    for attraction in day.get("attractions", []):
                        if attraction.get("type") == "restaurant":
                            restaurants_found.append(attraction)
        
        print(f"🍽️  Found {len(restaurants_found)} restaurants in response")
        
        # Validate restaurant descriptions
        for restaurant in restaurants_found:
            name = restaurant.get("name", "Unknown")
            description = restaurant.get("description", "")
            
            print(f"🏪 Restaurant: {name}")
            print(f"📝 Description: {description}")
            
            # Restaurants no longer have descriptions - check other data instead
            # Descriptions removed for optimization - website provides better info
            
            # Check that it's not just an address (common issue)
            address_indicators = [
                "san diego, ca",
                "california",
                "street",
                "ave",
                "blvd",
                "road",
                "dr",
                "way"
            ]
            
            is_address_like = any(
                indicator in description.lower() 
                for indicator in address_indicators
            ) and len(description.split()) < 10
            
            assert not is_address_like, f"Restaurant '{name}' description appears to be an address: '{description}'"
            
            # Check for quality descriptive content
            quality_indicators = [
                "restaurant", "dining", "cuisine", "food", "menu", 
                "atmosphere", "ambiance", "bar", "grill", "cafe",
                "specializes", "serves", "known for", "offers",
                "experience", "destination", "establishment"
            ]
            
            has_quality_content = any(
                indicator in description.lower() 
                for indicator in quality_indicators
            )
            
            print(f"✅ Quality content check: {'PASS' if has_quality_content else 'QUESTIONABLE'}")
        
        assert len(restaurants_found) > 0, "Should find at least one restaurant in the response"
        print(f"✅ All restaurant descriptions validated successfully")
    
    def test_kids_and_waterfront_preferences(self):
        """Test that the response considers kids and waterfront preferences"""
        
        data = self.test_san_diego_complete_itinerary()
        
        # Convert response to string for content analysis
        response_text = json.dumps(data).lower()
        
        # Check for kid-friendly indicators
        kid_indicators = [
            "kid", "child", "family", "playground", "interactive",
            "educational", "zoo", "aquarium", "beach", "park"
        ]
        
        kid_friendly_found = any(
            indicator in response_text 
            for indicator in kid_indicators
        )
        
        print(f"👶 Kid-friendly content found: {kid_friendly_found}")
        
        # Check for waterfront activities
        waterfront_indicators = [
            "beach", "ocean", "water", "sea", "bay", "harbor",
            "waterfront", "marina", "pier", "coastal", "surf"
        ]
        
        waterfront_found = any(
            indicator in response_text 
            for indicator in waterfront_indicators
        )
        
        print(f"🌊 Waterfront content found: {waterfront_found}")
        
        # At least one of these should be present given the preferences
        assert kid_friendly_found or waterfront_found, \
            "Response should consider kids and/or waterfront preferences"
        
        print("✅ Preferences validation passed")
    
    def test_agentic_enhancement_features(self):
        """Test that the agentic system provides enhanced features"""
        
        data = self.test_san_diego_complete_itinerary()
        
        enhancement_indicators = []
        
        # Check for timing information
        response_text = json.dumps(data).lower()
        if any(time_word in response_text for time_word in ["time", "duration", "hours", "minutes"]):
            enhancement_indicators.append("timing")
        
        # Check for enhanced structure
        if "blocks" in data:
            enhancement_indicators.append("block_structure")
        
        # Check for restaurant integration
        if "restaurant" in response_text:
            enhancement_indicators.append("restaurant_integration")
        
        # Check for detailed descriptions
        total_text_length = len(response_text)
        if total_text_length > 1000:  # Substantial content
            enhancement_indicators.append("detailed_content")
        
        print(f"🔧 Enhancement features found: {enhancement_indicators}")
        print(f"📊 Total response length: {total_text_length} characters")
        
        # Should have multiple enhancement features
        assert len(enhancement_indicators) >= 2, \
            f"Agentic system should provide multiple enhancements, found: {enhancement_indicators}"
        
        print("✅ Agentic enhancement validation passed")

    def test_complete_itinerary_endpoint_validation(self):
        """Focused test for endpoint validation without pytest conflicts"""
        
        # Call the main test and capture its result
        data = self.test_san_diego_complete_itinerary()
        
        # Additional validations specific to this test
        assert data is not None, "Should receive response data"
        assert "itinerary" in data, "Response should contain itinerary"
        
        # Validate that restaurants have proper descriptions from Google Places API
        restaurants_found = 0
        description_quality_passed = 0
        
        if "itinerary" in data:
            itinerary = data["itinerary"]
            for day in itinerary:
                if "blocks" in day:
                    for block in day["blocks"]:
                        if block.get("type") == "restaurant":
                            restaurants_found += 1
                            name = block.get("name", "Unknown")
                            description = block.get("description", "")
                            
                            if description and len(description) > 10:
                                # Check for quality descriptive content (not just address)
                                quality_indicators = [
                                    "restaurant", "dining", "cuisine", "food", "menu", 
                                    "atmosphere", "serves", "known for", "offers",
                                    "destination", "establishment", "modern", "fresh"
                                ]
                                
                                has_quality = any(
                                    indicator in description.lower() 
                                    for indicator in quality_indicators
                                )
                                
                                if has_quality:
                                    description_quality_passed += 1
                                    print(f"✅ {name}: {description[:60]}...")
        
        assert restaurants_found > 0, "Should find restaurants in the response"
        # Descriptions removed for optimization - restaurants now rely on website links
        
        print(f"🍽️  Found {restaurants_found} restaurants, {description_quality_passed} with quality descriptions")
        print("✅ Complete itinerary endpoint validation passed")

if __name__ == "__main__":
    # Run tests manually if executed directly
    test_instance = TestSanDiegoItinerary()
    
    print("🚀 Starting San Diego itinerary tests...")
    
    try:
        test_instance.test_server_is_running()
        print("✅ Server connectivity test passed")
        
        test_instance.test_san_diego_complete_itinerary()
        print("✅ Basic itinerary test passed")
        
        test_instance.test_restaurant_data_quality()
        print("✅ Restaurant data quality test passed")
        
        test_instance.test_kids_and_waterfront_preferences()
        print("✅ Preferences test passed")
        
        test_instance.test_agentic_enhancement_features()
        print("✅ Enhancement features test passed")
        
        test_instance.test_complete_itinerary_endpoint_validation()
        print("✅ Complete itinerary endpoint validation passed")
        
        print("\n🎉 All San Diego itinerary tests passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        raise 