#!/usr/bin/env python3
"""
Test script for Enhanced Agentic Itinerary System

This script demonstrates the enhanced agentic system with parallel processing,
duplicate detection, and performance improvements.

Usage:
    # Enable agentic system
    export ENABLE_AGENTIC_SYSTEM=true
    export OPENAI_API_KEY=your_key_here
    
    # Run test
    python test_agentic_system.py
    
    # Clear caches before testing
    python test_agentic_system.py --clear-cache
    
    # Generate curl commands
    python test_agentic_system.py --curl
"""

import os
import sys
import asyncio
import json
import time
import hashlib
from typing import Dict, Any
from datetime import datetime, timedelta
import importlib

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.schema import LandmarkSelection, TripDetails, DayAttraction, Attraction, Location
from app.agentic_itinerary import complete_itinerary_agentic
from app.places_client import GooglePlacesClient

# Test configurations
TEST_CONFIGURATIONS = [
    {
        "name": "Paris 3-Day Family Trip",
        "destination": "Paris",
        "travel_days": 3,
        "with_kids": True,
        "kids_age": [8, 12],
        "with_elderly": False,
        "special_requests": "Kid-friendly activities, some museums, good food",
        "selected_attractions": {
            1: [("Eiffel Tower", "landmark"), ("Louvre Museum", "landmark")],
            2: [("Arc de Triomphe", "landmark")],
            3: [("Notre-Dame Cathedral", "landmark")]
        }
    },
    {
        "name": "Tokyo 2-Day Business Trip",
        "destination": "Tokyo",
        "travel_days": 2,
        "with_kids": False,
        "kids_age": [],
        "with_elderly": False,
        "special_requests": "Traditional culture, modern tech, excellent restaurants",
        "selected_attractions": {
            1: [("Tokyo Tower", "landmark"), ("Senso-ji Temple", "landmark")],
            2: [("Shibuya Crossing", "landmark")]
        }
    },
    {
        "name": "London 4-Day Extended Trip",
        "destination": "London",
        "travel_days": 4,
        "with_kids": False,
        "kids_age": [],
        "with_elderly": True,
        "special_requests": "Historical sites, accessible venues, afternoon tea",
        "selected_attractions": {
            1: [("Tower of London", "landmark"), ("Westminster Abbey", "landmark")],
            2: [("British Museum", "landmark")],
            3: [("Buckingham Palace", "landmark")],
            4: [("Hyde Park", "landmark")]
        }
    }
]

def clear_all_caches():
    """Clear all caching systems to ensure fresh results"""
    print("🧹 Clearing all caches for fresh testing...")
    
    try:
        # Clear standard system cache
        from app.complete_itinerary import _itinerary_cache
        cache_count = len(_itinerary_cache)
        _itinerary_cache.clear()
        print(f"✅ Cleared standard system cache ({cache_count} entries)")
    except Exception as e:
        print(f"⚠️  Could not clear standard cache: {e}")
    
    try:
        # Clear agentic system caches
        from app.agentic_itinerary import enhanced_agentic_system
        
        day_cache_count = len(enhanced_agentic_system._day_cache)
        enhancement_cache_count = len(enhanced_agentic_system._enhancement_cache)
        validation_cache_count = len(enhanced_agentic_system._validation_cache)
        
        enhanced_agentic_system._day_cache.clear()
        enhanced_agentic_system._enhancement_cache.clear()
        enhanced_agentic_system._validation_cache.clear()
        
        print(f"✅ Cleared agentic system caches:")
        print(f"   - Day cache: {day_cache_count} entries")
        print(f"   - Enhancement cache: {enhancement_cache_count} entries")
        print(f"   - Validation cache: {validation_cache_count} entries")
    except Exception as e:
        print(f"⚠️  Could not clear agentic caches: {e}")
    
    print("🎯 All caches cleared - next requests will generate fresh results")

