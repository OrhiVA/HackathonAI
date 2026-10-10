# Image Repository System

A structured media database designed to optimize image organization and retrieval using a scalable **Category-and-Tag Funnel Filtering System**.

## 📌 Architecture Overview

This project implements a highly efficient two-tier filtering strategy:
1. **Categories (Hierarchical):** Drastically shrinks the search space into broad, parent-child contextual buckets (e.g., `Nature > Mountains`).
2. **Tags (Flat):** Pinpoints the exact media asset using independent descriptive keywords (e.g., `sunset`, `golden-hour`).

---

### Table Definitions

#### 1. `categories`
Manages the primary, tree-structured folders.
* `id` (INT, Primary Key)
* `name` (VARCHAR)
* `parent_id` (INT, Nullable, Self-referencing Foreign Key)

#### 2. `tags`
A global list of unique search terms.
* `id` (INT, Primary Key)
* `name` (VARCHAR, Unique)

#### 3. `images`
Stores file paths and references a single main category.
* `id` (INT, Primary Key)
* `title` (VARCHAR)
* `file_path` (VARCHAR)
* `category_id` (INT, Foreign Key)

#### 4. `image_tags`
Junction table resolving the many-to-many relationship between images and tags.
* `image_id` (INT, Foreign Key, Composite PK)
* `tag_id` (INT, Foreign Key, Composite PK)