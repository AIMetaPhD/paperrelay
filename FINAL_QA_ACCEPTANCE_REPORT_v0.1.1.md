# PaperRelay v0.1.1 验收记录

- 日期：2026-11-25
- 基线：公开仓库 `master`（v0.1.0 之后的后继迭代）
- 验证命令：`python test_verify.py`
- 结果：`RESULT tests=20 failures=0 errors=0 skipped=0`，`PaperRelay version: 0.1.1`

## 本轮新增验证

| 项 | 结果 | 证据/说明 |
|---|---|---|
| 环境自检 API | PASS | `GET /api/health/dependencies` 返回 python/ffmpeg/ffprobe/chromium=ok，edge_tts=warn（TCP 可达但服务可能 503） |
| 设置页自检面板 | PASS | Chromium 实测自检结果渲染；预设选择 Magpie 后 Base URL 自动填入 |
| arXiv 候选解析 | PASS | LoRA `2106.09685` 返回 title/authors/abstract/year/paper_url，来源 `arXiv API` |
| OpenReview 候选解析 | PASS（候选） | URL/ID 解析实现；venue 仅作为候选，不自动确认；无网络/无结果时返回 warning |
| Markdown 复制 | PASS | 每个文案平台均有 `复制 Markdown` 按钮（浏览器实测 5 个） |
| 分享长图 | PASS | `POST /api/projects/{id}/site/longimage` 返回 200，生成 `share_long.png`；浏览器按钮存在 |
| PDF 引擎插件 | PASS | `available_pdf_engines() = [pymupdf, pypdf]`；pypdf 实测 26 页/文本/claims 可用，无图 |
| 模型预设 | PASS | Ollama/Magpie/OpenAI-compatible/vLLM/DeepSeek 预设可填充 Base URL、模型和协议 |
| CI | PASS | `.github/workflows/ci.yml` 运行 20 项测试；未在 GitHub runner 上实际等待结果 |
| 社区模板 | PASS | CONTRIBUTING、Bug/Paper parsing issue 模板、PR 模板已加入 |
| Pages workflow | PASS（模板） | `workflow_dispatch` + `github-pages` environment；需要 `docs/site/index.html` 和人工批准，未实际部署 |
| 中文旁白回归 | PASS | 之前实测 62.176s、1920x1080、h264/aac、中文 SRT；仍由 `tests/test_video_language.py` 覆盖 |
| 重启恢复 | PASS | `test_restart_recovery.py` 独立端口 SIGTERM 重启，20 项测试全过 |

## 限制

1. CI 尚未在 GitHub Actions 上实际运行；本地 `test_verify.py` 已通过。
2. OpenReview API 可能限流；结果永远是候选，用户必须确认 venue/source。
3. pypdf 模式不裁图；需要图时用 PyMuPDF。
4. Pages workflow 只提供模板，未实际部署。
5. Edge TTS 仍依赖外部网络，503 时任务会明确失败。

## 结论

v0.1.1 的新增功能已实现并通过本地回归与浏览器检查；建议作为 v0.1.0 的后继补丁发布。
