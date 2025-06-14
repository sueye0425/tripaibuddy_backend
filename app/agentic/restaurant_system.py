"""
Restaurant integration system for agentic itinerary generation.
Handles restaurant search, description enhancement, and meal scheduling.
"""
import logging
from typing import Dict, List, Optional
import asyncio
from datetime import datetime, timedelta

from ..schema import ItineraryBlock, Location, StructuredDayPlan
from ..places_client import GooglePlacesClient

logger = logging.getLogger(__name__)

class RestaurantSystem:
    """Enhanced restaurant system with better descriptions"""
    
    def __init__(self):
        pass
    
    async def add_restaurants_to_day(
        self, 
        day_plan: StructuredDayPlan, 
        places_client: GooglePlacesClient, 
        destination: str,
        used_restaurants: set
    ) -> StructuredDayPlan:
        """Add restaurants to a day plan with intelligent meal scheduling"""
        
        logger.info(f"🍽️ Adding restaurants to Day {day_plan.day}")
        
        # Get landmarks for this day
        landmarks = [block for block in day_plan.blocks if block.type == 'landmark']
        
        if not landmarks:
            logger.warning(f"⚠️ Day {day_plan.day} has no landmarks - cannot add restaurants")
            return day_plan
        
        # Calculate center location
        center = self._get_day_center_location(day_plan)
        
        # Check if this is a theme park day
        is_theme_park = self._is_theme_park_day(landmarks)
        
        # Schedule meals based on day type
        if is_theme_park:
            meals = await self._schedule_theme_park_meals(
                center, landmarks, destination, places_client, used_restaurants, day_plan.day
            )
        else:
            meals = await self._schedule_regular_meals(
                center, landmarks, destination, places_client, used_restaurants, day_plan.day
            )
        
        # Add restaurants to day plan
        enhanced_blocks = []
        
        # Add landmarks and restaurants in chronological order
        all_blocks = day_plan.blocks.copy()
        
        # Add meal blocks
        for meal_type, meal_block in meals.items():
            if meal_block:
                all_blocks.append(meal_block)
                used_restaurants.add(meal_block.name)
        
        # Sort by start time
        all_blocks.sort(key=lambda x: self._parse_time_to_minutes(x.start_time))
        
        enhanced_day = StructuredDayPlan(day=day_plan.day, blocks=all_blocks)
        
        # Log results
        restaurants = [b for b in enhanced_day.blocks if b.type == 'restaurant']
        logger.info(f"✅ Day {day_plan.day}: Added {len(restaurants)} restaurants")
        for restaurant in restaurants:
            logger.info(f"   🍽️ {restaurant.name} ({restaurant.mealtime}) - {restaurant.description[:100]}...")
        
        return enhanced_day
    
    def _get_day_center_location(self, day_plan: StructuredDayPlan) -> Location:
        """Calculate center location for a day's activities"""
        landmarks = [block for block in day_plan.blocks if block.type == 'landmark' and block.location]
        
        if not landmarks:
            # Default to Orlando center
            return Location(lat=28.5383, lng=-81.3792)
        
        # Calculate centroid
        avg_lat = sum(block.location.lat for block in landmarks) / len(landmarks)
        avg_lng = sum(block.location.lng for block in landmarks) / len(landmarks)
        
        return Location(lat=avg_lat, lng=avg_lng)
    
    def _is_theme_park_day(self, landmarks: List[ItineraryBlock]) -> bool:
        """Check if this is a theme park day"""
        theme_park_keywords = [
            'disney', 'universal', 'studios', 'magic kingdom', 'epcot', 
            'hollywood studios', 'animal kingdom', 'islands of adventure',
            'volcano bay', 'seaworld', 'busch gardens', 'legoland'
        ]
        
        for landmark in landmarks:
            name_lower = landmark.name.lower()
            desc_lower = (landmark.description or "").lower()
            
            if any(keyword in name_lower or keyword in desc_lower for keyword in theme_park_keywords):
                return True
        
        return False
    
    async def _schedule_theme_park_meals(
        self,
        center: Location,
        landmarks: List[ItineraryBlock],
        destination: str,
        places_client: GooglePlacesClient,
        used_restaurants: set,
        day_num: int
    ) -> Dict[str, Optional[ItineraryBlock]]:
        """Schedule meals for theme park days with intelligent timing"""
        
        meals = {}
        
        # For theme parks, use more flexible timing
        theme_park_meal_times = self._calculate_theme_park_meal_times(landmarks)
        
        # Breakfast - before park opens
        meals["breakfast"] = await self._create_regular_restaurant(
            center, "breakfast", theme_park_meal_times["breakfast"], destination, places_client, used_restaurants
        )
        
        # Lunch - mid-day break
        meals["lunch"] = await self._create_theme_park_lunch_restaurant(
            center, theme_park_meal_times["lunch"], destination, places_client, used_restaurants
        )
        
        # Dinner - after park activities
        meals["dinner"] = await self._create_regular_restaurant_near_theme_park(
            center, "dinner", theme_park_meal_times["dinner"], destination, places_client, used_restaurants
        )
        
        return meals
    
    async def _schedule_regular_meals(
        self,
        center: Location,
        landmarks: List[ItineraryBlock],
        destination: str,
        places_client: GooglePlacesClient,
        used_restaurants: set,
        day_num: int
    ) -> Dict[str, Optional[ItineraryBlock]]:
        """Schedule regular meals for non-theme park days with intelligent timing"""
        
        meals = {}
        
        # Calculate intelligent meal times based on landmark schedule
        meal_times = self._calculate_intelligent_meal_times(landmarks)
        
        # Breakfast - early start
        meals["breakfast"] = await self._create_regular_restaurant(
            center, "breakfast", meal_times["breakfast"], destination, places_client, used_restaurants
        )
        
        # Lunch - strategically placed to break up activities
        meals["lunch"] = await self._create_regular_restaurant(
            center, "lunch", meal_times["lunch"], destination, places_client, used_restaurants
        )
        
        # Dinner - positioned to prevent large gaps
        meals["dinner"] = await self._create_regular_restaurant(
            center, "dinner", meal_times["dinner"], destination, places_client, used_restaurants
        )
        
        return meals
    
    async def _create_regular_restaurant(
        self,
        center: Location,
        meal_type: str,
        meal_time: str,
        destination: str,
        places_client: GooglePlacesClient,
        used_restaurants: set
    ) -> Optional[ItineraryBlock]:
        """Create a regular restaurant recommendation"""
        
        try:
            # Search for restaurants near the center
            search_radius = 5000  # 5km radius
            
            # Try different search strategies
            search_strategies = [
                {"keyword": f"{meal_type} restaurant {destination}", "type": "restaurant"},
                {"keyword": f"best {meal_type} {destination}", "type": "restaurant"},
                {"keyword": f"popular restaurant {destination}", "type": "restaurant"},
            ]
            
            for strategy in search_strategies:
                try:
                    results = await places_client.places_nearby(
                        location={"lat": center.lat, "lng": center.lng},
                        radius=search_radius,
                        place_type=strategy["type"],
                        keyword=strategy["keyword"]
                    )
                    
                    if results and results.get('results'):
                        for place_data in results['results']:
                            restaurant_name = place_data.get('name', '')
                            
                            # Skip if already used
                            if restaurant_name in used_restaurants:
                                continue
                            
                            # Get detailed place data
                            detailed_data = await self._get_detailed_place_data(place_data, places_client)
                            
                            # Create restaurant block
                            return self._create_restaurant_block_from_place_data(
                                detailed_data, meal_type, meal_time
                            )
                            
                except Exception as e:
                    logger.debug(f"Restaurant search strategy failed: {e}")
                    continue
            
            logger.warning(f"⚠️ No restaurants found for {meal_type} near {destination}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error creating {meal_type} restaurant: {e}")
            return None
    
    async def _create_theme_park_lunch_restaurant(
        self,
        center: Location,
        meal_time: str,
        destination: str,
        places_client: GooglePlacesClient,
        used_restaurants: set
    ) -> Optional[ItineraryBlock]:
        """Create theme park lunch restaurant"""
        
        # For theme park lunch, try nearby restaurants (could be inside or outside park)
        restaurant = await self._create_regular_restaurant(
            center, "lunch", meal_time, destination, places_client, used_restaurants
        )
        
        return restaurant
    
    async def _create_regular_restaurant_near_theme_park(
        self,
        center: Location,
        meal_type: str,
        meal_time: str,
        destination: str,
        places_client: GooglePlacesClient,
        used_restaurants: set
    ) -> Optional[ItineraryBlock]:
        """Create regular restaurant near theme park"""
        
        return await self._create_regular_restaurant(
            center, meal_type, meal_time, destination, places_client, used_restaurants
        )
    
    async def _get_detailed_place_data(self, basic_place_data: Dict, places_client: GooglePlacesClient) -> Dict:
        """Get detailed place data including better description fields"""
        
        place_id = basic_place_data.get('place_id')
        if not place_id:
            return basic_place_data
        
        try:
            # Get detailed place information
            detailed_data = await places_client.place_details(place_id)
            
            if detailed_data and detailed_data.get('result'):
                # Merge basic data with detailed data
                result = {**basic_place_data, **detailed_data['result']}
                return result
            
        except Exception as e:
            logger.debug(f"Failed to get detailed place data: {e}")
        
        return basic_place_data
    
    def _create_restaurant_block_from_place_data(
        self,
        place_data: Dict,
        meal_type: str,
        meal_time: str
    ) -> ItineraryBlock:
        """Create ItineraryBlock from Google Places data with enhanced descriptions"""
        
        # Get enhanced description using multiple fields
        description = self._get_enhanced_restaurant_description(place_data)
        
        # Extract location
        location = None
        if 'geometry' in place_data and 'location' in place_data['geometry']:
            location = Location(
                lat=place_data['geometry']['location']['lat'],
                lng=place_data['geometry']['location']['lng']
            )
        
        # Extract address
        address = (
            place_data.get('formatted_address') or
            place_data.get('vicinity') or
            None
        )
        
        # Set duration based on meal type
        durations = {
            "breakfast": "45m",
            "lunch": "1h",
            "dinner": "1.5h"
        }
        
        # Create the restaurant block
        return ItineraryBlock(
            type="restaurant",
            name=place_data.get('name', f"Local {meal_type.title()} Spot"),
            description=description,
            start_time=meal_time,
            duration=durations.get(meal_type, "1h"),
            mealtime=meal_type,
            place_id=place_data.get('place_id'),
            rating=place_data.get('rating'),
            location=location,
            address=address,
            photo_url=self._get_photo_url_from_place_data(place_data),
            website=place_data.get('website')
        )
    
    def _get_enhanced_restaurant_description(self, place_data: Dict) -> str:
        """Get enhanced restaurant description using multiple Google Places fields"""
        
        # Try multiple description sources in order of preference
        description_sources = [
            # 1. Editorial summary (rich descriptions)
            place_data.get('editorial_summary', {}).get('overview'),
            
            # 2. User reviews summary (if available)
            self._extract_description_from_reviews(place_data.get('reviews', [])),
            
            # 3. Business type and price level combination
            self._create_description_from_types_and_price(place_data),
            
            # 4. Simple type-based description (ONLY if specific cuisine type)
            self._create_specific_cuisine_description(place_data),
        ]
        
        # Use the first non-empty description
        for desc in description_sources:
            if desc and desc.strip() and not self._is_generic_description(desc):
                return self._format_description(desc)
        
        # If all else fails, return empty string to avoid generic descriptions
        return ""
    
    def _is_generic_description(self, description: str) -> bool:
        """Check if a description is too generic to be useful"""
        if not description:
            return True
            
        desc_lower = description.lower().strip()
        
        # Only flag descriptions that are EXACTLY these generic phrases (not containing them)
        exact_generic_phrases = [
            "restaurant",
            "local restaurant", 
            "eatery",
            "dining spot",
            "can dine inside theme park",
            "can dine inside theme park or exit/re-enter",
            "restaurant - can dine inside theme park or exit/re-enter",
            "food establishment",
            "eating establishment",
            "dining establishment"
        ]
        
        # If description is exactly one of these phrases or very short
        if desc_lower in exact_generic_phrases or len(description) < 15:
            return True
            
        # If description is very short and only contains basic restaurant words
        words = desc_lower.split()
        if len(words) <= 2 and all(word in ["restaurant", "eatery", "food", "dining", "establishment"] for word in words):
            return True
            
        return False
    
    def _extract_description_from_reviews(self, reviews: List[Dict]) -> Optional[str]:
        """Extract descriptive information from user reviews"""
        if not reviews:
            return None
        
        # Look for descriptive phrases in highly-rated reviews
        descriptive_phrases = []
        
        for review in reviews[:5]:  # Check top 5 reviews
            rating = review.get('rating', 0)
            text = review.get('text', '').lower()
            
            if rating >= 4 and len(text) > 20:  # Only from positive, substantial reviews
                # Look for specific food/cuisine descriptors
                food_keywords = [
                    'authentic', 'delicious', 'fresh', 'homemade', 'traditional', 'amazing',
                    'italian', 'mexican', 'chinese', 'asian', 'american', 'seafood', 'steakhouse',
                    'pizza', 'pasta', 'sushi', 'barbecue', 'grill', 'burgers', 'sandwiches',
                    'breakfast', 'brunch', 'lunch', 'dinner', 'dessert',
                    'family-friendly', 'casual', 'upscale', 'fine dining'
                ]
                
                for keyword in food_keywords:
                    if keyword in text:
                        # Extract a meaningful phrase around the keyword
                        sentences = text.split('.')
                        for sentence in sentences:
                            if keyword in sentence and len(sentence.strip()) > 15:
                                clean_sentence = sentence.strip().capitalize()
                                if len(clean_sentence) <= 150:  # Reasonable length
                                    descriptive_phrases.append(clean_sentence)
                                    break
                        if descriptive_phrases:
                            break
                if descriptive_phrases:
                    break
        
        if descriptive_phrases:
            return descriptive_phrases[0]  # Return the first good phrase
        
        return None
    
    def _create_description_from_types_and_price(self, place_data: Dict) -> Optional[str]:
        """Create description from business types and price level"""
        
        types = place_data.get('types', [])
        price_level = place_data.get('price_level')
        
        if not types:
            return None
        
        # Map specific restaurant types to meaningful descriptions  
        specific_type_descriptions = {
            'italian_restaurant': 'Authentic Italian trattoria serving handcrafted pasta, wood-fired pizza, and traditional specialties',
            'chinese_restaurant': 'Traditional Chinese cuisine featuring fresh ingredients and time-honored cooking techniques',
            'mexican_restaurant': 'Vibrant Mexican eatery offering authentic flavors from south of the border',
            'japanese_restaurant': 'Contemporary Japanese dining featuring fresh sushi, sashimi, and traditional specialties',
            'american_restaurant': 'Classic American bistro serving comfort food favorites and regional specialties',
            'seafood_restaurant': 'Fresh seafood establishment specializing in daily catches and coastal cuisine',
            'steakhouse': 'Premium steakhouse featuring expertly grilled meats and classic accompaniments',
            'pizzeria': 'Artisanal pizzeria crafting wood-fired pies with premium ingredients',
            'fast_food_restaurant': 'Quick-service establishment offering convenient meals and familiar favorites',
            'bakery': 'Artisanal bakery featuring freshly baked breads, pastries, and specialty desserts',
            'cafe': 'Cozy neighborhood cafe serving expertly crafted coffee and light fare',
            'bar': 'Local watering hole offering drinks, pub grub, and casual atmosphere',
            'restaurant': 'Restaurant serving food and beverages with a focus on quality and flavor',
            'meal_takeaway': 'Casual dining spot offering fresh meals for takeout and dining',
            'meal_delivery': 'Restaurant offering convenient meal delivery and takeout options',
            'food': 'Dining establishment serving a variety of freshly prepared meals',
            'establishment': 'Popular local eatery known for quality food and service'
        }
        
        # Find the most specific restaurant type
        description = None
        for restaurant_type in types:
            if restaurant_type in specific_type_descriptions:
                description = specific_type_descriptions[restaurant_type]
                break
        
        if not description:
            # Fallback: if we have "restaurant" in types, use generic description
            if any(t in ['restaurant', 'food', 'establishment'] for t in types):
                description = 'Restaurant serving a variety of freshly prepared dishes'
            else:
                return None
        
        # Add price level context if available
        if price_level:
            price_indicators = {
                1: "Budget-friendly",
                2: "Moderately priced", 
                3: "Upscale",
                4: "Fine dining"
            }
            
            if price_level in price_indicators:
                description = f"{price_indicators[price_level]} {description.lower()}"
        
        return description
    
    def _create_specific_cuisine_description(self, place_data: Dict) -> Optional[str]:
        """Create description only for specific cuisine types, not generic restaurants"""
        
        types = place_data.get('types', [])
        
        # Only create descriptions for specific cuisine types
        specific_cuisines = {
            'bakery': 'Artisanal bakery featuring freshly baked breads, pastries, and specialty items',
            'cafe': 'Local cafe offering expertly crafted coffee, light meals, and baked goods',
            'bar': 'Neighborhood bar and grill serving drinks alongside hearty pub favorites',
            'breakfast_restaurant': 'Breakfast and brunch spot serving hearty morning favorites',
            'brunch_restaurant': 'Popular brunch destination offering creative morning and afternoon dishes',
            'family_restaurant': 'Family-friendly restaurant serving comfort food and classic favorites',
            'casual_dining_restaurant': 'Casual dining establishment offering quality meals in a relaxed atmosphere',
            'fine_dining_restaurant': 'Upscale dining experience featuring expertly crafted cuisine',
            'fast_casual_restaurant': 'Fast-casual eatery offering fresh, quality meals with quick service',
            'sandwich_shop': 'Sandwich shop specializing in fresh, made-to-order subs and deli favorites',
            'grill': 'Grill house featuring flame-grilled specialties and classic American fare',
            'sports_bar': 'Sports bar and grill offering game-day atmosphere with food and drinks'
        }
        
        for cuisine_type in types:
            if cuisine_type in specific_cuisines:
                return specific_cuisines[cuisine_type]
        
        # Return basic description for common restaurant types
        if 'restaurant' in types or 'food' in types:
            return 'Restaurant serving a variety of freshly prepared dishes'
        
        return None
    
    def _format_description(self, description: str) -> str:
        """Format and clean up description text"""
        
        if not description:
            return ""
        
        # Clean up the text
        description = description.strip()
        
        # Ensure reasonable length (up to 200 chars for 1-2 sentences)
        if len(description) <= 200:
            return description
        
        # If longer, try to truncate at sentence boundary
        sentences = description.split('. ')
        if len(sentences) >= 2:
            # Show first two sentences if reasonable length
            first_two = sentences[0] + '. ' + sentences[1]
            if len(first_two) <= 200:
                return first_two + ('.' if not first_two.endswith('.') else '')
            else:
                return sentences[0] + '.'
        else:
            # No sentence breaks - truncate at word boundary
            truncate_point = description.rfind(' ', 0, 197)
            if truncate_point > 150:
                return description[:truncate_point] + "..."
            else:
                return description[:197] + "..."
    
    def _get_photo_url_from_place_data(self, place_data: Dict) -> Optional[str]:
        """Extract photo URL from place data"""
        if place_data.get('photos'):
            photo_reference = place_data['photos'][0].get('photo_reference')
            if photo_reference:
                return f"/photo-proxy/{photo_reference}?maxwidth=400&maxheight=400"
        return None
    
    def _parse_time_to_minutes(self, time_str: str) -> int:
        """Parse time string to minutes since midnight"""
        try:
            hours, minutes = map(int, time_str.split(':'))
            return hours * 60 + minutes
        except:
            return 0
    
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
        elif duration_str.endswith('min') or duration_str.endswith('m'):
            minutes_str = duration_str.replace('min', '').replace('m', '')
            try:
                return int(minutes_str)
            except ValueError:
                return 60
        else:
            try:
                hours = float(duration_str)
                return int(hours * 60)
            except ValueError:
                return 60
    
    def _calculate_intelligent_meal_times(self, landmarks: List[ItineraryBlock]) -> Dict[str, str]:
        """Calculate intelligent meal times based on landmark schedule to prevent gaps"""
        
        try:
            # Parse landmark times
            landmark_times = []
            for landmark in landmarks:
                if landmark.start_time:
                    try:
                        start_time = datetime.strptime(landmark.start_time, "%H:%M")
                        duration_minutes = self._parse_duration_to_minutes(landmark.duration or "2h")
                        end_time = start_time + timedelta(minutes=duration_minutes)
                        
                        landmark_times.append({
                            "start": start_time,
                            "end": end_time,
                            "name": landmark.name
                        })
                    except ValueError:
                        continue
            
            # Sort by start time
            landmark_times.sort(key=lambda x: x["start"])
            
            # Calculate meal times to fill gaps
            meal_times = {
                "breakfast": "08:00",  # Default early breakfast
                "lunch": "12:00",     # Changed from 13:00 to 12:00
                "dinner": "19:00"     # Default dinner
            }
            
            if landmark_times:
                # Breakfast: 1 hour before first activity
                first_activity = landmark_times[0]["start"]
                breakfast_time = first_activity - timedelta(hours=1)
                if breakfast_time.hour >= 7:  # Not too early
                    meal_times["breakfast"] = breakfast_time.strftime("%H:%M")
                
                # Lunch: Find optimal time between activities
                lunch_time = self._find_optimal_lunch_time(landmark_times)
                if lunch_time:
                    meal_times["lunch"] = lunch_time
                
                # Dinner: Find optimal time to prevent evening gaps (consider lunch time)
                lunch_end_time = datetime.strptime(meal_times["lunch"], "%H:%M") + timedelta(hours=1)  # 1h lunch duration
                dinner_time = self._find_optimal_dinner_time_with_lunch(landmark_times, lunch_end_time)
                if dinner_time:
                    meal_times["dinner"] = dinner_time
            
            logger.info(f"🍽️ Intelligent meal times: {meal_times}")
            return meal_times
            
        except Exception as e:
            logger.error(f"Error calculating intelligent meal times: {e}")
            # Return safe defaults
            return {
                "breakfast": "08:00",
                "lunch": "12:00",
                "dinner": "18:00"
            }
    
    def _find_optimal_lunch_time(self, landmark_times: List[Dict]) -> Optional[str]:
        """Find optimal lunch time to break up activities"""
        
        try:
            # Look for gaps between 11:00 AM and 2:00 PM (earlier window)
            lunch_window_start = datetime.strptime("11:00", "%H:%M")
            lunch_window_end = datetime.strptime("14:00", "%H:%M")
            
            # Find the largest gap in the lunch window
            best_gap = None
            best_gap_size = 0
            
            for i in range(len(landmark_times) - 1):
                current_end = landmark_times[i]["end"]
                next_start = landmark_times[i + 1]["start"]
                
                # Check if gap overlaps with lunch window
                gap_start = max(current_end, lunch_window_start)
                gap_end = min(next_start, lunch_window_end)
                
                if gap_start < gap_end:
                    gap_size = (gap_end - gap_start).total_seconds() / 60  # minutes
                    if gap_size > best_gap_size and gap_size >= 30:  # At least 30 minutes (reduced from 60)
                        best_gap = gap_start + timedelta(minutes=15)  # 15 min after activity ends
                        best_gap_size = gap_size
            
            # If no good gap found, schedule lunch strategically to prevent large gaps
            if not best_gap:
                # Calculate total time span of landmarks
                if landmark_times:
                    first_start = landmark_times[0]["start"]
                    last_end = landmark_times[-1]["end"]
                    total_span = (last_end - first_start).total_seconds() / 3600  # hours
                    
                    # If landmarks span more than 4 hours, insert lunch in the middle
                    if total_span > 4:
                        middle_time = first_start + timedelta(hours=total_span/2)
                        # Ensure it's within lunch window
                        if lunch_window_start <= middle_time <= lunch_window_end:
                            best_gap = middle_time
                        else:
                            # Default to 12:00 if middle time is outside window
                            best_gap = datetime.strptime("12:00", "%H:%M")
                    else:
                        # For shorter spans, use 12:00 if it doesn't conflict
                        default_lunch = datetime.strptime("12:00", "%H:%M")
                        conflicts = False
                        
                        for landmark_time in landmark_times:
                            if landmark_time["start"] <= default_lunch <= landmark_time["end"]:
                                conflicts = True
                                break
                        
                        if not conflicts:
                            best_gap = default_lunch
                        else:
                            # Find earliest non-conflicting time after 11:30
                            for hour in range(11, 14):
                                for minute in [30, 0]:
                                    test_time = datetime.strptime(f"{hour:02d}:{minute:02d}", "%H:%M")
                                    conflicts = False
                                    
                                    for landmark_time in landmark_times:
                                        if landmark_time["start"] <= test_time <= landmark_time["end"]:
                                            conflicts = True
                                            break
                                    
                                    if not conflicts:
                                        best_gap = test_time
                                        break
                                if best_gap:
                                    break
                else:
                    # No landmarks, use default
                    best_gap = datetime.strptime("12:00", "%H:%M")
            
            return best_gap.strftime("%H:%M") if best_gap else None
            
        except Exception as e:
            logger.error(f"Error finding optimal lunch time: {e}")
            return None
    
    def _find_optimal_dinner_time_with_lunch(self, landmark_times: List[Dict], lunch_end_time: datetime) -> Optional[str]:
        """
        Finds the optimal dinner time based on landmark schedule and lunch time.
        Tries to place dinner at 19:00, but avoids conflicts.
        """
        try:
            # Find the latest activity end time (either landmarks or lunch)
            latest_end_time = lunch_end_time
            
            if landmark_times:
                last_landmark_end = landmark_times[-1]["end"]
                latest_end_time = max(latest_end_time, last_landmark_end)
            
            # Schedule dinner 2-3 hours after lunch ends, but consider other activities
            min_gap_after_lunch = timedelta(hours=2)  # Reduced from 2.5 to 2 hours
            dinner_time = lunch_end_time + min_gap_after_lunch
            
            # If there are activities after lunch, schedule dinner after them
            if latest_end_time > lunch_end_time:
                # Schedule dinner 30 minutes after the last activity
                dinner_after_activities = latest_end_time + timedelta(minutes=30)
                # Use the later of the two times
                dinner_time = max(dinner_time, dinner_after_activities)
            
            # Ensure reasonable dinner time bounds
            earliest_dinner = datetime.strptime("17:00", "%H:%M")
            latest_dinner = datetime.strptime("20:00", "%H:%M")
            
            if dinner_time < earliest_dinner:
                dinner_time = earliest_dinner
            elif dinner_time > latest_dinner:
                dinner_time = latest_dinner
            
            return dinner_time.strftime("%H:%M")
            
        except Exception as e:
            logger.error(f"Error finding optimal dinner time with lunch: {e}")
            return None
    
    def _calculate_theme_park_meal_times(self, landmarks: List[ItineraryBlock]) -> Dict[str, str]:
        """Calculate meal times for theme park days"""
        
        try:
            # Theme parks typically have long single activities
            if landmarks and landmarks[0].start_time:
                park_start = datetime.strptime(landmarks[0].start_time, "%H:%M")
                
                # Breakfast 1 hour before park
                breakfast_time = park_start - timedelta(hours=1)
                if breakfast_time.hour < 7:
                    breakfast_time = datetime.strptime("07:30", "%H:%M")
                
                # Lunch in middle of park day (around 12:30-1:00)
                lunch_time = park_start + timedelta(hours=3.5)  # 3.5 hours into park day
                
                # Dinner after park or late in park day
                dinner_time = park_start + timedelta(hours=8)  # Near end of park day
                if dinner_time.hour > 19:
                    dinner_time = datetime.strptime("19:00", "%H:%M")
                
                return {
                    "breakfast": breakfast_time.strftime("%H:%M"),
                    "lunch": lunch_time.strftime("%H:%M"),
                    "dinner": dinner_time.strftime("%H:%M")
                }
            
        except Exception as e:
            logger.error(f"Error calculating theme park meal times: {e}")
        
        # Safe defaults for theme parks
        return {
            "breakfast": "08:00",
            "lunch": "12:30",
            "dinner": "18:30"
        } 