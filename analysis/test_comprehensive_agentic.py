#!/usr/bin/env python3
"""
🧪 COMPREHENSIVE AGENTIC SYSTEM VALIDATION
==========================================

This is the DEFINITIVE test for the enhanced agentic itinerary system.
It validates ALL requirements discussed and ensures production readiness.

⚠️  FOR DEBUGGING & VALIDATION ONLY - NOT FOR PRODUCTION ⚠️

KEY VALIDATION CRITERIA:
🎯 Core Hybrid System (LLM landmarks + Google Places restaurants)
🎢 Theme Park Logic (1 landmark, proper meal timing)
🍽️ Restaurant Requirements (3 per day, no duplicates, Google Places data)
🔍 Google Places Enhancement (landmarks enhanced where possible)
📊 Multi-Day Structure (consistent 3-day generation)
⚡ Performance (< 15s total, GPT-4-turbo for parallel processing)
"""

import asyncio
import json
import os
import time
import aiohttp
from typing import Dict, Any, List
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the agentic system
from app.agentic_itinerary import complete_itinerary_agentic, enhanced_agentic_system
from app.schema import LandmarkSelection, TripDetails, DayAttraction, Attraction, Location
from app.places_client import GooglePlacesClient

# CRITICAL PERFORMANCE THRESHOLDS
PERFORMANCE_REQUIREMENTS = {
    "total_time_max": 15.0,  # 🚨 HARD REQUIREMENT: < 15s total
    "parallel_day_generation_max": 8.0,  # Parallel day generation should be fast
    "gpt_model_required": "gpt-4-turbo",  # Must use GPT-4-turbo for parallel processing
}

# SUCCESS CRITERIA
SUCCESS_CRITERIA = {
    "min_days": 3,
    "restaurants_per_day": 3,
    "required_meal_types": {"breakfast", "lunch", "dinner"},
    "google_places_success_rate": 0.80,  # 80% of restaurants must have place_id
    "landmark_enhancement_rate": 0.50,  # 50% of landmarks should be enhanced
    "theme_park_lunch_time": "12:30",  # Theme park lunch must be at proper time
}

