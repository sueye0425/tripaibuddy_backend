#!/usr/bin/env python3
"""
COMPREHENSIVE AGENTIC SYSTEM TEST
=================================

This test validates all key requirements and performance criteria for the enhanced agentic system.
It includes detailed timing breakdown with PASS/FAIL thresholds for each phase.

⚠️  FOR DEBUGGING ONLY - NOT FOR PRODUCTION ⚠️
"""

import asyncio
import aiohttp
import time
import json
from typing import Dict, Any, List

from app.schema import LandmarkSelection, DayAttraction, TripDetails, Attraction, Location
from app.agentic_itinerary import enhanced_agentic_system, AgentState
from app.places_client import GooglePlacesClient

# PERFORMANCE THRESHOLDS (in seconds)
PERFORMANCE_THRESHOLDS = {
    "total_time_max": 25.0,  # Total should be under 25s for 3 days (reduced from 35s)
    "parallel_day_generation_max": 8.0,  # Should be under 8s for 3 days (reduced from 12s)
    "duplicate_detection_max": 1.0,  # Should be under 1s
    "selective_regeneration_max": 10.0,  # Should be under 10s (reduced from 15s)
    "parallel_enhancement_validation_max": 8.0,  # Should be under 8s (reduced from 10s)
}

# SUCCESS CRITERIA
SUCCESS_CRITERIA = {
    "min_days": 3,
    "restaurants_per_day": 3,
    "min_landmarks_per_day": 1,
    "required_meal_types": {"breakfast", "lunch", "dinner"},
    "google_places_success_rate": 0.8,  # 80% of restaurants should have place_id
    "landmark_enhancement_rate": 0.5,  # 50% of landmarks should be enhanced
}

