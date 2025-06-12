"""
LLM Prompt Generation System for Complete Itinerary

This module generates intelligent LLM prompts for landmark timing, scheduling,
and gap prevention in the /complete-itinerary endpoint.

Key Features:
1. Intelligent timing distribution throughout the day
2. Gap prevention between activities
3. Context-aware landmark selection
4. Meal timing optimization
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json

from .schema import TripDetails, DayAttraction, ItineraryBlock, Location

logger = logging.getLogger(__name__)


class LLMPromptGenerator:
    """Generates LLM prompts for intelligent itinerary planning"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def generate_landmark_timing_prompt(
        self,
        destination: str,
        day_num: int,
        existing_landmarks: List[Dict],
        trip_details: Dict,
        is_theme_park_day: bool = False
    ) -> str:
        """Generate LLM prompt for intelligent landmark timing and scheduling"""
        
        # Build context about existing landmarks
        existing_context = self._build_existing_landmarks_context(existing_landmarks)
        
        # Build traveler context
        traveler_context = self._build_traveler_context(trip_details)
        
        # Build timing requirements
        timing_requirements = self._build_timing_requirements(is_theme_park_day)
        
        # Generate the prompt
        prompt = f"""You are an expert travel planner creating a detailed daily itinerary for {destination}.

DESTINATION: {destination}
DAY: {day_num}
TRAVELER PROFILE: {traveler_context}

EXISTING LANDMARKS:
{existing_context}

TASK: Create a complete daily schedule with proper timing to avoid gaps.

{timing_requirements}

CRITICAL REQUIREMENTS:
1. NO GAPS longer than 2 hours between activities
2. Activities must span from 9:00 AM to 7:00 PM
3. Include 2-3 additional landmarks if not a theme park day
4. Provide specific start times and realistic durations
5. Consider travel time between locations
6. Ensure logical flow throughout the day

SPECIAL REQUESTS: {trip_details.get('specialRequests', 'None')}

OUTPUT FORMAT (JSON):
{{
    "landmarks": [
        {{
            "name": "Landmark Name",
            "description": "Brief description",
            "start_time": "HH:MM",
            "duration": "Xh" or "XhYm",
            "reasoning": "Why this timing works",
            "location_type": "indoor/outdoor/mixed"
        }}
    ],
    "meal_suggestions": [
        {{
            "meal_type": "breakfast/lunch/dinner",
            "suggested_time": "HH:MM",
            "reasoning": "Why this timing prevents gaps"
        }}
    ],
    "day_flow_analysis": "Overall analysis of day timing and gap prevention"
}}

Generate a well-timed itinerary that keeps travelers engaged throughout the day without exhausting gaps."""
        
        return prompt
    
    def generate_gap_detection_prompt(
        self,
        day_blocks: List[ItineraryBlock],
        destination: str,
        day_num: int
    ) -> str:
        """Generate LLM prompt for gap detection and regeneration suggestions"""
        
        # Analyze current schedule
        schedule_analysis = self._analyze_current_schedule(day_blocks)
        
        prompt = f"""You are a travel itinerary quality analyst reviewing Day {day_num} in {destination}.

CURRENT SCHEDULE:
{schedule_analysis}

TASK: Analyze this schedule for timing gaps and provide regeneration suggestions.

ANALYSIS CRITERIA:
1. Identify gaps longer than 2 hours between activities
2. Check if day utilization is optimal (9 AM - 7 PM)
3. Assess meal timing effectiveness
4. Evaluate activity flow and logistics

GAP DETECTION RULES:
- Breakfast to first activity: ≤ 1 hour gap acceptable
- Between activities: ≤ 2 hours gap acceptable  
- Lunch timing: Should break up long activity stretches
- Dinner timing: Should not create evening dead time
- Last activity should end by 7 PM

OUTPUT FORMAT (JSON):
{{
    "gaps_detected": [
        {{
            "gap_location": "between X and Y",
            "gap_duration": "X hours Y minutes",
            "severity": "minor/moderate/severe",
            "impact": "Description of impact on traveler experience"
        }}
    ],
    "regeneration_needed": true/false,
    "regeneration_suggestions": [
        {{
            "action": "add_landmark/adjust_timing/move_meal",
            "details": "Specific suggestion",
            "new_timing": "Suggested timing",
            "reasoning": "Why this fixes the gap"
        }}
    ],
    "overall_assessment": "Summary of day quality and recommendations"
}}

Provide actionable suggestions to eliminate gaps and improve day flow."""
        
        return prompt
    
    def generate_landmark_expansion_prompt(
        self,
        destination: str,
        existing_landmarks: List[str],
        trip_details: TripDetails,
        time_slots_to_fill: List[Dict[str, str]]
    ) -> str:
        """Generate LLM prompt for intelligent landmark expansion to fill gaps"""
        
        existing_names = ", ".join(existing_landmarks)
        traveler_context = self._build_traveler_context(trip_details)
        
        # Format time slots
        slots_context = []
        for slot in time_slots_to_fill:
            slots_context.append(f"- {slot['start_time']} to {slot['end_time']} ({slot['duration']})")
        slots_text = "\n".join(slots_context)
        
        prompt = f"""You are a local travel expert for {destination} tasked with filling specific time gaps in an itinerary.

DESTINATION: {destination}
TRAVELER PROFILE: {traveler_context}

EXISTING LANDMARKS (DO NOT REPEAT):
{existing_names}

TIME SLOTS TO FILL:
{slots_text}

TASK: Recommend specific landmarks that fit perfectly into these time slots.

SELECTION CRITERIA:
1. Must be different from existing landmarks
2. Must fit the exact time duration available
3. Should be logistically feasible (consider travel time)
4. Match traveler preferences and demographics
5. Provide variety in activity types (indoor/outdoor, active/relaxed)

SPECIAL REQUESTS: {trip_details.specialRequests or "None"}

OUTPUT FORMAT (JSON):
{{
    "landmark_recommendations": [
        {{
            "name": "Landmark Name",
            "description": "Brief description focusing on why it's perfect for this traveler",
            "target_time_slot": "HH:MM - HH:MM",
            "duration": "Xh" or "XhYm",
            "activity_type": "indoor/outdoor/mixed",
            "energy_level": "low/medium/high",
            "why_perfect": "Explanation of why this landmark fits this specific gap",
            "travel_logistics": "How to get there from previous location"
        }}
    ],
    "timing_rationale": "Overall explanation of how these recommendations eliminate gaps"
}}

Focus on landmarks that create seamless day flow without overwhelming the traveler."""
        
        return prompt
    
    def _build_existing_landmarks_context(self, landmarks: List[Dict]) -> str:
        """Build context string for existing landmarks"""
        if not landmarks:
            return "No existing landmarks scheduled."
        
        context_lines = []
        for landmark in landmarks:
            duration_str = landmark.get('duration', '2h')
            start_time = landmark.get('start_time', 'TBD')
            name = landmark.get('name', 'Unknown')
            description = landmark.get('description', '')
            context_lines.append(
                f"- {name}: {start_time} ({duration_str}) - {description}"
            )
        
        return "\n".join(context_lines)
    
    def _build_traveler_context(self, trip_details: Dict) -> str:
        """Build traveler context for LLM prompts"""
        context_parts = []
        
        if trip_details.get('withKids'):
            ages = trip_details.get('kidsAge', [])
            ages_str = ", ".join(map(str, ages)) if ages else "unspecified ages"
            context_parts.append(f"Traveling with kids (ages: {ages_str})")
        
        if trip_details.get('withElders'):
            context_parts.append("Traveling with elderly companions")
        
        if trip_details.get('specialRequests'):
            context_parts.append(f"Special requests: {trip_details['specialRequests']}")
        
        travel_days = trip_details.get('travelDays', 1)
        context_parts.append(f"Trip duration: {travel_days} days")
        
        return "; ".join(context_parts) if context_parts else "Standard adult travelers"
    
    def _build_timing_requirements(self, is_theme_park_day: bool) -> str:
        """Build timing requirements based on day type"""
        if is_theme_park_day:
            return """THEME PARK DAY TIMING:
- Single major attraction: 8-10 hours duration
- Start time: 9:00 AM
- Meals integrated within or nearby the park
- Minimal additional landmarks needed"""
        else:
            return """REGULAR DAY TIMING:
- Multiple landmarks: 2-3 activities
- Activity duration: 1.5-3 hours each
- Start first activity: 9:00-10:00 AM
- End last activity: 6:00-7:00 PM
- Strategic meal placement to prevent gaps
- Variety in activity types and energy levels"""
    
    def _analyze_current_schedule(self, blocks: List[ItineraryBlock]) -> str:
        """Analyze current schedule for gap detection prompt"""
        if not blocks:
            return "No activities scheduled."
        
        # Sort blocks by start time
        sorted_blocks = []
        for block in blocks:
            if block.start_time:
                try:
                    start_time = datetime.strptime(block.start_time, "%H:%M")
                    sorted_blocks.append((start_time, block))
                except ValueError:
                    continue
        
        sorted_blocks.sort(key=lambda x: x[0])
        
        # Build schedule analysis
        analysis_lines = []
        for i, (start_time, block) in enumerate(sorted_blocks):
            duration_str = block.duration or "1h"
            block_type = block.type or "activity"
            
            # Calculate end time
            try:
                duration_minutes = self._parse_duration_to_minutes(duration_str)
                end_time = start_time + timedelta(minutes=duration_minutes)
                
                analysis_lines.append(
                    f"{i+1}. {start_time.strftime('%H:%M')}-{end_time.strftime('%H:%M')}: "
                    f"{block.name} ({block_type}, {duration_str})"
                )
                
                # Check gap to next activity
                if i < len(sorted_blocks) - 1:
                    next_start_time = sorted_blocks[i + 1][0]
                    gap_minutes = (next_start_time - end_time).total_seconds() / 60
                    if gap_minutes > 0:
                        gap_hours = gap_minutes / 60
                        analysis_lines.append(f"   → GAP: {gap_minutes:.0f} minutes ({gap_hours:.1f} hours)")
                
            except Exception:
                analysis_lines.append(f"{i+1}. {block.start_time}: {block.name} ({block_type})")
        
        return "\n".join(analysis_lines)
    
    def _parse_duration_to_minutes(self, duration_str: str) -> int:
        """Parse duration string to minutes"""
        if not duration_str:
            return 60
        
        duration_str = duration_str.lower().strip()
        
        if duration_str.endswith('h'):
            hours_str = duration_str[:-1]
            try:
                hours = float(hours_str)
                return int(hours * 60)
            except ValueError:
                return 60
        elif 'h' in duration_str and 'm' in duration_str:
            # Format like "2h30m"
            try:
                parts = duration_str.replace('h', ':').replace('m', '').split(':')
                hours = int(parts[0])
                minutes = int(parts[1]) if len(parts) > 1 else 0
                return hours * 60 + minutes
            except ValueError:
                return 60
        else:
            try:
                return int(float(duration_str) * 60)
            except ValueError:
                return 60


