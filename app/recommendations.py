import logging
from typing import Dict, List, Optional, Any
from .places_client import GooglePlacesClient
from .preferences import PreferencesParser
import asyncio
import json
import aiohttp
from fastapi import HTTPException

class RecommendationGenerator:
    def __init__(self, places_client: Optional[GooglePlacesClient] = None):
        self.places_client = places_client if places_client else GooglePlacesClient()
        self.preferences_parser = PreferencesParser()
        self.logger = logging.getLogger(__name__)
        self.default_photo_max_width = 800 # Default max width for photos

    def format_place(self, place: Dict[str, Any], photo_max_width: Optional[int] = None) -> Dict[str, Any]:
        """Format a Google Place into our standard format, including full photo URLs."""
        
        current_photo_max_width = photo_max_width if photo_max_width is not None else self.default_photo_max_width

        try:
            # Handle nested result structure
            place_data = place.get('result', place)
            
            # Get name from either top level or nested result
            name = place_data.get('name') or place.get('name', 'Unknown Place')
            
            # Get photo references
            photo_references = []
            if 'photos' in place_data:
                photo_list_data = place_data['photos']
                if isinstance(photo_list_data, list):
                    photo_references = [photo.get('photo_reference') for photo in photo_list_data if photo and isinstance(photo, dict) and photo.get('photo_reference')]
                elif isinstance(photo_list_data, dict): # Handle case where 'photos' might be a single dict (though API usually returns list)
                    photo_ref = photo_list_data.get('photo_reference')
                    if photo_ref:
                        photo_references = [photo_ref]
            
            # Construct full photo URLs using the backend proxy
            photo_urls = []
            # No need to check for places_client.api_key here, proxy endpoint handles it server-side
            for ref in photo_references:
                if ref: # Ensure ref is not None or empty
                    # Construct URL to our own backend proxy
                    # The proxy will handle the Google API key and actual fetching
                    proxy_url = f"/api/v1/image_proxy?photoreference={ref}"
                    if current_photo_max_width:
                        proxy_url += f"&maxwidth={current_photo_max_width}"
                    # Add maxheight if needed, or make it exclusive with maxwidth in proxy
                    photo_urls.append(proxy_url)
            
            # Get location safely with better error handling
            location = {}
            geometry = place_data.get('geometry', {})
            if isinstance(geometry, dict):
                loc = geometry.get('location', {})
                if isinstance(loc, dict):
                    location = {
                        'lat': float(loc.get('lat', 0.0)),
                        'lng': float(loc.get('lng', 0.0))
                    }
            
            # Get rating and total ratings safely
            try:
                rating = float(place_data.get('rating', 0.0))
            except (TypeError, ValueError):
                rating = 0.0
                
            try:
                total_ratings = int(place_data.get('user_ratings_total', 0))
            except (TypeError, ValueError):
                total_ratings = 0
            
            # Generate proper description based on place types and available info
            description = self._generate_place_description(place_data)
            
            # Get other fields with safe defaults
            formatted_place = {
                "name": name,
                "description": description,  # Use generated description, not address
                "address": place_data.get('formatted_address', ''),  # Separate address field
                "place_id": place_data.get('place_id', ''),
                "rating": rating,
                "user_ratings_total": total_ratings,
                "location": location,
                "photos": photo_urls,  # Use the new list of full URLs
                "opening_hours": place_data.get('opening_hours', {}),
                "types": place_data.get('types', [])  # Add types from Google Places
            }
            
            # Add optional fields if they exist
            if 'price_level' in place_data:
                formatted_place['price_level'] = place_data['price_level']
            if 'website' in place_data:
                formatted_place['website'] = place_data['website']
            if 'formatted_phone_number' in place_data:
                formatted_place['phone'] = place_data['formatted_phone_number']
            if 'wheelchair_accessible_entrance' in place_data:
                formatted_place['wheelchair_accessible'] = place_data['wheelchair_accessible_entrance']
            
            return formatted_place
            
        except Exception as e:
            self.logger.error(f"Error formatting place: {str(e)}, place data: {json.dumps(place, indent=2)}")
            # Return minimal valid place data
            return {
                "name": place.get('name', 'Unknown Place'),
                "description": "",
                "address": place.get('formatted_address', ''),
                "place_id": place.get('place_id', ''),
                "rating": 0.0,
                "user_ratings_total": 0,
                "location": {},
                "photos": [], # Empty list if error occurs
                "opening_hours": {},
                "types": []
            }

    def _generate_place_description(self, place_data: Dict[str, Any]) -> str:
        """Generate a proper description for a place based on its types and Google Places data"""
        
        # Try to get editorial summary from Google Places first (best quality)
        if 'editorial_summary' in place_data and place_data['editorial_summary']:
            summary = place_data['editorial_summary'].get('overview', '')
            if summary and len(summary.strip()) > 10:
                return summary.strip()
        
        # Try to get business status or description from other fields
        if 'business_status' in place_data and place_data['business_status'] == 'OPERATIONAL':
            # Use first review snippet if available
            reviews = place_data.get('reviews', [])
            if reviews and len(reviews) > 0:
                first_review = reviews[0].get('text', '')
                if first_review and len(first_review.strip()) > 20:
                    # Use first sentence of review as description
                    first_sentence = first_review.split('.')[0].strip()
                    if len(first_sentence) > 10:
                        return first_sentence + '.'
        
        # Generate description based on place types
        types = place_data.get('types', [])
        name = place_data.get('name', '')
        
        if not types:
            return f"Local establishment"
        
        # Define type-based descriptions
        type_descriptions = {
            'tourist_attraction': 'Popular tourist destination and attraction',
            'museum': 'Museum with exhibits and collections',
            'park': 'Park with outdoor recreational facilities',
            'zoo': 'Zoo featuring various animal exhibits',
            'aquarium': 'Aquarium with marine life and underwater exhibits',
            'amusement_park': 'Amusement park with rides and entertainment',
            'theme_park': 'Theme park with attractions and entertainment',
            'art_gallery': 'Art gallery showcasing various artworks',
            'restaurant': 'Restaurant serving food and beverages',
            'cafe': 'Café with coffee and light meals',
            'food': 'Food establishment',
            'meal_takeaway': 'Takeaway food service',
            'shopping_mall': 'Shopping center with various stores',
            'store': 'Retail store',
            'lodging': 'Accommodation and lodging facility',
            'church': 'Religious place of worship',
            'mosque': 'Islamic place of worship',
            'synagogue': 'Jewish place of worship',
            'hindu_temple': 'Hindu temple and place of worship',
            'library': 'Library with books and resources',
            'school': 'Educational institution',
            'university': 'University and higher education institution',
            'hospital': 'Medical facility and hospital',
            'pharmacy': 'Pharmacy and medical supplies',
            'gas_station': 'Gas station and fuel services',
            'bank': 'Banking and financial services',
            'atm': 'ATM and banking services',
            'post_office': 'Postal services',
            'gym': 'Fitness center and gym',
            'spa': 'Spa and wellness services',
            'beauty_salon': 'Beauty salon and services',
            'movie_theater': 'Movie theater and cinema',
            'bowling_alley': 'Bowling alley and entertainment',
            'night_club': 'Nightclub and entertainment venue',
            'bar': 'Bar and beverage service',
            'stadium': 'Stadium and sports venue',
            'playground': 'Playground for children',
            'cemetery': 'Cemetery and memorial grounds'
        }
        
        # Find the most specific/relevant type
        priority_types = [
            'tourist_attraction', 'museum', 'park', 'zoo', 'aquarium', 
            'amusement_park', 'theme_park', 'art_gallery', 'restaurant', 
            'cafe', 'shopping_mall', 'church', 'mosque', 'synagogue', 
            'hindu_temple', 'library', 'stadium', 'playground'
        ]
        
        # Check priority types first
        for ptype in priority_types:
            if ptype in types:
                return type_descriptions.get(ptype, f"{ptype.replace('_', ' ').title()}")
        
        # Check remaining types
        for place_type in types:
            if place_type in type_descriptions:
                return type_descriptions[place_type]
        
        # Fallback to the first type, cleaned up
        if types:
            first_type = types[0].replace('_', ' ').title()
            return f"{first_type}"
        
        return "Local establishment"

    async def generate_recommendations(
        self,
        destination: str,
        travel_days: int,
        with_kids: bool = False,
        kids_age: Optional[List[int]] = None,
        with_elderly: bool = False,
        special_requests: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        try:
            # Validate dates if provided
            if start_date and end_date:
                try:
                    from datetime import datetime
                    datetime.strptime(start_date, "%Y-%m-%d")
                    datetime.strptime(end_date, "%Y-%m-%d")
                except ValueError as e:
                    self.logger.error(f"Invalid date format: {str(e)}")
                    return {
                        "error": "Invalid date format. Please use YYYY-MM-DD format.",
                        "landmarks": {},
                        "restaurants": {}
                    }

            # 1. Parse special requests
            preferences = await self.preferences_parser.parse_special_requests(special_requests)
            
            # 2. Enhance preferences based on user parameters
            enhanced_preferences = self.preferences_parser.enhance_preferences(
                preferences,
                with_kids,
                kids_age,
                with_elderly,
                start_date
            )
            
            # 3. Get location coordinates using the client's geocode method
            location = await self.places_client.geocode(destination)
            if not location:
                self.logger.error(f"Could not geocode destination: {destination}")
                raise HTTPException(status_code=404, detail=f"Could not find location for destination: {destination}")
                
            # 4. Refined search for landmarks and restaurants
            # 🎯 COST OPTIMIZED: Reduced landmark types configuration
            # Consolidate similar types to reduce API calls
            base_landmark_configs = [
                # Combine tourist attractions and theme parks into one search
                {'type': 'tourist_attraction', 'keywords': ['famous', 'popular', 'top attraction', 'must visit']},
                # Museums and cultural sites
                {'type': 'museum', 'keywords': ['art', 'history', 'science', 'cultural']},
                # Parks and outdoor spaces (combine park types)
                {'type': 'park', 'keywords': ['national park', 'botanical garden', 'famous park']},
                # Family entertainment (combine zoo/aquarium for efficiency)
                {'type': 'zoo', 'keywords': ['zoo', 'aquarium', 'wildlife']},
            ]

            # Destination-specific adjustments (simple heuristic)
            landmark_types_config = list(base_landmark_configs) # Start with a copy

            # Remove hardcoded city logic - let Google Places API handle relevance
            if special_requests and "farm" in special_requests.lower() and with_kids: # If user mentions farm
                landmark_types_config.append({'type': 'tourist_attraction', 'keywords': ['farm', 'petting zoo']})
            
            # Adjust types based on company (kids/elderly) - but keep it minimal
            if with_kids:
                # Only add playground if not already covered by parks
                landmark_types_config.append({'type': 'amusement_park', 'keywords': ['theme park', 'amusement park']})
            else:
                # Add art galleries for adults, but combine with museum search for efficiency
                if any(c['type'] == 'museum' for c in landmark_types_config):
                    # Add art gallery keywords to existing museum search
                    for config in landmark_types_config:
                        if config['type'] == 'museum':
                            config['keywords'].extend(['art gallery', 'gallery'])
                            break
                else:
                    landmark_types_config.append({'type': 'art_gallery', 'keywords': ['art', 'gallery']})

            # Remove duplicates that might have been added, prioritizing earlier entries
            unique_landmark_configs = []
            seen_types = set()
            for config in landmark_types_config:
                if config['type'] not in seen_types:
                    unique_landmark_configs.append(config)
                    seen_types.add(config['type'])
            landmark_types_config = unique_landmark_configs

            self.logger.info(f"💰 Cost-optimized landmark_types_config for {destination}: {json.dumps(landmark_types_config)}")

            landmark_tasks = []
            for config in landmark_types_config:
                # Combine base keywords from preferences with type-specific keywords
                current_keywords = list(set(enhanced_preferences.get('keywords', []) + config.get('keywords', [])))
                self.logger.info(f"Searching for type: {config['type']} with keywords: {current_keywords}")
                landmark_tasks.append(
                    self.places_client.get_places(
                        location=location,
                        place_type=config['type'],
                        keywords=current_keywords if current_keywords else None, # Pass None if no keywords
                        max_results=12  # Get more results per type to have a larger pool for popularity ranking
                    )
                )
            
            restaurant_keywords = enhanced_preferences.get('cuisine_types', [])
            self.logger.info(f"Initial restaurant keywords: {restaurant_keywords}")
            
            # Simplify cuisine keywords for better API results
            simplified_keywords = []
            if restaurant_keywords:
                for keyword in restaurant_keywords:
                    # Just use the basic cuisine type, not complex combinations
                    simplified_keywords.append(keyword.lower())
                
                # For Chinese specifically, just use 'chinese' - don't add extra terms
                # The API works better with simple keywords
                if any('chinese' in kw.lower() for kw in simplified_keywords):
                    simplified_keywords = ['chinese']  # Use only 'chinese' for best results
                    self.logger.info("Simplified Chinese restaurant search to use only 'chinese' keyword")
            
            self.logger.info(f"Final restaurant keywords for search: {simplified_keywords}")
            restaurant_task = self.places_client.get_places(
                location=location,
                place_type='restaurant',
                keywords=simplified_keywords if simplified_keywords else None,
                max_results=20,  # 💰 Increased from 10 to 20 to get more restaurant options
                special_requests=special_requests  # Pass special_requests to affect caching
            )
            
            # Execute all tasks in parallel with timeout
            try:
                # First try to get restaurants since that's the primary request
                restaurant_result = await asyncio.wait_for(
                    restaurant_task,
                    timeout=5  # 5 seconds timeout for restaurants
                )
                
                # Then get landmarks in parallel, but limit concurrent requests
                landmark_results = await asyncio.wait_for(
                    asyncio.gather(*landmark_tasks, return_exceptions=True),  # Use all landmark tasks
                    timeout=5  # 5 seconds timeout for landmarks
                )
                
                all_results = list(landmark_results)
                all_results.append(restaurant_result)
                
            except asyncio.TimeoutError:
                self.logger.error(f"API timeout for {destination}. Restaurant result: {restaurant_result if 'restaurant_result' in locals() else 'None'}")
                # If we have restaurant results but landmarks timed out, continue with what we have
                if 'restaurant_result' in locals() and restaurant_result:
                    all_results = [restaurant_result]
                    self.logger.info("Continuing with restaurant results only")
                else:
                    raise HTTPException(
                        status_code=504,
                        detail="Request timed out. Please try again."
                    )
            except Exception as e:
                self.logger.error(f"Error in parallel API calls: {str(e)}")
                # If we have any results, continue with those
                if 'restaurant_result' in locals() and restaurant_result:
                    all_results = [restaurant_result]
                    self.logger.info("Continuing with restaurant results after error")
                else:
                    raise HTTPException(status_code=500, detail="Failed to fetch place data from Google Places API")
            
            # Process landmark results
            landmarks = {}
            for result_set in all_results[:-1]:  # All except the last one (restaurants)
                if isinstance(result_set, Exception):
                    self.logger.error(f"Error fetching places: {str(result_set)}")
                    continue
                    
                if not result_set:  # Skip empty results
                    continue
                    
                for place in result_set:
                    try:
                        if not isinstance(place, dict):
                            self.logger.warning(f"Skipping invalid place data: {place}")
                            continue
                            
                        # Get the actual place data, whether it's nested or not
                        place_data = place.get('result', place)
                        
                        # Check for name in both top level and nested result
                        name = place_data.get('name') or place.get('name')
                        if not name:
                            self.logger.warning(f"Skipping place without name: {place}")
                            continue
                            
                        # 🚀 SPEED OPTIMIZATION: Skip opening hours date check for faster /generate
                        # Note: Date filtering removed for speed optimization in /generate endpoint
                        # This functionality can be added back in /complete-itinerary if needed
                                
                        formatted_place = self.format_place(place)
                        landmarks[formatted_place['name']] = formatted_place
                    except Exception as e:
                        self.logger.error(f"Error processing place: {str(e)}")
                        continue
            
            # Process restaurant results
            restaurants = {}
            restaurant_results = all_results[-1]
            
            if isinstance(restaurant_results, Exception):
                self.logger.error(f"Restaurant search failed with exception: {str(restaurant_results)}")
            elif not restaurant_results:
                self.logger.warning("No restaurant results returned from Google Places API.")
            else:
                self.logger.info(f"Processing {len(restaurant_results)} restaurants.")
                
                for place_container in restaurant_results:
                    try:
                        if not isinstance(place_container, dict):
                            continue
                            
                        place_data = place_container.get('result', place_container)
                        name = place_data.get('name')
                        if not name:
                            continue
                        
                        # Format the place
                        formatted_place = self.format_place(place_container)
                        
                        # Add types from the original place data
                        formatted_place['types'] = place_data.get('types', [])
                        
                        # Calculate priority score
                        priority_score = self._calculate_restaurant_priority(
                            formatted_place,
                            enhanced_preferences.get('cuisine_types', [])
                        )
                        formatted_place['_priority_score'] = priority_score
                        
                        # Add to restaurants dictionary
                        restaurants[name] = formatted_place
                        
                    except Exception as e:
                        self.logger.exception(f"Error processing restaurant: {str(e)}")
                        continue
                
                # Sort restaurants by priority score
                if restaurants:
                    sorted_restaurants = dict(
                        sorted(
                            restaurants.items(),
                            key=lambda x: x[1].get('_priority_score', 0),
                            reverse=True
                        )
                    )
                    restaurants = sorted_restaurants
                    self.logger.info(f"Successfully processed {len(restaurants)} restaurants.")

            # --- Start: Enhanced Popularity Ranking Logic for Landmarks ---
            if landmarks:
                # Convert landmarks dict to a list for sorting
                landmark_list = list(landmarks.values())
                
                # Calculate popularity score for each landmark
                for landmark in landmark_list:
                    popularity_score = self._calculate_landmark_popularity_score(landmark)
                    landmark['_popularity_score'] = popularity_score
                
                # Sort by popularity score (descending)
                landmark_list.sort(key=lambda x: x.get('_popularity_score', 0), reverse=True)
                
                # Log top landmarks for debugging
                self.logger.info(f"Top 5 most popular landmarks by score:")
                for i, landmark in enumerate(landmark_list[:5]):
                    score = landmark.get('_popularity_score', 0)
                    reviews = landmark.get('user_ratings_total', 0)
                    rating = landmark.get('rating', 0)
                    self.logger.info(f"  {i+1}. {landmark.get('name')} - Score: {score:.1f} (Reviews: {reviews}, Rating: {rating})")
                
                # Select top 15 most popular landmarks
                max_ranked_landmarks = 15
                ranked_landmarks_list = landmark_list[:max_ranked_landmarks]
                
                # Convert back to a dictionary for consistency
                landmarks = {lm['name']: lm for lm in ranked_landmarks_list}
                self.logger.info(f"Selected top {len(landmarks)} most popular landmarks from {len(landmark_list)} total.")
            # --- End: Enhanced Popularity Ranking Logic for Landmarks ---

            self.logger.info(f"Found {len(landmarks)} landmarks and {len(restaurants)} restaurants after ranking/trimming.")
            
            # Check if we have enough results from Google Places
            if len(landmarks) < 5: 
                self.logger.warning(f"Found only {len(landmarks)} landmarks from Google Places for {destination}. Consider expanding search criteria.")
                # Continue with whatever landmarks we found - Google Places is our primary source

            if not landmarks and not restaurants:
                 self.logger.error(f"No landmarks or restaurants found for {destination}.")
                 raise HTTPException(status_code=404, detail=f"Could not find sufficient information for {destination}")
            
            return {
                "landmarks": landmarks,
                "restaurants": restaurants
            }
            
        except HTTPException: # Re-raise HTTPExceptions directly
            raise
        except Exception as e:
            self.logger.exception(f"Overall error in generate_recommendations for {destination}: {str(e)}")
            # For other general errors, return a 500. The RAG bug needs to be fixed regardless.
            raise HTTPException(status_code=500, detail=f"An unexpected error occurred while generating recommendations for {destination}.")

 

    def _calculate_landmark_popularity_score(self, landmark: Dict[str, Any]) -> float:
        """Calculate popularity score for a landmark based on reviews, rating, and other factors."""
        try:
            # Base metrics
            rating = float(landmark.get('rating', 0.0))
            review_count = int(landmark.get('user_ratings_total', 0))
            
            # Base score from rating (0-5 scale, multiply by 20 to get 0-100)
            rating_score = rating * 20
            
            # Review count score (logarithmic scale to handle wide range)
            # Popular landmarks can have 10k+ reviews, while smaller ones have 100-1000
            if review_count > 0:
                import math
                # Use log scale: 100 reviews = 40 points, 1000 reviews = 60 points, 10000 reviews = 80 points
                review_score = min(80, 20 * math.log10(review_count))
            else:
                review_score = 0
            
            # Bonus for very highly rated places (4.5+ rating)
            high_rating_bonus = 0
            if rating >= 4.7:
                high_rating_bonus = 15
            elif rating >= 4.5:
                high_rating_bonus = 10
            elif rating >= 4.0:
                high_rating_bonus = 5
            
            # Bonus for very popular places (lots of reviews)
            popularity_bonus = 0
            if review_count >= 10000:
                popularity_bonus = 20  # Major landmark
            elif review_count >= 5000:
                popularity_bonus = 15  # Very popular
            elif review_count >= 2000:
                popularity_bonus = 10  # Popular
            elif review_count >= 1000:
                popularity_bonus = 5   # Well-known
            
            # Penalty for places with very few reviews (might be new or not well-known)
            low_review_penalty = 0
            if review_count < 50:
                low_review_penalty = -20
            elif review_count < 100:
                low_review_penalty = -10
            
            # Calculate final score
            final_score = rating_score + review_score + high_rating_bonus + popularity_bonus + low_review_penalty
            
            # Ensure score is non-negative
            final_score = max(0, final_score)
            
            self.logger.debug(f"Landmark {landmark.get('name')} popularity score: {final_score:.1f} "
                            f"(rating: {rating_score:.1f}, reviews: {review_score:.1f}, "
                            f"bonuses: {high_rating_bonus + popularity_bonus}, penalty: {low_review_penalty})")
            
            return final_score
            
        except Exception as e:
            self.logger.error(f"Error calculating landmark popularity score: {str(e)}")
            return 0.0

    def _calculate_restaurant_priority(self, place: Dict[str, Any], cuisine_preferences: List[str]) -> float:
        """Calculate priority score for a restaurant based on ratings and preferences."""
        try:
            # Base score from rating and number of reviews
            rating = float(place.get('rating', 0.0))
            num_ratings = int(place.get('user_ratings_total', 0))
            
            # Normalize ratings count (assuming most places have < 1000 reviews)
            normalized_ratings = min(num_ratings / 1000.0, 1.0)
            
            # Base score (0-10)
            base_score = (rating * 2) * (0.7 + 0.3 * normalized_ratings)
            
            # Preference bonus (up to +2)
            preference_bonus = 0
            description = place.get('description', '').lower()
            name = place.get('name', '').lower()
            types = place.get('types', [])  # Get place types from Google Places
            
            # Check cuisine preferences from both special requests and enhanced preferences
            if cuisine_preferences:
                for pref in cuisine_preferences:
                    pref_lower = pref.lower()
                    
                    # Special handling for Chinese restaurants
                    if pref_lower == 'chinese':
                        chinese_indicators = [
                            'chinese' in name,
                            'chinese' in description,
                            'chinese_restaurant' in types,
                            'asian_restaurant' in types and ('chinese' in name or 'chinese' in description),
                            any('chinese' in t.lower().replace('_', ' ') for t in types),
                            any(term in name.lower() for term in ['wok', 'szechuan', 'sichuan', 'hunan', 'canton', 'dim sum'])
                        ]
                        if any(chinese_indicators):
                            preference_bonus += 2  # Higher bonus for exact Chinese restaurant matches
                            self.logger.info(f"Added Chinese restaurant bonus for {name}")
                            continue
                    
                    # Regular preference matching
                    if (pref_lower in description or 
                        pref_lower in name or 
                        any(pref_lower in t.lower().replace('_', ' ') for t in types)):
                        preference_bonus += 1
                        self.logger.info(f"Added preference bonus for {name} due to match with {pref_lower}")
            
            # Cap the preference bonus
            preference_bonus = min(preference_bonus, 2)
            
            final_score = base_score + preference_bonus
            self.logger.info(f"Restaurant {name} scored {final_score} (base: {base_score}, bonus: {preference_bonus})")
            return final_score
            
        except Exception as e:
            self.logger.error(f"Error calculating restaurant priority: {str(e)}")
            return 0.0 