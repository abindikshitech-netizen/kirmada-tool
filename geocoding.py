import requests
from config import get_google_api_key, GoogleAPIError, is_billing_or_api_error
from constants import API_TIMEOUT, MAX_RETRIES
from utils import retry_on_exception
from logger import app_logger

def _show_result_gui(success, message):
    try:
        import tkinter as tk
        from tkinter import messagebox
        from tkinter.scrolledtext import ScrolledText
        
        # Check if default tkinter root window is running
        if tk._default_root is None:
            return
            
        root = tk._default_root
        
        def show():
            if success:
                messagebox.showinfo("Geocoding Connection Successful", message)
            else:
                # Create a custom scrollable dialog to show full traceback and JSON response
                dialog = tk.Toplevel(root)
                dialog.title("Geocoding Connection Failed")
                dialog.geometry("700x550")
                dialog.minsize(500, 400)
                dialog.grab_set()  # Modal dialog
                
                # Title
                lbl_title = tk.Label(dialog, text="Geocoding API Connection Test Failed!", font=("Arial", 12, "bold"), fg="red")
                lbl_title.pack(pady=10)
                
                # Scrollable Text area
                txt_area = ScrolledText(dialog, wrap="word", font=("Consolas", 10))
                txt_area.pack(fill="both", expand=True, padx=15, pady=5)
                txt_area.insert("1.0", message)
                txt_area.configure(state="disabled")
                
                # Close button
                btn_close = tk.Button(dialog, text="Close", command=dialog.destroy, bg="red", fg="white", font=("Arial", 10, "bold"), width=12)
                btn_close.pack(pady=10)
                
        # Schedule the window to be drawn on the Tkinter main event thread safely
        root.after(0, show)
    except Exception as e:
        # Fallback to simple logging if GUI cannot be displayed
        app_logger.error(f"Could not display connection result dialog: {e}")

