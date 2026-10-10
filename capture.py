from __future__ import annotations  # lets us write "str | None" on older Pythons

import ctypes          # talk to Windows directly (used for the display-scaling fix)
import queue           # a thread-safe "inbox" for hotkey presses
import sys             # read command-line arguments, check which OS we're on
import threading       # run the AI pipeline in the background
import time            # a tiny pause while our own window hides
import tkinter as tk   # Python's built-in GUI toolkit: draws the selection overlay
from datetime import datetime  # timestamps for unique file names
from pathlib import Path       # OS-safe file paths

import mss                                    # very fast screen grabbing
from PIL import Image, ImageEnhance, ImageTk  # Pillow: crop, dim and display images

PENDING_DIR = Path(__file__).resolve().parent / "Screenshots" / "_pending"
HOTKEY = "print screen"
MIN_SIZE = 5

def _make_dpi_aware() -> None:
    if sys.platform != "win32":       # only matters on Windows
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)   # Windows 8.1+ : per-monitor aware
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()    # older Windows fallback
        except (AttributeError, OSError):
            pass                                          # give up quietly

_make_dpi_aware()

def _main_monitor(sct: mss.base.MSSBase) -> dict:
    """Return the primary monitor's position and size."""
    for monitor in sct.monitors[1:]:
        if monitor["left"] == 0 and monitor["top"] == 0:
            return monitor
    return sct.monitors[1] #if nothing is called gets the first screen from the list

def _grab_main_monitor() -> tuple[Image.Image, dict]:
    """Take a full screenshot of the main monitor; return (image, monitor)."""
    with mss.mss() as sct:
        mon = _main_monitor(sct)
        shot = sct.grab(mon)

    image = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
    return image, mon # gets the actual photo and the position of the screenshot

def _save_pending(image: Image.Image) -> str:
    """Save an image into PENDING_DIR with a unique name; return its path."""
    PENDING_DIR.mkdir(parents=True, exist_ok=True)          # create folder if missing
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")     # %f = microseconds -> never clashes
    path = PENDING_DIR / f"screenshot_{stamp}.png"
    image.save(path, "PNG")
    return str(path)    # plain string = easiest for teammates to use


class _RegionSelector:

    def __init__(self, owner: tk.Misc, image: Image.Image, monitor: dict):
        self.image = image
        self.box = None     # the answer we're waiting for
        self.start = None   # (x, y) where the mouse was pressed
        self.rect = None    # id of the red rectangle drawn on the canvas

         # --- the window ---------------------------------------------------
        self.win = tk.Toplevel(owner)
        self.win.overrideredirect(True)          # no title bar or borders
        self.win.attributes("-topmost", True)    # stay above every other window
        # Size and place it exactly over the monitor: "WIDTHxHEIGHT+X+Y"
        self.win.geometry(
            f"{monitor['width']}x{monitor['height']}+{monitor['left']}+{monitor['top']}"
        )
        self.canvas = tk.Canvas(self.win, cursor="crosshair",
                                highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        dimmed = ImageEnhance.Brightness(image).enhance(0.6)
        self.photo = ImageTk.PhotoImage(dimmed, master=self.win)
        self.canvas.create_image(0, 0, image=self.photo, anchor="nw")

        self.canvas.create_text(
            monitor["width"] // 2, 30,
            text="Drag to capture   •   Esc or right-click to cancel",
            fill="white", font=("Segoe UI", 14, "bold"),
        )

        self.canvas.bind("<ButtonPress-1>", self._on_press)      # left button down
        self.canvas.bind("<B1-Motion>", self._on_drag)           # moving while held
        self.canvas.bind("<ButtonRelease-1>", self._on_release)  # left button up
        self.canvas.bind("<ButtonPress-3>", self._cancel)        # right-click = cancel
        self.win.bind("<Escape>", self._cancel)                  # Esc = cancel

        self.win.after(50, self._grab_focus)

    def _grab_focus(self) -> None:
        self.win.lift()
        self.win.focus_force()
        self.canvas.focus_set()

    def _on_press(self, event: tk.Event) -> None:
        self.start = (event.x, event.y)
        if self.rect: 
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y, outline="#ff3b3b", width=2
        )

    def _on_drag(self, event: tk.Event) -> None:
        if self.rect:
            x0, y0 = self.start
            self.canvas.coords(self.rect, x0, y0, event.x, event.y)
    
    def _on_release(self, event: tk.Event) -> None:
        if not self.start:
            return
        x0, y0 = self.start
        x1, y1 = event.x, event.y

        # sorted() makes it work whichever direction you dragged.
        left, right = sorted((x0, x1))
        top, bottom = sorted((y0, y1))

        # Keep the box inside the image.
        left, top = max(0, left), max(0, top)
        right = min(self.image.width, right)
        bottom = min(self.image.height, bottom)

         # Tiny box = probably a click, not a drag. Reset and let them retry.
        if right - left < MIN_SIZE or bottom - top < MIN_SIZE:
            self.canvas.delete(self.rect)
            self.rect, self.start = None, None
            return

        self.box = (left, top, right, bottom)
        self.win.destroy()      # closing the window ends the wait

    def _cancel(self, event: tk.Event | None = None) -> None:
        self.box = None
        self.win.destroy()

