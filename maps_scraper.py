import os
import time
import re
import random
import queue
import threading
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from models.shop import Shop
from logger import app_logger
from constants import SCREENSHOTS_DIR, PLAYWRIGHT_TIMEOUT
from utils import sanitize_filename

class PlaywrightTask:
    def __init__(self, shop: Shop, query_override=None):
        self.shop = shop
        self.query_override = query_override
        self.event = threading.Event()
        self.success = False
        self.error = None

def check_for_captcha(page) -> bool:
    try:
        if "google.com/sorry/" in page.url:
            return True
        if page.locator("iframe[src*='recaptcha']").count() > 0:
            return True
        if page.locator("div.g-recaptcha").count() > 0:
            return True
        if page.locator("body").count() > 0:
            body_text = page.locator("body").inner_text().lower()
            if "unusual traffic from your computer network" in body_text or "recaptcha" in body_text:
                return True
    except Exception:
        pass
    return False

def human_like_scroll(page):
    try:
        steps = random.randint(2, 4)
        for _ in range(steps):
            scroll_y = random.randint(150, 450)
            page.evaluate(f"window.scrollBy(0, {scroll_y})")
            page.wait_for_timeout(random.randint(500, 1500))
        page.evaluate(f"window.scrollBy(0, -{random.randint(100, 200)})")
        page.wait_for_timeout(random.randint(300, 800))
    except Exception:
        pass

def human_like_mouse_move(page):
    try:
        start_x, start_y = random.randint(100, 500), random.randint(100, 400)
        end_x, end_y = random.randint(500, 1000), random.randint(400, 700)
        page.mouse.move(start_x, start_y)
        steps = random.randint(5, 10)
        for i in range(steps):
            curr_x = start_x + (end_x - start_x) * (i / steps) + random.randint(-20, 20)
            curr_y = start_y + (end_y - start_y) * (i / steps) + random.randint(-20, 20)
            page.mouse.move(curr_x, curr_y)
            page.wait_for_timeout(random.randint(30, 80))
        page.mouse.move(end_x, end_y)
        page.wait_for_timeout(random.randint(100, 300))
    except Exception:
        pass

def human_like_click(page, locator):
    try:
        if locator.count() > 0:
            box = locator.first.bounding_box()
            if box:
                target_x = box["x"] + box["width"] / 2 + random.uniform(-3, 3)
                target_y = box["y"] + box["height"] / 2 + random.uniform(-3, 3)
                page.mouse.move(target_x, target_y, steps=random.randint(5, 12))
                page.wait_for_timeout(random.randint(100, 250))
                page.mouse.down()
                page.wait_for_timeout(random.randint(50, 150))
                page.mouse.up()
                return True
        locator.first.click()
        return True
    except Exception:
        try:
            locator.first.click()
            return True
        except Exception:
            return False


