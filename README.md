# mobile-auto — iOS Simulator 自动化数据采集 CLI

通过 Appium WebDriverAgent + xcrun simctl 实现 iOS Simulator 自动化操控。

## 安装

```bash
# 1. 安装依赖
pip install -e .

# 2. 配置 Xcode 环境
export DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer

# 3. 下载 iOS Simulator Runtime（首次）
# 打开 Simulator.app 按提示下载，或运行：
bash scripts/setup_runtime.sh
```

## 使用

```bash
# 创建并启动 Simulator
mobile-auto sim create --device "iPhone 16 Pro" --os iOS18
mobile-auto sim boot

# 安装应用 (.app 或通过 WDA 安装)
mobile-auto sim install --app ~/apps/xiaohongshu.app

# WebDriverAgent 操控
mobile-auto wda build      # 编译 WDA 到 Simulator
mobile-auto wda start      # 启动 WDA HTTP 服务 (port 8100)
mobile-auto wda tap --x 100 --y 200

# 自动化流程
mobile-auto flow login --app xiaohongshu
mobile-auto flow profile --app xiaohongshu --extract all
mobile-auto flow profile --app linkedin --extract posts

# JSON 输出（供 Agent 消费）
mobile-auto sim list --json
mobile-auto wda status --json
```

## 架构

```
mobile-auto/
├── src/mobile_auto/
│   ├── cli.py          # Click CLI 入口
│   ├── simctl.py       # Simulator 生命周期管理
│   ├── wda_client.py   # WebDriverAgent HTTP 客户端
│   ├── flow.py         # 自动化流程（登录/提取）
│   ├── ocr.py          # OCR 兜底
│   └── util.py         # 工具函数
├── scripts/
│   ├── setup_runtime.sh    # Runtime 下载引导
│   └── build_wda.sh        # WebDriverAgent 编译脚本
├── tests/
├── docs/specs/
└── pyproject.toml
```

## 技术依赖

- **simctl** — Xcode 内建，管理 Simulator 生命周期
- **WebDriverAgent** (appium fork) — 注入 Simulator 的 HTTP 服务，操控 UI 元素
- **facebook-wda** — Python 客户端，通过 HTTP :8100 控制 WDA
- **Apple Vision OCR** — 截图文字识别（兜底方案）
