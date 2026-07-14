import sys
import os
import threading
import time
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

# Debug wrapper to print and log everything at startup
def debug_print(msg):
    print(f"[DEBUG] {msg}")

@dataclass
class AuditTracker:
    input_count: int = 0
    parsed_count: int = 0
    queued_count: int = 0
    processing_count: int = 0
    completed_count: int = 0
    verified_count: int = 0
    manual_review_count: int = 0
    failed_count: int = 0
    exported_count: int = 0

audit_tracker = AuditTracker()

try:
    debug_print("Starting application...")
    from logger import app_logger
    debug_print("Loaded logger...")
    
    from gui import VerifierApp
    debug_print("Loaded GUI framework...")
    
    from excel_handler import ExcelHandler
    from resume import resume_state
    from cache_manager import cache
    from performance import perf_tracker
    from settings import app_settings
    from report_generator import ReportGenerator

    from places_api import PlacesAPI
    from geocoding import GeocodingAPI
    from maps_scraper import MapsScraper
    from verification_engine import VerificationEngine
    from constants import STATUS_MANUAL_REVIEW
    from models.shop import Shop
    debug_print("Loaded all imports successfully.")
except Exception as e:
    import traceback
    err = traceback.format_exc()
    print(err)
    try:
        from tkinter import messagebox
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Startup Error", f"Fatal error during imports:\n{err}")
    except: pass
    sys.exit(1)

def normalize_for_duplicate_check(name, address):
    import re
    text = f"{name} {address}".lower()
    text = re.sub(r'[^a-z0-9]', '', text)
    for word in ["jewellers", "jewellery", "store", "shop", "pvt", "ltd", "private", "limited", "and", "sons"]:
        text = text.replace(word, "")
    return text.strip()

def _copy_shop_fields(src, dest):
    dest.pincode = src.pincode
    dest.latest_address = src.latest_address
    dest.phone_number = src.phone_number
    dest.business_status = src.business_status
    dest.verification_status = src.verification_status
    dest.confidence_score = src.confidence_score
    dest.data_source = src.data_source
    dest.latitude = src.latitude
    dest.longitude = src.longitude
    dest.website = src.website
    dest.business_name = src.business_name
    dest.business_category = src.business_category
    dest.open_closed_status = src.open_closed_status
    dest.rating = src.rating
    dest.review_count = src.review_count
    dest.google_maps_url = src.google_maps_url
    dest.plus_code = src.plus_code
    dest.place_id = src.place_id
    dest.error_message = src.error_message

