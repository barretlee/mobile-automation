"""OCR utilities — screenshot text extraction (fallback).

P0: Apple Vision framework (macOS native, no extra deps)
P1: PaddleOCR (if installed)
P2: tesserocr (if installed)

Apple Vision is preferred as it requires zero additional packages.
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path


def ocr_apple_vision(image_path: str) -> str:
    """Extract text from image using macOS built-in Vision framework.

    Uses the `visions` CLI tool if available, or falls back to AppleScript.
    """
    # Try using the internal VNRecognizeTextRequest via a small Swift helper
    # For now, fall back to a simpler approach: use `textutil` or system OCR
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    # Best approach: use a tiny Python wrapper around Vision framework
    # Create a temporary Swift script
    swift_code = """
import Cocoa
import Vision

guard CommandLine.arguments.count > 1 else { exit(1) }
let imagePath = CommandLine.arguments[1]
guard let image = NSImage(contentsOfFile: imagePath) else { exit(1) }
guard let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else { exit(1) }

let request = VNRecognizeTextRequest { request, error in
    guard let observations = request.results as? [VNRecognizedTextObservation] else { exit(0) }
    for obs in observations {
        if let candidate = obs.topCandidates(1).first {
            print(candidate.string)
        }
    }
}
request.recognitionLevel = .accurate

let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
try? handler.perform([request])
"""
    swift_path = "/tmp/_ocr_helper.swift"
    with open(swift_path, "w") as f:
        f.write(swift_code)

    try:
        r = subprocess.run(
            ["swift", swift_path, image_path],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode == 0:
            return r.stdout.strip()
        else:
            return ""
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""
    finally:
        if os.path.exists(swift_path):
            os.unlink(swift_path)


def ocr_paddle(image_path: str) -> str:
    """Extract text using PaddleOCR (if installed)."""
    try:
        from paddleocr import PaddleOCR
        ocr = PaddleOCR(use_angle_cls=True, lang='ch', show_log=False)
        result = ocr.ocr(image_path, cls=True)
        text_lines = []
        for line in result[0]:
            text_lines.append(line[1][0])
        return "\n".join(text_lines)
    except ImportError:
        raise ImportError("PaddleOCR not installed. Run: pip install paddleocr")


def ocr(image_path: str, engine: str = "auto") -> str:
    """Extract text from image. Auto-picks best available engine."""
    if engine == "auto":
        # Try Apple Vision first
        text = ocr_apple_vision(image_path)
        if text:
            return text
        # Fall back to PaddleOCR
        try:
            return ocr_paddle(image_path)
        except ImportError:
            pass
        return ""
    elif engine == "apple":
        return ocr_apple_vision(image_path)
    elif engine == "paddle":
        return ocr_paddle(image_path)
    else:
        raise ValueError(f"Unknown OCR engine: {engine}")
