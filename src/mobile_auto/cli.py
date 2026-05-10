"""mobile-auto CLI — iOS Simulator automation for data extraction."""

from pathlib import Path
import json
import os
import subprocess
import sys

import click


def _xcode_dev():
    """Get the Xcode developer directory."""
    env = os.environ.get("DEVELOPER_DIR")
    if env:
        return env
    return "/Applications/Xcode.app/Contents/Developer"


def _xcrun(*args, timeout=60):
    """Run xcrun with DEVELOEPR_DIR set."""
    env = os.environ.copy()
    env["DEVELOPER_DIR"] = _xcode_dev()
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


def _output(data, json_output):
    """Print output in requested format."""
    if json_output:
        click.echo(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        if isinstance(data, str):
            click.echo(data)
        elif isinstance(data, dict):
            for k, v in data.items():
                click.echo(f"{k}: {v}")
        elif isinstance(data, list):
            for item in data:
                click.echo(str(item))


# ─── Simulator management ─────────────────────────────────────────


@click.group()
def cli():
    """mobile-auto — iOS Simulator automation CLI"""
    pass


@cli.group()
def sim():
    """Manage iOS Simulators"""
    pass


@sim.command(name="list")
@click.option("--json-output", "json_output", is_flag=True, help="JSON output")
def sim_list(json_output):
    """List available simulators"""
    code, out, err = _xcrun("simctl", "list", "devices", "available")
    if code != 0:
        click.echo(f"Error: {err}", err=True)
        sys.exit(1)

    # Parse devices from simctl output
    devices = []
    current_runtime = None
    for line in out.split("\n"):
        line = line.strip()
        if line.startswith("-- "):
            # Runtime header like "-- iOS 18.5 --"
            current_runtime = line.strip("- ")
        elif "(" in line and ")" in line:
            # Device line like "iPhone 16 Pro (UUID) (Shutdown)"
            name_part = line[: line.rindex("(")].strip()
            # Extract UDID
            udid = ""
            status = ""
            parts = line.split()
            for p in parts:
                if p.startswith("(") and p.endswith(")") and not p[1].isalpha():
                    udid = p.strip("()")
                elif p == "(Booted)" or p == "(Shutdown)" or p == "(Creating)":
                    status = p.strip("()")
            if udid:
                devices.append({
                    "name": name_part, "udid": udid,
                    "status": status, "runtime": current_runtime or "unknown",
                })

    _output({"count": len(devices), "devices": devices} if json_output else devices, json_output)


@sim.command()
@click.option("--device", default="iPhone 16 Pro", help="Device type name")
@click.option("--os", "os_version", default="iOS18", help="OS version")
@click.option("--name", default=None, help="Custom device name")
@click.option("--json-output", "json_output", is_flag=True)
def create(device, os_version, name, json_output):
    """Create a new iOS Simulator"""
    if not name:
        name = f"{device} ({os_version})"

    code, out, err = _xcrun("simctl", "create", name, device, os_version)
    if code != 0:
        click.echo(f"Error: {err}", err=True)
        sys.exit(1)

    udid = out.strip()
    result = {"udid": udid, "name": name, "device": device, "os": os_version}
    _output(result, json_output)


@sim.command()
@click.argument("udid", required=False)
@click.option("--json-output", "json_output", is_flag=True)
def boot(udid, json_output):
    """Boot a simulator (uses first available if no UDID)"""
    if not udid:
        # Find first shutdown device
        code, out, err = _xcrun("simctl", "list", "devices", "available")
        for line in out.split("\n"):
            if "(Shutdown)" in line:
                parts = line.split()
                for p in parts:
                    if p.startswith("(") and p.endswith(")") and len(p) > 20:
                        udid = p.strip("()")
                        break
                if udid:
                    break
        if not udid:
            click.echo("No available simulator to boot", err=True)
            sys.exit(1)

    code, out, err = _xcrun("simctl", "boot", udid)
    if code != 0:
        click.echo(f"Error: {err}", err=True)
        sys.exit(1)

    _output({"udid": udid, "status": "booted"}, json_output)


@sim.command()
@click.argument("udid", required=False)
@click.option("--app", required=True, help="Path to .app file")
@click.option("--json-output", "json_output", is_flag=True)
def install(udid, app, json_output):
    """Install an app on the simulator"""
    if not udid:
        udid = _get_booted_device()

    app_path = os.path.expanduser(app)
    if not os.path.exists(app_path):
        click.echo(f"App not found: {app_path}", err=True)
        sys.exit(1)

    code, out, err = _xcrun("simctl", "install", udid, app_path)
    if code != 0:
        click.echo(f"Error: {err}", err=True)
        sys.exit(1)

    _output({"udid": udid, "app": app, "status": "installed"}, json_output)


@sim.command()
@click.argument("udid", required=False)
@click.option("--bundle-id", required=True, help="App bundle identifier")
@click.option("--json-output", "json_output", is_flag=True)
def launch(udid, bundle_id, json_output):
    """Launch an app on the simulator"""
    if not udid:
        udid = _get_booted_device()

    code, out, err = _xcrun("simctl", "launch", udid, bundle_id)
    if code != 0:
        click.echo(f"Error: {err}", err=True)
        sys.exit(1)

    _output({"udid": udid, "bundle_id": bundle_id, "status": "launched"}, json_output)


@sim.command()
@click.argument("udid", required=False)
@click.option("--output", "-o", default=None, help="Output path for screenshot")
@click.option("--json-output", "json_output", is_flag=True)
def screenshot(udid, output, json_output):
    """Take a screenshot of the simulator"""
    if not udid:
        udid = _get_booted_device()

    if not output:
        output = os.path.expanduser(f"~/mobile-data/screenshots/sim_{udid[:8]}_{int(__import__('time').time())}.png")
    os.makedirs(os.path.dirname(output), exist_ok=True)

    code, out, err = _xcrun("simctl", "io", udid, "screenshot", output)
    if code != 0:
        click.echo(f"Error: {err}", err=True)
        sys.exit(1)

    _output({"udid": udid, "screenshot": output, "status": "captured"}, json_output)


# ─── WDA (WebDriverAgent) ────────────────────────────────────────


def _get_booted_device():
    """Get the UDID of the first booted device."""
    code, out, err = _xcrun("simctl", "list", "devices", "available")
    if code != 0:
        raise click.ClickException(f"simctl error: {err}")
    for line in out.split("\n"):
        if "(Booted)" in line:
            parts = line.split()
            for p in parts:
                if p.startswith("(") and p.endswith(")") and len(p) > 20:
                    return p.strip("()")
    raise click.ClickException("No booted simulator found. Boot one first with `mobile-auto sim boot`.")


@cli.group()
def wda():
    """WebDriverAgent — UI element control"""
    pass


@wda.command(name="build")
@click.argument("wda_path", default=lambda: os.path.expanduser("~/work/WebDriverAgent"))
@click.option("--device", default="iPhone 16 Pro", help="Target device")
@click.option("--json-output", "json_output", is_flag=True)
def wda_build(wda_path, device, json_output):
    """Build and inject WebDriverAgent into the simulator"""
    wda_path = os.path.expanduser(wda_path)

    if not os.path.exists(wda_path):
        click.echo("WebDriverAgent not found. Cloning...")
        subprocess.run(
            ["git", "clone", "https://github.com/appium/WebDriverAgent.git", wda_path],
            check=True,
        )
        click.echo(f"Cloned to {wda_path}")

    # Build for simulator (no code signing needed)
    dev_dir = _xcode_dev()
    env = os.environ.copy()
    env["DEVELOPER_DIR"] = dev_dir

    dest = f"platform=iOS Simulator,name={device}"
    cmd = [
        "xcodebuild", "build-for-testing",
        "-project", os.path.join(wda_path, "WebDriverAgent.xcodeproj"),
        "-scheme", "WebDriverAgentRunner",
        "-destination", dest,
        "CODE_SIGN_IDENTITY=", "CODE_SIGNING_REQUIRED=NO",
    ]

    click.echo(f"Building WebDriverAgent for {device}...")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=env)

    if r.returncode != 0:
        click.echo(f"Build failed:\n{r.stderr[:500]}", err=True)
        sys.exit(1)

    _output({
        "status": "built",
        "path": wda_path,
        "destination": dest,
    }, json_output)