class RegenerationAgent:
    """Agent responsible for regenerating landmarks when gaps are detected"""
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.prompt_generator = LLMPromptGenerator()
        self.logger = logging.getLogger(__name__)
    
    async def detect_and_fix_gaps(
        self,
        day_blocks: List[ItineraryBlock],
        destination: str,
        day_num: int,
        trip_details: TripDetails
    ) -> List[ItineraryBlock]:
        """Detect gaps and regenerate landmarks to fix them"""
        
        try:
            # Generate gap detection prompt
            gap_prompt = self.prompt_generator.generate_gap_detection_prompt(
                day_blocks, destination, day_num
            )
            
            # Call LLM for gap analysis (if LLM client available)
            if self.llm_client:
                gap_analysis = await self._call_llm_for_gap_analysis(gap_prompt)
                
                if gap_analysis.get("regeneration_needed", False):
                    self.logger.info(f"🔄 Gaps detected on Day {day_num}, regenerating landmarks...")
                    
                    # Generate landmark expansion prompt
                    time_slots = self._extract_time_slots_from_analysis(gap_analysis)
                    existing_landmark_names = [b.name for b in day_blocks if b.type == "landmark"]
                    
                    expansion_prompt = self.prompt_generator.generate_landmark_expansion_prompt(
                        destination, existing_landmark_names, trip_details, time_slots
                    )
                    
                    # Get new landmarks to fill gaps
                    new_landmarks = await self._call_llm_for_landmark_expansion(expansion_prompt)
                    
                    # Integrate new landmarks into day blocks
                    enhanced_blocks = self._integrate_new_landmarks(day_blocks, new_landmarks)
                    
                    self.logger.info(f"✅ Day {day_num} gaps fixed with {len(new_landmarks)} additional landmarks")
                    return enhanced_blocks
            
            # If no LLM or no gaps detected, return original blocks
            return day_blocks
            
        except Exception as e:
            self.logger.error(f"Error in gap detection/fixing: {e}")
            return day_blocks
    
    async def _call_llm_for_gap_analysis(self, prompt: str) -> Dict[str, Any]:
        """Call LLM for gap analysis (placeholder for actual LLM integration)"""
        # This would integrate with your actual LLM client (OpenAI, Anthropic, etc.)
        # For now, return a mock response
        return {
            "gaps_detected": [],
            "regeneration_needed": False,
            "regeneration_suggestions": [],
            "overall_assessment": "Schedule analysis completed"
        }
    
    async def _call_llm_for_landmark_expansion(self, prompt: str) -> List[Dict[str, Any]]:
        """Call LLM for landmark expansion (placeholder for actual LLM integration)"""
        # This would integrate with your actual LLM client
        # For now, return empty list
        return []
    
    def _extract_time_slots_from_analysis(self, gap_analysis: Dict[str, Any]) -> List[Dict[str, str]]:
        """Extract time slots that need to be filled from gap analysis"""
        time_slots = []
        
        for gap in gap_analysis.get("gaps_detected", []):
            # Parse gap information to create time slots
            # This is a simplified implementation
            time_slots.append({
                "start_time": "14:00",  # Example
                "end_time": "16:00",    # Example
                "duration": "2h"       # Example
            })
        
        return time_slots
    
    def _integrate_new_landmarks(
        self,
        existing_blocks: List[ItineraryBlock],
        new_landmarks: List[Dict[str, Any]]
    ) -> List[ItineraryBlock]:
        """Integrate new landmarks into existing day blocks"""
        enhanced_blocks = existing_blocks.copy()
        
        for landmark_data in new_landmarks:
            # Create new ItineraryBlock from landmark data
            new_block = ItineraryBlock(
                name=landmark_data.get("name", "New Landmark"),
                type="landmark",
                description=landmark_data.get("description", ""),
                start_time=landmark_data.get("target_time_slot", "").split(" - ")[0],
                duration=landmark_data.get("duration", "2h")
            )
            enhanced_blocks.append(new_block)
        
        return enhanced_blocks 