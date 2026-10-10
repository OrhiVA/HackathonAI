import capture                    # FIRST, before any window exists
import queue, threading
import tkinter as tk
from ai_analysis import analyse_screenshot   # Person A
from storage import save_screenshot          # Person C

root = tk.Tk()
jobs = queue.Queue()    # letterbox for hotkey presses
done = queue.Queue()    # letterbox for finished results

def take_screenshot():                       # main chef only
    path = capture.capture_screenshot(parent=root)
    if path is None:
        return                               # user cancelled
    status.config(text="Thinking...")
    threading.Thread(target=process, args=(path,), daemon=True).start()

def process(path):                           # helper thread: slow AI work, no windows!
    try:
        metadata = analyse_screenshot(path)
        record = save_screenshot(path, metadata)
        done.put(("ok", record))
    except Exception as e:
        done.put(("error", str(e)))          # picture is still safe in _pending

def check_letterboxes():                     # main chef glances every 0.1 s
    if not jobs.empty():
        while not jobs.empty():
            jobs.get()                       # ignore extra presses
        take_screenshot()
    while not done.empty():
        kind, info = done.get()
        status.config(text="Saved!" if kind == "ok" else f"Failed: {info}")
        # refresh_gallery()  <- Person D's own function
    root.after(100, check_letterboxes)

tk.Button(root, text="Take screenshot", command=take_screenshot).pack()
status = tk.Label(root, text="Ready")
status.pack()

capture.start_hotkey_listener(lambda: jobs.put("snip"))   # Print Screen → letterbox
check_letterboxes()
root.mainloop()