def create_cache_busting_selection(config: Dict[str, Any], cache_buster: str = None) -> LandmarkSelection:
    """Create a LandmarkSelection object with optional cache busting"""
    
    # Add cache buster to special requests if provided
    special_requests = config["special_requests"]
    if cache_buster:
        special_requests = f"{special_requests}. Cache buster: {cache_buster}"
    
    # Generate default dates if not provided
    start_date = datetime.now().strftime('%Y-%m-%d')
    end_date = (datetime.now() + timedelta(days=config["travel_days"] - 1)).strftime('%Y-%m-%d')
    
    # Create trip details with required fields
    details = TripDetails(
        destination=config["destination"],
        travelDays=config["travel_days"],
        startDate=start_date,
        endDate=end_date,
        withKids=config["with_kids"],
        kidsAge=config["kids_age"],
        withElders=config["with_elderly"],
        specialRequests=special_requests
    )
    
    # Proper coordinates for Orlando landmarks
    landmark_coordinates = {
        "Universal Islands of Adventure": Location(lat=28.4716879, lng=-81.4701971),
        "Universal Studios Florida": Location(lat=28.4793754, lng=-81.4685422),
        "SEA LIFE Orlando Aquarium": Location(lat=28.4425885, lng=-81.46856799999999)
    }
    
    # Create day plans with selected attractions
    itinerary = []
    for day_num in range(1, config["travel_days"] + 1):
        attractions = []
        if day_num in config["selected_attractions"]:
            for attraction_name, attraction_type in config["selected_attractions"][day_num]:
                # Use proper coordinates if available, otherwise use destination default
                location = landmark_coordinates.get(attraction_name)
                if not location:
                    # Default Orlando area coordinates
                    location = Location(lat=28.5, lng=-81.4)
                
                attraction = Attraction(
                    name=attraction_name,
                    type=attraction_type,
                    description=f"Popular {attraction_type} in {config['destination']}",
                    location=location
                )
                attractions.append(attraction)
        
        # Use DayAttraction instead of DayPlan
        day_attraction = DayAttraction(day=day_num, attractions=attractions)
        itinerary.append(day_attraction)
    
    # Create wishlist (optional)
    wishlist = [
        {"name": "Local Market", "type": "landmark"},
        {"name": "Scenic Viewpoint", "type": "landmark"}
    ]
    
    return LandmarkSelection(
        details=details,
        itinerary=itinerary,
        wishlist=wishlist
    )

async def run_performance_test(config: Dict[str, Any]) -> Dict[str, Any]:
    """Run a performance test for the given configuration"""
    
    print(f"\n🚀 Testing: {config['name']}")
    print("=" * 60)
    
    # Create test selection
    selection = create_cache_busting_selection(config)
    
    # Initialize places client (optional for testing)
    places_client = None
    try:
        google_api_key = os.getenv("GOOGLE_PLACES_API_KEY")
        if google_api_key:
            import aiohttp
            session = aiohttp.ClientSession()
            places_client = GooglePlacesClient(session=session)
            print("✅ Google Places client initialized")
        else:
            print("⚠️  No Google Places API key - running without enhancement")
    except Exception as e:
        print(f"⚠️  Could not initialize Google Places client: {e}")
    
    # Run the agentic system
    start_time = time.time()
    
    try:
        result = await complete_itinerary_agentic(selection, places_client)
        
        total_time = time.time() - start_time
        
        # Analyze results
        if isinstance(result, dict) and "itinerary" in result:
            days_generated = len(result["itinerary"])
            total_activities = sum(len(day.get("blocks", [])) for day in result["itinerary"])
            
            print(f"✅ Success! Generated {days_generated} days with {total_activities} activities")
            print(f"⏱️  Total time: {total_time:.2f}s")
            
            # Calculate theoretical speedup
            estimated_sequential_time = total_time * days_generated
            theoretical_speedup = estimated_sequential_time / total_time if total_time > 0 else 1
            print(f"🚀 Estimated parallel speedup: {theoretical_speedup:.1f}x")
            
            # Show sample day
            if result["itinerary"]:
                sample_day = result["itinerary"][0]
                print(f"\n📋 Sample Day 1 ({len(sample_day.get('blocks', []))} activities):")
                for i, block in enumerate(sample_day.get("blocks", [])[:3], 1):
                    print(f"   {i}. {block.get('name')} ({block.get('type')}) at {block.get('start_time')}")
                if len(sample_day.get("blocks", [])) > 3:
                    print(f"   ... and {len(sample_day.get('blocks', [])) - 3} more activities")
            
            # Clean up
            if places_client and hasattr(places_client, 'session'):
                await places_client.session.close()
            
            return {
                "success": True,
                "total_time": total_time,
                "days_generated": days_generated,
                "total_activities": total_activities,
                "theoretical_speedup": theoretical_speedup
            }
        
        else:
            print(f"❌ Failed: {result}")
            return {"success": False, "error": str(result)}
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return {"success": False, "error": str(e)}
    
    finally:
        # Clean up
        if places_client and hasattr(places_client, 'session'):
            try:
                await places_client.session.close()
            except:
                pass

