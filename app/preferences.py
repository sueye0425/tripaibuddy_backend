import os
import json
from typing import Dict, List, Optional
from openai import OpenAI
import logging

class PreferencesParser:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv('OPENAI_API_KEY'),
            timeout=30.0,
            max_retries=2,
            **({"base_url": os.getenv("OPENAI_BASE_URL")} if os.getenv("OPENAI_BASE_URL") else {})  # Use base_url if set, otherwise use
        )
        self.logger = logging.getLogger(__name__)

    async def parse_special_requests(self, text: Optional[str]) -> Dict:
        """Parse special requests using GPT-3.5-turbo"""
        if not text:
            return self.default_preferences()

        try:
            prompt = """
            Extract travel preferences from the text below as JSON with these keys only:
            - keywords: list of search terms for attractions
            - cuisine_types: list of food types or restaurant preferences
            - accessibility: list of accessibility requirements
            
            Example inputs and outputs:
            Input: "Looking for Japanese food and quiet museums, need wheelchair access"
            Output: {
                "keywords": ["quiet", "museum"],
                "cuisine_types": ["Japanese"],
                "accessibility": ["wheelchair"]
            }

            Input: "I would prefer Chinese restaurants"
            Output: {
                "keywords": [],
                "cuisine_types": ["Chinese"],
                "accessibility": []
            }

            Input: "I prefer Italian food"
            Output: {
                "keywords": [],
                "cuisine_types": ["Italian"],
                "accessibility": []
            }

            Text: {text}
            
            Return only the JSON, no other text.
            """

            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{
                    "role": "user",
                    "content": prompt.format(text=text)
                }],
                temperature=0.3,
                max_tokens=150
            )

            content = response.choices[0].message.content.strip()
            # Remove any non-JSON text that might be around the JSON object
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            if json_start >= 0 and json_end > 0:
                content = content[json_start:json_end]
            
            try:
                result = json.loads(content)
                # Validate the result has all required keys
                for key in ['keywords', 'cuisine_types', 'accessibility']:
                    if key not in result:
                        result[key] = []
                    elif not isinstance(result[key], list):
                        result[key] = []
                self.logger.info(f"Parsed preferences from text: {text}")
                self.logger.info(f"GPT response content: {content}")
                self.logger.info(f"Final parsed preferences: {result}")
                return result
            except json.JSONDecodeError as e:
                self.logger.error(f"Error parsing JSON response: {str(e)}, content: {content}")
                return self.default_preferences()

        except Exception as e:
            self.logger.error(f"Error parsing preferences: {str(e)}")
            return self.default_preferences()

    def default_preferences(self) -> Dict:
        """Return default preferences when none are specified"""
        return {
            "keywords": [],
            "cuisine_types": [],
            "accessibility": []
        }

    def get_season(self, date_str: Optional[str] = None) -> str:
        """Get season from date string"""
        if not date_str:
            return "current"
            
        try:
            from datetime import datetime
            date = datetime.strptime(date_str, '%Y-%m-%d')
            month = date.month
            
            if month in [12, 1, 2]:
                return "winter"
            elif month in [3, 4, 5]:
                return "spring"
            elif month in [6, 7, 8]:
                return "summer"
            else:
                return "fall"
        except Exception as e:
            self.logger.error(f"Error determining season: {str(e)}")
            return "current"

    def enhance_preferences(
        self,
        preferences: Dict,
        with_kids: bool,
        kids_age: Optional[List[int]],
        with_elderly: bool,
        start_date: Optional[str]
    ) -> Dict:
        """Enhance preferences based on user parameters"""
        enhanced = preferences.copy()
        
        # Add kid-friendly keywords
        if with_kids and kids_age:
            if any(age < 6 for age in kids_age):
                enhanced["keywords"].extend(["toddler-friendly", "playground"])
            if any(3 <= age <= 12 for age in kids_age):
                enhanced["keywords"].extend(["interactive", "family-friendly"])
            if any(age > 10 for age in kids_age):
                enhanced["keywords"].extend(["teen-friendly", "adventure"])
                
        # Add elderly-friendly keywords
        if with_elderly:
            enhanced["keywords"].extend(["accessible", "relaxed"])
            enhanced["accessibility"].extend(["wheelchair", "seating"])
            
        # Add seasonal keywords
        season = self.get_season(start_date)
        if season != "current":
            enhanced["keywords"].append(f"{season} activities")
            
        # Remove duplicates while preserving order
        enhanced["keywords"] = list(dict.fromkeys(enhanced["keywords"]))
        enhanced["cuisine_types"] = list(dict.fromkeys(enhanced["cuisine_types"]))
        enhanced["accessibility"] = list(dict.fromkeys(enhanced["accessibility"]))
        
        return enhanced 