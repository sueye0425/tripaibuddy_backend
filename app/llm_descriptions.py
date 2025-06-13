import asyncio
import json
import logging
import os
from typing import List, Dict, Any, Optional
import aiohttp

class LLMDescriptionService:
    """Service to generate place descriptions using LLM instead of Google place_details"""
    
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')  # or your preferred LLM provider
        self.cache = {}  # Simple in-memory cache for now
        self.logger = logging.getLogger(__name__)
        
        # Model configuration - GPT-3.5-turbo optimized for maximum speed
        self.model_config = {
            'model': 'gpt-3.5-turbo',
            'max_tokens': 60,       # Very short descriptions for speed
            'temperature': 0.1,     # Very low temperature for fastest generation
            'timeout': 2            # Very short timeout for maximum speed
        }

    async def generate_place_descriptions(
        self, 
        places: List[Dict[str, Any]], 
        destination: str,
        user_preferences: Optional[Dict] = None,
        batch_size: int = 4  # Smaller batches for faster processing
    ) -> List[Dict[str, Any]]:
        """
        Generate descriptions for multiple places in a single LLM call
        
        Args:
            places: List of places from Google nearby_search (basic data only)
            destination: Destination city for context
            user_preferences: User preferences for personalized descriptions
        """
        
        # Check cache first
        cache_key = self._get_cache_key(places, destination, user_preferences)
        if cache_key in self.cache:
            cached_descriptions = self.cache[cache_key]
            self.logger.info(f"Found cached LLM descriptions for {len(places)} places")
            return cached_descriptions

        try:
            # 🚀 SPEED OPTIMIZATION: Process in parallel batches for faster response
            if len(places) <= batch_size:
                # Small batch - single API call
                prompt = self._build_batch_prompt(places, destination, user_preferences)
                descriptions = await self._call_llm(prompt, len(places))
                enhanced_places = self._merge_descriptions(places, descriptions)
            else:
                # Large batch - parallel processing
                enhanced_places = await self._process_parallel_batches(
                    places, destination, user_preferences, batch_size
                )
            
            # Cache the results (simple in-memory cache)
            self.cache[cache_key] = enhanced_places
            
            self.logger.info(f"Generated LLM descriptions for {len(places)} places")
            return enhanced_places
            
        except Exception as e:
            self.logger.error(f"LLM description generation failed: {e}")
            # Fallback: return places with basic descriptions
            return self._add_fallback_descriptions(places)

    async def _process_parallel_batches(
        self, 
        places: List[Dict], 
        destination: str, 
        user_preferences: Optional[Dict],
        batch_size: int
    ) -> List[Dict]:
        """Process places in parallel batches for maximum speed"""
        
        # Split places into batches
        batches = [places[i:i + batch_size] for i in range(0, len(places), batch_size)]
        
        # Create tasks for parallel processing
        tasks = []
        for batch in batches:
            task = self._process_single_batch(batch, destination, user_preferences)
            tasks.append(task)
        
        # Execute all batches in parallel
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Combine results
        enhanced_places = []
        for result in batch_results:
            if isinstance(result, Exception):
                self.logger.error(f"Batch processing failed: {result}")
                continue
            enhanced_places.extend(result)
        
        return enhanced_places

    async def _process_single_batch(
        self, 
        batch: List[Dict], 
        destination: str, 
        user_preferences: Optional[Dict]
    ) -> List[Dict]:
        """Process a single batch of places"""
        try:
            prompt = self._build_batch_prompt(batch, destination, user_preferences)
            descriptions = await self._call_llm(prompt, len(batch))
            return self._merge_descriptions(batch, descriptions)
        except Exception as e:
            self.logger.error(f"Single batch processing failed: {e}")
            return self._add_fallback_descriptions(batch)

    def _build_batch_prompt(
        self, 
        places: List[Dict], 
        destination: str, 
        user_preferences: Optional[Dict] = None
    ) -> str:
        """Build optimized prompt for batch description generation"""
        
        # Extract user context
        context = f"Destination: {destination}"
        if user_preferences:
            if user_preferences.get('with_kids'):
                context += ", traveling with children"
            if user_preferences.get('with_elderly'):
                context += ", traveling with elderly"
            if user_preferences.get('special_requests'):
                context += f", special interests: {user_preferences['special_requests']}"

        # Build place list for prompt
        place_list = []
        for i, place in enumerate(places, 1):
            place_info = f"{i}. {place.get('name', 'Unknown')} "
            place_info += f"(Rating: {place.get('rating', 'N/A')}, "
            place_info += f"Type: {', '.join(place.get('types', [])[:2])}, "
            place_info += f"Reviews: {place.get('user_ratings_total', 0)})"
            place_list.append(place_info)

        prompt = f"""Brief descriptions for {destination} landmarks:

{chr(10).join(place_list)}

JSON: [{{"place_number": 1, "description": "30-word description"}}]"""

        return prompt

    async def _call_llm(self, prompt: str, expected_count: int) -> List[str]:
        """Make LLM API call with error handling and retries"""
        
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': self.model_config['model'],
            'messages': [
                {'role': 'system', 'content': 'You are a travel expert who creates engaging place descriptions.'},
                {'role': 'user', 'content': prompt}
            ],
            'max_tokens': self.model_config['max_tokens'] * expected_count,
            'temperature': self.model_config['temperature']
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    'https://api.openai.com/v1/chat/completions',
                    headers=headers,
                    json=payload,
                    timeout=self.model_config['timeout']
                ) as response:
                    
                    if response.status != 200:
                        raise Exception(f"LLM API error: {response.status}")
                    
                    result = await response.json()
                    content = result['choices'][0]['message']['content']
                    
                    # Parse JSON response
                    descriptions_data = json.loads(content.strip())
                    descriptions = [item['description'] for item in descriptions_data]
                    
                    self.logger.info(f"LLM generated {len(descriptions)} descriptions")
                    return descriptions
                    
            except Exception as e:
                self.logger.error(f"LLM API call failed: {e}")
                raise

    def _merge_descriptions(self, places: List[Dict], descriptions: List[str]) -> List[Dict]:
        """Merge LLM descriptions with original place data"""
        enhanced_places = []
        
        for i, place in enumerate(places):
            enhanced_place = place.copy()
            
            if i < len(descriptions):
                enhanced_place['description'] = descriptions[i]
            else:
                # Fallback description
                enhanced_place['description'] = self._generate_fallback_description(place)
            
            # Add metadata
            enhanced_place['description_source'] = 'llm'
            enhanced_places.append(enhanced_place)
        
        return enhanced_places

    def _add_fallback_descriptions(self, places: List[Dict]) -> List[Dict]:
        """Add simple fallback descriptions if LLM fails"""
        for place in places:
            place['description'] = self._generate_fallback_description(place)
            place['description_source'] = 'fallback'
        return places

    def _generate_fallback_description(self, place: Dict) -> str:
        """Generate simple description from place types"""
        name = place.get('name', 'This place')
        types = place.get('types', [])
        rating = place.get('rating')
        
        if 'restaurant' in types:
            desc = f"{name} is a popular restaurant"
        elif 'tourist_attraction' in types:
            desc = f"{name} is a notable tourist attraction"
        elif 'museum' in types:
            desc = f"{name} is a museum"
        elif 'park' in types:
            desc = f"{name} is a park"
        else:
            desc = f"{name} is a local point of interest"
        
        if rating and rating >= 4.0:
            desc += f" with excellent reviews ({rating}/5 stars)"
        elif rating:
            desc += f" with good reviews ({rating}/5 stars)"
        
        desc += "."
        return desc

    def _get_cache_key(self, places: List[Dict], destination: str, preferences: Optional[Dict]) -> str:
        """Generate cache key for place descriptions"""
        place_ids = [place.get('place_id', place.get('name', '')) for place in places]
        key_parts = [
            'llm_descriptions',
            destination.lower().replace(' ', '_'),
            '_'.join(sorted(place_ids[:5])),  # Use first 5 place IDs for key
            str(hash(str(preferences)) if preferences else 'no_prefs')[:8]
        ]
        return ':'.join(key_parts)

    async def close(self):
        """Close connections"""
        self.cache.clear() 