async def run_all_tests():
    """Run all performance tests"""
    
    print("🤖 Enhanced Agentic Itinerary System - Performance Tests")
    print("=" * 60)
    
    # Check environment
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY not set - tests will fail")
        return
    
    agentic_enabled = os.getenv("ENABLE_AGENTIC_SYSTEM", "false").lower() == "true"
    if not agentic_enabled:
        print("⚠️  ENABLE_AGENTIC_SYSTEM not set to 'true' - will use fallback system")
    else:
        print("✅ Enhanced Agentic System enabled")
    
    print(f"🔑 OpenAI API Key: {os.getenv('OPENAI_API_KEY', 'NOT_SET')[:10]}...")
    print(f"🗝️  Google API Key: {os.getenv('GOOGLE_PLACES_API_KEY', 'NOT_SET')[:10]}...")
    
    # Run tests
    test_results = []
    for config in TEST_CONFIGURATIONS:
        result = await run_performance_test(config)
        result["config_name"] = config["name"]
        test_results.append(result)
        
        # Brief pause between tests
        await asyncio.sleep(1)
    
    # Summary
    print("\n🎉 Test Summary")
    print("=" * 60)
    
    successful_tests = [r for r in test_results if r.get("success", False)]
    total_time = sum(r.get("total_time", 0) for r in successful_tests)
    total_activities = sum(r.get("total_activities", 0) for r in successful_tests)
    
    print(f"✅ Successful tests: {len(successful_tests)}/{len(test_results)}")
    print(f"⏱️  Total processing time: {total_time:.2f}s")
    print(f"🎯 Total activities generated: {total_activities}")
    
    if successful_tests:
        avg_speedup = sum(r.get("theoretical_speedup", 1) for r in successful_tests) / len(successful_tests)
        print(f"🚀 Average theoretical speedup: {avg_speedup:.1f}x")
    
    # Individual results
    for result in test_results:
        status = "✅" if result.get("success") else "❌"
        print(f"{status} {result['config_name']}: {result.get('total_time', 'N/A')}s")

def main():
    """Main entry point"""
    
    # Handle command line arguments
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        
        if arg == "--enable-agentic":
            os.environ["ENABLE_AGENTIC_SYSTEM"] = "true"
            print("🔧 Agentic system enabled via command line")
        
        elif arg == "--curl":
            generate_curl_commands()
            return
        
        elif arg == "--clear-cache":
            clear_all_caches()
            return
        
        elif arg == "--compare":
            asyncio.run(run_comparison_test())
            return
        
        elif arg == "--direct-agentic":
            asyncio.run(run_direct_agentic_test())
            return
        
        elif arg == "--help":
            print_help()
            return
    
    # Check required environment variables
    required_env = ["OPENAI_API_KEY"]
    missing_env = [var for var in required_env if not os.getenv(var)]
    
    if missing_env:
        print(f"❌ Missing required environment variables: {missing_env}")
        print_help()
        return
    
    # Run tests
    asyncio.run(run_all_tests())

def print_help():
    """Print help information"""
    print("🤖 Enhanced Agentic Itinerary System - Test Runner")
    print("=" * 60)
    print("Usage: python test_agentic_system.py [OPTION]")
    print("")
    print("Options:")
    print("  --help              Show this help message")
    print("  --compare           Run side-by-side comparison of both systems")
    print("  --direct-agentic    Test agentic system directly (bypass fallback)")
    print("  --clear-cache       Clear all caches and exit")
    print("  --curl              Generate curl commands for manual testing")
    print("  --enable-agentic    Enable agentic system and run tests")
    print("")
    print("Environment Variables:")
    print("  ENABLE_AGENTIC_SYSTEM=true   Enable the enhanced agentic system")
    print("  OPENAI_API_KEY              Required for LLM generation")
    print("  GOOGLE_PLACES_API_KEY       Optional for enhanced data")
    print("")
    print("Examples:")
    print("  python test_agentic_system.py --compare")
    print("  ENABLE_AGENTIC_SYSTEM=true python test_agentic_system.py --direct-agentic")
    print("  python test_agentic_system.py --curl")