def navigate_to_google_maps(page):
    page.goto("https://www.google.com/maps", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(3000)


def wait_for_google_maps_search_box(page):
    candidates = [
        ("page.get_by_role('textbox')", page.get_by_role("textbox")),
        ("locator('input[aria-label*=\"Search\"]')", page.locator("input[aria-label*='Search']")),
        ("locator('input[placeholder*=\"Search\"]')", page.locator("input[placeholder*='Search']")),
        ("locator('input')", page.locator("input")),
    ]

    deadline = time.time() + 60
    while time.time() < deadline:
        for selector_name, locator in candidates:
            try:
                for i in range(locator.count()):
                    box = locator.nth(i)
                    if box.is_visible() and box.is_editable():
                        return box, selector_name
            except Exception:
                continue
        page.wait_for_timeout(500)
    return None, None


class MapsScraper:
    _queue = queue.Queue()
    _worker_thread = None
    _is_running = False
    _ready_event = threading.Event()
    total_browser_time = 0.0
    app = None
    orchestrator = None

    @classmethod
    def initialize(cls, app_instance, orchestrator_instance):
        cls.app = app_instance
        cls.orchestrator = orchestrator_instance
        if cls._worker_thread is None:
            cls._is_running = True
            cls._ready_event.clear()
            cls._worker_thread = threading.Thread(target=cls._worker, daemon=True)
            cls._worker_thread.start()

    @classmethod
    def wait_for_ready(cls):
        cls._ready_event.wait()

    @classmethod
    def shutdown(cls):
        if cls._worker_thread:
            cls._is_running = False
            cls._queue.put(None)
            cls._worker_thread.join(timeout=5)
            cls._worker_thread = None
            app_logger.info("Playwright worker thread shut down.")

    @classmethod
    def enqueue(cls, shop):
        app_logger.info(f"Queued Shop {shop.row_index+1}")
        cls._queue.put(shop)

    @classmethod
    def _scrape_single(cls, context, shop, query):
        page = None
        nav_start = time.perf_counter()
        nav_end = None
        ext_start = None
        ext_end = None
        try:
            app_logger.info("Opening page")
            page = context.new_page()
            app_logger.info("Page Created")
            page.set_default_timeout(PLAYWRIGHT_TIMEOUT)
            page.evaluate("() => { Object.defineProperty(navigator, 'webdriver', { get: () => undefined }); }")
            app_logger.info("Navigating to Google Maps")
            navigate_to_google_maps(page)
            curr_url = page.url
            curr_title = page.title()
            app_logger.info(f"Page URL: {curr_url}")
            app_logger.info(f"Page Title: {curr_title}")
            app_logger.info("Navigation Complete")
            if check_for_captcha(page):
                app_logger.warning("CAPTCHA detected on load. Attempting reload...")
                navigate_to_google_maps(page)
                if check_for_captcha(page):
                    app_logger.warning("CAPTCHA remains. Re-creating page context...")
                    page.close()
                    page = context.new_page()
                    navigate_to_google_maps(page)
            # Consent handling
            try:
                consent_button = page.locator("button:has-text('Accept all')")
                if consent_button.is_visible(timeout=2000):
                    human_like_click(page, consent_button)
                    page.wait_for_timeout(random.randint(500, 1200))
            except Exception:
                pass
            # Resilient search box locating
            search_box, chosen_selector = wait_for_google_maps_search_box(page)
            if not search_box:
                app_logger.error("Search box cannot be found!")
                safe_name = sanitize_filename(shop.shop_name)
                err_png = os.path.join(SCREENSHOTS_DIR, f"error_no_searchbox_{safe_name}_{shop.row_index}.png")
                page.screenshot(path=err_png)
                err_html = os.path.join(SCREENSHOTS_DIR, f"error_no_searchbox_{safe_name}_{shop.row_index}.html")
                with open(err_html, "w", encoding="utf-8") as f:
                    f.write(page.content())
                page.close()
                nav_end = time.perf_counter()
                return False, (nav_end - nav_start), 0.0, "search_box_not_found"
            app_logger.info(f"Chosen Selector: {chosen_selector}")
            app_logger.info("Search Box Found")
            human_like_mouse_move(page)
            human_like_click(page, search_box)
            app_logger.info("Search Started")
            search_box.fill(query)
            search_box.press("Enter")
            app_logger.info("Search Completed")
            app_logger.info("Waiting for results")
            try:
                page.wait_for_selector("div[role='main']", timeout=15000)
                page.wait_for_timeout(random.randint(1500, 3000))
                app_logger.info("Results found")
            except PlaywrightTimeoutError:
                if check_for_captcha(page):
                    app_logger.warning("CAPTCHA triggered after search. Reloading page...")
                    page.reload()
                    page.wait_for_timeout(random.randint(4000, 7000))
                else:
                    raise
            safe_name = sanitize_filename(shop.shop_name)
            screenshot_path = os.path.join(SCREENSHOTS_DIR, f"{safe_name}_{shop.row_index}.png")
            page.screenshot(path=screenshot_path)
            app_logger.info("Screenshot saved")
            # Handle multiple results
            is_place_view = page.locator("button[data-value='Directions']").count() > 0
            if not is_place_view:
                cards = page.locator("a[href*='/maps/place/']")
                if cards.count() > 0:
                    app_logger.info("Multiple results found. Clicking the first valid business card.")
                    human_like_click(page, cards.first)
                    page.wait_for_timeout(random.randint(2000, 4000))
                    page.screenshot(path=screenshot_path)
                    app_logger.info("Screenshot saved after card click")
                else:
                    app_logger.info("Extraction Finished: Place not found")
                    page.close()
                    nav_end = time.perf_counter()
                    return False, (nav_end - nav_start), 0.0, None
            nav_end = time.perf_counter()
            ext_start = time.perf_counter()
            # Extraction
            human_like_mouse_move(page)
            human_like_scroll(page)
            app_logger.info("Extracting fields")
            title_loc = page.locator("h1")
            shop.business_name = title_loc.first.inner_text().strip() if title_loc.count() > 0 else shop.shop_name
            address_loc = page.locator("button[data-item-id='address']")
            if address_loc.count() > 0:
                shop.latest_address = address_loc.inner_text().strip()
            if shop.latest_address:
                pincode_match = re.search(r"\\b\\d{6}\\b", shop.latest_address)
                if pincode_match:
                    shop.pincode = pincode_match.group(0)
            phone_loc = page.locator("button[data-item-id^='phone:tel:']")
            if phone_loc.count() > 0:
                shop.phone_number = phone_loc.inner_text().strip()
            website_loc = page.locator("a[data-item-id='authority']")
            if website_loc.count() > 0:
                shop.website = website_loc.get_attribute("href")
            cat_loc = page.locator("button[jsaction*='category']").first
            if cat_loc.count() > 0:
                shop.business_category = cat_loc.inner_text().strip()
            else:
                fallback = page.locator(".DkEaCc").first
                if fallback.count() > 0:
                    shop.business_category = fallback.inner_text().strip()
            hours_loc = page.locator("button[data-item-id^='oh:']").first
            if hours_loc.count() > 0:
                shop.open_closed_status = hours_loc.inner_text().strip().replace("\n", " ")
            else:
                hours_div = page.locator("div[jsaction*='pane.hours']").first
                if hours_div.count() > 0:
                    shop.open_closed_status = hours_div.inner_text().strip().replace("\n", " ")
            rating_cont = page.locator("div.F7nice").first
            if rating_cont.count() > 0:
                txt = rating_cont.inner_text().strip()
                rating_match = re.search(r'^(\\d\\.\\d)', txt)
                if rating_match:
                    shop.rating = rating_match.group(1)
                rev_match = re.search(r'\\((\\d+[,.\\d]*)\\)', txt)
                if rev_match:
                    shop.review_count = rev_match.group(1).replace(",", "")
            else:
                fallback = page.locator("span.fontBodyMedium").first
                if fallback.count() > 0:
                    fb_txt = fallback.inner_text().strip()
                    rating_match = re.search(r'^(\\d\\.\\d)', fb_txt)
                    if rating_match:
                        shop.rating = rating_match.group(1)
            shop.google_maps_url = page.url
            coord_match = re.search(r"@(-?\\d+\\.\\d+),(-?\\d+\\.\\d+)", page.url)
            if coord_match:
                shop.latitude = float(coord_match.group(1))
                shop.longitude = float(coord_match.group(2))
            plus_loc = page.locator("button[data-item-id='oloc']")
            if plus_loc.count() > 0:
                shop.plus_code = plus_loc.inner_text().strip().replace(" Plus Code", "")
            body_txt = page.locator("body").inner_text()
            if "Permanently closed" in body_txt:
                shop.business_status = "CLOSED_PERMANENTLY"
            elif "Temporarily closed" in body_txt:
                shop.business_status = "CLOSED_TEMPORARILY"
            else:
                shop.business_status = "OPERATIONAL"
            place_id = ""
            try:
                canonical = page.locator("link[rel='canonical']").first
                if canonical.count() > 0:
                    canon_url = canonical.get_attribute("href")
                    if "1s0x" in canon_url:
                        m = re.search(r'1s(0x[0-9a-fA-F]+:0x[0-9a-fA-F]+)', canon_url)
                        if m:
                            place_id = m.group(1)
            except Exception:
                pass
            if not place_id:
                try:
                    m = re.search(r'ftid:(0x[0-9a-fA-F]+:0x[0-9a-fA-F]+)', page.url)
                    if m:
                        place_id = m.group(1)
                except Exception:
                    pass
            shop.place_id = place_id
            shop.data_source = "Google Maps Scraper"
            app_logger.info("Extraction Finished")
            ext_end = time.perf_counter()
            return True, (nav_end - nav_start), (ext_end - ext_start), None
        except Exception as e:
            app_logger.error(f"Playwright error inside worker during extraction: {e}")
            if nav_end is None:
                nav_end = time.perf_counter()
            ext_end = time.perf_counter()
            try:
                safe_name = sanitize_filename(shop.shop_name)
                err_png = os.path.join(SCREENSHOTS_DIR, f"error_{safe_name}_{shop.row_index}.png")
                page.screenshot(path=err_png)
                err_html = os.path.join(SCREENSHOTS_DIR, f"error_{safe_name}_{shop.row_index}.html")
                with open(err_html, "w", encoding="utf-8") as f:
                    f.write(page.content())
                app_logger.error(f"Saved error screenshot and HTML for {shop.shop_name}")
            except Exception:
                pass
            nav_time = nav_end - nav_start
            ext_time = (ext_end - ext_start) if ext_start is not None else 0.0
            return False, nav_time, ext_time, None
        finally:
            if page:
                app_logger.info("Closing page")
                page.close()
                app_logger.info("Page Closed")

    @classmethod
    def _worker(cls):
        app_logger.info("Worker Started")
        playwright = None
        browser = None
        context = None
        try:
            playwright = sync_playwright().start()
            browser = playwright.chromium.launch(headless=False)
            context = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            app_logger.info("Browser Started")
            if browser.is_connected():
                cls._ready_event.set()
            else:
                app_logger.error("Browser failed to start and connect.")
                cls._is_running = False
                cls._ready_event.set()
                return
            while cls._is_running:
                try:
                    shop = cls._queue.get(timeout=1)
                except queue.Empty:
                    continue
                if shop is None:
                    cls._queue.task_done()
                    break
                try:
                    app_logger.info(f"Queue received Shop {shop.row_index+1}")
                    app_logger.info(f"Worker received Shop {shop.row_index+1}")
                    app_logger.info(f"Browser processing Shop {shop.row_index+1}")
                    strategies = []
                    strategies.append(("Name + District", f"{shop.shop_name} {shop.original_district}"))
                    strategies.append(("Name + Old Address", f"{shop.shop_name} {shop.original_shop_name_address}"))
                    pincode_match = re.search(r"\\b\\d{6}\\b", shop.original_shop_name_address)
                    if pincode_match:
                        strategies.append(("Name + Pincode", f"{shop.shop_name} {pincode_match.group(0)}"))
                    strategies.append(("Name Only", shop.shop_name))
                    best_shop = None
                    best_conf = -1
                    total_nav_time = 0.0
                    total_ext_time = 0.0
                    for name, query in strategies:
                        temp_shop = Shop(
                            original_shop_name_address=shop.original_shop_name_address,
                            original_district=shop.original_district,
                            row_index=shop.row_index
                        )
                        app_logger.info("Calling scrape_google_maps()")
                        success, nav_t, ext_t, err_type = cls._scrape_single(context, temp_shop, query)
                        total_nav_time += nav_t
                        total_ext_time += ext_t
                        if err_type == "search_box_not_found":
                            app_logger.error(f"Search box not found on Google Maps. Stopping retries for Row {shop.row_index+1}.")
                            break
                        if success:
                            from verification_engine import VerificationEngine
                            from geocoding import GeocodingAPI
                            from config import GoogleAPIError
                            if not temp_shop.latitude and not temp_shop.longitude and cls.orchestrator.google_apis_usable:
                                try:
                                    geocoding = GeocodingAPI()
                                    geocoding.enrich_with_coordinates(temp_shop)
                                except GoogleAPIError:
                                    cls.orchestrator.google_apis_usable = False
                            VerificationEngine.verify(temp_shop)
                            app_logger.info(f"Playwright Strategy '{name}' for Row {shop.row_index+1}: Conf={temp_shop.confidence_score}")
                            if temp_shop.confidence_score > best_conf:
                                best_conf = temp_shop.confidence_score
                                best_shop = temp_shop
                            if best_conf >= 90:
                                break
                    total_time = total_nav_time + total_ext_time
                    cls.total_browser_time += total_time
                    app_logger.info(f"Shop {shop.row_index+1}\nNavigation: {total_nav_time:.1f} sec\nExtraction: {total_ext_time:.1f} sec\nTotal: {total_time:.1f} sec")
                    app_logger.info(f"Extraction complete Shop {shop.row_index+1}")
                    from main import _copy_shop_fields
                    from performance import perf_tracker
                    from cache_manager import cache
                    from constants import STATUS_MANUAL_REVIEW
                    if best_shop:
                        _copy_shop_fields(best_shop, shop)
                        if shop.confidence_score >= 80:
                            perf_tracker.record_success()
                        else:
                            shop.verification_status = STATUS_MANUAL_REVIEW
                            perf_tracker.record_manual()
                    else:
                        shop.verification_status = STATUS_MANUAL_REVIEW
                        perf_tracker.record_manual()
                    shop.processed = True
                    cache.set(shop)
                    app_logger.info(f"Result Saved Shop {shop.row_index+1}")
                    from resume import resume_state
                    resume_state.mark_processed(shop.row_index)
                    cls.orchestrator._trigger_autosave()
                    stats = perf_tracker.get_stats()
                    cls.app.update_stats(shop.original_shop_name_address, len(resume_state.state["processed_rows"]), len(cls.orchestrator.shops), stats)
                    app_logger.info("Shop completed")
                    app_logger.info("Progress Updated")
                    app_logger.info(f"Progress {len(resume_state.state['processed_rows'])}/{len(cls.orchestrator.shops)}")
                except Exception as e:
                    import traceback
                    err_msg = traceback.format_exc()
                    app_logger.error("Exception in worker loop")
                    app_logger.error(f"Playwright error for shop {shop.original_shop_name_address}:\n{err_msg}")
                    shop.error_message = str(e)
                    from constants import STATUS_MANUAL_REVIEW
                    shop.verification_status = STATUS_MANUAL_REVIEW
                    shop.processed = True
                    from performance import perf_tracker
                    from cache_manager import cache
                    from resume import resume_state
                    perf_tracker.record_failed()
                    cache.set(shop)
                    resume_state.mark_processed(shop.row_index)
                    cls.orchestrator._trigger_autosave()
                    stats = perf_tracker.get_stats()
                    cls.app.update_stats(shop.original_shop_name_address, len(resume_state.state["processed_rows"]), len(cls.orchestrator.shops), stats)
                finally:
                    cls._queue.task_done()
                    if cls._queue.empty():
                        app_logger.info("Queue Empty")
        except Exception as e:
            app_logger.error(f"Fatal error in Playwright worker thread: {e}")
        finally:
            if context:
                try:
                    context.close()
                except Exception:
                    pass
            if browser:
                try:
                    browser.close()
                except Exception:
                    pass
            if playwright:
                try:
                    playwright.stop()
                except Exception:
                    pass
            app_logger.info("Browser Stopped")