class Orchestrator:
    def __init__(self):
        self.is_paused = False
        self.is_stopped = False
        self.pause_condition = threading.Condition()
        self.app = None
        self.autosave_counter = 0
        self.autosave_lock = threading.Lock()
        self.handler = None
        self.shops = []
        
        # Batch Duplicate Detection structures
        self.batch_lock = threading.Lock()
        self.batch_processed = {}
        self.batch_processing = set()

    def pause(self):
        self.is_paused = True
        app_logger.info("Orchestrator paused.")

    def resume(self):
        self.is_paused = False
        with self.pause_condition:
            self.pause_condition.notify_all()
        app_logger.info("Orchestrator resumed.")

    def stop(self):
        self.is_stopped = True
        self.resume()
        app_logger.info("Orchestrator stopped. Initiating graceful shutdown...")

    def process_shop(self, shop):
        if self.is_stopped: return shop
        with self.pause_condition:
            while self.is_paused:
                self.pause_condition.wait()
                if self.is_stopped: return shop

        norm_key = normalize_for_duplicate_check(shop.shop_name, shop.original_shop_name_address)
        
        # Wait if another thread is currently processing the same business
        while True:
            with self.batch_lock:
                if norm_key in self.batch_processed:
                    dup = self.batch_processed[norm_key]
                    _copy_shop_fields(dup, shop)
                    shop.data_source = f"Duplicate of Row {dup.row_index + 1}"
                    shop.processed = True
                    app_logger.info(f"Smart Duplicate Detection: Row {shop.row_index + 1} matches Row {dup.row_index + 1}. Copying results.")
                    if shop.verification_status in ["Verified", "Likely Match"]: 
                        perf_tracker.record_success()
                    else: 
                        perf_tracker.record_manual()
                    return shop
                if norm_key not in self.batch_processing:
                    self.batch_processing.add(norm_key)
                    break
            time.sleep(0.5)

        try:
            # Check DB Cache first
            cached_data = cache.get(shop.original_shop_name_address, shop.original_district)
            use_cache = False
            if cached_data:
                v_status = cached_data.get("Verification Status", "")
                has_address = bool(cached_data.get("Latest Complete Address", "").strip())
                has_coords = bool(cached_data.get("Latitude")) and bool(cached_data.get("Longitude"))
                has_phone = bool(cached_data.get("Phone Number", "").strip())
                
                is_status_ok = v_status in ["Verified", "Likely Match"]
                
                if is_status_ok and has_address and has_coords and has_phone:
                    app_logger.info("Cache Hit (Verified)")
                    use_cache = True
                else:
                    if v_status == "Manual Review":
                        app_logger.info("Cache Hit (Manual Review)")
                    app_logger.info("Cache Invalid")
                    app_logger.info("Reprocessing Shop")

            if use_cache:
                app_logger.info(f"Shop {shop.row_index+1} loaded from cache")
                shop.pincode = cached_data.get("Pincode", "")
                shop.latest_address = cached_data.get("Latest Complete Address", "")
                shop.phone_number = cached_data.get("Phone Number", "")
                shop.business_status = cached_data.get("Business Status", "")
                shop.verification_status = cached_data.get("Verification Status", "")
                shop.confidence_score = cached_data.get("Confidence Score", 0)
                shop.data_source = cached_data.get("Data Source", "")
                shop.latitude = cached_data.get("Latitude", 0.0)
                shop.longitude = cached_data.get("Longitude", 0.0)
                shop.website = cached_data.get("Website", "")
                
                shop.business_name = cached_data.get("Business Name", "")
                shop.business_category = cached_data.get("Business Category", "")
                shop.open_closed_status = cached_data.get("Open/Closed Status", "")
                shop.rating = cached_data.get("Ratings", "")
                shop.review_count = cached_data.get("Review Count", "")
                shop.google_maps_url = cached_data.get("Google Maps URL", "")
                shop.plus_code = cached_data.get("Plus Code", "")
                shop.place_id = cached_data.get("Place ID", "")
                shop.error_message = cached_data.get("Error Message", "")
                
                shop.processed = True
                perf_tracker.record_success()
                return shop
            elif cached_data:
                app_logger.info("Playwright Started")
                MapsScraper.enqueue(shop)
                return shop

            app_logger.info(f"Worker Processing Shop {shop.row_index+1}")
            
            with PlacesAPI() as places, GeocodingAPI() as geocoding:
                # Setup search strategies
                strategies = []
                strategies.append(("Name + District", f"{shop.shop_name} {shop.original_district}"))
                strategies.append(("Name + Old Address", f"{shop.shop_name} {shop.original_shop_name_address}"))
                import re
                orig_pincode_match = re.search(r'\b\d{6}\b', shop.original_shop_name_address)
                if orig_pincode_match:
                    strategies.append(("Name + Pincode", f"{shop.shop_name} {orig_pincode_match.group(0)}"))
                strategies.append(("Name Only", shop.shop_name))
    
                time.sleep(app_settings.get("delay", 1.0))
                
                best_google_shop = None
                best_google_confidence = -1
                
                from config import GoogleAPIError
                
                if self.google_apis_usable:
                    for strat_name, query_val in strategies:
                        temp_shop = Shop(
                            original_shop_name_address=shop.original_shop_name_address,
                            original_district=shop.original_district,
                            row_index=shop.row_index
                        )
                        try:
                            success = places.search(temp_shop, query_override=query_val)
                            if success:
                                geocoding.enrich_with_coordinates(temp_shop)
                                VerificationEngine.verify(temp_shop)
                                
                                app_logger.info(f"Google API Strategy '{strat_name}' for Row {shop.row_index+1}: Conf={temp_shop.confidence_score}")
                                if temp_shop.confidence_score > best_google_confidence:
                                    best_google_confidence = temp_shop.confidence_score
                                    best_google_shop = temp_shop
                                    
                                if best_google_confidence >= 90:
                                    break
                        except GoogleAPIError as ge:
                            self.google_apis_usable = False
                            app_logger.warning(f"Google API unavailable (Billing/Quota limit hit). Switching to Playwright... Reason: {ge}")
                            break
                
                # If Google API worked and confidence >= 80, we use it!
                if best_google_shop and best_google_confidence >= 80:
                    _copy_shop_fields(best_google_shop, shop)
                    perf_tracker.record_success()
                    shop.processed = True
                    cache.set(shop)
                    return shop

            # Fallback to Playwright
            app_logger.info("Playwright Started")
            MapsScraper.enqueue(shop)
            return shop
            
        except Exception as e:
            app_logger.error(f"Error processing shop {shop.original_shop_name_address}: {e}")
            import traceback
            app_logger.error(f"Traceback: {traceback.format_exc()}")
            shop.error_message = str(e)
            shop.verification_status = STATUS_MANUAL_REVIEW
            shop.processed = True
            perf_tracker.record_failed()
            return shop
            
        finally:
            with self.batch_lock:
                self.batch_processed[norm_key] = shop
                if norm_key in self.batch_processing:
                    self.batch_processing.remove(norm_key)

    def _trigger_autosave(self):
        with self.autosave_lock:
            self.autosave_counter += 1
            if self.autosave_counter >= 5:
                resume_state.save()
                cache.save()
                self.autosave_counter = 0

    def _run_production_self_test(self):
        app_logger.info("Running Production Self Test...")
        errors = []
        if not MapsScraper._queue.empty():
            errors.append("Queue is not empty.")
        if MapsScraper._is_running:
            errors.append("Playwright worker thread is still running.")
        
        # Verify output exists
        if self.handler and not os.path.exists(os.path.join(self.handler.output_path, "Updated_Jewellery_Shops.xlsx")):
            errors.append("Output Excel file was not generated.")
            
        # Verify Playwright timing if any shops went to manual review
        if audit_tracker.manual_review_count > 0:
            time_spent = getattr(MapsScraper, 'total_browser_time', 0.0)
            if time_spent < 10.0:
                errors.append("Playwright execution skipped unexpectedly.")
            
        if errors:
            raise RuntimeError(f"Production Self Test Failed: {'; '.join(errors)}")
        app_logger.info("Production Self Test Passed.")

    def run(self, input_path, output_path, app_instance, retry_failed=False):
        self.app = app_instance
        self.is_stopped = False
        self.is_paused = False
        self.autosave_counter = 0
        
        global audit_tracker
        audit_tracker = AuditTracker()
        
        logger_id = app_logger.add(self.app.log_to_console, format="{time:HH:mm:ss} | {level} | {message}", level="INFO")
        
        try:
            from config import detect_connection_mode, get_google_api_key
            mode = detect_connection_mode(get_google_api_key())
            self.google_apis_usable = (mode == "Google API")
            app_logger.info(f"Centralized connection mode detected: {mode}. Google API usable = {self.google_apis_usable}")
            
            MapsScraper.initialize(self.app, self)
            MapsScraper.wait_for_ready()
            
            self.handler = ExcelHandler(input_path, output_path)
            all_shops, total = self.handler.read_input()
            audit_tracker.input_count = len(all_shops)
            audit_tracker.parsed_count = len(all_shops)
            
            app_logger.info(f"Loaded {audit_tracker.input_count} Shops")
            
            if retry_failed:
                self.shops = [s for s in all_shops if not cache.get(s.original_shop_name_address, s.original_district) or cache.get(s.original_shop_name_address, s.original_district).get("Verification Status") not in ["Verified", "Likely Match"]]
                app_logger.info(f"Retry Failed mode: Processing {len(self.shops)} non-verified shops.")
            else:
                self.shops = all_shops

            perf_tracker.start(len(self.shops))
            concurrency = app_settings.get("concurrency", 5)
            
            for shop in self.shops:
                if retry_failed or not resume_state.is_processed(shop.row_index):
                    audit_tracker.queued_count += 1
            
            app_logger.info(f"Sent to ThreadPool: {audit_tracker.queued_count}")
            
            # Since skipped shops are not processed, they must be manually populated from cache to be exported.
            for shop in self.shops:
                if not retry_failed and resume_state.is_processed(shop.row_index):
                    cached_data = cache.get(shop.original_shop_name_address, shop.original_district)
                    if cached_data:
                        shop.pincode = cached_data.get("Pincode", "")
                        shop.latest_address = cached_data.get("Latest Complete Address", "")
                        shop.phone_number = cached_data.get("Phone Number", "")
                        shop.business_status = cached_data.get("Business Status", "")
                        shop.verification_status = cached_data.get("Verification Status", "")
                        shop.confidence_score = cached_data.get("Confidence Score", 0)
                        shop.data_source = cached_data.get("Data Source", "")
                        shop.latitude = cached_data.get("Latitude", 0.0)
                        shop.longitude = cached_data.get("Longitude", 0.0)
                        shop.website = cached_data.get("Website", "")
                        shop.business_name = cached_data.get("Business Name", "")
                        shop.business_category = cached_data.get("Business Category", "")
                        shop.open_closed_status = cached_data.get("Open/Closed Status", "")
                        shop.rating = cached_data.get("Ratings", "")
                        shop.review_count = cached_data.get("Review Count", "")
                        shop.google_maps_url = cached_data.get("Google Maps URL", "")
                        shop.plus_code = cached_data.get("Plus Code", "")
                        shop.place_id = cached_data.get("Place ID", "")
                        shop.error_message = cached_data.get("Error Message", "")
                        shop.processed = True
                        audit_tracker.processing_count += 1
                        audit_tracker.completed_count += 1

            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                futures = {}
                for shop in self.shops:
                    if retry_failed or not resume_state.is_processed(shop.row_index):
                        audit_tracker.processing_count += 1
                        futures[executor.submit(self.process_shop, shop)] = shop
                        
                for future in as_completed(futures):
                    if self.is_stopped:
                        executor.shutdown(wait=False, cancel_futures=True)
                        break
                        
                    shop = future.result()
                    if shop.processed:
                        resume_state.mark_processed(shop.row_index)
                        self._trigger_autosave()
                        
                        stats = perf_tracker.get_stats()
                        self.app.update_stats(shop.original_shop_name_address, len(resume_state.state["processed_rows"]), len(self.shops), stats)
                        
            if not self.is_stopped:
                MapsScraper._queue.join()
                app_logger.info("Queue Joined")
                
                audit_tracker.completed_count = sum(1 for shop in self.shops if shop.processed)
                audit_tracker.verified_count = sum(1 for shop in self.shops if shop.verification_status in ["Verified", "Likely Match"])
                audit_tracker.failed_count = sum(1 for shop in self.shops if shop.error_message != "")
                audit_tracker.manual_review_count = sum(1 for shop in self.shops if shop.verification_status == "Manual Review" and shop.error_message == "")
                
                app_logger.info(f"Processed {audit_tracker.completed_count}")
                app_logger.info(f"Verified {audit_tracker.verified_count}")
                app_logger.info(f"Manual Review {audit_tracker.manual_review_count}")
                app_logger.info(f"Failed {audit_tracker.failed_count}")
                
                if len(self.shops) != audit_tracker.completed_count:
                    raise RuntimeError(f"End-to-End Audit Failed: {len(self.shops)} loaded but only {audit_tracker.completed_count} completed!")
                    
                if len(self.shops) != (audit_tracker.verified_count + audit_tracker.manual_review_count + audit_tracker.failed_count):
                    raise RuntimeError(f"End-to-End Audit Failed: Count mismatch. Total ({len(self.shops)}) != Verified ({audit_tracker.verified_count}) + Manual ({audit_tracker.manual_review_count}) + Failed ({audit_tracker.failed_count})")
                
                # Verification: At least one successful extraction occurred
                successful_extractions = sum(1 for shop in self.shops if shop.data_source in ["Google Maps Scraper", "Google Places API"] and not shop.error_message)
                if successful_extractions == 0:
                    raise RuntimeError("No successful extraction occurred. Refusing to export empty/unextracted data.")
                
                app_logger.info("Writing Excel")
                self.finalize_export()
                app_logger.info("Export Complete")
                
                MapsScraper.shutdown() # Ensure browser is closed before self test
                self._run_production_self_test()
                app_logger.info("Application Finished Successfully")
                self.app.load_manual_review(self.shops)
                self.app.processing_finished()
                
        except Exception as e:
            app_logger.error(f"Critical error in execution: {e}")
            import traceback
            app_logger.error(traceback.format_exc())
            raise
        finally:
            resume_state.save()
            cache.save()
            MapsScraper.shutdown()
            app_logger.remove(logger_id)
            if self.is_stopped:
                app_logger.info("Execution stopped safely.")

    def finalize_export(self):
        if self.handler and self.shops:
            try:
                self.handler.write_output(self.shops)
                report_gen = ReportGenerator(self.handler.output_path)
                report_gen.generate_all(self.shops)
                resume_state.clear()
            except Exception as e:
                app_logger.error(f"Failed to export: {e}")
                raise RuntimeError(f"Output generation failed: {e}")

def main():
    try:
        debug_print("Instantiating Orchestrator...")
        orchestrator = Orchestrator()
        
        debug_print("Creating GUI main window...")
        app = VerifierApp(
            orchestrator_callback=orchestrator.run,
            pause_callback=orchestrator.pause,
            resume_callback=orchestrator.resume,
            stop_callback=orchestrator.stop,
            finalize_callback=orchestrator.finalize_export
        )
        
        debug_print("Starting mainloop...")
        app.mainloop()
        debug_print("Mainloop exited cleanly.")
    except Exception as e:
        import traceback
        err = traceback.format_exc()
        print(err)
        try:
            from tkinter import messagebox
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Runtime Error", f"Fatal error during runtime:\n{err}")
        except: pass
        sys.exit(1)

if __name__ == "__main__":
    main()
