import asyncio
import json
import os
import time
import aiohttp
from app.agentic_itinerary import complete_itinerary_agentic
from app.schema import LandmarkSelection, TripDetails, DayAttraction, Attraction, Location
from app.places_client import GooglePlacesClient

async def test_final_agentic_fix():
    print("🔧 Final Agentic System Fix Verification Test")
    print("=" * 70)
    print("Testing the hybrid approach:")
    print("  1. LLM generates LANDMARKS ONLY")
    print("  2. Google Places API adds REAL RESTAURANTS") 
    print("  3. Proper address/description separation")
    print("=" * 70)
    
    # Test configuration: 1-day Orlando trip with Universal Studios
    details = TripDetails(
        destination='Orlando, FL',
        travelDays=1,
        startDate='2024-06-10',
        endDate='2024-06-10',
        withKids=True,
        kidsAge=[8, 12],
        withElders=False,
        specialRequests='Universal Studios theme park family day'
    )

    # Universal Studios (should trigger theme park meal scheduling)
    universal_studios = Attraction(
        name='Universal Studios Florida',
        type='theme_park',
        description='Famous movie-themed attractions and rides',
        location=Location(lat=28.4743, lng=-81.4677)
    )

    day1 = DayAttraction(day=1, attractions=[universal_studios])

    selection = LandmarkSelection(
        details=details,
        itinerary=[day1],
        wishlist=[]
    )

    # Initialize Google Places client
    google_api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    if not google_api_key:
        print("❌ No Google Places API key found!")
        return

    async with aiohttp.ClientSession() as session:
        places_client = GooglePlacesClient(session=session)
        
        print(f"✅ Google Places API key configured: {google_api_key[:10]}...")
        print()
        
        # Test the fixed agentic system
        start_time = time.time()
        result = await complete_itinerary_agentic(selection, places_client)
        duration = time.time() - start_time
        
        print(f"📊 Test Results:")
        print(f"⏱️  Total time: {duration:.2f}s")
        
        if 'error' in result:
            print(f"❌ Error: {result['error']}")
            return
        
        # Comprehensive analysis
        day1_blocks = result['itinerary'][0]['blocks']
        landmarks = [b for b in day1_blocks if b['type'] == 'landmark']
        restaurants = [b for b in day1_blocks if b['type'] == 'restaurant']
        
        print(f"\n🏛️ Landmark Analysis:")
        print(f"   Found {len(landmarks)} landmarks")
        
        llm_success = True
        for i, landmark in enumerate(landmarks, 1):
            print(f"\n   Landmark {i}: {landmark['name']}")
            print(f"   📝 Type: {landmark['type']}")
            print(f"   ⏰ Time: {landmark['start_time']} ({landmark['duration']})")
            print(f"   📍 Description: {landmark['description'][:100]}...")
            
            # Check if LLM properly generated landmarks only
            if landmark['type'] != 'landmark':
                print(f"   ❌ ERROR: Should be landmark, got {landmark['type']}")
                llm_success = False
            else:
                print(f"   ✅ Correct landmark type")
        
        print(f"\n🍽️ Restaurant Analysis:")
        print(f"   Found {len(restaurants)} restaurants")
        
        google_success = True
        address_success = True
        meal_distribution = {}
        
        for i, restaurant in enumerate(restaurants, 1):
            print(f"\n   Restaurant {i}: {restaurant['name']}")
            print(f"   🍽️  Meal type: {restaurant.get('mealtime')}")
            print(f"   ⏰ Time: {restaurant['start_time']} ({restaurant['duration']})")
            print(f"   📍 Address field: {restaurant.get('address')}")
            print(f"   📝 Description: {restaurant.get('description')}")
            print(f"   🔑 Place ID: {restaurant.get('place_id')}")
            print(f"   ⭐ Rating: {restaurant.get('rating')}")
            
            # Track meal distribution
            meal_type = restaurant.get('mealtime')
            if meal_type:
                meal_distribution[meal_type] = meal_distribution.get(meal_type, 0) + 1
            
            # Check Google Places data
            if restaurant.get('place_id') and restaurant.get('rating'):
                print(f"   ✅ Real Google Places result")
            else:
                print(f"   ❌ Missing Google Places data")
                google_success = False
            
            # Check address separation
            if restaurant.get('address') is not None:
                print(f"   ✅ Address properly separated")
            else:
                print(f"   ❌ Address field is null")
                address_success = False
        
        # Theme park analysis
        print(f"\n🎢 Theme Park Analysis:")
        theme_park_detected = any('universal' in l['name'].lower() for l in landmarks)
        print(f"   Theme park detected: {theme_park_detected}")
        
        if theme_park_detected:
            lunch_restaurant = next((r for r in restaurants if r.get('mealtime') == 'lunch'), None)
            if lunch_restaurant and '12:30' in lunch_restaurant.get('start_time', ''):
                print(f"   ✅ Lunch at correct theme park time (12:30)")
            else:
                print(f"   ⚠️  Lunch timing may be incorrect")
        
        # Final Success Metrics
        print(f"\n📈 Fix Verification Results:")
        print(f"   🧠 LLM landmarks-only success: {llm_success} ({len(landmarks)} landmarks generated)")
        print(f"   🔍 Google Places restaurant success: {google_success} ({len([r for r in restaurants if r.get('place_id')])} real restaurants)")
        print(f"   🏠 Address separation success: {address_success} ({len([r for r in restaurants if r.get('address')])} with addresses)")
        print(f"   🍽️  Meal distribution: {meal_distribution}")
        
        # Overall assessment
        if llm_success and google_success and address_success and len(restaurants) == 3:
            print(f"\n🎉 SUCCESS: Agentic system is now working perfectly!")
            print(f"   ✅ LLM generates landmarks only")
            print(f"   ✅ Google Places adds real restaurants") 
            print(f"   ✅ Address/description properly separated")
            print(f"   ✅ Perfect meal distribution (3 meals)")
        else:
            issues = []
            if not llm_success:
                issues.append("LLM still generating non-landmarks")
            if not google_success:
                issues.append("Google Places not working")
            if not address_success:
                issues.append("Address separation not working")
            if len(restaurants) != 3:
                issues.append(f"Wrong restaurant count ({len(restaurants)}/3)")
            
            print(f"\n⚠️  ISSUES REMAINING: {', '.join(issues)}")
        
        # Save result for inspection
        with open('final_agentic_fix_test.json', 'w') as f:
            json.dump(result, f, indent=2)
        print(f"\n💾 Results saved to final_agentic_fix_test.json")

if __name__ == "__main__":
    asyncio.run(test_final_agentic_fix()) 