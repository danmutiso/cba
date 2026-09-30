"""
photo_ops.py
Core image-processing logic for the Kikule Secondary CBA Photo Prep Tool.
Kept separate from the GUI so it can be tested / reused headlessly.
"""

import os
import io
import cv2
import numpy as np
from PIL import Image

MAX_SIZE_BYTES = 1_000_000  # 1 MB hard ceiling (target ~950KB to be safe)
TARGET_SIZE_BYTES = 950_000
SUPPORTED_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

# Haar cascade shipped with opencv-python -- no internet/model download needed.
_CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
_FACE_DETECTOR = cv2.CascadeClassifier(_CASCADE_PATH)


class ProcessResult:
    def __init__(self, filename, status, detail="", final_size_kb=0):
        self.filename = filename
        self.status = status          # "OK", "FALLBACK", "ERROR"
        self.detail = detail
        self.final_size_kb = final_size_kb


def list_image_files(folder):
    files = []
    for name in sorted(os.listdir(folder)):
        ext = os.path.splitext(name)[1].lower()
        if ext in SUPPORTED_EXT:
            files.append(name)
    return files


def detect_largest_face(gray_img):
    """Return (x, y, w, h) of the largest detected face, or None."""
    faces = _FACE_DETECTOR.detectMultiScale(
        gray_img,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(60, 60),
    )
    if len(faces) == 0:
        return None
    # pick the largest bounding box (most likely the main subject)
    faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
    return tuple(faces[0])


def compute_crop_box(img_w, img_h, face_box, aspect_ratio=0.8):
    """
    Given a face box (x, y, w, h), compute a portrait-style crop that
    includes the full head plus shoulders, with sensible padding.
    Falls back to a center crop if face_box is None.

    aspect_ratio = crop width / crop height (e.g. 0.8 for a 4:5 portrait).
    """
    if face_box is not None:
        fx, fy, fw, fh = face_box
        cx = fx + fw / 2

        # Head room above the face, generous shoulder room below.
        top = fy - fh * 0.75
        bottom = fy + fh * 2.6          # extends down to include shoulders
        crop_h = bottom - top
        crop_w = crop_h * aspect_ratio

        left = cx - crop_w / 2
        right = cx + crop_w / 2
    else:
        # Center-crop fallback: same aspect ratio from the middle of frame
        crop_h = img_h
        crop_w = img_h * aspect_ratio
        left = (img_w - crop_w) / 2
        right = (img_w + crop_w) / 2
        top = 0
        bottom = img_h

    # Clamp to image bounds
    left = max(0, left)
    top = max(0, top)
    right = min(img_w, right)
    bottom = min(img_h, bottom)

    return int(left), int(top), int(right), int(bottom)


def resize_to_output(pil_img, output_width, output_height):
    """Resize the cropped image to the exact target output dimensions."""
    if output_width and output_height:
        return pil_img.resize((int(output_width), int(output_height)), Image.LANCZOS)
    return pil_img


def compress_to_target(pil_img, target_bytes=TARGET_SIZE_BYTES, max_bytes=MAX_SIZE_BYTES):
    """
    Iteratively reduce JPEG quality, then dimensions if needed,
    until the encoded image fits under max_bytes. Returns raw bytes.
    """
    quality = 92
    img = pil_img.convert("RGB")

    while True:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        size = buf.tell()

        if size <= target_bytes:
            return buf.getvalue()

        if quality > 40:
            quality -= 8
        else:
            # quality floor reached -- start downscaling dimensions instead
            w, h = img.size
            if min(w, h) < 300:
                # already small; accept whatever we have if under hard cap
                if size <= max_bytes:
                    return buf.getvalue()
                # last resort, force it down further
                quality = max(20, quality - 5)
            else:
                img = img.resize((int(w * 0.9), int(h * 0.9)), Image.LANCZOS)
                quality = 85


def process_one_image(src_path, dst_path, output_width=None, output_height=None,
                       target_bytes=TARGET_SIZE_BYTES, max_bytes=MAX_SIZE_BYTES):
    """
    Process a single image file: detect face, crop to face+shoulders
    (or center-crop fallback), resize to the requested output dimensions,
    compress under max_bytes, save to dst_path.
    Returns a ProcessResult.
    """
    filename = os.path.basename(src_path)
    try:
        cv_img = cv2.imdecode(np.fromfile(src_path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if cv_img is None:
            return ProcessResult(filename, "ERROR", "Could not read image (corrupt/unsupported)")

        h, w = cv_img.shape[:2]
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        face_box = detect_largest_face(gray)

        aspect_ratio = (output_width / output_height) if (output_width and output_height) else 0.8

        left, top, right, bottom = compute_crop_box(w, h, face_box, aspect_ratio)
        cropped = cv_img[top:bottom, left:right]

        if cropped.size == 0:
            # safety net -- shouldn't happen, but never crash the batch
            cropped = cv_img

        rgb = cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)
        pil_img = resize_to_output(pil_img, output_width, output_height)

        final_bytes = compress_to_target(pil_img, target_bytes, max_bytes)

        with open(dst_path, "wb") as f:
            f.write(final_bytes)

        status = "OK" if face_box is not None else "FALLBACK"
        detail = "" if face_box is not None else "No face detected -- used center crop"
        return ProcessResult(filename, status, detail, round(len(final_bytes) / 1024, 1))

    except Exception as e:
        return ProcessResult(filename, "ERROR", str(e))


def process_folder(input_folder, output_folder, progress_callback=None,
                    output_width=None, output_height=None,
                    target_bytes=TARGET_SIZE_BYTES, max_bytes=MAX_SIZE_BYTES):
    """
    Process every supported image in input_folder, writing results to
    output_folder with the SAME filename (admission number preserved),
    always saved as .jpg for predictable compression.

    output_width / output_height: exact pixel dimensions for the final
        cropped photo. If either is left as None, the crop keeps its
        natural size (aspect ratio only, no forced resize).
    target_bytes / max_bytes: compression target and hard ceiling in bytes.

    progress_callback(index, total, ProcessResult) is called after each file.
    Returns list of ProcessResult.
    """
    os.makedirs(output_folder, exist_ok=True)
    files = list_image_files(input_folder)
    results = []

    for i, name in enumerate(files, start=1):
        src_path = os.path.join(input_folder, name)
        base_name = os.path.splitext(name)[0]  # preserve admission number
        dst_path = os.path.join(output_folder, base_name + ".jpg")

        result = process_one_image(
            src_path, dst_path,
            output_width=output_width, output_height=output_height,
            target_bytes=target_bytes, max_bytes=max_bytes,
        )
        results.append(result)

        if progress_callback:
            progress_callback(i, len(files), result)

    return results