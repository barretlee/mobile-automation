"""Simulator lifecycle management via xcrun simctl."""

import json
import os
import subprocess
from pathlib import Path


def _xcrun(*args, timeout=60):
    """Run xcrun with DEVELOPER_DIR preset."""
    env = os.environ.copy()
    env["DEVELOPER_DIR"] = os.environ.get(
        "DEVELOPER_DIR", "/Applications/Xcode.app/Contents/Developer"
    )
    try:
        r = subprocess.run(
            ["xcrun"] + list(args),
            capture_output=True, text=True, timeout=timeout, env=env,
        )
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except FileNotFoundError:
        return -1, "", "xcrun not found"


def list_devices():
    """List all available iOS Simulators."""
    code, out, err = _xcrun("simctl", "list", "devices", "available")
    if code != 0:
        raise RuntimeError(f"simctl list devices failed: {err}")

    devices = []
    current_runtime = None
    for line in out.split("\n"):
        line = line.strip()
        if line.startswith("-- "):
            current_runtime = line.strip("- ")
        elif "(" in line and ")" in line and not line.startswith("--"):
            name_part = line[: line.rindex("(")].strip()
            udid = ""
            status = ""
            parts = line.split()
            for p in parts:
                if p.startswith("(") and p.endswith(")") and len(p.strip("()")) > 10:
                    udid = p.strip("()")
                elif p in ("(Booted)", "(Shutdown)", "(Creating)"):
                    status = p.strip("()")
            if udid:
                devices.append({
                    "name": name_part, "udid": udid,
                    "status": status, "runtime": current_runtime or "unknown",
                })
    return devices


def get_booted_device():
    """Get the first booted simulator's UDID."""
    devices = list_devices()
    for d in devices:
        if d["status"] == "Booted":
            return d["udid"]
    return None


def create(name, device_type="iPhone 16 Pro", runtime="com.apple.CoreSimulator.SimRuntime.iOS-18-6"):
    """Create a new simulator."""
    cmd = ["simctl", "create", name, device_type, runtime]
    code, out, err = _xcrun(*cmd)
    if code != 0:
        raise RuntimeError(f"simctl create failed: {err}")
    return out.strip()


def boot(udid):
    """Boot a simulator."""
    code, out, err = _xcrun("simctl", "boot", udid)
    if code != 0:
        raise RuntimeError(f"simctl boot failed: {err}")
    return True


def install(udid, app_path):
    """Install an .app on the simulator."""
    if not os.path.exists(app_path):
        raise FileNotFoundError(f"App not found: {app_path}")
    code, out, err = _xcrun("simctl", "install", udid, app_path)
    if code != 0:
        raise RuntimeError(f"simctl install failed: {err}")
    return True


def launch(udid, bundle_id):
    """Launch an app by bundle ID."""
    code, out, err = _xcrun("simctl", "launch", udid, bundle_id)
    if code != 0:
        raise RuntimeError(f"simctl launch failed: {err}")
    return True


def screenshot(udid, output_path):
    """Take a screenshot of the simulator screen."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    code, out, err = _xcrun("simctl", "io", udid, "screenshot", output_path)
    if code != 0:
        raise RuntimeError(f"simctl screenshot failed: {err}")
    return output_path