class GeocodingAPI:
    def __init__(self):
        self.api_key = get_google_api_key()
        self.url = "https://maps.googleapis.com/maps/api/geocode/json"
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
    def enrich_with_coordinates(self, shop):
        self.api_key = get_google_api_key()
        if not self.api_key: return False
        if not shop.latest_address: return False
        params = {"address": shop.latest_address, "key": self.api_key}
        
        resp = None
        data = None
        try:
            resp = self._session.get(self.url, params=params, timeout=API_TIMEOUT)
            
            # Check for Google billing or permission errors
            if resp.status_code != 200:
                try:
                    err_json = resp.json()
                    g_status = err_json.get("status")
                    g_msg = err_json.get("error_message")
                except Exception:
                    g_status = None
                    g_msg = resp.text
                    
                if is_billing_or_api_error(g_status, g_msg):
                    raise GoogleAPIError(
                        f"Geocoding API Error: {g_msg} (status: {g_status})",
                        status_code=resp.status_code,
                        google_status=g_status
                    )
                else:
                    resp.raise_for_status()
                    
            data = resp.json()
            google_status = data.get("status")
            error_message = data.get("error_message", "No error message field in response")
            
            if google_status not in ["OK", "ZERO_RESULTS"]:
                if is_billing_or_api_error(google_status, error_message):
                    raise GoogleAPIError(
                        f"Geocoding API Error: {error_message} (status: {google_status})",
                        status_code=200,
                        google_status=google_status
                    )
                    
            if google_status == "OK":
                loc = data["results"][0]["geometry"]["location"]
                shop.latitude = loc["lat"]
                shop.longitude = loc["lng"]
                
                # Extract pincode
                for comp in data["results"][0]["address_components"]:
                    if "postal_code" in comp["types"]:
                        shop.pincode = comp["long_name"]
                        break
                return True
            else:
                import json
                app_logger.error(
                    f"Geocoding API validation failed.\n"
                    f"HTTP Status: {resp.status_code}\n"
                    f"Google Status: {google_status}\n"
                    f"Error Message: {error_message}\n"
                    f"Full JSON Response:\n{json.dumps(data, indent=2)}"
                )
                return False
        except GoogleAPIError:
            raise
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            http_status = resp.status_code if resp is not None else "N/A"
            g_status = "N/A"
            g_msg = str(e)
            
            json_response_str = "N/A"
            if resp is not None:
                try:
                    data = resp.json()
                    g_status = data.get("status", "N/A")
                    g_msg = data.get("error_message", g_msg)
                    import json
                    json_response_str = json.dumps(data, indent=2)
                except:
                    json_response_str = resp.text
                    
            app_logger.error(
                f"Geocoding API exception occurred: {e}\n"
                f"HTTP Status: {http_status}\n"
                f"Google Status: {g_status}\n"
                f"Error Message: {g_msg}\n"
                f"Full Response/JSON:\n{json_response_str}\n"
                f"Traceback:\n{tb}"
            )
        return False

    def test_connection(self):
        import traceback
        import sys
        import json
        
        self.api_key = get_google_api_key()
        test_address = "Chennai, Tamil Nadu"
        params = {"address": test_address, "key": self.api_key}
        
        resp = None
        data = None
        try:
            if not self.api_key:
                raise ValueError("API Key is missing or empty")
                
            resp = self._session.get(self.url, params=params, timeout=API_TIMEOUT)
            http_status = resp.status_code
            
            try:
                data = resp.json()
            except Exception as json_err:
                data = None
                raise Exception(f"Failed to parse JSON response. Response text: {resp.text}") from json_err
                
            google_status = data.get("status")
            
            if http_status != 200 or google_status != "OK":
                if is_billing_or_api_error(google_status, data.get("error_message")):
                    raise GoogleAPIError(f"Google API Billing/Permission Error: {data.get('error_message')}", status_code=http_status, google_status=google_status)
                raise Exception(f"Validation failed: HTTP Status = {http_status}, Google Status = {google_status}")
                
            # Parse success fields
            result = data["results"][0]
            formatted_address = result.get("formatted_address")
            loc = result["geometry"]["location"]
            lat = loc["lat"]
            lng = loc["lng"]
            
            # Display success information
            success_msg = (
                f"HTTP Status: {http_status}\n"
                f"Google Status: {google_status}\n"
                f"Formatted Address: {formatted_address}\n"
                f"Latitude: {lat}\n"
                f"Longitude: {lng}"
            )
            print("\n=== Geocoding API Connection Test Succeeded ===")
            print(success_msg)
            print("===============================================\n")
            app_logger.info(f"Geocoding API Connection Test Succeeded:\n{success_msg}")
            
            _show_result_gui(True, success_msg)
            self.close()
            return True
            
        except Exception as e:
            tb = traceback.format_exc()
            
            fail_msg_parts = []
            fail_msg_parts.append("=== Geocoding API Connection Test Failed ===")
            if resp is not None:
                fail_msg_parts.append(f"HTTP Status: {resp.status_code}")
            else:
                fail_msg_parts.append("HTTP Status: N/A (Failed to connect)")
                
            google_status = "N/A"
            error_message = str(e)
            
            if isinstance(data, dict):
                google_status = data.get("status", "N/A")
                error_message = data.get("error_message", error_message)
                fail_msg_parts.append(f"Google Status: {google_status}")
                fail_msg_parts.append(f"Error Message: {error_message}")
                json_str = json.dumps(data, indent=2)
                fail_msg_parts.append(f"Complete JSON Response:\n{json_str}")
            elif resp is not None:
                fail_msg_parts.append(f"Complete Response Text:\n{resp.text}")
                
            fail_msg_parts.append(f"Exception: {str(e)}")
            fail_msg_parts.append(f"Exception Traceback:\n{tb}")
            fail_msg_parts.append("============================================")
            
            full_fail_msg = "\n".join(fail_msg_parts)
            
            print(full_fail_msg, file=sys.stderr)
            app_logger.error(full_fail_msg)
            
            _show_result_gui(False, full_fail_msg)
            
            self.close()
            raise Exception(f"Geocoding connection test failed: {e}") from e
