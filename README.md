# Stream Deck AI Monitor

把 Stream Deck MK.2 (15 键) 改造成「AI Agent 指挥面板」：实时展示 Herdr 等 agent 系统中各任务状态，并通过实体按键进行审批/暂停等操作。

## 布局（5 列 × 3 行）

```
┌─────────┬─────────┬─────────┬─────────┬─────────┐
│ AI OPS  │ RUNNING │ WAITING │ FAILED  │ ⏸ PAUSE │
│ (来源)  │   n     │   n     │   n     │  切换    │
├─────────┼─────────┼─────────┼─────────┼─────────┤
│ agent 1 │ agent 2 │ agent 3 │ agent 4 │ agent 5 │
├─────────┼─────────┼─────────┼─────────┼─────────┤
│ agent 6 │ agent 7 │ agent 8 │ agent 9 │ agent10 │
└─────────┴─────────┴─────────┴─────────┴─────────┘
```

每个 agent 键位（72×72）：顶部状态色条 / 名称 / 任务或备注 / 状态+ETA / 进度条。

状态配色：RUN=青、WAIT=琥珀（待审批）、FAIL=红、DONE=绿、IDLE=灰。

## 文件

| 文件 | 作用 |
|---|---|
| `state.example.json` | 状态契约（任何 agent 系统写出此 JSON 即可上屏） |
| `render_tiles.py` | 状态 JSON → 15 张 72×72 键位图（PIL） |
| `push_to_deck.py` | 推送上屏；`--watch` 模式监听状态文件变化实时刷新，按键回调 |

## 运行

```bash
# 需指定自编译的 hidapi 库（本机无 Homebrew，源码 clang 编译）
PY=python3

$PY -m pip install streamdeck pillow
$PY render_tiles.py state.example.json      # 只渲染预览 tiles/preview.png
$PY push_to_deck.py state.json              # 上屏一次
$PY push_to_deck.py state.json --watch      # 常驻监听 + 按键响应
```

## 接入 Herdr（已完成）

`herdr_adapter.py` 轮询 `herdr api snapshot`（herdr.dev v0.9.1），把 SessionSnapshot 转成 state.json：

```bash
PY=python3

$PY herdr_adapter.py &                    # 每 2s 拉取 herdr 实时状态 -> state.json
$PY push_to_deck.py state.json --watch    # 监听 state.json -> 上屏 + 按键响应
```

状态映射：working→RUN、blocked→WAIT（置顶，琥珀色）、done→DONE、idle/unknown→IDLE；
token 用量显示在键位副标题（如 `tok 48.2k`）。herdr 未启动时面板显示 0 agents（offline）。

**按键操作**：点任意 agent 键位 → `herdr agent focus <pane_id>`（iTerm 里直接聚焦该 agent）；
点 PAUSE 键 → 面板暂停/恢复切换。

**下一步**：WAIT 键长按审批（`herdr agent send-keys`）、FAILED 键红色闪烁、agent >10 翻页。

## 已验证环境

- 设备：Stream Deck MK.2 (VID 0x0FD9, PID 0x0080, 15 键, 72×72 JPEG, 需双向翻转)
- macOS 无 brew 方案：`clang -dynamiclib` 编译 hidapi (`mac/hid.c`，依赖 IOKit/CoreFoundation)
  + pip `streamdeck` + `DYLD_LIBRARY_PATH` 指向自编译库目录
- 驱动库：python-elgato-streamdeck 0.10.0 + pillow