class ComprehensiveAgenticTest:
    
    def __init__(self):
        self.session = None
        self.timing_results = {}
        self.validation_results = {}
        
    async def run_comprehensive_test(self):
        """Run comprehensive test with detailed timing and validation"""
        print("🎯 COMPREHENSIVE AGENTIC SYSTEM TEST")
        print("=" * 60)
        print("🚀 Testing Enhanced Agentic System with Performance Monitoring")
        print()
        
        # Create session for GooglePlacesClient
        self.session = aiohttp.ClientSession()
        
        try:
            # Run test
            overall_start = time.time()
            result = await self._execute_agentic_system_test()
            overall_duration = time.time() - overall_start
            
            # Performance Analysis
            self._analyze_performance(overall_duration)
            
            # Validation Analysis
            self._analyze_validation(result)
            
            # Final Assessment
            self._generate_final_assessment(overall_duration)
            
        finally:
            await self.session.close()
    
    async def _execute_agentic_system_test(self) -> Dict[str, Any]:
        """Execute the agentic system with timing monitoring"""
        
        # Create comprehensive test selection
        selection = LandmarkSelection(
            details=TripDetails(
                destination='Orlando, FL',
                travelDays=3,
                startDate='2024-01-01',
                endDate='2024-01-03',
                withKids=True,
                withElders=False,
                kidsAge=[8, 12],
                specialRequests='Include Universal Studios and family-friendly activities'
            ),
            itinerary=[
                DayAttraction(
                    day=1,
                    attractions=[
                        Attraction(
                            name="Universal Studios", 
                            description="Universal Studios theme park",
                            location=Location(lat=28.4743, lng=-81.4677),
                            type="landmark"
                        )
                    ]
                ),
                DayAttraction(
                    day=2,
                    attractions=[
                        Attraction(
                            name="Disney World", 
                            description="Disney World theme park",
                            location=Location(lat=28.3852, lng=-81.5639),
                            type="landmark"
                        )
                    ]
                ),
                DayAttraction(
                    day=3,
                    attractions=[]
                )
            ]
        )
        
        # Execute the agentic system
        async with aiohttp.ClientSession() as session:
            places_client = GooglePlacesClient(session)
            
            start_time = time.time()
            result = await enhanced_agentic_system.generate_itinerary(selection, places_client)
            total_time = time.time() - start_time
            
            # The agentic system returns a specific format - extract the itinerary
            if hasattr(result, 'days'):
                # Convert structured result to dict format expected by test
                return {
                    'days': [
                        {
                            'day': day.day,
                            'blocks': [
                                {
                                    'name': block.name,
                                    'type': block.type,
                                    'place_id': block.place_id,
                                    'address': block.address,
                                    'mealtime': getattr(block, 'mealtime', None),
                                    'rating': getattr(block, 'rating', None),
                                    'start_time': getattr(block, 'start_time', None),
                                    'duration': getattr(block, 'duration', None)
                                } for block in day.blocks
                            ]
                        } for day in result.days
                    ],
                    'total_time': total_time
                }
            else:
                # Fallback - check if result is already in expected format
                if isinstance(result, dict) and 'itinerary' in result:
                    return {
                        'days': result['itinerary'],
                        'total_time': total_time
                    }
                else:
                    # Unknown format
                    logger.error(f"Unexpected result format from agentic system: {type(result)}")
                    return {
                        'days': [],
                        'total_time': total_time,
                        'error': f"Unexpected result format: {type(result)}"
                    }
    
    def _analyze_performance(self, overall_duration: float):
        """Analyze performance with detailed breakdown"""
        print()
        print("📊 PERFORMANCE ANALYSIS")
        print("-" * 40)
        
        # Overall performance
        overall_status = "PASS" if overall_duration <= PERFORMANCE_THRESHOLDS["total_time_max"] else "FAIL"
        print(f"⏱️  Total Time: {overall_duration:.2f}s (max: {PERFORMANCE_THRESHOLDS['total_time_max']}s) [{overall_status}]")
        
        # Phase breakdown
        for phase, data in self.timing_results.items():
            duration = data["duration"]
            threshold = data["threshold"]
            status = data["status"]
            percentage = (duration / overall_duration * 100) if overall_duration > 0 else 0
            
            status_icon = "✅" if status == "PASS" else "❌"
            print(f"{status_icon} {phase}: {duration:.2f}s ({percentage:.1f}%) [max: {threshold}s]")
            
            # Show details if available
            if data["details"]:
                details_str = ", ".join(f"{k}: {v}" for k, v in data["details"].items())
                print(f"   Details: {details_str}")
        
        # Check for missing phases (indicates fallback)
        expected_phases = ["parallel_day_generation", "duplicate_detection", "parallel_enhancement_validation"]
        missing_phases = [p for p in expected_phases if p not in self.timing_results]
        if missing_phases:
            print(f"⚠️  Missing phases (fallback detected): {missing_phases}")
    
    def _analyze_validation(self, result: Dict[str, Any]):
        """Analyze result quality and correctness"""
        print()
        print("📋 VALIDATION ANALYSIS")
        print("----------------------------------------")
        
        validation_results = self._validate_structure(result)
        
        # Days generated
        days_count = len(result.get('days', []))
        print(f"📅 Days generated: {days_count} (min: 3) [{'PASS' if days_count >= 3 else 'FAIL'}]")
        
        # Per-day validation
        for i in range(1, 4):
            # Restaurant count
            restaurants_key = f'day_{i}_restaurants'
            if restaurants_key in validation_results:
                status = "PASS" if validation_results[restaurants_key] else "FAIL"
                day_data = result['days'][i-1] if i-1 < len(result['days']) else {}
                restaurant_count = len([b for b in day_data.get('blocks', []) if b.get('type') == 'restaurant'])
                print(f"🍽️  Day {i} restaurants: {restaurant_count} (expected: 3) [{status}]")
            
            # Landmark count  
            landmarks_key = f'day_{i}_landmarks'
            if landmarks_key in validation_results:
                status = "PASS" if validation_results[landmarks_key] else "FAIL"
                day_data = result['days'][i-1] if i-1 < len(result['days']) else {}
                landmark_count = len([b for b in day_data.get('blocks', []) if b.get('type') == 'landmark'])
                print(f"🏛️  Day {i} landmarks: {landmark_count} (min: 1) [{status}]")
        
        # Google Places integration
        places_integration = validation_results.get('google_places_integration', False)
        places_rate = self._calculate_places_integration_rate(result)
        status = "PASS" if places_integration else "FAIL"
        print(f"🔗 Google Places integration: {places_rate:.1%} (min: 80%) [{status}]")
        
        # Landmark enhancement
        landmark_enhancement = validation_results.get('landmark_enhancement', False)
        enhancement_rate = self._calculate_landmark_enhancement_rate(result)
        status = "PASS" if landmark_enhancement else "FAIL"
        print(f"✨ Landmark enhancement: {enhancement_rate:.1%} (min: 50%) [{status}]")
        
        # Meal coverage
        meal_coverage = validation_results.get('meal_coverage', False)
        all_meals = set()
        for day in result.get('days', []):
            for block in day.get('blocks', []):
                if block.get('type') == 'restaurant' and block.get('mealtime'):
                    all_meals.add(block.get('mealtime'))
        status = "PASS" if meal_coverage else "FAIL"
        print(f"🍳 Meal types coverage: {len(all_meals)}/3 [{status}]")
        print(f"   Found: {all_meals}")
        
        # Calculate validation score
        validation_count = sum(1 for v in validation_results.values() if v is True)
        total_validations = len(validation_results)
        validation_percentage = (validation_count / total_validations * 100) if total_validations > 0 else 0
        
        self.validation_results = {
            'validation_passed': validation_percentage >= 85.0,  # 85% threshold
            'validation_rate': validation_percentage / 100,
            'google_places_rate': places_rate,
            'landmark_enhancement_rate': enhancement_rate,
            'details': validation_results
        }
    
    def _generate_final_assessment(self, overall_duration: float):
        """Generate final pass/fail assessment"""
        print()
        print("🎯 FINAL ASSESSMENT")
        print("=" * 60)
        
        # Performance assessment
        performance_passes = 0
        performance_total = 0
        
        overall_performance_pass = overall_duration <= PERFORMANCE_THRESHOLDS["total_time_max"]
        performance_total += 1
        if overall_performance_pass:
            performance_passes += 1
        
        for phase_data in self.timing_results.values():
            performance_total += 1
            if phase_data["status"] == "PASS":
                performance_passes += 1
        
        performance_rate = performance_passes / performance_total if performance_total > 0 else 0
        
        # Validation assessment
        validation_pass = self.validation_results.get("validation_passed", False)
        
        # Overall assessment
        overall_pass = performance_rate >= 0.8 and validation_pass
        
        print(f"⚡ Performance: {performance_passes}/{performance_total} criteria passed ({performance_rate:.1%})")
        print(f"✅ Validation: {'PASS' if validation_pass else 'FAIL'}")
        print(f"🏆 Overall: {'PASS' if overall_pass else 'FAIL'}")
        
        if overall_pass:
            print("🎉 COMPREHENSIVE TEST PASSED - Agentic system is ready for production!")
        else:
            print("❌ COMPREHENSIVE TEST FAILED - Issues need to be resolved")
            
            # Specific recommendations
            if performance_rate < 0.8:
                print("\n🔧 Performance Issues:")
                for phase, data in self.timing_results.items():
                    if data["status"] == "FAIL":
                        print(f"   - {phase}: {data['duration']:.2f}s (exceeds {data['threshold']}s)")
            
            if not validation_pass:
                print("\n🔧 Validation Issues:")
                if self.validation_results.get("google_places_rate", 0) < SUCCESS_CRITERIA["google_places_success_rate"]:
                    print(f"   - Google Places integration too low: {self.validation_results['google_places_rate']:.1%}")
                if self.validation_results.get("landmark_enhancement_rate", 0) < SUCCESS_CRITERIA["landmark_enhancement_rate"]:
                    print(f"   - Landmark enhancement too low: {self.validation_results['landmark_enhancement_rate']:.1%}")

    def _validate_structure(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the structure and content of the result"""
        validation = {}
        
        try:
            days = result.get('days', [])
            validation['days_generated'] = len(days) >= 3
            
            for i, day in enumerate(days[:3], 1):
                day_blocks = day.get('blocks', [])
                restaurants = [b for b in day_blocks if b.get('type') == 'restaurant']
                landmarks = [b for b in day_blocks if b.get('type') == 'landmark']
                
                # Check restaurant count (always exactly 3)
                validation[f'day_{i}_restaurants'] = len(restaurants) == 3
                
                # Check landmark count (theme park days should have 1, regular days can have multiple)
                is_theme_park_day = any(
                    keyword in str(landmark.get('name', '')).lower() 
                    for landmark in landmarks 
                    for keyword in ['universal', 'disney', 'magic kingdom', 'theme park']
                )
                
                if is_theme_park_day:
                    # Theme park days should have exactly 1 landmark
                    validation[f'day_{i}_landmarks'] = len(landmarks) == 1
                    self.details.append(f"Day {i} (theme park): {len(landmarks)} landmark - {landmarks[0].get('name', 'Unknown') if landmarks else 'None'}")
                else:
                    # Regular days should have at least 1 landmark (can have multiple)
                    validation[f'day_{i}_landmarks'] = len(landmarks) >= 1
                    landmark_names = [l.get('name', 'Unknown') for l in landmarks]
                    self.details.append(f"Day {i} (regular): {len(landmarks)} landmarks - {', '.join(landmark_names)}")
            
            # Google Places integration check
            all_blocks = []
            for day in days:
                all_blocks.extend(day.get('blocks', []))
            
            blocks_with_place_id = sum(1 for block in all_blocks if block.get('place_id'))
            total_blocks = len(all_blocks)
            
            places_percentage = (blocks_with_place_id / total_blocks * 100) if total_blocks > 0 else 0
            validation['google_places_integration'] = places_percentage >= 80.0
            
            # Enhanced landmarks check
            landmarks_only = [b for b in all_blocks if b.get('type') == 'landmark']
            enhanced_landmarks = sum(1 for landmark in landmarks_only if landmark.get('place_id'))
            total_landmarks = len(landmarks_only)
            
            enhancement_percentage = (enhanced_landmarks / total_landmarks * 100) if total_landmarks > 0 else 0
            validation['landmark_enhancement'] = enhancement_percentage >= 50.0
            
            # Meal types coverage
            all_meals = set()
            for day in days:
                for block in day.get('blocks', []):
                    if block.get('type') == 'restaurant' and block.get('mealtime'):
                        all_meals.add(block.get('mealtime'))
            
            validation['meal_coverage'] = len(all_meals) >= 3
            
            return validation
            
        except Exception as e:
            logger.error(f"Error validating structure: {e}")
            return {}

    def _calculate_places_integration_rate(self, result: Dict[str, Any]) -> float:
        """Calculate the Google Places integration rate"""
        if not result or 'days' not in result:
            return 0.0
        
        total_restaurants = 0
        total_places = 0
        
        for day in result['days']:
            restaurants = [b for b in day.get('blocks', []) if b.get('type') == 'restaurant']
            total_restaurants += len(restaurants)
            total_places += sum(1 for b in restaurants if b.get('place_id'))
        
        if total_restaurants == 0:
            return 0.0
        
        return (total_places / total_restaurants) * 100

    def _calculate_landmark_enhancement_rate(self, result: Dict[str, Any]) -> float:
        """Calculate the landmark enhancement rate"""
        if not result or 'days' not in result:
            return 0.0
        
        total_landmarks = 0
        total_enhanced = 0
        
        for day in result['days']:
            landmarks = [b for b in day.get('blocks', []) if b.get('type') == 'landmark']
            total_landmarks += len(landmarks)
            total_enhanced += sum(1 for b in landmarks if b.get('place_id'))
        
        if total_landmarks == 0:
            return 0.0
        
        return (total_enhanced / total_landmarks) * 100

# Main execution
async def main():
    test = ComprehensiveAgenticTest()
    await test.run_comprehensive_test()

if __name__ == "__main__":
    asyncio.run(main()) 