def load_test_config():
    """Load test configuration for Orlando theme parks case"""
    return {
        "name": "Orlando Theme Parks (Comparison Test)",
        "destination": "Orlando, FL",
        "travel_days": 3,
        "with_kids": True,
        "kids_age": [2],
        "with_elderly": False,
        "special_requests": "Family-friendly theme park experience",
        "selected_attractions": {
            1: [("Universal Islands of Adventure", "landmark")],
            2: [("Universal Studios Florida", "landmark")],
            3: [("SEA LIFE Orlando Aquarium", "landmark")]
        }
    }

async def run_comparison_test():
    """Run side-by-side comparison between standard and agentic systems"""
    print("🔄 Running Side-by-Side System Comparison")
    print("=" * 60)
    
    # Clear caches for fair comparison
    clear_all_caches()
    
    # Load test configuration
    config = load_test_config()
    
    # Create Places Client for proper testing
    import aiohttp
    from app.places_client import GooglePlacesClient
    
    session = aiohttp.ClientSession()
    places_client = GooglePlacesClient(session)
    
    try:
        # Test standard system
        print("🔧 Testing STANDARD System...")
        
        # Create selection with cache buster
        standard_cache_buster = f"standard-{int(time.time())}"
        standard_selection = create_cache_busting_selection(config, standard_cache_buster)
        
        standard_start = time.time()
        try:
            # Directly import and call the standard system
            from app.complete_itinerary import complete_itinerary_from_selection
            standard_result = await complete_itinerary_from_selection(standard_selection, places_client)
            standard_duration = time.time() - standard_start
            standard_success = True
            
            if isinstance(standard_result, dict) and "itinerary" in standard_result:
                standard_activities = sum(len(day.get("blocks", [])) for day in standard_result["itinerary"])
                print(f"✅ Standard system: {standard_duration:.2f}s, {standard_activities} activities")
                
                # Check for the Harry Potter issue
                day2_blocks = standard_result["itinerary"][1].get("blocks", []) if len(standard_result["itinerary"]) > 1 else []
                harry_potter_found = any("harry potter" in block.get("name", "").lower() for block in day2_blocks)
                if harry_potter_found:
                    print("❌ ISSUE: Found Harry Potter suggestion on Universal Studios day")
                else:
                    print("✅ GOOD: No Harry Potter sub-attraction found")
            else:
                print(f"❌ Standard system failed: {standard_result}")
                standard_success = False
                
        except Exception as e:
            print(f"❌ Standard system error: {e}")
            standard_success = False
            standard_duration = time.time() - standard_start
        
        # Test agentic system
        print("\n🤖 Testing AGENTIC System...")
        
        # Create selection with different cache buster
        agentic_cache_buster = f"agentic-{int(time.time())}"
        agentic_selection = create_cache_busting_selection(config, agentic_cache_buster)
        
        agentic_start = time.time()
        try:
            # Directly import and force the agentic system to run
            from app.agentic_itinerary import enhanced_agentic_system
            agentic_result = await enhanced_agentic_system.generate_itinerary(agentic_selection, places_client)
            agentic_duration = time.time() - agentic_start
            agentic_success = True
            
            if isinstance(agentic_result, dict) and "itinerary" in agentic_result:
                agentic_activities = sum(len(day.get("blocks", [])) for day in agentic_result["itinerary"])
                print(f"✅ Agentic system: {agentic_duration:.2f}s, {agentic_activities} activities")
                
                # Check for the Harry Potter issue
                day2_blocks = agentic_result["itinerary"][1].get("blocks", []) if len(agentic_result["itinerary"]) > 1 else []
                harry_potter_found = any("harry potter" in block.get("name", "").lower() for block in day2_blocks)
                if harry_potter_found:
                    print("❌ ISSUE: Found Harry Potter suggestion on Universal Studios day")
                else:
                    print("✅ GOOD: No Harry Potter sub-attraction found")
            else:
                print(f"❌ Agentic system failed: {agentic_result}")
                agentic_success = False
                
        except Exception as e:
            print(f"❌ Agentic system error: {e}")
            agentic_success = False
            agentic_duration = time.time() - agentic_start
        
        # Comparison summary
        print("\n📊 COMPARISON SUMMARY")
        print("=" * 40)
        if standard_success and agentic_success:
            speedup = standard_duration / agentic_duration if agentic_duration > 0 else 1
            print(f"Standard System: {standard_duration:.2f}s")
            print(f"Agentic System:  {agentic_duration:.2f}s")
            if speedup > 1:
                print(f"🚀 Agentic system is {speedup:.1f}x FASTER")
            elif speedup < 1:
                print(f"⚠️  Agentic system is {1/speedup:.1f}x slower")
            else:
                print("⚖️  Both systems have similar speed")
        else:
            print("❌ One or both systems failed - cannot compare performance")
        
        # Save results for manual inspection
        if standard_success:
            with open('standard_result.json', 'w') as f:
                json.dump(standard_result, f, indent=2)
            print("📁 Standard result saved to: standard_result.json")
        
        if agentic_success:
            with open('agentic_result.json', 'w') as f:
                json.dump(agentic_result, f, indent=2)
            print("📁 Agentic result saved to: agentic_result.json")
    
    finally:
        # Clean up the session
        await session.close()

