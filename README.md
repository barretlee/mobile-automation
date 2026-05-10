# Mobile Automation — iOS Simulator 自动化数据采集

通过手机应用（如小红书、LinkedIn）自动采集数据的 CLI 工具。

## 项目目标

在 iOS Simulator 中实现自动化操控，支持：
1. 启动/管理 Simulator
2. 安装和启动 App
3. 通过 WebDriverAgent 操控 UI（点击、长按、滚动、复制、截图）
4. 提取数据到本地目录
5. 可被 Hermes Agent 调度

## 技术选型

- **simctl** — Xcode 内建，负责 Simulator 生命周期
- **WebDriverAgent**（appium fork）— UI 元素级操控
- **facebook-wda** — Python 客户端控制 WDA
- **Apple Vision OCR** — 截图文字识别（兜底）

## 项目结构

```
mobile-automation/
├── docs/
│   └── specs/
│       └── 2026-05-10-mobile-automation/   # SDD 文档包
│           ├── PRD.md
│           ├── RESEARCH.md
│           ├── SYSTEM.md
│           ├── TASKS.md
│           └── TEST.md
├── src/
│   ├── mobile_auto/
│   │   ├── __init__.py
│   │   ├── cli.py          # 主入口
│   │   ├── simctl.py       # Simulator 管理
│   │   ├── wda_client.py   # WDA 操控
│   │   ├── flow.py         # 自动化流程
│   │   └── ocr.py          # OCR 兜底
│   └── ...
├── tests/
├── pyproject.toml
└── README.md
```

## 状态

- [x] SDD 文档完成
- [ ] 阶段 1：基础设施
- [ ] 阶段 2：WebDriverAgent 集成
- [ ] 阶段 3：CLI 实现
- [ ] 阶段 4：数据提取
- [ ] 阶段 5：可调度集成