@wda.command(name="start")
@click.argument("udid", required=False)
@click.option("--wda-path", default=lambda: os.path.expanduser("~/work/WebDriverAgent"))
@click.option("--port", default=8100, help="WDA HTTP port")
@click.option("--json-output", "json_output", is_flag=True)
def wda_start(udid, wda_path, port, json_output):
    """Start WebDriverAgent on the simulator"""
    if not udid:
        udid = _get_booted_device()

    wda_path = os.path.expanduser(wda_path)
    dev_dir = _xcode_dev()
    env = os.environ.copy()
    env["DEVELOPER_DIR"] = dev_dir

    dest = f"platform=iOS Simulator,id={udid}"
    cmd = [
        "xcodebuild", "test-without-building",
        "-project", os.path.join(wda_path, "WebDriverAgent.xcodeproj"),
        "-scheme", "WebDriverAgentRunner",
        "-destination", dest,
    ]

    click.echo(f"Starting WDA on device {udid} (port {port})...")
    # Run in background
    subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )

    _output({
        "udid": udid,
        "port": port,
        "status": "starting",
        "note": "WDA starting in background. Check http://localhost:8100/status",
    }, json_output)


@wda.command(name="status")
@click.option("--port", default=8100)
@click.option("--json-output", "json_output", is_flag=True)
def wda_status(port, json_output):
    """Check if WebDriverAgent is running"""
    import requests
    try:
        r = requests.get(f"http://localhost:{port}/status", timeout=5)
        data = r.json()
        _output(data, json_output)
    except requests.RequestException as e:
        click.echo(f"WDA not reachable on port {port}: {e}", err=True)
        sys.exit(1)


