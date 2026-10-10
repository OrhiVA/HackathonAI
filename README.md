# Screenshot Sorter

**Screenshots that file themselves.** Take a screenshot, and an AI gives it a title, a category and tags, then saves it into the right folder. Later you can find it by category or tag instead of scrolling through a pile of `Screenshot_2026….png` files.

Built for the **Invisible AI** hackathon. The AI is not a chatbot or a prompt box. It is the sorting step you would never do by hand, and it happens in the background.

## How it works

```
Print Screen / button  →  drag to select  →  saved to Screenshots/_pending/
        →  Gemini reads the image  →  title, category, tags
        →  copied to Screenshots/<Category>/  →  recorded in SQLite
        →  gallery refreshes  →  search by category and tags (no AI call)
```

| Part | File | What it does |
|---|---|---|
| Entry point and UI | `main.py` | Window, status line, hotkey, background worker thread |
| Capture | `capture.py` | Drag-to-select overlay, saves a PNG (uses `mss`, Pillow, Tkinter) |
| AI analysis | `ai_analyses.py` | Sends the image to Gemini and returns a validated title, category, tags and description |
| Categories | `categories.py` | The one list of categories, shared by the AI and storage |
| Storage | `storage.py` | Creates or reuses the category folder, copies the file without overwriting, writes the metadata to SQLite |
| Gallery and search | `image_browser.py` | Category dropdown and tag filters, reading only saved data |
| Database schema | `image_repository.sql` | Tables: `categories`, `tags`, `images`, `image_tags` (see `databaseStructure.md`) |

## Requirements

- Python 3.10 or newer (tested on 3.12)
- A Google Gemini API key (free tier works): create one at <https://aistudio.google.com>
- Windows is the main target. The app also runs elsewhere, but the Print Screen hotkey may need extra permissions (see Troubleshooting).

## Setup

```bash
pip install -r requirements.txt
```

Give the app your API key in one of two ways. **Never commit the key.**

1. Create a file named `.env` next to `main.py` containing one line (`.env` is already in `.gitignore`):
   ```
   GEMINI_API_KEY=your-key-here
   ```
2. Or set an environment variable. On Windows PowerShell: `$env:GEMINI_API_KEY="your-key-here"`

| Variable | Required | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | Yes | Your Gemini API key |
| `GEMINI_MODEL` | No | Overrides the model name (default is set in `ai_analyses.py`). Use this if you get a "model not found" error. |
| `AI_MOCK` | No | Set to `1` to use fake metadata with no API call. For testing only; the app shows a warning banner when it is on. |

## Run

```bash
python main.py
```

## Using it

1. Click **Take screenshot** or press **Print Screen**.
2. Drag over the area you want. Press **Esc** or right-click to cancel.
3. The status line shows *Analysing…*, then *Saved to 'Code': <title>*.
4. The screenshot appears in the list, and the file is in `Screenshots/<Category>/`.
5. Filter by **Category** and/or select **tags** (Ctrl+click for several; a screenshot must have all selected tags), then click **Search**.

You can take another screenshot while earlier ones are still being analysed.

## What happens when something goes wrong

- **No API key, no internet, or the AI fails:** the screenshot is still saved, under the category **Other**, and the status line says the AI analysis failed.
- **Filing fails** (for example a disk or database error): the original stays in `Screenshots/_pending/` and the status line shows where.
- **Name clashes:** a file is never overwritten; a numeric suffix is added instead.
- **Closing the window while screenshots are processing:** the app asks first. Anything unfinished stays in `Screenshots/_pending/`.

## Files the app creates

- `Screenshots/<Category>/…png`: your sorted screenshots
- `Screenshots/_pending/`: screenshots waiting to be sorted, or kept after a failure
- `screenshot_library.db`: the SQLite database (created on first run from `image_repository.sql`)

`image_repository.db` is the original sample database (made-up categories and images). The app does not use it.

To start a demo with an empty library, close the app and run `python clear_db.py` (it asks before deleting). It empties the database only; delete the files in `Screenshots/` yourself if you want those gone too.

## Privacy

Each screenshot is sent to the Google Gemini API for analysis (downscaled so its longest side is at most 1600 px). Do not capture anything you would not want sent there. A local, on-device model is on the roadmap (below).

## Tests

```bash
python -m unittest tests.test_storage -v
```

These cover storage (filing, no overwrite, rollback on failure, concurrent saves). They need no display or API key. `tests/test_gui_xvfb.py` is a Linux-only headless test of the whole app (it needs `xvfb` and `xdotool`), and it is not needed on Windows.

## Known limitations

- Search is by category and exact tags only. It does not match meaning, so "tree" will not find a screenshot tagged only "BST".
- Categories are a fixed list in `categories.py`, plus **Other** as the fallback.
- Gemini's one-sentence description is generated but not stored, because the database has no column for it.
- The gallery is a list of titles and file paths, with no thumbnails.
- Needs an internet connection to analyse screenshots.
- While the app is running, it captures the Print Screen key, so other tools will not receive it.

## Roadmap

- Meaning-based search
- The AI proposes categories from your own screenshots, so no presets are needed
- An optional on-device model for privacy and offline use (the AI sits behind one function, `analyse_screenshot()`, so swapping the model touches one file)
- Beyond screenshots: photos, scans and PDFs, screen recordings and phone galleries, using a folder watcher in place of the capture overlay

## Troubleshooting

- **"Hotkey unavailable":** the `keyboard` library could not start. On Linux it needs root; on macOS it may not work at all. The **Take screenshot** button still works.
- **"model not found" or the AI always fails:** check `GEMINI_API_KEY`, and set `GEMINI_MODEL` to a current model name from AI Studio. The exact reason appears in the status line.
- **Screenshot looks the wrong size or in the wrong place on a high-DPI screen:** make sure you start the app with `python main.py` (it enables Windows DPI awareness on startup).

## Credits and disclosure

Built during the hackathon with Python, Tkinter, [mss](https://pypi.org/project/mss/), [Pillow](https://pypi.org/project/pillow/), [keyboard](https://pypi.org/project/keyboard/), SQLite, [python-dotenv](https://pypi.org/project/python-dotenv/) and the [Google Gemini API](https://ai.google.dev/) via the `google-genai` library.
