import asyncio
import json
import os
import time
import aiohttp
from app.agentic_itinerary import complete_itinerary_agentic
from app.schema import LandmarkSelection, TripDetails, DayAttraction, Attraction, Location
from app.places_client import GooglePlacesClient

async def test_simple_debug():
    """Simple debug test to see what's happening"""
    
    print("🔍 SIMPLE DEBUG TEST")
    print("=" * 50)
    
    # Very simple 1-day test
    details = TripDetails(
        destination='Orlando, FL',
        travelDays=1,
        startDate='2024-06-10',
        endDate='2024-06-10',
        withKids=True,
        kidsAge=[8, 12],
        withElders=False,
        specialRequests='Universal Studios theme park day'
    )

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

    print(f"✅ Test setup complete")
    print(f"📍 Destination: {details.destination}")
    print(f"📅 Days: {details.travelDays}")
    print(f"🎢 Selected attraction: {universal_studios.name}")
    print()

    # Initialize Google Places client
    google_api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    if not google_api_key:
        print("❌ No Google Places API key found!")
        return

    async with aiohttp.ClientSession() as session:
        places_client = GooglePlacesClient(session=session)
        
        print(f"🔑 Google Places client initialized")
        print()
        
        # Call the agentic system directly
        print("🤖 Calling complete_itinerary_agentic...")
        start_time = time.time()
        
        try:
            result = await complete_itinerary_agentic(selection, places_client)
            duration = time.time() - start_time
            
            print(f"✅ Agentic system completed in {duration:.2f}s")
            print()
            
            # Analyze the result
            if 'error' in result:
                print(f"❌ Error in result: {result['error']}")
                return
            
            # Check what we got
            days = result.get('itinerary', [])
            print(f"📊 RESULT ANALYSIS:")
            print(f"   Days returned: {len(days)}")
            
            if days:
                day1_data = days[0]
                blocks = day1_data.get('blocks', [])
                landmarks = [b for b in blocks if b['type'] == 'landmark']
                restaurants = [b for b in blocks if b['type'] == 'restaurant']
                
                print(f"   Total activities: {len(blocks)}")
                print(f"   Landmarks: {len(landmarks)}")
                print(f"   Restaurants: {len(restaurants)}")
                print()
                
                # Check if landmarks have Google Places data
                print(f"🏛️ LANDMARK DETAILS:")
                for landmark in landmarks:
                    print(f"   {landmark['name']}")
                    print(f"     place_id: {landmark.get('place_id')}")
                    print(f"     address: {landmark.get('address')}")
                    print(f"     rating: {landmark.get('rating')}")
                
                print()
                print(f"🍽️ RESTAURANT DETAILS:")
                for restaurant in restaurants:
                    print(f"   {restaurant['name']} ({restaurant.get('mealtime')})")
                    print(f"     place_id: {restaurant.get('place_id')}")
                    print(f"     address: {restaurant.get('address')}")
                    print(f"     description: {restaurant.get('description')[:50]}...")
                
                # Determine if this looks like agentic or standard system output
                has_place_ids = any(r.get('place_id') for r in restaurants)
                has_proper_addresses = any(r.get('address') for r in restaurants)
                addresses_in_description = any('Orlando' in r.get('description', '') for r in restaurants)
                
                print()
                print(f"🔍 SYSTEM IDENTIFICATION:")
                print(f"   Has place_ids: {has_place_ids}")
                print(f"   Has proper addresses: {has_proper_addresses}")
                print(f"   Addresses in description: {addresses_in_description}")
                
                if has_place_ids and has_proper_addresses:
                    print(f"   ✅ LOOKS LIKE AGENTIC SYSTEM")
                elif addresses_in_description and not has_place_ids:
                    print(f"   ❌ LOOKS LIKE STANDARD SYSTEM (fallback occurred)")
                else:
                    print(f"   ❓ UNCERTAIN SYSTEM TYPE")
            
            # Save for inspection
            with open('simple_debug_result.json', 'w') as f:
                json.dump(result, f, indent=2)
            print(f"\n💾 Result saved to simple_debug_result.json")
            
        except Exception as e:
            print(f"❌ EXCEPTION in agentic system: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_simple_debug()) 