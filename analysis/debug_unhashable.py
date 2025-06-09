import asyncio
from app.schema import LandmarkSelection, DayAttraction, TripDetails, Attraction, Location
from app.agentic_itinerary import enhanced_agentic_system
from app.places_client import GooglePlacesClient
import logging
import traceback

logging.basicConfig(level=logging.DEBUG)

async def test_debug():
    try:
        selection = LandmarkSelection(
            details=TripDetails(
                destination='Orlando, FL',
                travelDays=3,
                startDate='2024-01-01',
                endDate='2024-01-03',
                withKids=False,
                withElders=False,
                kidsAge=[],
                specialRequests='Include Universal Studios'
            ),
            itinerary=[
                DayAttraction(
                    day=1,
                    attractions=[
                        Attraction(
                            name='Universal Studios Florida',
                            description='Theme park',
                            location=Location(lat=28.4731, lng=-81.4683),
                            type='theme_park'
                        )
                    ]
                )
            ]
        )
        
        places_client = GooglePlacesClient()
        result = await enhanced_agentic_system.generate_itinerary(selection, places_client)
        print('SUCCESS')
        
    except Exception as e:
        print(f'ERROR: {e}')
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_debug()) 