# ─── Flow (Automation) ────────────────────────────────────────────


@cli.group()
def flow():
    """Automation flows (login, profile extraction)"""
    pass


@flow.command(name="login")
@click.option("--app", required=True, help="App bundle ID or alias")
@click.option("--account", default=None, help="Account to login with")
@click.option("--json-output", "json_output", is_flag=True)
def flow_login(app, account, json_output):
    """Execute login flow for an app"""
    click.echo(f"Login flow for {app}...")
    click.echo("  1. Launching app")
    click.echo("  2. Navigating to login page")
    click.echo("  3. Entering credentials (user-assisted for now)")
    click.echo("  4. Detecting captcha...")
    click.echo("")
    click.echo("⚠️  Login flow requires interactive user input for:")
    click.echo("   - Captcha solving")
    click.echo("   - SMS verification codes")
    click.echo("")
    click.echo("Run with actual WDA active for full flow.")

    _output({
        "app": app,
        "status": "not-implemented",
        "note": "Login flow requires WDA to be running. Use `mobile-auto wda build && mobile-auto wda start` first.",
    }, json_output)


@flow.command(name="profile")
@click.option("--app", required=True, help="App bundle ID or alias")
@click.option("--extract", default="all", help="What to extract: all, posts, images, text")
@click.option("--output", "-o", default=None, help="Output directory")
@click.option("--json-output", "json_output", is_flag=True)
def flow_profile(app, extract, output, json_output):
    """Extract profile data from an app"""
    if not output:
        output = os.path.expanduser(f"~/mobile-data/{app}")

    click.echo(f"Profile extraction for {app}...")
    click.echo(f"  Output: {output}")
    click.echo(f"  Extract: {extract}")
    click.echo("")
    click.echo("⚠️  Profile extraction requires WDA to be running.")
    click.echo("    This is a placeholder. Full implementation coming in Phase 4.")

    _output({
        "app": app,
        "extract": extract,
        "output": output,
        "status": "placeholder",
    }, json_output)


# ─── Main entry ────────────────────────────────────────────────────

if __name__ == "__main__":
    cli()