def generate_curl_commands():
    """Generate curl commands for testing both systems"""
    
    print("🚀 Curl Commands for Performance Testing")
    print("=" * 60)
    
    # Sample payload (the problematic Orlando case)
    sample_payload = {
        "details": {
            "destination": "Orlando, FL",
            "travelDays": 3,
            "startDate": "2025-06-03",
            "endDate": "2025-06-05",
            "withKids": True,
            "withElders": False,
            "kidsAge": [2],
            "specialRequests": ""
        },
        "wishlist": [],
        "itinerary": [
            {
                "day": 1,
                "attractions": [
                    {
                        "name": "Universal Islands of Adventure",
                        "description": "6000 Universal Blvd, Orlando, FL 32819, USA",
                        "location": {"lat": 28.4716879, "lng": -81.4701971},
                        "type": "landmark"
                    }
                ]
            },
            {
                "day": 2,
                "attractions": [
                    {
                        "name": "Universal Studios Florida",
                        "description": "6000 Universal Blvd, Orlando, FL 32819, USA", 
                        "location": {"lat": 28.4793754, "lng": -81.4685422},
                        "type": "landmark"
                    }
                ]
            },
            {
                "day": 3,
                "attractions": [
                    {
                        "name": "SEA LIFE Orlando Aquarium",
                        "description": "8449 International Dr, Orlando, FL 32819, USA",
                        "location": {"lat": 28.4425885, "lng": -81.46856799999999},
                        "type": "landmark"
                    }
                ]
            }
        ]
    }
    
    payload_json = json.dumps(sample_payload, indent=2)
    
    print("📋 Sample Test Payload (Orlando Theme Parks):")
    print("-" * 40)
    print(payload_json)
    print("-" * 40)
    
    print("\n🔧 STANDARD SYSTEM TEST:")
    print("-" * 40)
    print("# Set environment to use standard system")
    print("export ENABLE_AGENTIC_SYSTEM=false")
    print()
    print("# Test with curl (measure latency)")
    print("time curl -X POST http://localhost:8000/complete-itinerary \\")
    print("  -H 'Content-Type: application/json' \\")
    print("  -d '", end="")
    print(payload_json.replace('\n', '\\n').replace('"', '\\"'), end="")
    print("'")
    print()
    print("# Alternative: Save payload to file and use")
    print("echo '", end="")
    print(payload_json.replace('\n', '\\n').replace('"', '\\"'), end="")
    print("' > orlando_test.json")
    print("time curl -X POST http://localhost:8000/complete-itinerary \\")
    print("  -H 'Content-Type: application/json' \\")
    print("  -d @orlando_test.json")
    
    print("\n🤖 ENHANCED AGENTIC SYSTEM TEST:")
    print("-" * 40)
    print("# Set environment to use agentic system")
    print("export ENABLE_AGENTIC_SYSTEM=true")
    print()
    print("# Test with curl (measure latency)")
    print("time curl -X POST http://localhost:8000/complete-itinerary \\")
    print("  -H 'Content-Type: application/json' \\")
    print("  -d @orlando_test.json")
    
    print("\n📊 PERFORMANCE COMPARISON:")
    print("-" * 40)
    print("# Run both tests and compare")
    print("echo '=== STANDARD SYSTEM TEST ==='")
    print("export ENABLE_AGENTIC_SYSTEM=false")
    print("time curl -s -X POST http://localhost:8000/complete-itinerary \\")
    print("  -H 'Content-Type: application/json' \\")
    print("  -d @orlando_test.json | jq '.itinerary | length'")
    print()
    print("echo '=== AGENTIC SYSTEM TEST ==='")
    print("export ENABLE_AGENTIC_SYSTEM=true")
    print("time curl -s -X POST http://localhost:8000/complete-itinerary \\")
    print("  -H 'Content-Type: application/json' \\")
    print("  -d @orlando_test.json | jq '.itinerary | length'")
    
    print("\n⚡ QUICK LATENCY TEST SCRIPT:")
    print("-" * 40)
    print("#!/bin/bash")
    print("# Save as test_latency.sh and run: chmod +x test_latency.sh && ./test_latency.sh")
    print()
    print("# Create test payload")
    print("cat > orlando_test.json << 'EOF'")
    print(payload_json)
    print("EOF")
    print()
    print("echo '🔧 Testing Standard System...'")
    print("export ENABLE_AGENTIC_SYSTEM=false")
    print("STANDARD_TIME=$(time ( curl -s -X POST http://localhost:8000/complete-itinerary \\")
    print("  -H 'Content-Type: application/json' \\")
    print("  -d @orlando_test.json > /dev/null ) 2>&1 | grep real | awk '{print $2}')")
    print("echo \"Standard system: $STANDARD_TIME\"")
    print()
    print("echo '🤖 Testing Agentic System...'")
    print("export ENABLE_AGENTIC_SYSTEM=true")
    print("AGENTIC_TIME=$(time ( curl -s -X POST http://localhost:8000/complete-itinerary \\")
    print("  -H 'Content-Type: application/json' \\")
    print("  -d @orlando_test.json > /dev/null ) 2>&1 | grep real | awk '{print $2}')")
    print("echo \"Agentic system: $AGENTIC_TIME\"")
    print()
    print("echo '📊 Performance Summary:'")
    print("echo \"Standard: $STANDARD_TIME\"")
    print("echo \"Agentic:  $AGENTIC_TIME\"")
    
    print("\n💡 DEBUGGING TIPS:")
    print("-" * 40)
    print("# Enable debug logging")
    print("export DEBUG_ITINERARY=true")
    print()
    print("# Check logs for performance breakdown")
    print("curl -X POST http://localhost:8000/complete-itinerary \\")
    print("  -H 'Content-Type: application/json' \\")
    print("  -d @orlando_test.json 2>&1 | grep -E '(⏱️|🚀|✅)'")
    print()
    print("# Test specific issues")
    print("curl -X POST http://localhost:8000/complete-itinerary \\")
    print("  -H 'Content-Type: application/json' \\")
    print("  -d @orlando_test.json | jq '.itinerary[1].blocks[] | select(.name | contains(\"Harry Potter\"))'")
    print()
    print("# Save clean output")
    print("curl -s -X POST http://localhost:8000/complete-itinerary \\")
    print("  -H 'Content-Type: application/json' \\")
    print("  -d @orlando_test.json | jq '.' > result.json")
    
    print("\n🎯 EXPECTED RESULTS:")
    print("-" * 40)
    print("✅ GOOD: Day 2 should only have Universal Studios + meals")
    print("❌ BAD: Day 2 suggesting 'Wizarding World of Harry Potter' (it's inside Universal)")
    print("✅ GOOD: Days should have 3-6 activities each")
    print("✅ GOOD: Theme park days should have fewer total activities")
    print("⚡ PERFORMANCE: Agentic system should be 2-3x faster for 3-day trips")
    
    # Create the test file
    with open('orlando_test.json', 'w') as f:
        json.dump(sample_payload, f, indent=2)
    
    print(f"\n📁 Created test file: orlando_test.json")
    print("You can now run the curl commands above!")

