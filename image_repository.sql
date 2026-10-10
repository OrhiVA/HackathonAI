BEGIN TRANSACTION;
CREATE TABLE categories (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       VARCHAR(100) NOT NULL,
    parent_id  INTEGER NULL,
    FOREIGN KEY (parent_id) REFERENCES categories(id)
);
CREATE TABLE image_tags (
    image_id  INTEGER NOT NULL,
    tag_id    INTEGER NOT NULL,
    PRIMARY KEY (image_id, tag_id),
    FOREIGN KEY (image_id) REFERENCES images(id),
    FOREIGN KEY (tag_id)   REFERENCES tags(id)
);
CREATE TABLE images (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        VARCHAR(255) NOT NULL,
    file_path    VARCHAR(500) NOT NULL,
    category_id  INTEGER NOT NULL,
    FOREIGN KEY (category_id) REFERENCES categories(id)
);
CREATE TABLE tags (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name  VARCHAR(100) NOT NULL UNIQUE
);
DELETE FROM "sqlite_sequence";
COMMIT;