def capture_screenshot(parent: tk.Misc | None = None) -> str | None:
    """Drag-to-select screenshot.

    parent: pass Person D's tkinter root window if the app is open. It gets
            hidden during the capture so it doesn't appear in the screenshot.
            Leave as None when running on its own.

    Returns the saved PNG path, or None if the user cancelled.
    """
    temp_root = None
    hid_parent = False


    if parent is None:
        # No app window exists, so make a hidden one just for this capture.
        temp_root = tk.Tk()
        temp_root.withdraw()
        owner = temp_root
    else:
        owner = parent
        if parent.winfo_viewable():      # only hide it if it's currently showing
            parent.withdraw()
            parent.update()
            time.sleep(0.3)              # Windows' hide animation takes a moment
            hid_parent = True

    try:
        image, monitor = _grab_main_monitor()            # 1. freeze the screen
        selector = _RegionSelector(owner, image, monitor)  # 2. show the overlay
        owner.wait_window(selector.win)                  # 3. wait until it closes
    finally:
        # 'finally' runs even if something crashed, so we always tidy up.
        if temp_root is not None:
            temp_root.destroy()
        elif hid_parent:
            parent.deiconify()           # bring the app window back

    if selector.box is None:
        return None                      # user cancelled
    return _save_pending(image.crop(selector.box))   # 4. crop + save

def capture_fullscreen() -> str:
    """Fallback: save the whole main monitor with no selection step."""
    image, _ = _grab_main_monitor()
    return _save_pending(image)

def start_hotkey_listener(on_request, hotkey: str = HOTKEY) -> None:
    
    try:
        import keyboard   # imported here so 'full' and 'snip' work without it
    except ImportError:
        raise SystemExit("Missing library. Run:  pip install keyboard")
    keyboard.add_hotkey(hotkey, on_request, suppress=True)

def run_capture_service(on_captured=None, hotkey: str = HOTKEY) -> None:
    """The 'invisible' mode. Runs forever (Ctrl+C to stop).

    Every hotkey press -> drag-to-select capture -> on_captured(path) is
    started in a background thread, so a slow AI call never blocks the
    next screenshot.
    """
    requests = queue.Queue()
    start_hotkey_listener(lambda: requests.put("snip"), hotkey)
    print(f"Listening... press {hotkey!r} to take a screenshot. Ctrl+C to stop.")

    try:
        while True:
            try:
                # timeout lets Ctrl+C work on Windows (a plain get() would block it)
                requests.get(timeout=0.5)
            except queue.Empty:
                continue

            path = capture_screenshot()     # tkinter must run on THIS (main) thread

            # Throw away extra presses made while the overlay was open,
            # so we don't pop up a second overlay straight away.
            while not requests.empty():
                requests.get_nowait()

            if path is None:
                print("Cancelled.")
                continue
            print("Saved:", path)
            if on_captured:
                threading.Thread(target=on_captured, args=(path,), daemon=True).start()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "snip"

    if mode == "full":
        print("Saved:", capture_fullscreen())

    elif mode == "snip":
        result = capture_screenshot()
        if result:
            print("Saved:", result)
        else:
            print("Cancelled.")

    elif mode == "listen":
        # Stand-in for the real pipeline until Person A and C's code is ready.
        run_capture_service(on_captured=lambda p: print("  -> pipeline would process:", p))

    else:
        print("Usage: python capture.py [full|snip|listen]")

