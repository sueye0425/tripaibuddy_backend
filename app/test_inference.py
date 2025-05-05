from rag import generate_structured_itinerary
destinations = [
    ("Dallas, TX", True, False),
    ("Orlando, FL", True, False),
    ("Chicago, IL", False, False)
]

for city, with_kids, with_elderly in destinations:
    print(f"\n🧳 Testing: {city} | with_kids={with_kids} | with_elderly={with_elderly}")
    result = generate_structured_itinerary(destination=city, travel_days=3, with_kids=with_kids, with_elderly=with_elderly)
    print("📄 Result:\n", result)