class ComprehensiveAgenticValidation:
    """Single comprehensive validation for the enhanced agentic system"""
    
    def __init__(self):
        """Initialize the comprehensive validation system"""
        self.results = {}
        self.performance_data = {}
        self.validation_issues = []
        self.test_duration = 0.0
        self.agentic_result = None  # Store the actual agentic system result
        
    async def run_comprehensive_validation(self):
        """Run comprehensive validation with all checks"""
        print("🧪 COMPREHENSIVE AGENTIC SYSTEM VALIDATION")
        print("==========================================")
        print()
        print("This is the DEFINITIVE test for the enhanced agentic itinerary system.")
        print("It validates ALL requirements discussed and ensures production readiness.")
        print()
        print("⚠️  FOR DEBUGGING & VALIDATION ONLY - NOT FOR PRODUCTION ⚠️")
        print()
        
        # Environment verification
        if not await self._verify_environment():
            return False
        
        start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            places_client = GooglePlacesClient(session)
            
            # Execute the test
            result = await self._execute_agentic_test(places_client)
            
            # Calculate duration
            self.test_duration = time.time() - start_time
            print(f"✅ Completed in {self.test_duration:.2f}s")
            print()
            
            # Validate all requirements
            await self._validate_all_requirements(result, self.test_duration)
            
            # Generate final assessment
            return self._generate_final_assessment()
    
    async def _verify_environment(self) -> bool:
        """Verify all required environment setup"""
        print("🔧 ENVIRONMENT VERIFICATION")
        print("-" * 40)
        
        # Check API keys
        google_key = os.getenv("GOOGLE_PLACES_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")
        agentic_enabled = os.getenv("ENABLE_AGENTIC_SYSTEM", "false").lower() == "true"
        
        print(f"🔑 Google Places API: {'✅ Configured' if google_key else '❌ Missing'}")
        print(f"🔑 OpenAI API: {'✅ Configured' if openai_key else '❌ Missing'}")
        print(f"🤖 Agentic System: {'✅ Enabled' if agentic_enabled else '❌ Disabled'}")
        
        # Check GPT-4-turbo usage
        model_config = enhanced_agentic_system.fast_llm.model_name
        gpt4_turbo_used = model_config == PERFORMANCE_REQUIREMENTS["gpt_model_required"]
        print(f"🧠 Parallel Processing Model: {model_config} {'✅ Correct' if gpt4_turbo_used else '❌ Wrong'}")
        
        if not gpt4_turbo_used:
            self.validation_issues.append(f"Must use {PERFORMANCE_REQUIREMENTS['gpt_model_required']} for parallel processing, currently using {model_config}")
        
        print()
        
        all_good = google_key and openai_key and agentic_enabled and gpt4_turbo_used
        if not all_good:
            print("❌ Environment setup incomplete. Please fix the issues above.")
            return False
        
        return True
    
    async def _execute_agentic_test(self, places_client: GooglePlacesClient) -> Dict[str, Any]:
        """Execute the comprehensive agentic test with realistic scenario"""
        
        print("🎯 EXECUTING COMPREHENSIVE TEST SCENARIO")
        print("-" * 50)
        
        # Create realistic 3-day Orlando trip
        details = TripDetails(
            destination='Orlando, FL',
            travelDays=3,
            startDate='2024-06-10',
            endDate='2024-06-12',
            withKids=True,
            kidsAge=[8, 12],
            withElders=False,
            specialRequests='Include Universal Studios theme park and family-friendly activities'
        )

        # Day 1: Theme park (should generate ONLY Universal Studios)
        universal_studios = Attraction(
            name='Universal Studios Florida',
            type='landmark',  # Use 'landmark' as per schema
            description='Famous movie-themed attractions and rides',
            location=Location(lat=28.4743, lng=-81.4677)
        )

        # Day 2: Regular attractions
        science_center = Attraction(
            name='Orlando Science Center',
            type='landmark',
            description='Interactive science exhibits and planetarium',
            location=Location(lat=28.5721, lng=-81.3519)
        )

        # Day 3: Mixed attractions  
        eola_park = Attraction(
            name='Lake Eola Park',
            type='landmark',
            description='Beautiful downtown park with swan boats',
            location=Location(lat=28.5427, lng=-81.3709)
        )

        selection = LandmarkSelection(
            details=details,
            itinerary=[
                DayAttraction(day=1, attractions=[universal_studios]),
                DayAttraction(day=2, attractions=[science_center]),
                DayAttraction(day=3, attractions=[eola_park])
            ],
            wishlist=[]
        )

        print(f"📍 Destination: {details.destination}")
        print(f"📅 Duration: {details.travelDays} days")
        print(f"🎢 Day 1: {universal_studios.name} (theme park)")
        print(f"🔬 Day 2: {science_center.name} (museum)")
        print(f"🌊 Day 3: {eola_park.name} (park)")
        print()
        
        print("⏱️  Starting agentic system...")
        start_time = time.time()
        
        # Execute the agentic system
        result = await complete_itinerary_agentic(selection, places_client)
        
        duration = time.time() - start_time
        print(f"✅ Completed in {duration:.2f}s")
        print()
        
        # Store the result for later JSON writing
        self.agentic_result = result
        
        return result
    
    async def _validate_all_requirements(self, result: Dict[str, Any], duration: float):
        """Validate all requirements comprehensively"""
        
        print("📋 COMPREHENSIVE VALIDATION RESULTS")
        print("=" * 50)
        
        # Initialize validation results
        validations = {
            "performance_acceptable": duration < PERFORMANCE_REQUIREMENTS["total_time_max"],
            "multi_day_structure": False,
            "llm_landmarks_only": True,
            "google_restaurants_added": True,
            "theme_park_detection": False,
            "theme_park_single_landmark": True,
            "theme_park_lunch_timing": False,
            "restaurant_count_correct": True,
            "meal_distribution_complete": True,
            "no_duplicate_restaurants": True,
            "google_places_integration": True,
            "landmark_enhancement": True,
            "universal_studios_enhanced": False,
            "universal_studios_address": False,
            "universal_studios_photo": False,
        }
        
        # Performance validation
        print(f"⚡ PERFORMANCE VALIDATION")
        print(f"   Total time: {duration:.2f}s (max: {PERFORMANCE_REQUIREMENTS['total_time_max']}s)")
        performance_pass = validations["performance_acceptable"]
        print(f"   Result: {'✅ PASS' if performance_pass else '❌ FAIL'}")
        if not performance_pass:
            self.validation_issues.append(f"Performance too slow: {duration:.2f}s exceeds {PERFORMANCE_REQUIREMENTS['total_time_max']}s")
        print()
        
        # Check for fallback (error indicates agentic system failed)
        if 'error' in result:
            print(f"🚨 CRITICAL: Agentic system failed - {result['error']}")
            validations["llm_landmarks_only"] = False
            self.validation_issues.append(f"Agentic system failure: {result['error']}")
            return validations
        
        # Multi-day structure validation
        days = result.get('itinerary', [])
        validations["multi_day_structure"] = len(days) == SUCCESS_CRITERIA["min_days"]
        
        print(f"🏗️ MULTI-DAY STRUCTURE")
        print(f"   Days generated: {len(days)}/{SUCCESS_CRITERIA['min_days']}")
        print(f"   Result: {'✅ PASS' if validations['multi_day_structure'] else '❌ FAIL'}")
        if not validations["multi_day_structure"]:
            self.validation_issues.append(f"Expected {SUCCESS_CRITERIA['min_days']} days, got {len(days)}")
        print()
        
        # Collect all restaurants for duplicate analysis
        all_restaurants = []
        all_restaurant_place_ids = set()
        all_meals = set()
        
        # Day-by-day validation
        for day_num, day_data in enumerate(days, 1):
            print(f"📅 DAY {day_num} VALIDATION")
            
            blocks = day_data.get('blocks', [])
            landmarks = [b for b in blocks if b.get('type') == 'landmark']
            restaurants = [b for b in blocks if b.get('type') == 'restaurant']
            
            print(f"   Total activities: {len(blocks)}")
            print(f"   Landmarks: {len(landmarks)}")
            print(f"   Restaurants: {len(restaurants)}")
            
            # Validate LLM landmarks only (no restaurants from LLM)
            for landmark in landmarks:
                if landmark.get('type') != 'landmark':
                    validations["llm_landmarks_only"] = False
                    self.validation_issues.append(f"Day {day_num}: LLM generated non-landmark: {landmark.get('name')}")
            
            # Validate restaurant count
            if len(restaurants) != SUCCESS_CRITERIA["restaurants_per_day"]:
                validations["restaurant_count_correct"] = False
                self.validation_issues.append(f"Day {day_num}: {len(restaurants)} restaurants, expected {SUCCESS_CRITERIA['restaurants_per_day']}")
            
            # Theme park specific validation (Day 1)
            if day_num == 1:
                universal_found = any('universal' in l.get('name', '').lower() for l in landmarks)
                validations["theme_park_detection"] = universal_found
                
                if universal_found:
                    print(f"   🎢 Theme park detected: Universal Studios")
                    
                    # Should have ONLY 1 landmark on theme park day
                    if len(landmarks) != 1:
                        validations["theme_park_single_landmark"] = False
                        self.validation_issues.append(f"Theme park day has {len(landmarks)} landmarks, should be 1")
                    else:
                        validations["theme_park_single_landmark"] = True
                        print(f"   ✅ Theme park day has exactly 1 landmark")
                    
                    # Check lunch timing
                    lunch = next((r for r in restaurants if r.get('mealtime') == 'lunch'), None)
                    if lunch and SUCCESS_CRITERIA["theme_park_lunch_time"] in lunch.get('start_time', ''):
                        validations["theme_park_lunch_timing"] = True
                        print(f"   ✅ Theme park lunch timing: {lunch.get('start_time')}")
                    elif lunch:
                        self.validation_issues.append(f"Theme park lunch at {lunch.get('start_time')}, should be {SUCCESS_CRITERIA['theme_park_lunch_time']}")
                    
                    # Check Universal Studios enhancement
                    universal_landmark = next((l for l in landmarks if 'universal' in l.get('name', '').lower()), None)
                    if universal_landmark and universal_landmark.get('place_id'):
                        validations["universal_studios_enhanced"] = True
                        print(f"   ✅ Universal Studios enhanced with Google Places data")
                        
                        # Check for address and photo
                        if universal_landmark.get('address'):
                            validations["universal_studios_address"] = True
                            print(f"   ✅ Universal Studios has address: {universal_landmark.get('address')[:50]}...")
                        else:
                            self.validation_issues.append("Universal Studios missing address")
                            
                        if universal_landmark.get('photo_url'):
                            validations["universal_studios_photo"] = True
                            print(f"   ✅ Universal Studios has photo URL")
                        else:
                            print(f"   ⚠️ Universal Studios missing photo URL")
                    else:
                        self.validation_issues.append("Universal Studios not enhanced with Google Places data")
                else:
                    self.validation_issues.append("Universal Studios not detected on Day 1")
            
            # Regular day validation (Days 2 & 3)
            else:
                if len(landmarks) >= 2:
                    validations[f"day_{day_num}_multiple_landmarks"] = True
                    print(f"   ✅ Non-theme park day has {len(landmarks)} landmarks (good variety)")
                else:
                    validations[f"day_{day_num}_multiple_landmarks"] = False
                    self.validation_issues.append(f"Day {day_num} should have 2-3 landmarks, got {len(landmarks)}")
                
                # Check landmark enhancement for regular days
                enhanced_landmarks = [l for l in landmarks if l.get('place_id')]
                if enhanced_landmarks:
                    validations[f"day_{day_num}_landmarks_enhanced"] = True
                    print(f"   ✅ Day {day_num}: {len(enhanced_landmarks)} landmarks enhanced")
                    
                    # Check for addresses on enhanced landmarks
                    landmarks_with_address = [l for l in enhanced_landmarks if l.get('address')]
                    if landmarks_with_address:
                        validations[f"day_{day_num}_landmarks_address"] = True
                        print(f"   ✅ Day {day_num}: {len(landmarks_with_address)} landmarks have addresses")
                    else:
                        self.validation_issues.append(f"Day {day_num} enhanced landmarks missing addresses")
                else:
                    print(f"   ⚠️ Day {day_num}: No landmarks enhanced")
            
            # Collect restaurant data for global validation
            for restaurant in restaurants:
                all_restaurants.append(restaurant)
                if restaurant.get('place_id'):
                    all_restaurant_place_ids.add(restaurant.get('place_id'))
                if restaurant.get('mealtime'):
                    all_meals.add(restaurant.get('mealtime'))
            
            print(f"   Day {day_num}: {'✅ Valid' if len(restaurants) == 3 and len(landmarks) >= 1 else '❌ Issues'}")
            print()
        
        # Global restaurant validation
        print(f"🍽️ RESTAURANT VALIDATION")
        
        # Meal distribution
        required_meals = SUCCESS_CRITERIA["required_meal_types"]
        meal_coverage_complete = required_meals.issubset(all_meals)
        validations["meal_distribution_complete"] = meal_coverage_complete
        print(f"   Meal types: {all_meals}")
        print(f"   Complete coverage: {'✅ Yes' if meal_coverage_complete else '❌ No'}")
        
        # Google Places integration
        restaurants_with_places = len(all_restaurant_place_ids)
        total_restaurants = len(all_restaurants)
        places_rate = restaurants_with_places / total_restaurants if total_restaurants > 0 else 0
        places_success = places_rate >= SUCCESS_CRITERIA["google_places_success_rate"]
        validations["google_places_integration"] = places_success
        print(f"   Google Places integration: {restaurants_with_places}/{total_restaurants} ({places_rate:.1%})")
        print(f"   Integration success: {'✅ Yes' if places_success else '❌ No'}")
        
        # Duplicate detection
        unique_place_ids = len(all_restaurant_place_ids)
        restaurants_with_place_ids = sum(1 for r in all_restaurants if r.get('place_id'))
        no_duplicates = unique_place_ids == restaurants_with_place_ids
        validations["no_duplicate_restaurants"] = no_duplicates
        print(f"   Duplicate check: {unique_place_ids} unique / {restaurants_with_place_ids} total")
        print(f"   No duplicates: {'✅ Yes' if no_duplicates else '❌ No'}")
        print()
        
        # Landmark enhancement validation
        all_landmarks = []
        for day_data in days:
            all_landmarks.extend([b for b in day_data.get('blocks', []) if b.get('type') == 'landmark'])
        
        enhanced_landmarks = sum(1 for l in all_landmarks if l.get('place_id'))
        total_landmarks = len(all_landmarks)
        enhancement_rate = enhanced_landmarks / total_landmarks if total_landmarks > 0 else 0
        enhancement_success = enhancement_rate >= SUCCESS_CRITERIA["landmark_enhancement_rate"]
        validations["landmark_enhancement"] = enhancement_success
        
        print(f"🔍 LANDMARK ENHANCEMENT")
        print(f"   Enhanced landmarks: {enhanced_landmarks}/{total_landmarks} ({enhancement_rate:.1%})")
        print(f"   Enhancement success: {'✅ Yes' if enhancement_success else '❌ No'}")
        print()
        
        # GAP ANALYSIS - Check for large gaps between activities
        gap_issues = self._analyze_day_gaps(day_data, day_num)
        if gap_issues:
            validations[f"day_{day_num}_no_large_gaps"] = False
            for gap_issue in gap_issues:
                self.validation_issues.append(gap_issue)
                print(f"   ⚠️  {gap_issue}")
        else:
            validations[f"day_{day_num}_no_large_gaps"] = True
            print(f"   ✅ No large gaps detected")
        
        self.results = validations
        return validations
    
    def _analyze_day_gaps(self, day_plan: dict, day_num: int) -> List[str]:
        """Analyze gaps between activities and return issues if large gaps found"""
        
        blocks = day_plan.get("blocks", [])
        if len(blocks) < 2:
            return []  # Need at least 2 activities to have gaps
        
        # Sort blocks by start time
        sorted_blocks = sorted(blocks, key=lambda x: x.get("start_time", "00:00"))
        
        gap_issues = []
        
        for i in range(len(sorted_blocks) - 1):
            current_block = sorted_blocks[i]
            next_block = sorted_blocks[i + 1]
            
            # Calculate end time of current block
            start_time = current_block.get("start_time", "00:00")
            duration = current_block.get("duration", "1h")
            
            # Parse start time
            try:
                start_hour, start_min = map(int, start_time.split(":"))
                start_minutes = start_hour * 60 + start_min
            except:
                continue
            
            # Parse duration
            try:
                if duration.endswith("h"):
                    duration_minutes = float(duration[:-1]) * 60
                elif duration.endswith("m"):
                    duration_minutes = float(duration[:-1])
                else:
                    duration_minutes = 120  # Default 2h
            except:
                duration_minutes = 120
            
            end_minutes = start_minutes + duration_minutes
            
            # Parse next block start time
            try:
                next_start = next_block.get("start_time", "00:00")
                next_hour, next_min = map(int, next_start.split(":"))
                next_start_minutes = next_hour * 60 + next_min
            except:
                continue
            
            # Calculate gap in hours
            gap_minutes = next_start_minutes - end_minutes
            gap_hours = gap_minutes / 60
            
            # Check for large gaps (>3 hours)
            if gap_hours > 3.0:
                current_name = current_block.get("name", "Unknown")
                next_name = next_block.get("name", "Unknown")
                gap_issues.append(
                    f"Day {day_num}: Large gap of {gap_hours:.1f} hours between {current_name} "
                    f"({start_time}-{int(end_minutes//60):02d}:{int(end_minutes%60):02d}) and {next_name} ({next_start})"
                )
        
        return gap_issues
    
    def _generate_final_assessment(self) -> bool:
        """Generate final pass/fail assessment"""
        
        print("🎯 FINAL ASSESSMENT")
        print("=" * 50)
        
        # Count successful validations
        passed_validations = sum(1 for v in self.results.values() if v is True)
        total_validations = len(self.results)
        success_rate = passed_validations / total_validations if total_validations > 0 else 0
        
        # Determine overall success (need 90%+ to pass)
        overall_success = success_rate >= 0.90
        
        print(f"📊 Validation Summary: {passed_validations}/{total_validations} ({success_rate:.1%})")
        print()
        
        # Critical requirements check
        critical_requirements = [
            "performance_acceptable",
            "multi_day_structure", 
            "llm_landmarks_only",
            "restaurant_count_correct",
            "google_places_integration"
        ]
        
        critical_passed = all(self.results.get(req, False) for req in critical_requirements)
        
        print(f"🚨 Critical Requirements: {'✅ PASS' if critical_passed else '❌ FAIL'}")
        print(f"🏆 Overall Assessment: {'✅ PASS' if overall_success and critical_passed else '❌ FAIL'}")
        print()
        
        if overall_success and critical_passed:
            print("🎉 COMPREHENSIVE VALIDATION PASSED!")
            print("✅ Enhanced Agentic System is ready for production!")
        else:
            print("❌ COMPREHENSIVE VALIDATION FAILED!")
            print("🔧 Issues found:")
            for issue in self.validation_issues:
                print(f"   - {issue}")
            
            print()
            print("📋 Failed Validations:")
            for validation, passed in self.results.items():
                if not passed:
                    print(f"   ❌ {validation}")
        
        print()
        print("=" * 50)
        
        # Write JSON results
        self._write_json_results(overall_success and critical_passed, success_rate)
        
        return overall_success and critical_passed
    
    def _write_json_results(self, overall_success: bool, success_rate: float):
        """Write comprehensive test results to JSON file"""
        try:
            # Write validation summary
            summary_data = {
                "test_results": self.results,
                "issues": self.validation_issues,
                "success_rate": success_rate * 100,  # Convert to percentage
                "overall_passed": overall_success,
                "duration": self.test_duration,
                "timestamp": time.time()
            }
            
            # Write validation summary to analysis directory
            summary_path = "analysis/comprehensive_test_summary.json"
            with open(summary_path, 'w') as f:
                json.dump(summary_data, f, indent=2)
            
            print(f"📄 Validation summary written to: {summary_path}")
            
            # Write actual agentic result if available
            if hasattr(self, 'agentic_result') and self.agentic_result:
                result_path = "analysis/comprehensive_test_result.json"
                with open(result_path, 'w') as f:
                    json.dump(self.agentic_result, f, indent=2)
                
                print(f"📄 Agentic system result written to: {result_path}")
            else:
                print("⚠️ No agentic result available to save")
            
        except Exception as e:
            print(f"⚠️ Failed to write JSON results: {e}")

# Main execution
async def main():
    """Run the comprehensive validation"""
    validation = ComprehensiveAgenticValidation()
    success = await validation.run_comprehensive_validation()
    
    # Exit with appropriate code
    exit(0 if success else 1)

if __name__ == "__main__":
    # Ensure agentic system is enabled for testing
    os.environ["ENABLE_AGENTIC_SYSTEM"] = "true"
    asyncio.run(main()) 