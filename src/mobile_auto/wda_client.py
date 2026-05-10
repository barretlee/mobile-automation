"""WebDriverAgent HTTP client — controls iOS Simulator UI elements.

Uses Appium's WebDriverAgent injected into the simulator.
WDA exposes a WebDriver-compatible HTTP API on port :8100.

Related:
  https://github.com/appium/WebDriverAgent
  https://github.com/openatx/facebook-wda
"""

import json
import time
from dataclasses import dataclass
from typing import Optional

import requests


WDA_DEFAULT_PORT = 8100


class WDAError(Exception):
    """WebDriverAgent communication error."""
    pass


@dataclass
class Element:
    """A UI element found on screen."""
    ref: str          # WDA element reference (e.g., "E1")
    label: str = ""
    value: str = ""
    rect: dict = None  # {x, y, width, height}


class WDAClient:
    """Client for WebDriverAgent HTTP API."""

    def __init__(self, port: int = WDA_DEFAULT_PORT, timeout: int = 10):
        self.base_url = f"http://localhost:{port}"
        self._session = requests.Session()
        self._session.timeout = timeout
        self._session_id = None

    def _req(self, method, path, **kwargs):
        url = f"{self.base_url}{path}"
        if self._session_id and "/session/" not in path:
            url = f"{self.base_url}/session/{self._session_id}{path}"
        try:
            r = self._session.request(method, url, **kwargs)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            raise WDAError(f"WDA request failed: {e}") from e

    # ─── Session ────────────────────────────────────────────────

    def session(self, bundle_id: Optional[str] = None):
        """Create a new session. Optionally launch an app bundle."""
        payload = {
            "capabilities": {
                "bundleId": bundle_id,
            } if bundle_id else {}
        }
        r = self._req("POST", "/session", json=payload)
        self._session_id = r.get("sessionId") or r.get("value", {}).get("sessionId")
        return self._session_id

    def close_session(self):
        if self._session_id:
            self._req("DELETE", f"/session/{self._session_id}")
            self._session_id = None

    # ─── Status ─────────────────────────────────────────────────

    def status(self) -> dict:
        """Check WDA server status."""
        return self._req("GET", "/status")

    # ─── Screen ─────────────────────────────────────────────────

    def screenshot(self) -> bytes:
        """Take screenshot and return PNG bytes."""
        r = self._req("GET", "/screenshot")
        import base64
        return base64.b64decode(r["value"])

    def save_screenshot(self, path: str):
        """Take screenshot and save to file."""
        data = self.screenshot()
        with open(path, "wb") as f:
            f.write(data)
        return path

    def window_size(self) -> dict:
        """Get screen size as {width, height}."""
        r = self._req("GET", "/window/size")
        val = r.get("value", r)
        if isinstance(val, dict):
            return val
        raise WDAError(f"Unexpected response: {r}")

    def source(self) -> str:
        """Get page source as XML — all UI elements in the current view."""
        r = self._req("GET", "/source")
        return r.get("value", "")

    # ─── Element finding ────────────────────────────────────────

    def find(self, predicate: str = None, xpath: str = None,
             class_chain: str = None, id: str = None) -> Element:
        """Find first matching element.

        Uses predicate string (most reliable):
          wda.find(predicate='label == "登录"')
          wda.find(predicate='type == "XCUIElementTypeButton"')
        """
        if predicate:
            strategy, value = "predicate string", predicate
        elif xpath:
            strategy, value = "xpath", xpath
        elif class_chain:
            strategy, value = "class chain", class_chain
        elif id:
            strategy, value = "id", id
        else:
            raise ValueError("Provide one of: predicate, xpath, class_chain, id")

        payload = {"using": strategy, "value": value}
        r = self._req("POST", "/element", json=payload)
        val = r.get("value", {})
        ref = val.get("ELEMENT") or val.get("element-6066-11e4-a52e-4f735466cecf") or ""
        if not ref:
            raise WDAError(f"Element not found: {predicate or xpath or class_chain or id}")

        # Get element attributes for richer data
        try:
            label_req = self._req("POST", f"/element/{ref}/attribute/label")
            label = label_req.get("value", "")
        except WDAError:
            label = ""

        try:
            rect_req = self._req("POST", f"/element/{ref}/rect")
            rect = rect_req.get("value", {})
        except WDAError:
            rect = {}

        return Element(ref=ref, label=label, rect=rect)

    def find_all(self, predicate: str = None, xpath: str = None) -> list[Element]:
        """Find all matching elements."""
        if predicate:
            strategy, value = "predicate string", predicate
        elif xpath:
            strategy, value = "xpath", xpath
        else:
            raise ValueError("Provide predicate or xpath")

        r = self._req("POST", "/elements", json={"using": strategy, "value": value})
        elements = []
        for item in r.get("value", []):
            ref = item.get("ELEMENT") or item.get("element-6066-11e4-a52e-4f735466cecf") or ""
            if ref:
                elements.append(Element(ref=ref))
        return elements

    # ─── Element actions ────────────────────────────────────────

    def tap(self, x: int, y: int):
        """Tap at screen coordinates."""
        self._req("POST", "/wda/tap", json={"x": x, "y": y})

    def tap_element(self, element: Element):
        """Tap a UI element (center of its rect)."""
        if element.rect:
            x = element.rect["x"] + element.rect["width"] // 2
            y = element.rect["y"] + element.rect["height"] // 2
            self.tap(x, y)
        else:
            self._req("POST", f"/element/{element.ref}/click")

    def long_press(self, x: int, y: int, duration: float = 1.0):
        """Long press at coordinates for duration (seconds)."""
        self._req("POST", "/wda/touchAndHold", json={
            "x": x, "y": y, "duration": duration,
        })

    def long_press_element(self, element: Element, duration: float = 1.0):
        """Long press a UI element."""
        if element.rect:
            x = element.rect["x"] + element.rect["width"] // 2
            y = element.rect["y"] + element.rect["height"] // 2
            self.long_press(x, y, duration)

    def scroll(self, direction: str = "down", distance: float = 0.5):
        """Scroll in a direction. distance: 0.0-1.0 (fraction of screen)."""
        size = self.window_size()
        start_x = size["width"] // 2
        start_y = size["height"] // 2
        delta = int(size["height"] * distance)

        if direction == "down":
            end_x, end_y = start_x, start_y - delta
        elif direction == "up":
            end_x, end_y = start_x, start_y + delta
        elif direction == "left":
            end_x, end_y = start_x - delta, start_y
        elif direction == "right":
            end_x, end_y = start_x + delta, start_y
        else:
            raise ValueError(f"Invalid direction: {direction}")

        self._req("POST", "/wda/drag", json={
            "fromX": start_x, "fromY": start_y,
            "toX": end_x, "toY": end_y,
            "duration": 0.5,
        })

    # ─── Text ───────────────────────────────────────────────────

    def text(self, element: Element = None) -> str:
        """Get text value of an element or from the active element."""
        if element:
            r = self._req("POST", f"/element/{element.ref}/text")
        else:
            r = self._req("POST", "/wda/activeApp")
        return r.get("value", "")

    # ─── Alerts ─────────────────────────────────────────────────

    def alert_accept(self):
        """Accept an alert dialog."""
        self._req("POST", "/alert/accept")

    def alert_text(self) -> str:
        """Get alert text."""
        r = self._req("GET", "/alert/text")
        return r.get("value", "")

    # ─── Pasteboard ─────────────────────────────────────────────

    def get_pasteboard(self) -> str:
        """Get system pasteboard content (text copied by user action)."""
        r = self._req("POST", "/wda/getPasteboard")
        return r.get("value", "")

    def set_pasteboard(self, text: str):
        """Set system pasteboard content."""
        self._req("POST", "/wda/setPasteboard", json={"content": text})
