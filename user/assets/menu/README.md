# Menu photos

AI-generated illustrative Korean pub food photos; these are not photos of the
restaurant's actual servings. The original generation sheets stay outside the
repository in `/workspace/generated_images`.

32 square WebP thumbnails, 308 × 308 pixels, encoded at quality 76. Together they
are approximately 546 KiB; each is 8–23 KiB. Metadata is not retained. Only the
compressed thumbnails are included in the application.

`user/menu_images.py` maps menu IDs to these files for both dummy and API data.
Flavor and portion variants share assets, and configured HTTP(S) menu image URLs
take precedence. Missing photos fall back to the menu emoji. Photos are read and
encoded on demand, cached once per shared asset, and included only for rendered
cards. Browser image decoding is asynchronous and images are marked for lazy
loading. To replace a photo, keep the filename and WebP format.
