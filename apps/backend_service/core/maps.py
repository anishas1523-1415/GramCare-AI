import os
import logging
import googlemaps
from typing import Optional, Dict, Any, List
from functools import lru_cache

logger = logging.getLogger("gramcare.maps")

class MapsClient:
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        self.client = None
        if self.api_key:
            try:
                self.client = googlemaps.Client(key=self.api_key)
                logger.info("Google Maps Client initialized.")
            except Exception as e:
                logger.error(f"Failed to initialize Google Maps Client: {e}")
        else:
            logger.warning("GOOGLE_MAPS_API_KEY is missing. Maps API calls will fail.")

    @lru_cache(maxsize=1024)
    def get_distance_and_eta(self, origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float) -> Optional[Dict[str, Any]]:
        """
        Uses Distance Matrix API to calculate road distance and ETA.
        Returns dict with 'distance_meters', 'duration_seconds', 'distance_text', 'duration_text'.
        LRU cache prevents redundant API calls for static locations (e.g., hospital to hospital).
        """
        if not self.client:
            return None

        try:
            origins = f"{origin_lat},{origin_lng}"
            destinations = f"{dest_lat},{dest_lng}"
            
            result = self.client.distance_matrix(origins, destinations, mode="driving")
            
            if result['status'] == 'OK':
                element = result['rows'][0]['elements'][0]
                if element['status'] == 'OK':
                    return {
                        'distance_meters': element['distance']['value'],
                        'duration_seconds': element['duration']['value'],
                        'distance_text': element['distance']['text'],
                        'duration_text': element['duration']['text'],
                    }
            logger.warning(f"Distance Matrix API returned non-OK status: {result}")
            return None
        except Exception as e:
            logger.error(f"Error fetching distance matrix: {e}")
            return None

    def get_nearest_destination(self, origin_lat: float, origin_lng: float, destinations: List[Dict[str, float]]) -> Optional[Dict[str, Any]]:
        """
        Takes a single origin and a list of destinations [{"id": 1, "lat": 12.0, "lng": 77.0}, ...].
        Uses Distance Matrix API to find the destination with the shortest driving duration.
        """
        if not self.client or not destinations:
            return None
            
        try:
            origins = f"{origin_lat},{origin_lng}"
            dest_strings = [f"{d['lat']},{d['lng']}" for d in destinations]
            
            # API allows max 25 destinations per request, but we assume destinations list is already coarse-filtered
            result = self.client.distance_matrix(origins, dest_strings, mode="driving")
            
            if result['status'] == 'OK':
                elements = result['rows'][0]['elements']
                best_dest = None
                best_duration = float('inf')
                
                for i, element in enumerate(elements):
                    if element['status'] == 'OK':
                        duration = element['duration']['value']
                        if duration < best_duration:
                            best_duration = duration
                            best_dest = destinations[i].copy()
                            best_dest.update({
                                'distance_meters': element['distance']['value'],
                                'duration_seconds': duration,
                                'distance_text': element['distance']['text'],
                                'duration_text': element['duration']['text'],
                            })
                return best_dest
            return None
        except Exception as e:
            logger.error(f"Error finding nearest destination: {e}")
            return None

    def get_distance_list(self, origin_lat: float, origin_lng: float, destinations: List[Dict[str, float]]) -> Dict[int, float]:
        """
        Returns a dict of destination ID -> distance in km using Distance Matrix API.
        Takes max 25 destinations.
        """
        if not self.client or not destinations:
            return {}
            
        try:
            origins = f"{origin_lat},{origin_lng}"
            dest_strings = [f"{d['lat']},{d['lng']}" for d in destinations[:25]]
            
            result = self.client.distance_matrix(origins, dest_strings, mode="driving")
            distances = {}
            if result['status'] == 'OK':
                elements = result['rows'][0]['elements']
                for i, element in enumerate(elements):
                    if element['status'] == 'OK':
                        # Convert meters to km
                        distances[destinations[i]['id']] = round(element['distance']['value'] / 1000.0, 1)
            return distances
        except Exception as e:
            logger.error(f"Error fetching distance matrix list: {e}")
            return {}

    def reverse_geocode(self, lat: float, lng: float) -> Optional[str]:
        """
        Converts coordinates into a human-readable address.
        """
        if not self.client:
            return None
            
        try:
            result = self.client.reverse_geocode((lat, lng))
            if result and len(result) > 0:
                return result[0]['formatted_address']
            return None
        except Exception as e:
            logger.error(f"Error reverse geocoding ({lat}, {lng}): {e}")
            return None

maps_client = MapsClient()
