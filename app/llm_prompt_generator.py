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

    def _analyze_current_schedule(self, blocks: List[ItineraryBlock]) -> str:
        """Analyze the current schedule to identify gaps and issues"""
        
        if not blocks:
            return "No activities scheduled yet."
        
        # Sort blocks by start time
        try:
            sorted_blocks = sorted(
                [b for b in blocks if b.start_time], 
                key=lambda b: datetime.strptime(b.start_time, "%H:%M")
            )
        except (ValueError, TypeError):
            # Handle cases where start_time is missing or invalid
            return "Invalid schedule format; unable to analyze."

        if not sorted_blocks:
            return "No activities with valid start times."
            
        schedule_lines = []
        last_end_time = None
        
        # Set day start time
        day_start_time = datetime.strptime("09:00", "%H:%M").time()
        
        first_activity_start_time = datetime.strptime(sorted_blocks[0].start_time, "%H:%M").time()
        if first_activity_start_time > day_start_time:
            gap_duration = datetime.combine(datetime.today(), first_activity_start_time) - datetime.combine(datetime.today(), day_start_time)
            schedule_lines.append(f"GAP: {gap_duration} before the first activity.")
            
        for block in sorted_blocks:
            start_time_dt = datetime.strptime(block.start_time, "%H:%M")
            
            if last_end_time:
                gap = start_time_dt - last_end_time
                if gap.total_seconds() > 120 * 60: # More than 2 hours
                    schedule_lines.append(f"GAP: {gap} between {schedule_lines[-1].split(' ')[0]} and {block.name}")
            
            duration_minutes = self._parse_duration_to_minutes(block.duration)
            end_time_dt = start_time_dt + timedelta(minutes=duration_minutes)
            last_end_time = end_time_dt
            
            schedule_lines.append(
                f"{block.name}: {block.start_time} - {end_time_dt.strftime('%H:%M')} ({block.duration})"
            )
            
        return "\n".join(schedule_lines)
        
    def _parse_duration_to_minutes(self, duration_str: str) -> int:
        """Parse duration string (e.g., '2h', '1h30m', '45m') into minutes."""
        if not duration_str:
            return 120  # Default to 2 hours
        
        duration_str = duration_str.lower()
        total_minutes = 0
        
        try:
            if 'h' in duration_str:
                parts = duration_str.split('h')
                total_minutes += int(parts[0]) * 60
                if parts[1] and 'm' in parts[1]:
                    total_minutes += int(parts[1].replace('m', ''))
            elif 'm' in duration_str:
                total_minutes += int(duration_str.replace('m', ''))
            else:
                # Assume it's hours if no suffix
                total_minutes = int(float(duration_str) * 60)
                
        except (ValueError, IndexError):
            logger.warning(f"Could not parse duration: '{duration_str}'. Defaulting to 120 minutes.")
            return 120
            
        return total_minutes if total_minutes > 0 else 120

def generate_gap_detection_prompt(
    day_blocks: List[ItineraryBlock],
    destination: str,
    day_num: int
) -> str:
    """Generate LLM prompt for gap detection and regeneration suggestions"""
    
    prompt_generator = LLMPromptGenerator()
    return prompt_generator.generate_gap_detection_prompt(day_blocks, destination, day_num)

def generate_landmark_expansion_prompt(
    destination: str,
    existing_landmarks: List[str],
    trip_details: TripDetails,
    time_slots_to_fill: List[Dict[str, str]]
) -> str:
    """Generate LLM prompt for intelligent landmark expansion to fill gaps"""
    
    prompt_generator = LLMPromptGenerator()
    return prompt_generator.generate_landmark_expansion_prompt(
        destination, existing_landmarks, trip_details, time_slots_to_fill
    ) 