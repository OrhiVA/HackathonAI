"""
main.py - the ONE entry point.   Run:  python main.py

Flow (matches example.py):
    button / Print Screen  ->  capture.capture_screenshot()      [main thread: needs Tk]
                           ->  analyse_screenshot(path)          [worker thread: slow API call]
                           ->  save_screenshot(path, metadata)   [worker thread: folder + SQLite]
                           ->  result sent back through a queue  [main thread updates the UI]

Rules this file follows:
  - Tk widgets are only touched on the main thread. Worker threads only put results on a queue.
  - The original screenshot stays in Screenshots/_pending if anything fails.
  - analyse_screenshot() never raises (it returns a fallback record), so an AI failure
    still files the screenshot under "Other" and the status line says so.
"""

import capture  # FIRST: switches on Windows DPI awareness before any window exists

import os
import queue
import threading
import tkinter as tk
from tkinter import messagebox

import ai_analyses
from ai_analyses import analyse_screenshot
from image_browser import ImageBrowser
from storage import init_db, save_screenshot

COLOURS = {"info": "#444444", "busy": "#1a56c4", "ok": "#15803d", "warn": "#b45309", "error": "#b91c1c"}


class App:
    def __init__(self, root):
        self.root = root
        self.jobs = queue.Queue()   # hotkey presses (put from the keyboard thread)
        self.done = queue.Queue()   # finished results (put from worker threads)
        self.capturing = False      # True while the selection overlay is open
        self.in_flight = 0          # screenshots currently being analysed/saved (main thread only)

        root.title("Screenshot Organiser")
        root.geometry("700x700")

        top = tk.Frame(root)
        top.pack(fill="x", padx=10, pady=(10, 0))
        self.button = tk.Button(top, text="Take screenshot", command=self.take_screenshot)
        self.button.pack(side="left")
        self.status = tk.Label(top, text="Ready", anchor="w", justify="left", wraplength=520)
        self.status.pack(side="left", padx=10, fill="x", expand=True)

        self.browser = ImageBrowser(root)
        self.browser.pack(fill="both", expand=True)

        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.start_hotkey()
        self.show_startup_warnings()
        self.poll()

    # ------------------------------------------------------------------ status
    def set_status(self, text, kind="info"):
        self.status.config(text=text, fg=COLOURS[kind])

    def show_startup_warnings(self):
        if os.environ.get("AI_MOCK", "").strip().lower() in ("1", "true", "yes"):
            self.set_status("WARNING: AI_MOCK is on - metadata is FAKE, Gemini is not being called. "
                            + self.hotkey_note, "warn")
        elif not ai_analyses.GEMINI_API_KEY:
            self.set_status("WARNING: GEMINI_API_KEY is not set - screenshots will be saved under "
                            "'Other' with no AI title/tags. " + self.hotkey_note, "warn")
        else:
            self.set_status(self.hotkey_note or "Ready")

    # ----------------------------------------------------------------- hotkey
    def start_hotkey(self):
        self.hotkey_note = ""
        try:
            capture.start_hotkey_listener(lambda: self.jobs.put("snip"))  # runs on keyboard's thread
            self.hotkey_note = f"Ready - press {capture.HOTKEY.title()} or click the button."
        except (Exception, SystemExit) as exc:   # missing 'keyboard' library, no permission, ...
            self.hotkey_note = f"Hotkey unavailable ({str(exc) or type(exc).__name__}). Use the button."

    def drain_jobs(self):
        while True:
            try:
                self.jobs.get_nowait()
            except queue.Empty:
                return

    # ---------------------------------------------------------------- capture
    def take_screenshot(self):                  # main thread only (Tk overlay)
        if self.capturing:
            return                              # ignore repeat presses while the overlay is open
        self.capturing = True
        try:
            path = capture.capture_screenshot(parent=self.root)
        except Exception as exc:
            self.set_status(f"Capture failed: {exc}", "error")
            return
        finally:
            self.capturing = False
            self.drain_jobs()                   # presses made during the overlay are dropped

        if path is None:
            self.set_status("Capture cancelled.", "info")
            return

        self.in_flight += 1
        self.set_status(f"Analysing screenshot with AI... ({self.in_flight} in progress)", "busy")
        threading.Thread(target=self.process, args=(path,), daemon=True).start()

    # ------------------------------------------------------- background worker
    def process(self, path):                    # worker thread: NO Tk calls in here
        try:
            metadata = analyse_screenshot(path)         # never raises; may return a fallback record
            record = save_screenshot(path, metadata)    # raises if filing fails; original stays put
            self.done.put(("ok", record))
        except Exception as exc:
            self.done.put(("error", path, f"{type(exc).__name__}: {exc}"))

    # --------------------------------------------------------- results -> UI
    def poll(self):                             # runs on the main thread every 100 ms
        try:
            if not self.jobs.empty() and not self.capturing:
                self.drain_jobs()
                self.take_screenshot()
            elif self.capturing:
                self.drain_jobs()
            while True:
                try:
                    item = self.done.get_nowait()
                except queue.Empty:
                    break
                self.handle_result(item)
        finally:
            self.root.after(100, self.poll)     # keep polling even if something above raised

    def handle_result(self, item):
        self.in_flight = max(0, self.in_flight - 1)
        more = f"  ({self.in_flight} still processing)" if self.in_flight else ""

        if item[0] == "ok":
            rec = item[1]
            self.browser.refresh()              # reads saved metadata only; no AI call
            if rec["ai_failed"]:
                self.set_status(f"Saved to '{rec['category']}' but AI analysis failed "
                                f"({rec['error']}). Screenshot kept.{more}", "warn")
            else:
                self.set_status(f"Saved to '{rec['category']}': {rec['title']}{more}", "ok")
        else:
            _, path, error = item
            self.set_status(f"Could not file screenshot: {error}. Original kept at {path}{more}", "error")

    # ------------------------------------------------------------------ close
    def on_close(self):
        if self.in_flight and not messagebox.askokcancel(
            "Still processing",
            f"{self.in_flight} screenshot(s) are still being analysed.\n"
            "If you quit now they stay in Screenshots/_pending and are not sorted.\n\nQuit anyway?",
        ):
            return
        try:
            import keyboard
            keyboard.unhook_all()
        except Exception:
            pass
        self.root.destroy()


def main():
    init_db()
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
