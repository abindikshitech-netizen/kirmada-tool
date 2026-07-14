import os
import sys
import requests
import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import psutil
import time
from typing import List
from settings import app_settings
from logger import app_logger
from config import set_google_api_key_env
import queue
from models.shop import Shop

class VerifierApp(ctk.CTk):
    def __init__(self, orchestrator_callback=None, pause_callback=None, resume_callback=None, stop_callback=None, finalize_callback=None):
        super().__init__()
        
        self.orchestrator_callback = orchestrator_callback
        self.pause_callback = pause_callback
        self.resume_callback = resume_callback
        self.stop_callback = stop_callback
        self.finalize_callback = finalize_callback
        
        self.title("Jewellery Address Verifier Pro")
        self.geometry("1100x800")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.is_running = False
        self.is_paused = False
        self.manual_review_shops: List[Shop] = []
        self.current_review_index = 0
        
        self.result_queue = queue.Queue()
        
        self._build_ui()
        self._load_settings()
        self._start_system_monitor()
        self.after(500, self._test_connection)
        self.after(100, self._process_result_queue)
        
    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        header = ctk.CTkLabel(self, text="Jewellery Address Verifier Pro", font=ctk.CTkFont(size=24, weight="bold"))
        header.grid(row=0, column=0, padx=20, pady=20, sticky="w")
        
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=1, column=0, padx=20, pady=0, sticky="nsew")
        self.tabview.add("Dashboard")
        self.tabview.add("Settings")
        self.tabview.add("Manual Review")
        self.tabview.add("Live Console")
        
        self._build_dashboard_tab()
        self._build_settings_tab()
        self._build_manual_review_tab()
        self._build_console_tab()
        
    def _build_dashboard_tab(self):
        tab = self.tabview.tab("Dashboard")
        tab.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(tab, text="Input Excel:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.input_entry = ctk.CTkEntry(tab)
        self.input_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        ctk.CTkButton(tab, text="Browse", command=self._browse_input).grid(row=0, column=2, padx=10, pady=10)
        
        ctk.CTkLabel(tab, text="Output Folder:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.output_entry = ctk.CTkEntry(tab)
        self.output_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
        ctk.CTkButton(tab, text="Browse", command=self._browse_output).grid(row=1, column=2, padx=10, pady=10)
        
        ctk.CTkLabel(tab, text="Google API Key:").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.api_key_entry = ctk.CTkEntry(tab, show="*")
        self.api_key_entry.grid(row=2, column=1, padx=10, pady=10, sticky="ew")
        self.remember_var = ctk.BooleanVar()
        ctk.CTkCheckBox(tab, text="Remember", variable=self.remember_var).grid(row=2, column=2, padx=10, pady=10)
        
        controls = ctk.CTkFrame(tab)
        controls.grid(row=3, column=0, columnspan=3, padx=10, pady=20, sticky="ew")
        
        self.test_conn_btn = ctk.CTkButton(controls, text="Test Connection", command=self._test_connection, fg_color="blue")
        self.test_conn_btn.pack(side="left", padx=10, pady=10)
        
        self.start_btn = ctk.CTkButton(controls, text="Start", command=lambda: self._start(retry_failed=False))
        self.start_btn.pack(side="left", padx=10, pady=10)
        
        self.retry_failed_btn = ctk.CTkButton(controls, text="Retry Failed", command=lambda: self._start(retry_failed=True), fg_color="orange")
        self.retry_failed_btn.pack(side="left", padx=10, pady=10)
        
        self.mode_status_lbl = ctk.CTkLabel(controls, text="Status: Detecting...", font=ctk.CTkFont(weight="bold"))
        self.mode_status_lbl.pack(side="left", padx=15, pady=10)
        
        self.pause_btn = ctk.CTkButton(controls, text="Pause", command=self._pause, state="disabled")
        self.pause_btn.pack(side="left", padx=10, pady=10)
        
        self.resume_btn = ctk.CTkButton(controls, text="Resume", command=self._resume, state="disabled")
        self.resume_btn.pack(side="left", padx=10, pady=10)
        
        self.stop_btn = ctk.CTkButton(controls, text="Stop", command=self._stop, state="disabled", fg_color="red")
        self.stop_btn.pack(side="left", padx=10, pady=10)
        
        progress_frame = ctk.CTkFrame(tab)
        progress_frame.grid(row=4, column=0, columnspan=3, padx=10, pady=10, sticky="ew")
        progress_frame.grid_columnconfigure((0,1,2,3), weight=1)
        
        self.progress_bar = ctk.CTkProgressBar(progress_frame)
        self.progress_bar.grid(row=0, column=0, columnspan=4, padx=10, pady=10, sticky="ew")
        self.progress_bar.set(0)
        
        self.status_label = ctk.CTkLabel(progress_frame, text="Ready")
        self.status_label.grid(row=1, column=0, columnspan=4, padx=10, pady=5, sticky="w")
        
        self.stat_remaining = ctk.CTkLabel(progress_frame, text="Remaining: 0")
        self.stat_remaining.grid(row=2, column=0, padx=10, sticky="w")
        
        self.stat_eta = ctk.CTkLabel(progress_frame, text="ETA: 0s")
        self.stat_eta.grid(row=2, column=1, padx=10, sticky="w")
        
        self.stat_speed = ctk.CTkLabel(progress_frame, text="Speed: 0/s")
        self.stat_speed.grid(row=2, column=2, padx=10, sticky="w")
        
        self.stat_success = ctk.CTkLabel(progress_frame, text="Success: 0")
        self.stat_success.grid(row=2, column=3, padx=10, sticky="w")
        
        sys_frame = ctk.CTkFrame(tab)
        sys_frame.grid(row=5, column=0, columnspan=3, padx=10, pady=10, sticky="ew")
        self.stat_cpu = ctk.CTkLabel(sys_frame, text="CPU: 0%")
        self.stat_cpu.pack(side="left", padx=20, pady=10)
        self.stat_mem = ctk.CTkLabel(sys_frame, text="RAM: 0MB")
        self.stat_mem.pack(side="left", padx=20, pady=10)
        
    def _build_manual_review_tab(self):
        tab = self.tabview.tab("Manual Review")
        tab.grid_columnconfigure(1, weight=1)
        
        self.rev_status = ctk.CTkLabel(tab, text="No shops pending review.", font=ctk.CTkFont(weight="bold"))
        self.rev_status.grid(row=0, column=0, columnspan=2, pady=10)
        
        fields = ["Shop Name:", "Original Address:", "Suggested Address:", "Phone:", "Website:", "Confidence:"]
        self.rev_entries = {}
        for i, f in enumerate(fields):
            ctk.CTkLabel(tab, text=f).grid(row=i+1, column=0, padx=10, pady=5, sticky="w")
            entry = ctk.CTkEntry(tab, width=400)
            entry.grid(row=i+1, column=1, padx=10, pady=5, sticky="ew")
            self.rev_entries[f] = entry
            
        ctrl = ctk.CTkFrame(tab)
        ctrl.grid(row=len(fields)+1, column=0, columnspan=2, pady=20)
        
        ctk.CTkButton(ctrl, text="< Prev", command=self._rev_prev).pack(side="left", padx=5)
        ctk.CTkButton(ctrl, text="Accept (Verify)", command=self._rev_accept, fg_color="green").pack(side="left", padx=5)
        ctk.CTkButton(ctrl, text="Save Edits", command=self._rev_save).pack(side="left", padx=5)
        ctk.CTkButton(ctrl, text="Reject", command=self._rev_reject, fg_color="red").pack(side="left", padx=5)
        ctk.CTkButton(ctrl, text="Next >", command=self._rev_next).pack(side="left", padx=5)
        
        ctk.CTkButton(tab, text="Finalize & Export", command=self._finalize_export, fg_color="purple").grid(row=len(fields)+2, column=0, columnspan=2, pady=20)

    def _build_settings_tab(self):
        tab = self.tabview.tab("Settings")
        ctk.CTkLabel(tab, text="Concurrency:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.concurrency_slider = ctk.CTkSlider(tab, from_=1, to=20, number_of_steps=19)
        self.concurrency_slider.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        ctk.CTkButton(tab, text="Save Settings", command=self._save_settings).grid(row=3, column=0, columnspan=2, pady=20)
        
    def _build_console_tab(self):
        tab = self.tabview.tab("Live Console")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        self.console = ctk.CTkTextbox(tab, state="disabled")
        self.console.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
    def load_manual_review(self, shops: List[Shop]):
        self.manual_review_shops = [s for s in shops if s.verification_status == "Manual Review"]
        self.current_review_index = 0
        self._update_review_ui()
        
    def _update_review_ui(self):
        if not self.manual_review_shops:
            self.rev_status.configure(text="No shops pending review.")
            for e in self.rev_entries.values():
                e.delete(0, "end")
            return
            
        shop = self.manual_review_shops[self.current_review_index]
        self.rev_status.configure(text=f"Reviewing {self.current_review_index+1} of {len(self.manual_review_shops)}")
        
        self.rev_entries["Shop Name:"].delete(0, "end")
        self.rev_entries["Shop Name:"].insert(0, shop.original_shop_name_address)
        self.rev_entries["Original Address:"].delete(0, "end")
        self.rev_entries["Original Address:"].insert(0, shop.old_address)
        self.rev_entries["Suggested Address:"].delete(0, "end")
        self.rev_entries["Suggested Address:"].insert(0, shop.latest_address)
        self.rev_entries["Phone:"].delete(0, "end")
        self.rev_entries["Phone:"].insert(0, shop.phone_number)
        self.rev_entries["Website:"].delete(0, "end")
        self.rev_entries["Website:"].insert(0, shop.website)
        self.rev_entries["Confidence:"].delete(0, "end")
        self.rev_entries["Confidence:"].insert(0, str(shop.confidence_score))
        
    def _rev_prev(self):
        if self.current_review_index > 0:
            self.current_review_index -= 1
            self._update_review_ui()
            
    def _rev_next(self):
        if self.current_review_index < len(self.manual_review_shops) - 1:
            self.current_review_index += 1
            self._update_review_ui()
            
    def _rev_save(self):
        if not self.manual_review_shops: return
        shop = self.manual_review_shops[self.current_review_index]
        shop.latest_address = self.rev_entries["Suggested Address:"].get()
        shop.phone_number = self.rev_entries["Phone:"].get()
        shop.website = self.rev_entries["Website:"].get()
        
    def _rev_accept(self):
        if not self.manual_review_shops: return
        self._rev_save()
        shop = self.manual_review_shops[self.current_review_index]
        shop.verification_status = "Verified"
        self._rev_next()
        
    def _rev_reject(self):
        if not self.manual_review_shops: return
        shop = self.manual_review_shops[self.current_review_index]
        shop.verification_status = "Failed"
        shop.error_message = "Rejected in manual review"
        self._rev_next()
        
    def _finalize_export(self):
        if self.finalize_callback: self.finalize_callback()

    def _start_system_monitor(self):
        def monitor():
            while True:
                cpu = psutil.cpu_percent()
                mem = psutil.Process().memory_info().rss / (1024 * 1024)
                try:
                    self.stat_cpu.configure(text=f"CPU: {cpu}%")
                    self.stat_mem.configure(text=f"RAM: {mem:.1f}MB")
                except:
                    break
                time.sleep(2)
        threading.Thread(target=monitor, daemon=True).start()
        
    def _process_result_queue(self):
        try:
            while True:
                item = self.result_queue.get_nowait()
                if item["type"] == "stats":
                    self._update_stats_ui(**item["data"])
                elif item["type"] == "log":
                    self._log_to_console_ui(item["data"])
                self.result_queue.task_done()
        except queue.Empty:
            pass
        finally:
            if self.winfo_exists():
                self.after(100, self._process_result_queue)
                
    def log_to_console(self, msg: str):
        self.result_queue.put({"type": "log", "data": msg})

    def _log_to_console_ui(self, msg: str):
        self.console.configure(state="normal")
        self.console.insert("end", msg + "\n")
        self.console.see("end")
        self.console.configure(state="disabled")
        
    def update_stats(self, current_shop, processed, total, stats: dict):
        self.result_queue.put({"type": "stats", "data": {
            "current_shop": current_shop,
            "processed": processed,
            "total": total,
            "stats": stats
        }})

    def _update_stats_ui(self, current_shop, processed, total, stats: dict):
        if total > 0: self.progress_bar.set(processed / total)
        self.status_label.configure(text=f"Current: {current_shop}")
        remaining = stats.get("total_shops", total) - stats.get("processed_shops", processed)
        self.stat_remaining.configure(text=f"Remaining: {remaining}")
        self.stat_eta.configure(text=f"ETA: {stats.get('eta_seconds', 0):.0f}s")
        self.stat_speed.configure(text=f"Speed: {stats.get('speed_shops_per_sec', 0):.1f}/s")
        self.stat_success.configure(text=f"Success: {stats.get('success_count', 0)}")

    def _browse_input(self):
        file = filedialog.askopenfilename(filetypes=[("Excel Files", "*.xlsx *.xls")])
        if file:
            self.input_entry.delete(0, "end")
            self.input_entry.insert(0, file)

    def _browse_output(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_entry.delete(0, "end")
            self.output_entry.insert(0, folder)
            
    def _load_settings(self):
        self.input_entry.insert(0, app_settings.get("last_input_dir", ""))
        self.output_entry.insert(0, app_settings.get("last_output_dir", ""))
        from config import APIKeyManager
        api_key = APIKeyManager.get_key()
        if api_key: self.api_key_entry.insert(0, api_key)
        self.remember_var.set(app_settings.get("remember_api_key", False))
        self.concurrency_slider.set(app_settings.get("concurrency", 5))
        
    def _save_settings(self):
        app_settings.set("concurrency", int(self.concurrency_slider.get()))
        messagebox.showinfo("Success", "Settings saved!")
        
    def _test_connection(self):
        api_key = self.api_key_entry.get().strip()
        in_path = self.input_entry.get().strip()
        out_path = self.output_entry.get().strip()
        
        from config import APIKeyManager
        APIKeyManager.set_key(api_key)
        
        self.mode_status_lbl.configure(text="Status: Testing...", text_color="gray")
        self.test_conn_btn.configure(state="disabled")
        
        def run_detect():
            import requests
            import os
            from playwright.sync_api import sync_playwright
            from config import get_google_api_key, detect_connection_mode
            
            diagnostic = []
            all_passed = True
            
            # 1. Internet Check
            try:
                requests.get("https://www.google.com", timeout=5)
                diagnostic.append("✅ Internet Connection: OK")
            except Exception as e:
                diagnostic.append(f"❌ Internet Connection: FAILED ({e})")
                all_passed = False
                
            # 2. Input Excel Check
            if in_path:
                if os.path.exists(in_path) and in_path.endswith((".xlsx", ".xls")):
                    diagnostic.append("✅ Input Excel: OK")
                else:
                    diagnostic.append("❌ Input Excel: FAILED (File not found or invalid format)")
                    all_passed = False
            else:
                diagnostic.append("⚠️ Input Excel: NOT PROVIDED (Required for processing)")
                
            # 3. Output Folder Check
            if out_path:
                if os.path.exists(out_path) and os.path.isdir(out_path):
                    if os.access(out_path, os.W_OK):
                        diagnostic.append("✅ Output Folder: OK (Write permissions verified)")
                    else:
                        diagnostic.append("❌ Output Folder: FAILED (No write permissions)")
                        all_passed = False
                else:
                    diagnostic.append("❌ Output Folder: FAILED (Directory not found)")
                    all_passed = False
            else:
                diagnostic.append("⚠️ Output Folder: NOT PROVIDED (Required for processing)")
                
            # 4. Playwright Check
            try:
                with sync_playwright() as p:
                    b = p.chromium.launch(headless=True)
                    if b.is_connected():
                        diagnostic.append("✅ Playwright: OK (Chromium launched successfully)")
                        b.close()
                    else:
                        diagnostic.append("❌ Playwright: FAILED (Chromium failed to connect)")
                        all_passed = False
            except Exception as e:
                diagnostic.append(f"❌ Playwright: FAILED ({e})")
                all_passed = False
                
            # 5. Google API Check
            mode = detect_connection_mode(api_key)
            if mode == "Google API":
                diagnostic.append("✅ Google API: OK (Key is valid and billing is active)")
                text = "Status: Google API Mode"
                color = "green"
            elif mode == "Playwright (Google Billing Disabled)":
                diagnostic.append("⚠️ Google API: DISABLED or INVALID (Falling back to Playwright Mode)")
                text = "Status: Playwright Mode"
                color = "orange"
            else:
                diagnostic.append("❌ Connection Mode: OFFLINE")
                text = "Status: Offline"
                color = "red"
                
            diagnostic_msg = "\n".join(diagnostic)
            
            def update_ui():
                self.mode_status_lbl.configure(text=text, text_color=color)
                self.test_conn_btn.configure(state="normal")
                self.start_btn.configure(state="normal")
                self.retry_failed_btn.configure(state="normal")
                
                # Show popup
                if all_passed:
                    messagebox.showinfo("Diagnostic Report (Passed)", diagnostic_msg)
                else:
                    messagebox.showwarning("Diagnostic Report (Issues Found)", diagnostic_msg)
                    
            self.after(0, update_ui)
            
        threading.Thread(target=run_detect, daemon=True).start()

    def _start(self, retry_failed=False):
        in_path = self.input_entry.get()
        out_path = self.output_entry.get()
        api_key = self.api_key_entry.get().strip()
        remember = self.remember_var.get()
        
        if not in_path or not out_path:
            messagebox.showerror("Error", "Please fill all required fields in the Dashboard.")
            return
            
        app_settings.set("last_input_dir", in_path)
        app_settings.set("last_output_dir", out_path)
        app_settings.set("remember_api_key", remember)
        
        from config import APIKeyManager
        APIKeyManager.set_key(api_key)
        if remember:
            APIKeyManager.save_to_env(api_key)
        else:
            APIKeyManager.save_to_env("")
        
        self.test_conn_btn.configure(state="disabled")
        self.start_btn.configure(state="disabled")
        self.retry_failed_btn.configure(state="disabled")
        self.pause_btn.configure(state="normal")
        self.stop_btn.configure(state="normal")
        self.is_running = True
        self.is_paused = False
        
        if self.orchestrator_callback:
            threading.Thread(target=self.orchestrator_callback, args=(in_path, out_path, self, retry_failed), daemon=True).start()
            
    def _pause(self):
        self.is_paused = True
        self.pause_btn.configure(state="disabled")
        self.resume_btn.configure(state="normal")
        if self.pause_callback: self.pause_callback()
            
    def _resume(self):
        self.is_paused = False
        self.resume_btn.configure(state="disabled")
        self.pause_btn.configure(state="normal")
        if self.resume_callback: self.resume_callback()
            
    def _stop(self):
        self.is_running = False
        self.test_conn_btn.configure(state="normal")
        self.start_btn.configure(state="normal")
        self.retry_failed_btn.configure(state="normal")
        self.pause_btn.configure(state="disabled")
        self.resume_btn.configure(state="disabled")
        self.stop_btn.configure(state="disabled")
        if self.stop_callback: self.stop_callback()

    def processing_finished(self):
        self._stop()
        messagebox.showinfo("Complete", "Processing finished! Check Manual Review tab if needed.")
