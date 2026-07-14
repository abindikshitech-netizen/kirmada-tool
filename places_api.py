import requests
from config import get_google_api_key, GoogleAPIError, is_billing_or_api_error
from models.shop import Shop
from logger import app_logger
from utils import retry_on_exception
from constants import API_TIMEOUT, MAX_RETRIES

class PlacesAPI:
    def __init__(self):
        self.api_key = get_google_api_key()
        self.url = "https://places.googleapis.com/v1/places:searchText"
        self._session = requests.Session()
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            self._session.close()
            
    def close(self):
        if self._session:
            self._session.close()
        
    @retry_on_exception(max_retries=MAX_RETRIES)
    def search(self, shop: Shop, query_override=None):
        self.api_key = get_google_api_key()
        if not self.api_key: return False
        query = query_override or f"{shop.original_shop_name_address} {shop.original_district}"
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.nationalPhoneNumber,places.websiteUri,places.location,places.businessStatus,places.primaryTypeDisplayName,places.rating,places.userRatingCount,places.googleMapsUri,places.plusCode"
        }
        payload = {"textQuery": query, "languageCode": "en", "maxResultCount": 1}
        try:
            resp = self._session.post(self.url, json=payload, headers=headers, timeout=API_TIMEOUT)
            
            if resp.status_code != 200:
                # Check for Google billing or permission errors
                try:
                    err_json = resp.json().get("error", {})
                    g_status = err_json.get("status")
                    g_msg = err_json.get("message")
                    details = err_json.get("details", [{}])[0]
                    reason = details.get("reason") if isinstance(details, dict) else None
                except Exception:
                    g_status = None
                    g_msg = resp.text
                    reason = None
                    
                if is_billing_or_api_error(g_status, g_msg, reason):
                    raise GoogleAPIError(
                        f"Places API Error: {g_msg} (status: {g_status}, reason: {reason})",
                        status_code=resp.status_code,
                        google_status=g_status,
                        reason=reason
                    )
                else:
                    resp.raise_for_status()
                    
            data = resp.json()
            if "places" in data and data["places"]:
                p = data["places"][0]
                shop.latest_address = p.get("formattedAddress", "")
                shop.phone_number = p.get("nationalPhoneNumber", "")
                shop.website = p.get("websiteUri", "")
                shop.business_status = p.get("businessStatus", "OPERATIONAL")
                if "location" in p:
                    shop.latitude = p["location"].get("latitude", 0.0)
                    shop.longitude = p["location"].get("longitude", 0.0)
                
                # Extended fields
                shop.business_name = p.get("displayName", {}).get("text", "")
                shop.business_category = p.get("primaryTypeDisplayName", {}).get("text", "")
                shop.rating = str(p.get("rating", "")) if p.get("rating") is not None else ""
                shop.review_count = str(p.get("userRatingCount", "")) if p.get("userRatingCount") is not None else ""
                shop.google_maps_url = p.get("googleMapsUri", "")
                shop.plus_code = p.get("plusCode", {}).get("globalCode", "")
                
                if shop.business_status == "OPERATIONAL":
                    shop.open_closed_status = "Open now"
                elif shop.business_status == "CLOSED_TEMPORARILY":
                    shop.open_closed_status = "Temporarily closed"
                elif shop.business_status == "CLOSED_PERMANENTLY":
                    shop.open_closed_status = "Permanently closed"
                
                shop.data_source = "Google Places API"
                return True
        except GoogleAPIError:
            raise
        except Exception as e:
            app_logger.error(f"Places API failed: {e}")
        return False
