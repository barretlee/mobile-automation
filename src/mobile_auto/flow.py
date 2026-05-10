"""Automation flows — login, profile extraction, data collection.

High-level orchestrator that uses simctl + WDA to drive real app interactions.
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from . import simctl
from .wda_client import WDAClient, WDAError


# Known app bundle IDs for common Chinese apps
APP_BUNDLES = {
    "xiaohongshu": "com.xingin.xiaohongshu",
    "linkedin": "com.linkedin.LinkedIn",
    "wechat": "com.tencent.xin",
    "weibo": "com.sina.weibo",
}

# Safari 网页版 URL 映射 (用于不需要原生 App 的场景)
PAGE_URLS = {
    "linkedin": "https://www.linkedin.com/feed",
    "linkedin_profile": "https://www.linkedin.com/in/{username}",
    "linkedin_posts": "https://www.linkedin.com/in/{username}/recent-activity/",
}

# Data output root
DATA_ROOT = os.path.expanduser("~/mobile-data")


def _ensure_data_dir(platform: str, timestamp: str = None) -> str:
    """Create data output directory for a platform."""
    if not timestamp:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join(DATA_ROOT, platform, timestamp)
    os.makedirs(os.path.join(out_dir, "screenshots"), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "images"), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "text"), exist_ok=True)
    return out_dir


def _wait_for_wda(wda: WDAClient, max_retries: int = 30, interval: float = 2) -> bool:
    """Wait for WDA to become available."""
    for i in range(max_retries):
        try:
            status = wda.status()
            if status.get("value", {}).get("ready") or status.get("ready"):
                return True
        except WDAError:
            pass
        time.sleep(interval)
    return False


def login(wda: WDAClient, app: str, account: str = None,
          output_dir: str = None) -> dict:
    """Login flow for a given app.

    Returns: {"status": "ok"|"captcha"|"error", "output_dir": str, ...}
    """
    bundle_id = APP_BUNDLES.get(app, app)
    if not output_dir:
        output_dir = _ensure_data_dir(app)

    # 1. Create WDA session and launch app
    print(f"📱 Launching {app} ({bundle_id})...")
    wda.session(bundle_id=bundle_id)
    time.sleep(3)

    # 2. Screenshot the login page
    screenshot_path = os.path.join(output_dir, "screenshots", "login_page.png")
    wda.save_screenshot(screenshot_path)
    print(f"   Screenshot saved: {screenshot_path}")

    # 3. Detect login button
    try:
        login_btn = wda.find(predicate='label CONTAINS "登录"')
        print(f"   Login button found: {login_btn.label}")
        wda.tap_element(login_btn)
        time.sleep(2)
    except WDAError:
        print("   Login button not found by label. Checking by type...")
        try:
            btn = wda.find(xpath='//XCUIElementTypeButton')
            wda.tap_element(btn)
            time.sleep(2)
        except WDAError:
            print("   ⚠️  Could not find login button. User interaction needed.")

    # 4. Screenshot after login attempt (may show captcha)
    captcha_path = os.path.join(output_dir, "screenshots", "after_login.png")
    wda.save_screenshot(captcha_path)

    # 5. Check for captcha (simplified — check for known patterns)
    try:
        captcha_label = wda.find(predicate='label CONTAINS "验证码"', xpath='//XCUIElementTypeStaticText')
        print(f"   ⚠️  Captcha detected! Saved to {captcha_path}")
        return {
            "status": "captcha",
            "screenshot": captcha_path,
            "output_dir": output_dir,
            "message": "Captcha detected. User must solve it visually.",
        }
    except WDAError:
        pass

    return {
        "status": "ok" if account else "incomplete",
        "output_dir": output_dir,
        "note": "Login triggered. May need credentials input.",
    }


def extract_profile(wda: WDAClient, app: str, extract: str = "all",
                    output_dir: str = None) -> dict:
    """Extract profile data from an app.

    Steps:
    1. Navigate to profile/me tab
    2. Extract visible text via WDA element tree
    3. Long-press to copy text for non-standard elements
    4. Screenshot as fallback
    5. Scroll to load more content
    6. Save all to output_dir
    """
    bundle_id = APP_BUNDLES.get(app, app)
    if not output_dir:
        output_dir = _ensure_data_dir(app)

    # Ensure WDA session exists
    try:
        wda.status()
    except WDAError:
        wda.session(bundle_id=bundle_id)
        time.sleep(2)

    collected = {
        "texts": [],
        "screenshots": [],
        "images": [],
        "platform": app,
        "output_dir": output_dir,
    }

    # ─── Step 1: Navigate to profile tab ────────────────────────
    print(f"📱 Navigating to profile in {app}...")

    # Try common profile tab labels
    profile_labels = ["我", "我的", "Profile", "Me", "个人"]
    found_profile = False

    for label in profile_labels:
        try:
            tab = wda.find(predicate=f'label == "{label}"')
            wda.tap_element(tab)
            time.sleep(2)
            found_profile = True
            print(f"   Profile tab found: '{label}'")
            break
        except WDAError:
            continue

    if not found_profile:
        print("   Profile tab not found by label, trying bottom-right tap...")
        size = wda.window_size()
        wda.tap(int(size["width"] * 0.9), int(size["height"] * 0.9))
        time.sleep(2)

    # Screenshot the profile page
    profile_ss = os.path.join(output_dir, "screenshots", "profile.png")
    wda.save_screenshot(profile_ss)
    collected["screenshots"].append(profile_ss)
    print(f"   Profile screenshot: {profile_ss}")

    # ─── Step 2: Extract text from visible elements ───────────
    if extract in ("all", "text"):
        print("📝 Extracting visible text...")

        # Get all static text elements visible
        try:
            texts = wda.find_all(predicate='type == "XCUIElementTypeStaticText"')
            for i, el in enumerate(texts[:50]):
                try:
                    text_content = wda.text(el)
                    if text_content.strip():
                        text_path = os.path.join(output_dir, "text", f"element_{i:03d}.txt")
                        with open(text_path, "w") as f:
                            f.write(text_content)
                        collected["texts"].append({"index": i, "text": text_content, "file": text_path})
                except WDAError:
                    pass
            print(f"   Extracted {len(collected['texts'])} text elements")
        except WDAError:
            print("   Could not extract text elements")

    # ─── Step 3: Scroll and extract more ─────────────────────────
    if extract in ("all", "posts", "text"):
        print("📜 Scrolling to load more content...")
        for scroll_idx in range(5):
            wda.scroll("down", 0.6)
            time.sleep(1.5)

            # Screenshot after each scroll
            ss_path = os.path.join(output_dir, "screenshots", f"scroll_{scroll_idx:02d}.png")
            wda.save_screenshot(ss_path)
            collected["screenshots"].append(ss_path)

            # Try extracting new text
            if extract in ("all", "text"):
                try:
                    new_texts = wda.find_all(predicate='type == "XCUIElementTypeStaticText"')
                    for el in new_texts[len(collected["texts"]):]:
                        try:
                            text_content = wda.text(el)
                            if text_content.strip():
                                collected["texts"].append({"index": len(collected["texts"]), "text": text_content})
                        except WDAError:
                            pass
                except WDAError:
                    pass

    # ─── Step 4: Save profile metadata ───────────────────────────
    metadata = {
        "platform": app,
        "bundle_id": bundle_id,
        "extract_mode": extract,
        "output_dir": output_dir,
        "text_count": len(collected["texts"]),
        "screenshot_count": len(collected["screenshots"]),
        "image_count": len(collected["images"]),
    }

    meta_path = os.path.join(output_dir, "profile.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    collected["metadata"] = metadata
    print(f"✅ Profile data saved to {output_dir}")

    return collected


# ─── LinkedIn Safari flow ────────────────────────────────────


def linkedin_safari_feed(wda: WDAClient, username: str = None,
                          scroll_pages: int = 3, output_dir: str = None) -> dict:
    """Open LinkedIn feed in Safari and extract posts via screenshot+OCR+source.

    No native app needed — works entirely through Safari on the simulator.
    """
    SAFARI_BUNDLE = "com.apple.mobilesafari"

    if not output_dir:
        output_dir = _ensure_data_dir("linkedin_web")

    print(f"🌐 Opening LinkedIn in Safari...")

    # 1. Launch Safari
    wda.session(bundle_id=SAFARI_BUNDLE)
    time.sleep(3)

    # 2. Navigate to URL bar and type LinkedIn URL
    # In simulator Safari, tap the URL bar (usually at top of screen)
    size = wda.window_size()
    # URL bar at top of screen — tap it
    wda.tap(size["width"] // 2, 30)
    time.sleep(1)

    # Try typing URL via clipboard + paste
    target_url = PAGE_URLS["linkedin"]
    if username:
        target_url = PAGE_URLS["linkedin_posts"].format(username=username)

    # Type URL using keyboard (WDA can type into active text field)
    # WDA supports /wda/keys endpoint
    import requests
    try:
        r = requests.post(
            f"{wda.base_url}/session/{wda._session_id}/wda/keys",
            json={"value": [target_url]},
            timeout=10,
        )
    except Exception:
        # Fallback: set pasteboard and long-press to paste
        wda.set_pasteboard(target_url)
        time.sleep(0.5)
        wda.long_press(size["width"] // 2, 30, duration=1.5)
        time.sleep(1)

    # Press Enter/Go
    try:
        r = requests.post(
            f"{wda.base_url}/session/{wda._session_id}/wda/keys",
            json={"value": ["\n"]},
            timeout=10,
        )
    except Exception:
        pass

    time.sleep(5)  # Wait for page load

    collected = {
        "platform": "linkedin_web",
        "url": target_url,
        "screenshots": [],
        "texts": [],
        "output_dir": output_dir,
    }

    # 3. Take initial screenshot
    ss_path = os.path.join(output_dir, "screenshots", "page_00.png")
    wda.save_screenshot(ss_path)
    collected["screenshots"].append(ss_path)
    print(f"   Screenshot: {ss_path}")

    # 4. Extract page source for text
    try:
        src = wda.source()
        text_path = os.path.join(output_dir, "text", "page_source.xml")
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(src)
        collected["texts"].append({"file": text_path, "length": len(src)})
        print(f"   Page source: {text_path} ({len(src)} chars)")
    except WDAError as e:
        print(f"   Source extraction: {e}")

    # 5. Scroll and screenshot more
    for page in range(scroll_pages):
        print(f"📜 Scrolling page {page + 1}/{scroll_pages}...")
        wda.scroll("down", 0.7)
        time.sleep(2)

        ss_path = os.path.join(output_dir, "screenshots", f"page_{page + 1:02d}.png")
        wda.save_screenshot(ss_path)
        collected["screenshots"].append(ss_path)

    # 6. OCR all screenshots
    print("🔍 Running OCR on all screenshots...")
    from .ocr import ocr

    all_text = []
    for i, ss in enumerate(collected["screenshots"]):
        text = ocr(ss)
        if text:
            ocr_path = os.path.join(output_dir, "text", f"ocr_{i:02d}.txt")
            with open(ocr_path, "w", encoding="utf-8") as f:
                f.write(text)
            all_text.append(text)
            print(f"   OCR page {i}: {len(text)} chars")

    # 7. Save metadata
    metadata = {
        "platform": "linkedin_web",
        "url": target_url,
        "username": username,
        "scroll_pages": scroll_pages,
        "screenshot_count": len(collected["screenshots"]),
        "texts_count": len(collected["texts"]),
        "ocr_text_count": len(all_text),
        "total_ocr_chars": sum(len(t) for t in all_text),
        "output_dir": output_dir,
    }
    meta_path = os.path.join(output_dir, "metadata.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print(f"✅ LinkedIn feed data saved to {output_dir}")
    print(f"   {len(collected['screenshots'])} screenshots, {len(all_text)} OCR pages")

    return collected
