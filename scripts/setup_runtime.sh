#!/bin/bash
# setup_runtime.sh — 一键配置 iOS Simulator Runtime
# 
# iOS 18.5 Simulator Runtime 需要在 Xcode > Settings > Platforms 中下载
# 或首次打开 Simulator.app 时会引导下载
#
# 此脚本自动完成配置：切换 DEVELOPER_DIR + 启动 Simulator 引导下载

set -e

echo "🔧 Setting Xcode developer directory..."
sudo xcode-select -s /Applications/Xcode.app/Contents/Developer 2>/dev/null || {
  echo "⚠️  sudo not available, will use DEVELOPER_DIR env var"
}

echo "📱 Starting Simulator.app to auto-prompt runtime download..."
echo "   If runtime is not installed, Simulator will show a download dialog."
echo "   Complete the download in the GUI, then re-run this script."
echo ""
open -a Simulator

echo ""
echo "⏳ Waiting for runtime to become available..."
for i in $(seq 1 60); do
  COUNT=$(DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcrun simctl runtime list 2>/dev/null | grep -c "iOS" || true)
  if [ "$COUNT" -gt 0 ]; then
    echo "✅ Runtime detected! ($COUNT iOS runtime(s) found)"
    break
  fi
  sleep 5
done

if [ "$COUNT" -eq 0 ]; then
  echo "❌ Runtime not detected after 5 minutes."
  echo "   Please download manually: Xcode > Settings > Platforms > iOS 18.5 Simulator"
  exit 1
fi

echo "✅ Setup complete!"