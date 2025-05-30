#!/usr/bin/env python3
import os
import sys
import redis
import googlemaps
import pinecone
import requests
from dotenv import load_dotenv
from openai import OpenAI

def test_redis():
    """Test Redis connection"""
    print("\n🔄 Testing Redis connection...")
    try:
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        r = redis.from_url(redis_url)
        r.ping()
        print("✅ Redis connection successful")
    except Exception as e:
        print(f"❌ Redis connection failed: {str(e)}")

def test_openai():
    """Test OpenAI API"""
    print("\n🤖 Testing OpenAI API...")
    try:
        import openai
        version = tuple(map(int, openai.__version__.split('.')))
        if version < (1, 12, 0):
            print(f"❌ OpenAI version {openai.__version__} is too old. Please run: pip install --upgrade openai")
            return False
        client = OpenAI(
            api_key=os.getenv('OPENAI_API_KEY'),
            timeout=30.0,
            max_retries=2
        )
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Say 'test' in one word"}],
            max_tokens=5
        )
        print("✅ OpenAI API connection successful")
    except Exception as e:
        print(f"❌ OpenAI API test failed: {str(e)}")
        print("If you see a 'proxies' error, try: pip install --upgrade openai")
        return False

def test_google_places():
    """Test Google Places API"""
    print("\n🗺️ Testing Google Places API...")
    try:
        gmaps = googlemaps.Client(key=os.getenv('GOOGLE_PLACES_API_KEY'))
        # Simple geocoding request as a test
        result = gmaps.geocode('Sydney Opera House')
        if result:
            print("✅ Google Places API connection successful")
        else:
            print("❌ Google Places API returned no results")
    except Exception as e:
        print(f"❌ Google Places API test failed: {str(e)}")

def test_google_routes():
    """Test Google Routes API and Geocoding"""
    print("\n🗺️ Testing Google APIs...")
    try:
        # Test geocoding
        gmaps = googlemaps.Client(key=os.getenv('GOOGLE_PLACES_API_KEY'))
        result = gmaps.geocode('Sydney, Australia')
        if result:
            print("✅ Geocoding API test successful")
        else:
            print("❌ Geocoding API test failed")
            
        # Test routes API using the same key
        response = requests.post(
            'https://routes.googleapis.com/directions/v2:computeRoutes',
            headers={
                'Content-Type': 'application/json',
                'X-Goog-Api-Key': os.getenv('GOOGLE_PLACES_API_KEY'),
                'X-Goog-FieldMask': 'routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline'
            },
            json={
                "origin": {"location": {"latLng": {"latitude": -33.8688, "longitude": 151.2093}}},
                "destination": {"location": {"latLng": {"latitude": -33.8568, "longitude": 151.2153}}},
                "travelMode": "DRIVE",
                "routingPreference": "TRAFFIC_AWARE",
                "departureTime": "2024-01-02T15:01:23.045123456Z",
                "computeAlternativeRoutes": False,
                "routeModifiers": {"avoidTolls": False, "avoidHighways": False, "avoidFerries": False}
            }
        )
        if response.status_code == 200:
            print("✅ Routes API test successful")
        else:
            print(f"❌ Routes API test failed with status code {response.status_code}")
    except Exception as e:
        print(f"❌ Google APIs test failed: {str(e)}")

def test_pinecone():
    """Test Pinecone connection"""
    print("\n📍 Testing Pinecone connection...")
    try:
        from pinecone import Pinecone
        import os

        pc = Pinecone(api_key=os.getenv('PINECONE_API_KEY'))
        index_name = os.getenv('INDEX_NAME')
        if not index_name:
            print("❌ INDEX_NAME environment variable is not set.")
            return False

        indexes = pc.list_indexes()
        index_names = [index.name for index in indexes]

        print("✅ Pinecone connection successful")
        print(f"   Available indexes: {', '.join(index_names)}")

        if index_name not in index_names:
            print(f"❌ Index '{index_name}' not found in Pinecone account.")
            return False
        else:
            print(f"✅ Index '{index_name}' exists.")
        return True

    except Exception as e:
        print(f"❌ Pinecone test failed: {str(e)}")
        return False

def main():
    # Determine environment
    is_cloud_run = os.getenv('K_SERVICE') is not None
    env_type = "Cloud Run" if is_cloud_run else "Local"
    
    print(f"\n🔍 Testing {env_type} Environment Setup")
    print("=====================================")
    
    if not is_cloud_run:
        # Load .env file for local testing
        load_dotenv()
        print("📝 Loaded .env file for local testing")
    
    # First test all API connections
    print("🔍 Testing API Connections")
    print("=========================")
    test_redis()
    test_openai()
    test_google_places()
    test_google_routes()
    test_pinecone()
    
    print("\n📊 Summary")
    print("==========")
    print(f"Environment: {env_type}")
    print(f"Redis URL: {os.getenv('REDIS_URL', 'redis://localhost:6379')}")
    print(f"OpenAI API Key: {'✅ Set' if os.getenv('OPENAI_API_KEY') else '❌ Missing'}")
    print(f"Google Places API Key: {'✅ Set' if os.getenv('GOOGLE_PLACES_API_KEY') else '❌ Missing'}")
    print(f"Pinecone API Key: {'✅ Set' if os.getenv('PINECONE_API_KEY') else '❌ Missing'}")
    print(f"Pinecone Environment: {os.getenv('PINECONE_ENVIRONMENT', 'Not Set')}")

if __name__ == "__main__":
    main() 