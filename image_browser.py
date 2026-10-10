import sqlite3
import tkinter as tk
from tkinter import ttk

import storage

# Same database the rest of the app writes to (see storage.py)
DB_PATH = str(storage.DB_PATH)


def query(sql, params=()):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


class ImageBrowser(ttk.Frame):
    """The search/gallery panel. Put it in any window: ImageBrowser(root).pack(...).

    Call refresh() after new screenshots are saved. It only reads the database;
    it never calls the AI.
    """

    def __init__(self, parent):
        super().__init__(parent)
        storage.init_db()   # make sure the tables exist before the first query

        self.category_ids = {"All categories": None}
        self.tag_ids = []   # same order as the listbox rows
        self.result_paths = []

        # ---- category dropdown (single select) ----
        ttk.Label(self, text="Category:").pack(anchor="w", padx=10, pady=(10, 0))
        self.category_box = ttk.Combobox(self, values=list(self.category_ids), state="readonly")
        self.category_box.set("All categories")
        self.category_box.pack(fill="x", padx=10)

        # ---- tags list (multi select) ----
        ttk.Label(self, text="Tags (Ctrl+click to select several):").pack(anchor="w", padx=10, pady=(10, 0))
        tag_frame = ttk.Frame(self)
        tag_frame.pack(fill="x", padx=10)
        self.tag_list = tk.Listbox(tag_frame, selectmode="multiple", height=8, exportselection=False)
        tag_scroll = ttk.Scrollbar(tag_frame, command=self.tag_list.yview)
        self.tag_list.config(yscrollcommand=tag_scroll.set)
        self.tag_list.pack(side="left", fill="x", expand=True)
        tag_scroll.pack(side="right", fill="y")

        # ---- results ----
        self.results = tk.Listbox(self, height=10)
        self.status = ttk.Label(self, text=f"Database: {DB_PATH}")

        ttk.Button(self, text="Search", command=self.search).pack(pady=10)
        ttk.Label(self, text="Matching screenshots (newest first):").pack(anchor="w", padx=10)
        self.status.pack(side="bottom", anchor="w", padx=10, pady=(0, 8))
        self.results.pack(fill="both", expand=True, padx=10, pady=(0, 5))

        self.refresh()

    def refresh(self):
        """Reload categories and tags from the database, keep the user's filters, re-run the search."""
        chosen_category = self.category_box.get()
        chosen_tags = {self.tag_list.get(i) for i in self.tag_list.curselection()}

        categories = query("SELECT id, name FROM categories ORDER BY name")
        tags = query("SELECT id, name FROM tags ORDER BY name")

        self.category_ids = {"All categories": None}
        self.category_ids.update({name: cid for cid, name in categories})
        self.category_box["values"] = list(self.category_ids)
        self.category_box.set(chosen_category if chosen_category in self.category_ids else "All categories")

        self.tag_ids = [tid for tid, _ in tags]
        self.tag_list.delete(0, "end")
        for index, (_, name) in enumerate(tags):
            self.tag_list.insert("end", name)
            if name in chosen_tags:
                self.tag_list.selection_set(index)

        self.search()

    def search(self):
        sql = "SELECT title, file_path FROM images WHERE 1=1"
        params = []

        cat_id = self.category_ids.get(self.category_box.get())
        if cat_id is not None:
            sql += " AND category_id = ?"
            params.append(cat_id)

        selected = [self.tag_ids[i] for i in self.tag_list.curselection()]
        if selected:  # image must have ALL selected tags
            marks = ",".join("?" * len(selected))
            sql += (f" AND id IN (SELECT image_id FROM image_tags WHERE tag_id IN ({marks})"
                    f" GROUP BY image_id HAVING COUNT(DISTINCT tag_id) = ?)")
            params += selected + [len(selected)]

        sql += " ORDER BY id DESC"

        self.results.delete(0, "end")
        rows = query(sql, params)
        self.result_paths = [path for _, path in rows]
        for title, path in rows:
            self.results.insert("end", f"{title}   —   {path}")
        self.status.config(text=f"{len(rows)} image(s) found   |   Database: {DB_PATH}")


if __name__ == "__main__":
    # Stand-alone mode, as before: python image_browser.py
    root = tk.Tk()
    root.title("Image Repository")
    root.geometry("600x550")
    ImageBrowser(root).pack(fill="both", expand=True)
    root.mainloop()
