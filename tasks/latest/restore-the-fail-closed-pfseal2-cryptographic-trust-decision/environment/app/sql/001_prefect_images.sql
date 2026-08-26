CREATE TABLE prefect_images (
    image_digest VARCHAR PRIMARY KEY,
    image_annotations_json VARCHAR NOT NULL
);
