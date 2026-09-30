# Kikule Secondary School — CBA Photo Prep Tool

Batch-crops and compresses student photos for CBA portal upload:
detects the face in each photo, crops to a clean head-and-shoulders
portrait, and compresses each file to under 1MB — while keeping the
original filename (admission number).

## 1. Setup (one-time)

You need Python 3.9+ installed. Then, in the folder with these files:

```
pip install -r requirements.txt
```

If `pip` isn't recognized on Windows, use `py -m pip install -r requirements.txt`.

## 2. (Optional) Add sound effects

Drop any of these files into the **same folder** as `cba.py`. All are optional —
the app runs silently if any/all are missing:

- `boot.wav` — plays once when the app opens
- `scan.wav` — plays when a batch starts
- `complete.wav` — plays when a batch finishes with no errors
- `alert.wav` — plays if any file failed to process

Short `.wav` files work best. `.mp3` also works with pygame.

## 3. Run it

```
python3 cba.py
```

(On Windows: `python cba.py` or double-click `cba.py` if `.py` files are
associated with Python.)

## 4. Using the app

1. **INPUT DIR** — the folder holding the raw, oversized student photos.
2. **OUTPUT DIR** — where the processed photos will be saved. This can be
   a different folder — your originals are never modified or overwritten.
3. **OUTPUT SPECS** — set your target crop size and file size ceiling:
   - `WIDTH (px)` / `HEIGHT (px)` — exact pixel dimensions every photo is
     cropped and resized to (defaults: 600 x 750, a standard portrait ratio).
     This also guides the face-crop aspect ratio, so change these together.
   - `MAX SIZE (KB)` — hard ceiling for the compressed file (defaults to 950,
     just under the 1MB CBA limit). Lower it if the portal needs smaller files.
4. Click **ENGAGE / START PROCESSING**.
5. Watch the log:
   - Green `OK` = face detected, cropped cleanly.
   - Amber `FALLBACK` = no face was detected automatically, so the app
     used a safe center-crop instead. **Worth a quick visual spot-check**
     on these ones before upload.
   - Red `ERROR` = the file couldn't be read/processed at all (corrupt
     file, unsupported format, etc.) — nothing was written for it.

Every output file:
- Keeps the **original filename** (so admission-number-named files stay
  admission-number-named).
- Is saved as **`.jpg`**, regardless of the original format, since JPEG
  compression is what gets us reliably under the size limit.
- Is cropped/resized to the **exact WIDTH x HEIGHT** you set in OUTPUT SPECS.
- Is compressed to fit under your **MAX SIZE (KB)** setting.

## 5. Supported input formats

`.jpg` `.jpeg` `.png` `.bmp` `.webp`

## Notes on the cropping logic

- Face detection uses OpenCV's Haar cascade — fast, works fully offline,
  no model downloads needed.
- The crop box is built from the detected face: generous headroom above,
  extended down past the face to include the shoulders, portrait aspect
  ratio.
- If no face is found (bad lighting, side profile, group shot, etc.), the
  tool falls back to a safe center-crop rather than skipping the file
  entirely — but flags it in amber so you know to eyeball it.

## Next step: portal upload automation

This tool only handles the photo prep stage. To automate uploading into
the CBA portal itself, I'll need whatever you can get me from the upload
page — the request the browser sends when a photo is submitted (open dev
tools → Network tab → submit one photo manually → send me that request),
or the official API/form documentation if the portal provider has one.
Once I can see the actual fields it expects, I can wire up a script that
walks through your admission-number-named photos and student list and
submits them automatically.