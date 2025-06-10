import os
import json
import logging
from typing import Dict, List, Optional, Tuple, Any
import aiohttp
from datetime import datetime

class GoogleRoutesClient:
    def __init__(self, session: aiohttp.ClientSession):
        self.api_key = os.getenv('GOOGLE_PLACES_API_KEY')
        if not self.api_key:
            logging.critical("GOOGLE_PLACES_API_KEY environment variable is not set!")
            raise ValueError("GOOGLE_PLACES_API_KEY environment variable is required")
        self.base_url = "https://routes.googleapis.com/directions/v2:computeRoutes"
        self.geocoding_url = "https://maps.googleapis.com/maps/api/geocode/json"
        self.logger = logging.getLogger(__name__)
        self._session = session

    async def reverse_geocode(self, location: Dict[str, float]) -> List[Dict[str, Any]]:
        """
        Async Reverse geocode a location using Google Maps Geocoding API
        Args:
            location: Dict with 'lat' and 'lng' keys
        Returns:
            List of address components or empty list on error.
        """
        params = {
            'latlng': f"{location['lat']},{location['lng']}",
            'key': self.api_key
        }
        self.logger.debug(f"Async reverse_geocode: Requesting {self.geocoding_url} with params: {params}")
        try:
            async with self._session.get(self.geocoding_url, params=params, timeout=10) as response:
                response.raise_for_status()
                result = await response.json()
                self.logger.debug(f"Async reverse_geocode: Response status {result.get('status')}")

                if result.get('status') == 'OK':
                    self.logger.info(f"Async reverse_geocode successful for {location}. Found {len(result.get('results', []))} results.")
                    return result.get('results', [])
                else:
                    self.logger.error(f"Async reverse_geocode API error for {location}: {result.get('status')}, message: {result.get('error_message', 'No error message')}")
                    return []
        except aiohttp.ClientResponseError as e:
            self.logger.error(f"Async reverse_geocode: HTTP error for {location}: {e.status} {e.message}")
            return []
        except asyncio.TimeoutError:
            self.logger.error(f"Async reverse_geocode: Timeout for {location}")
            return []
        except Exception as e:
            self.logger.error(f"Async reverse_geocode: Unexpected error for {location}: {str(e)}")
            return []

    async def calculate_distance_matrix(
        self,
        origins: List[Dict[str, float]],
        destinations: List[Dict[str, float]],
        mode: str = "DRIVE"
    ) -> List[List[Dict[str, Any]]]:
        """
        Async Calculate distance matrix using Google Routes API
        Args:
            origins: List of dicts with 'lat' and 'lng' keys
            destinations: List of dicts with 'lat' and 'lng' keys
            mode: Travel mode (e.g., DRIVE, WALK)
        Returns:
            Matrix of distances and durations, or empty list on error.
        """
        headers = {
            'Content-Type': 'application/json',
            'X-Goog-Api-Key': self.api_key,
            'X-Goog-FieldMask': 'routes.duration,routes.distanceMeters'
        }

        results_matrix = []
        self.logger.debug(f"Async calculate_distance_matrix: Processing {len(origins)} origins and {len(destinations)} destinations.")

        for origin_loc in origins:
            row = []
            for dest_loc in destinations:
                data = {
                    'origin': {'location': {'latLng': {'latitude': origin_loc['lat'], 'longitude': origin_loc['lng']}}},
                    'destination': {'location': {'latLng': {'latitude': dest_loc['lat'], 'longitude': dest_loc['lng']}}},
                    'travelMode': mode.upper(),
                    'routingPreference': 'TRAFFIC_AWARE'
                }
                
                self.logger.debug(f"Async calculate_distance_matrix: Requesting {self.base_url} for origin {origin_loc} to dest {dest_loc}")
                try:
                    async with self._session.post(self.base_url, headers=headers, json=data, timeout=10) as response:
                        response.raise_for_status()
                        result = await response.json()

                        if 'routes' in result and result['routes']:
                            route = result['routes'][0]
                            duration_str = route.get('duration', '0s').rstrip('s')
                            row.append({
                                'distance_meters': route.get('distanceMeters', 0),
                                'duration_seconds': int(float(duration_str)) if duration_str else 0,
                                'distance_km': float(route.get('distanceMeters', 0)) / 1000 if route.get('distanceMeters') is not None else 0,
                                'duration_text': f"{int(float(duration_str) / 60)} mins" if duration_str else "N/A"
                            })
                        else:
                            self.logger.warning(f"Async calculate_distance_matrix: No routes found for origin {origin_loc} to dest {dest_loc}. API response: {result}")
                            row.append({'distance_meters': None, 'duration_seconds': None, 'error': 'No route found'})
                except aiohttp.ClientResponseError as e:
                    self.logger.error(f"Async calculate_distance_matrix: HTTP error for origin {origin_loc} to dest {dest_loc}: {e.status} {e.message}")
                    row.append({'distance_meters': None, 'duration_seconds': None, 'error': f"HTTP {e.status}"})
                except asyncio.TimeoutError:
                    self.logger.error(f"Async calculate_distance_matrix: Timeout for origin {origin_loc} to dest {dest_loc}")
                    row.append({'distance_meters': None, 'duration_seconds': None, 'error': 'Timeout'})
                except Exception as e:
                    self.logger.error(f"Async calculate_distance_matrix: Unexpected error for origin {origin_loc} to dest {dest_loc}: {str(e)}")
                    row.append({'distance_meters': None, 'duration_seconds': None, 'error': 'Unexpected error'})
            results_matrix.append(row)
        
        return results_matrix

    async def close(self):
        self.logger.info("GoogleRoutesClient close called (session managed externally).")
        pass 