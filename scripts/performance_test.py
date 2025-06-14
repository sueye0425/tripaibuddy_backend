#!/usr/bin/env python3
"""
Performance and Cost Testing Script for TripAI Backend Endpoints

This script tests both /generate and /complete-itinerary endpoints to measure:
- Response times
- API call counts
- Estimated costs
- Sample outputs for frontend integration

Usage:
    python scripts/performance_test.py
"""

import asyncio
import json
import time
import requests
import os
from typing import Dict, Any

# Configuration
BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8080")
TEST_DESTINATIONS = [
    "San Francisco, CA",
    "New York, NY", 
    "Orlando, FL"
]

# API Cost Constants (per Google Cloud Pricing)
GOOGLE_API_COSTS = {
    "nearby_search": 0.032,
    "place_details": 0.017,
    "geocoding": 0.005,
    "photo": 0.007
}

OPENAI_API_COSTS = {
    "gpt-4-turbo": {
        "input": 0.01 / 1000,   # per token
        "output": 0.03 / 1000   # per token
    },
    "gpt-3.5-turbo": {
        "input": 0.0005 / 1000, # per token
        "output": 0.0015 / 1000 # per token
    }
}

class PerformanceTester:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = requests.Session()
        self.results = {
            "generate": [],
            "complete_itinerary": []
        }

    def test_generate_endpoint(self, destination: str) -> Dict[str, Any]:
        """Test /generate endpoint performance"""
        print(f"\n🚀 Testing /generate for {destination}")
        print("-" * 50)
        
        payload = {
            "destination": destination,
            "travel_days": 3,
            "with_kids": False,
            "with_elderly": False,
            "special_requests": "Love art museums and great food"
        }
        
        start_time = time.time()
        try:
            response = self.session.post(f"{self.base_url}/generate", json=payload, timeout=30)
            end_time = time.time()
            
            response_time = end_time - start_time
            
            if response.status_code == 200:
                data = response.json()
                
                # Count results
                landmarks_count = len(data.get("landmarks", {}))
                restaurants_count = len(data.get("restaurants", {}))
                
                # Estimate API costs
                estimated_cost = self._estimate_generate_cost(landmarks_count, restaurants_count)
                
                result = {
                    "destination": destination,
                    "status": "success",
                    "response_time": round(response_time, 2),
                    "landmarks_count": landmarks_count,
                    "restaurants_count": restaurants_count,
                    "estimated_cost": estimated_cost,
                    "sample_data": self._extract_sample_data(data)
                }
                
                print(f"✅ Success: {response_time:.2f}s")
                print(f"📍 Results: {landmarks_count} landmarks, {restaurants_count} restaurants")
                print(f"💰 Estimated cost: ${estimated_cost:.3f}")
                
                return result
                
            else:
                print(f"❌ Failed: {response.status_code} - {response.text}")
                return {
                    "destination": destination,
                    "status": "error",
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "response_time": round(response_time, 2)
                }
                
        except Exception as e:
            end_time = time.time()
            response_time = end_time - start_time
            print(f"❌ Exception: {str(e)}")
            return {
                "destination": destination,
                "status": "error",
                "error": str(e),
                "response_time": round(response_time, 2)
            }

    def test_complete_itinerary_endpoint(self, destination: str) -> Dict[str, Any]:
        """Test /complete-itinerary endpoint performance"""
        print(f"\n⚡ Testing /complete-itinerary for {destination}")
        print("-" * 50)
        
        # First get some landmarks from /generate to use as input
        generate_payload = {
            "destination": destination,
            "travel_days": 2,
            "with_kids": False,
            "with_elderly": False
        }
        
        try:
            generate_response = self.session.post(f"{self.base_url}/generate", json=generate_payload, timeout=30)
            if generate_response.status_code != 200:
                print(f"❌ Failed to get landmarks for complete-itinerary test")
                return {"destination": destination, "status": "error", "error": "Could not get landmarks"}
            
            landmarks_data = generate_response.json().get("landmarks", {})
            if not landmarks_data:
                print(f"❌ No landmarks returned for complete-itinerary test")
                return {"destination": destination, "status": "error", "error": "No landmarks available"}
            
            # Select first 3 landmarks
            selected_landmarks = []
            for i, (name, data) in enumerate(list(landmarks_data.items())[:3]):
                selected_landmarks.append({
                    "name": name,
                    "description": data.get("description", ""),
                    "location": data.get("location", {"lat": 0, "lng": 0}),
                    "type": "landmark"
                })
            
            # Create complete-itinerary payload
            payload = {
                "details": {
                    "destination": destination,
                    "travelDays": 2,
                    "startDate": "2024-06-15",
                    "endDate": "2024-06-16",
                    "withKids": False,
                    "withElders": False,
                    "kidsAge": [],
                    "specialRequests": "Love art and culture"
                },
                "wishlist": [],
                "itinerary": [
                    {
                        "day": 1,
                        "attractions": selected_landmarks[:2]
                    },
                    {
                        "day": 2,
                        "attractions": selected_landmarks[2:3] if len(selected_landmarks) > 2 else selected_landmarks[:1]
                    }
                ]
            }
            
            start_time = time.time()
            response = self.session.post(f"{self.base_url}/complete-itinerary", json=payload, timeout=60)
            end_time = time.time()
            
            response_time = end_time - start_time
            
            if response.status_code == 200:
                data = response.json()
                
                # Count results
                total_blocks = 0
                landmarks_count = 0
                restaurants_count = 0
                
                for day in data.get("itinerary", []):
                    blocks = day.get("blocks", [])
                    total_blocks += len(blocks)
                    landmarks_count += len([b for b in blocks if b.get("type") == "landmark"])
                    restaurants_count += len([b for b in blocks if b.get("type") == "restaurant"])
                
                # Extract performance metrics if available
                performance_metrics = data.get("performance_metrics", {})
                estimated_cost = self._estimate_complete_itinerary_cost(performance_metrics)
                
                result = {
                    "destination": destination,
                    "status": "success",
                    "response_time": round(response_time, 2),
                    "total_blocks": total_blocks,
                    "landmarks_count": landmarks_count,
                    "restaurants_count": restaurants_count,
                    "estimated_cost": estimated_cost,
                    "performance_metrics": performance_metrics,
                    "sample_data": self._extract_complete_itinerary_sample(data)
                }
                
                print(f"✅ Success: {response_time:.2f}s")
                print(f"📍 Results: {total_blocks} total blocks ({landmarks_count} landmarks, {restaurants_count} restaurants)")
                print(f"💰 Estimated cost: ${estimated_cost:.3f}")
                
                return result
                
            else:
                print(f"❌ Failed: {response.status_code} - {response.text}")
                return {
                    "destination": destination,
                    "status": "error",
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "response_time": round(response_time, 2)
                }
                
        except Exception as e:
            print(f"❌ Exception: {str(e)}")
            return {
                "destination": destination,
                "status": "error",
                "error": str(e),
                "response_time": 0
            }

    def _estimate_generate_cost(self, landmarks_count: int, restaurants_count: int) -> float:
        """Estimate cost for /generate endpoint"""
        # Estimated API calls based on current implementation
        nearby_searches = 4  # tourist_attraction, museum, park, restaurant
        place_details = min(15, landmarks_count + restaurants_count)  # Limited by optimization
        geocoding = 1
        
        cost = (
            nearby_searches * GOOGLE_API_COSTS["nearby_search"] +
            place_details * GOOGLE_API_COSTS["place_details"] +
            geocoding * GOOGLE_API_COSTS["geocoding"]
        )
        
        return cost

    def _estimate_complete_itinerary_cost(self, performance_metrics: Dict) -> float:
        """Estimate cost for /complete-itinerary endpoint"""
        cost = 0.0
        
        # Google Places API costs
        google_costs = performance_metrics.get("costs", {}).get("google_places", {})
        api_calls = google_costs.get("enhancement_api_calls", 8)  # Default estimate
        
        # Estimate breakdown
        nearby_searches = 6  # More searches for restaurants
        place_details = api_calls + 15  # Enhancement + restaurant details
        geocoding = 1
        
        cost += (
            nearby_searches * GOOGLE_API_COSTS["nearby_search"] +
            place_details * GOOGLE_API_COSTS["place_details"] +
            geocoding * GOOGLE_API_COSTS["geocoding"]
        )
        
        # OpenAI costs
        openai_costs = performance_metrics.get("costs", {}).get("openai", {})
        if "primary" in openai_costs:
            tokens = openai_costs["primary"]
            prompt_tokens = tokens.get("prompt_tokens", 1250)
            completion_tokens = tokens.get("completion_tokens", 890)
            
            cost += (
                prompt_tokens * OPENAI_API_COSTS["gpt-4-turbo"]["input"] +
                completion_tokens * OPENAI_API_COSTS["gpt-4-turbo"]["output"]
            )
        else:
            # Default estimate
            cost += 0.02  # ~$0.02 for typical LLM call
        
        return cost

    def _extract_sample_data(self, data: Dict) -> Dict:
        """Extract sample data for frontend documentation"""
        landmarks = data.get("landmarks", {})
        restaurants = data.get("restaurants", {})
        
        sample = {
            "landmarks": {},
            "restaurants": {}
        }
        
        # Get first 2 landmarks
        for i, (name, landmark_data) in enumerate(list(landmarks.items())[:2]):
            sample["landmarks"][name] = landmark_data
        
        # Get first 2 restaurants
        for i, (name, restaurant_data) in enumerate(list(restaurants.items())[:2]):
            sample["restaurants"][name] = restaurant_data
        
        return sample

    def _extract_complete_itinerary_sample(self, data: Dict) -> Dict:
        """Extract sample data for complete-itinerary documentation"""
        itinerary = data.get("itinerary", [])
        
        # Return first day only for sample
        if itinerary:
            return {
                "itinerary": [itinerary[0]],
                "performance_metrics": data.get("performance_metrics", {})
            }
        
        return {"itinerary": [], "performance_metrics": {}}

    def run_all_tests(self):
        """Run all performance tests"""
        print("🔍 TripAI Backend Performance & Cost Analysis")
        print("=" * 60)
        
        for destination in TEST_DESTINATIONS:
            # Test /generate
            generate_result = self.test_generate_endpoint(destination)
            self.results["generate"].append(generate_result)
            
            # Test /complete-itinerary
            complete_result = self.test_complete_itinerary_endpoint(destination)
            self.results["complete_itinerary"].append(complete_result)
            
            time.sleep(2)  # Brief pause between destinations
        
        self._print_summary()
        self._save_results()

    def _print_summary(self):
        """Print performance summary"""
        print("\n📊 PERFORMANCE SUMMARY")
        print("=" * 60)
        
        # Generate endpoint summary
        generate_times = [r["response_time"] for r in self.results["generate"] if r["status"] == "success"]
        generate_costs = [r["estimated_cost"] for r in self.results["generate"] if r["status"] == "success"]
        
        if generate_times:
            print(f"\n🚀 /generate Endpoint:")
            print(f"   Average response time: {sum(generate_times)/len(generate_times):.2f}s")
            print(f"   Fastest response: {min(generate_times):.2f}s")
            print(f"   Slowest response: {max(generate_times):.2f}s")
            print(f"   Average cost: ${sum(generate_costs)/len(generate_costs):.3f}")
            print(f"   Monthly cost (1000 calls): ${sum(generate_costs)/len(generate_costs)*1000:.2f}")
        
        # Complete-itinerary endpoint summary
        complete_times = [r["response_time"] for r in self.results["complete_itinerary"] if r["status"] == "success"]
        complete_costs = [r["estimated_cost"] for r in self.results["complete_itinerary"] if r["status"] == "success"]
        
        if complete_times:
            print(f"\n⚡ /complete-itinerary Endpoint:")
            print(f"   Average response time: {sum(complete_times)/len(complete_times):.2f}s")
            print(f"   Fastest response: {min(complete_times):.2f}s")
            print(f"   Slowest response: {max(complete_times):.2f}s")
            print(f"   Average cost: ${sum(complete_costs)/len(complete_costs):.3f}")
            print(f"   Monthly cost (1000 calls): ${sum(complete_costs)/len(complete_costs)*1000:.2f}")
        
        # Combined monthly estimate
        if generate_costs and complete_costs:
            monthly_generate = sum(generate_costs)/len(generate_costs) * 1000
            monthly_complete = sum(complete_costs)/len(complete_costs) * 1000
            print(f"\n💰 Combined Monthly Estimate (1000 calls each):")
            print(f"   Total: ${monthly_generate + monthly_complete:.2f}")

    def _save_results(self):
        """Save detailed results to JSON file"""
        output_file = "performance_test_results.json"
        
        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\n📁 Detailed results saved to: {output_file}")

def main():
    """Main function"""
    tester = PerformanceTester(BASE_URL)
    tester.run_all_tests()

if __name__ == "__main__":
    main() 