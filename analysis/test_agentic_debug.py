import asyncio
import json
import traceback
import aiohttp
from app.agentic_itinerary import complete_itinerary_agentic, EnhancedAgenticItinerarySystem
from app.schema import LandmarkSelection, TripDetails, DayAttraction, Attraction, Location
from app.places_client import GooglePlacesClient

async def test_agentic_debug():
    """Debug test to catch exact error in agentic system"""
    
    print("🔍 AGENTIC DEBUG TEST")
    print("=" * 50)
    
    # Test with 2 days to reproduce the multi-day issue
    details = TripDetails(
        destination='Orlando, FL',
        travelDays=2,  # Multi-day to reproduce the issue
        startDate='2024-06-10',
        endDate='2024-06-11',
        withKids=True,
        kidsAge=[8, 12],
        withElders=False,
        specialRequests='Universal Studios theme park day'
    )

    # Create selection
    attractions = [
        Attraction(
            name="Universal Studios Florida",
            description="Famous movie-themed attractions and rides",
            type="theme_park",
            location=Location(lat=28.4743969, lng=-81.4679803)
        )
    ]
    
    selection = LandmarkSelection(
        details=details,
        itinerary=[
            DayAttraction(day=1, attractions=attractions),
            DayAttraction(day=2, attractions=[attractions[0]])  # Same attraction for day 2
        ]
    )
    
    # Initialize Google Places client properly
    async with aiohttp.ClientSession() as session:
        places_client = GooglePlacesClient(session)
        
        try:
            print("🚀 Testing direct agentic system call")
            
            # Call the agentic system directly to catch any errors
            system = EnhancedAgenticItinerarySystem()
            result = await system.generate_itinerary(selection, places_client)
            
            print("✅ AGENTIC SYSTEM SUCCESS!")
            print(f"📅 Days generated: {len(result.get('itinerary', []))}")
            
            # Check if we got real Google Places data
            day1 = result['itinerary'][0] if result.get('itinerary') else None
            if day1:
                restaurants = [b for b in day1['blocks'] if b['type'] == 'restaurant']
                if restaurants:
                    first_restaurant = restaurants[0]
                    has_place_id = first_restaurant.get('place_id') is not None
                    print(f"🍽️ First restaurant has place_id: {has_place_id}")
                    if has_place_id:
                        print("✅ Google Places integration working!")
                    else:
                        print("❌ Google Places integration failed!")
            
        except Exception as e:
            print(f"❌ AGENTIC SYSTEM ERROR: {str(e)}")
            print("📄 Full traceback:")
            traceback.print_exc()
            
            print("\n🔄 Testing fallback behavior...")
            try:
                # Test the complete_itinerary_agentic function (which has fallback logic)
                result = await complete_itinerary_agentic(selection, places_client)
                print("✅ Fallback worked")
                print(f"📅 Fallback days: {len(result.get('itinerary', []))}")
            except Exception as fallback_error:
                print(f"❌ Even fallback failed: {fallback_error}")

if __name__ == "__main__":
    asyncio.run(test_agentic_debug()) 