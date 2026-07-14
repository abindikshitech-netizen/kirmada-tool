import os
from dotenv import load_dotenv

# Run load_dotenv once on module startup
load_dotenv()

class APIKeyManager:
    _api_key = ""

    @classmethod
    def load_from_env(cls):
        """Load API key from .env file directly, falling back to os.getenv."""
        key = ""
        env_path = os.path.join(os.getcwd(), ".env")
        if os.path.exists(env_path):
            try:
                with open(env_path, "r") as f:
                    for line in f:
                        if line.strip().startswith("GOOGLE_API_KEY="):
                            key = line.strip().split("=", 1)[1].strip()
                            if (key.startswith('"') and key.endswith('"')) or (key.startswith("'") and key.endswith("'")):
                                key = key[1:-1]
                            break
            except Exception as e:
                print(f"Error reading .env file: {e}")
        
        if not key:
            key = os.getenv("GOOGLE_API_KEY", "")
            
        cls._api_key = key
        return key

    @classmethod
    def get_key(cls):
        """Always return the in-memory API key."""
        return cls._api_key

    @classmethod
    def set_key(cls, key):
        """Update the in-memory API key."""
        cls._api_key = key
        os.environ["GOOGLE_API_KEY"] = key

    @classmethod
    def save_to_env(cls, key):
        """Save the key to .env file and update in-memory and environment variables."""
        cls._api_key = key
        env_path = os.path.join(os.getcwd(), ".env")
        lines = []
        key_found = False
        
        if os.path.exists(env_path):
            try:
                with open(env_path, "r") as f:
                    lines = f.readlines()
            except Exception as e:
                print(f"Error reading .env for saving: {e}")
                
        new_lines = []
        for line in lines:
            if line.strip().startswith("GOOGLE_API_KEY="):
                new_lines.append(f"GOOGLE_API_KEY={key}\n")
                key_found = True
            else:
                new_lines.append(line)
                
        if not key_found:
            if new_lines and not new_lines[-1].endswith("\n"):
                new_lines[-1] = new_lines[-1] + "\n"
            new_lines.append(f"GOOGLE_API_KEY={key}\n")
            
        try:
            with open(env_path, "w") as f:
                f.writelines(new_lines)
            os.environ["GOOGLE_API_KEY"] = key
        except Exception as e:
            print(f"Error writing to .env: {e}")

# Load key initially from env on application startup
APIKeyManager.load_from_env()

def get_google_api_key():
    return APIKeyManager.get_key()

def set_google_api_key_env(key):
    APIKeyManager.set_key(key)

class GoogleAPIError(Exception):
    def __init__(self, message, status_code=None, google_status=None, reason=None):
        super().__init__(message)
        self.status_code = status_code
        self.google_status = google_status
        self.reason = reason

def is_billing_or_api_error(status, message, reason=None):
    status_str = str(status).upper() if status else ""
    msg_str = str(message).upper() if message else ""
    reason_str = str(reason).upper() if reason else ""
    
    triggers = [
        "REQUEST_DENIED",
        "BILLING_DISABLED",
        "BILLING_NOT_ENABLED",
        "API_NOT_ENABLED",
        "API_KEY_INVALID",
        "PERMISSION_DENIED",
        "OVER_QUERY_LIMIT",
        "RESOURCE_EXHAUSTED",
        "QUOTA_EXCEEDED",
        "API_DISABLED",
        "BILLING",
        "KEY_INVALID"
    ]
    for trigger in triggers:
        if trigger in status_str or trigger in msg_str or trigger in reason_str:
            return True
    return False

def detect_connection_mode(api_key):
    import requests
    # 1. Internet check
    try:
        requests.get("https://www.google.com", timeout=5)
    except Exception:
        return "Offline"
        
    # 2. Key existence check
    if not api_key or not api_key.strip():
        return "Playwright (Google Billing Disabled)"
        
    # 3. Google API Validation
    key = api_key.strip()
    try:
        # Check Geocoding API
        geocode_url = "https://maps.googleapis.com/maps/api/geocode/json"
        geocode_params = {"address": "Chennai, Tamil Nadu", "key": key}
        resp_geo = requests.get(geocode_url, params=geocode_params, timeout=5)
        
        if resp_geo.status_code != 200:
            try:
                err_data = resp_geo.json()
                g_status = err_data.get("status")
                g_msg = err_data.get("error_message")
            except:
                g_status = None
                g_msg = resp_geo.text
            if is_billing_or_api_error(g_status, g_msg):
                return "Playwright (Google Billing Disabled)"
        else:
            data = resp_geo.json()
            g_status = data.get("status")
            g_msg = data.get("error_message", "")
            if g_status not in ["OK", "ZERO_RESULTS"]:
                if is_billing_or_api_error(g_status, g_msg):
                    return "Playwright (Google Billing Disabled)"
            
        # Check Places API
        places_url = "https://places.googleapis.com/v1/places:searchText"
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": key,
            "X-Goog-FieldMask": "places.displayName"
        }
        payload = {"textQuery": "Googleplex", "maxResultCount": 1}
        resp_places = requests.post(places_url, json=payload, headers=headers, timeout=5)
        
        if resp_places.status_code != 200:
            try:
                err_data = resp_places.json().get("error", {})
                status = err_data.get("status")
                msg = err_data.get("message")
                details = err_data.get("details", [{}])[0]
                reason = details.get("reason") if isinstance(details, dict) else None
            except:
                status = None
                msg = resp_places.text
                reason = None
            if is_billing_or_api_error(status, msg, reason):
                return "Playwright (Google Billing Disabled)"
        else:
            # Succeeded! Both work
            return "Google API"
            
    except Exception:
        # Any network or decoding exception
        return "Playwright (Google Billing Disabled)"
        
    return "Playwright (Google Billing Disabled)"
