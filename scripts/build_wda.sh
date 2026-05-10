#!/bin/bash
# build_wda.sh — Build and inject WebDriverAgent into iOS Simulator
# Usage: bash scripts/build_wda.sh [device_name]
set -e

DEVICE="${1:-iPhone 16 Pro}"
WDA_DIR="${WDA_DIR:-$HOME/work/WebDriverAgent}"
DEVELOPER_DIR="${DEVELOPER_DIR:-/Applications/Xcode.app/Contents/Developer}"

echo "🔧 WebDriverAgent Build Script"
echo "   Target device: $DEVICE"
echo "   WDA path:      $WDA_DIR"
echo ""

# 1. Clone if not exists
if [ ! -d "$WDA_DIR" ]; then
    echo "📦 Cloning WebDriverAgent..."
    git clone https://github.com/appium/WebDriverAgent.git "$WDA_DIR"
else
    echo "📦 WebDriverAgent already exists at $WDA_DIR"
    cd "$WDA_DIR"
    git pull --ff-only 2>/dev/null || echo "   (latest)"
fi

# 2. Modify bundle ID to avoid conflicting with other WDA instances
#    (Appium already uses a unique bundle ID by default)

# 3. Build for iOS Simulator (no code signing needed for simulator)
echo "🔨 Building WebDriverAgent for iOS Simulator..."
cd "$WDA_DIR"

DEVELOPER_DIR="$DEVELOPER_DIR" \
xcodebuild build-for-testing \
    -project WebDriverAgent.xcodeproj \
    -scheme WebDriverAgentRunner \
    -destination "platform=iOS Simulator,name=$DEVICE" \
    CODE_SIGN_IDENTITY="" \
    CODE_SIGNING_REQUIRED=NO \
    CODE_SIGNING_ALLOWED=NO \
    | tail -5

echo "✅ Build complete!"

# 4. Show where the built product is
BUILT_PATH=$(find "$WDA_DIR/build" -name "WebDriverAgentRunner-Runner.app" -type d 2>/dev/null | head -1)
if [ -n "$BUILT_PATH" ]; then
    echo "   Built app: $BUILT_PATH"
fi

echo ""
echo "To start WDA on a booted simulator:"
echo "  export DEVELOPER_DIR=$DEVELOPER_DIR"
echo "  xcodebuild test-without-building \\"
echo "    -project \$WDA_DIR/WebDriverAgent.xcodeproj \\"
echo "    -scheme WebDriverAgentRunner \\"
echo "    -destination 'platform=iOS Simulator,id=\$(xcrun simctl list devices | grep Booted | head -1 | grep -oE \"[a-f0-9-]{36}\")'"
echo ""
echo "Then verify: curl http://localhost:8100/status"