async def run_direct_agentic_test():
    """Run the agentic system directly without fallbacks"""
    print("🤖 Running Direct Agentic System Test")
    print("=" * 60)
    
    # Clear caches first
    clear_all_caches()
    
    # Use Orlando test case (the problematic one)
    config = {
        "name": "Orlando Theme Parks (Direct Agentic Test)",
        "destination": "Orlando, FL",
        "travel_days": 3,
        "with_kids": True,
        "kids_age": [2],
        "with_elderly": False,
        "special_requests": "Family-friendly theme park experience",
        "selected_attractions": {
            1: [("Universal Islands of Adventure", "landmark")],
            2: [("Universal Studios Florida", "landmark")],
            3: [("SEA LIFE Orlando Aquarium", "landmark")]
        }
    }
    
    # Create selection with cache buster
    agentic_cache_buster = f"direct-agentic-{int(time.time())}"
    agentic_selection = create_cache_busting_selection(config, agentic_cache_buster)
    
    print("\n🤖 Testing DIRECT AGENTIC System...")
    agentic_start = time.time()
    try:
        # Directly import and force the agentic system to run
        from app.agentic_itinerary import EnhancedAgenticItinerarySystem
        from app.places_client import GooglePlacesClient
        
        # Create the agentic system instance
        agentic_system = EnhancedAgenticItinerarySystem()
        
        # Initialize places client (optional for testing)
        places_client = None
        try:
            google_api_key = os.getenv("GOOGLE_PLACES_API_KEY")
            if google_api_key:
                import aiohttp
                session = aiohttp.ClientSession()
                places_client = GooglePlacesClient(session=session)
                print("✅ Google Places client initialized for agentic test")
            else:
                print("⚠️  No Google Places API key - running agentic test without enhancement")
        except Exception as e:
            print(f"⚠️  Could not initialize Google Places client: {e}")
        
        # Run the agentic system directly
        agentic_result = await agentic_system.generate_itinerary(agentic_selection, places_client)
        agentic_duration = time.time() - agentic_start
        
        if isinstance(agentic_result, dict) and "itinerary" in agentic_result:
            agentic_activities = sum(len(day.get("blocks", [])) for day in agentic_result["itinerary"])
            print(f"✅ DIRECT Agentic system: {agentic_duration:.2f}s, {agentic_activities} activities")
            
            # Check for the Harry Potter issue
            day2_blocks = agentic_result["itinerary"][1].get("blocks", []) if len(agentic_result["itinerary"]) > 1 else []
            harry_potter_found = any("harry potter" in block.get("name", "").lower() for block in day2_blocks)
            if harry_potter_found:
                print("❌ ISSUE: Found Harry Potter suggestion on Universal Studios day")
                # Print the problematic suggestions
                for block in day2_blocks:
                    if "harry potter" in block.get("name", "").lower():
                        print(f"   🐛 Problematic suggestion: {block.get('name')}")
            else:
                print("✅ GOOD: No Harry Potter sub-attraction found")
            
            # Show Day 2 activities
            print(f"\n📋 Day 2 Activities ({len(day2_blocks)} total):")
            for i, block in enumerate(day2_blocks, 1):
                print(f"   {i}. {block.get('name')} ({block.get('type')}) at {block.get('start_time')}")
                
            # Check for performance metrics
            if "performance_summary" in agentic_result:
                print(f"\n⚡ Performance Metrics:")
                for metric, value in agentic_result["performance_summary"].items():
                    print(f"   - {metric}: {value}")
        else:
            print(f"❌ Direct agentic system failed: {agentic_result}")
            
        # Clean up
        if places_client and hasattr(places_client, 'session'):
            await places_client.session.close()
            
        # Save result for inspection
        with open('direct_agentic_result.json', 'w') as f:
            json.dump(agentic_result, f, indent=2)
        print("📁 Direct agentic result saved to: direct_agentic_result.json")
            
    except Exception as e:
        print(f"❌ Direct agentic system error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up
        if 'places_client' in locals() and places_client and hasattr(places_client, 'session'):
            try:
                await places_client.session.close()
            except:
                pass

if __name__ == "__main__":
    main() 