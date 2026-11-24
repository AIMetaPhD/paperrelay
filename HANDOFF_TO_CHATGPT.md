# PaperRelay 产品交接（R1 修复轮）

状态：本地可运行的 v0.1 + R1 修复版。项目负责人指令要求继续开发、暂不正式验收；本轮已完成集中修复并推送到独立分支，等待项目负责人 ChatGPT 复核。仓库保持 Private，未创建公开 Release，未修改 AIMetaPhD 开源列表。

## 1. 当前交付

- 私有仓库：[AIMetaPhD/paperrelay](https://github.com/AIMetaPhD/paperrelay)
- 当前工作分支：`fix/acceptance-r1`
- R1 提交：`34a5181 Fix acceptance blockers and add QA evidence`
- 本地试用地址：http://127.0.0.1:8787/
- 配置好的模型接入：Magpie 网关 `http://127.0.0.1:3425/v1`，协议 `responses`，模型 `group/claude-desktop-priority`

## 2. 本地启动

```powershell
cd app
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python -m playwright install chromium
.\.venv\Scripts\python run.py
```

打开 http://127.0.0.1:8787/ 。前置条件：Python 3.11+；视频需要 ffmpeg/ffprobe；Edge TTS 需要网络。

## 3. 本轮已修复

| 指令项 | 结果 |
|---|---|
| 事实可靠性 | venue 必须有来源才算确认；代码链接自动抽取后需人工确认归属；模型大小不作为数值结果；文案/视频/主页共用同一份确认事实 |
| Attention/BERT 复测 | Attention 保留有 OpenReview 来源的 NeurIPS 2017；BERT venue 为空时不再写会议名，且不再出现 tensor2tensor 错误链接 |
| 发布安全 P0 | approve 与 publish 服务端校验事实错误、版本、stale、文件存在性；未批准返回 blocked；Pages 推送后实际请求 URL，页面真实可访问才标记 live，否则 pending_verification |
| 完整体验 | 刷新后恢复上次项目；文案可编辑保存；重新生成产生可对比候选稿；异步任务带版本保护，旧版本结果不会覆盖新版本 |
| 传播矩阵 | 来源变化后自动准备文案/主页更新候选，人工稿保留；X/LinkedIn/微信/小红书明确为手动发布 |
| 模型接入 | 支持 Ollama/OpenAI 的 chat 协议与 Magpie 的 responses 协议；设置页可测试并自动提示可用协议 |
| 许可复用 | 更正 edge-tts 为 LGPL-3.0；说明 PyMuPDF AGPL/商业许可与三条合规路径；说明 ResearchStudio/pptx2video 仅参考、不复用的具体原因 |
| 统一验收 | 真实 Chromium 操作、API 门禁测试三篇论文与用户试用论文，保存截图、导出 ZIP 与报告 |

## 4. 验收证据

- `QA_FINAL_REPORT.md`：R1 实测报告与剩余限制
- `API_CHECKS.md`：接口级证据
- `docs/qa-r1/`：浏览器截图、四份导出 ZIP、来源检查脚本

关键实测结果：

- Magpie Responses API 测试：连接成功，返回 OK 与模型列表
- 浏览器刷新后仍停留在同一项目；人工编辑刷新后保留
- 视频 readyState=4，播放进度推进，无 console error
- 导出 ZIP 返回 200，排除 video_work 中间文件
- 未批准发布、stale 物料 approve、stale site publish 均被服务端阻断
- BERT 的 `384 MB` 与 tensor2tensor 不再进入生成物

## 5. 剩余限制

1. 视频可能超过 120 秒（BERT 约 126.8 秒），当前只警告不自动变速。
2. 未做依赖 CVE 扫描；公开分发前仍需处理 PyMuPDF 与 edge-tts 的许可义务。
3. 外部元数据 API 限流时，未确认字段留空，用户需在论文卡确认并填来源。
4. 真实 GitHub Pages 发布未执行：它会创建外部公开页面，仍需用户明确批准。
5. 候选稿对比按钮只在新候选与人工稿不同且人工稿仍保留时出现。

## 6. 给项目负责人 ChatGPT 的验收重点

请核对：事实门禁是否足够保守、发布阻断是否无可绕过、候选稿对比是否满足“可比较再采用”、三篇论文产物是否一致、许可说明是否可执行。通过后由 Human Decision Maker 再决定是否合并 master、公开发布或创建 Release。


---

## R2 增补交接（2026-11-21）

- R2 代码修复完成 commit：`06544ac`（分支 `fix/acceptance-r1`，Private）；后续证据与交接文档提交见该分支 `git log`，最终 HEAD 以交接时的 git 状态为准。
- PM 审查基线：`4ae76d5`
- 从基线到 R2 的主要变更：`22889d5` 启动/生成/调度/发布硬化；`6b67f72` + `06544ac` venue acronym 修正；`a0dbeef` 历史材料核对；`dcbd3b8` 事实与旁白文档澄清；证据提交 `f95e34d` / `65bbf31` / `f25e509` / `25ea18f` / `2b935f2`。
- 开发侧证据：`docs/qa-r2/developer/`（基线、ffprobe、最终状态）、`docs/qa-r2/export_clean_attention.zip`、`docs/qa-r2/export_clean_bert.zip`、`docs/qa-r2/facts_*.json`、`docs/qa-r2/magpie_check.json`。
- 独立验收报告：`QA_PRODUCT_REPORT_R2.md`（两位 Agent QA 因上下文/输出上限中断，主执行者据真实证据续接完成；D1–D8/D10 PASS，D9 部分 BLOCKED；建议有条件进入 PM/Human 最终复审）。
- 历史材料存在性核对：`EVIDENCE_MATERIALS_REVIEW/REPORT.md`。旧的 `_qa_product/QA_PRODUCT_REPORT.md` 仍是 2026-11-19 的历史 NOT ACCEPT 报告，不被 R2 覆盖。
- 第三篇真实论文证据：历史 QA 报告与截图中的 BERT（HTTP UI 上传、生成、播放与站点检查），本轮干净克隆也重新上传了 BERT；不要把第三篇写成未验证或未运行。
- GitHub 私有库持续维护；R3 已按 PM 指令转为公开仓库并创建 `v0.1.0` Release；未创建 GitHub Pages，未向真实社交平台发布。

## R3 最终开源交付（2026-11-24）

- 仓库：https://github.com/AIMetaPhD/paperrelay （public）
- Release：https://github.com/AIMetaPhD/paperrelay/releases/tag/v0.1.0
- 当前主分支：`master`；发布 tag：`v0.1.0`
- 工作区：仅保留根目录工程（`run.py`、`requirements.txt`、`backend/`、`frontend/`）；历史 `_handoff*`、`_g0*`、`_build_test`、旧 ZIP 已移到仓库外的私有归档，不进入公开仓库。
- 版本：`backend/__init__.py` 与 FastAPI 均为 `0.1.0`。
- 修复：D9 独立端口 SIGTERM 重启测试 `tests/test_restart_recovery.py`；中文旁白 `video_language=zh` + `zh-CN-YunxiNeural`，实测 62.176s / 1920x1080 / h264+aac；bundle 完成后的前端轮询自动重绘候选对比。
- 验证：`test_verify.py` 17 项全通过；`FINAL_QA_ACCEPTANCE_REPORT.md` D1–D10 全部 PASS，无 BLOCKED。
- 发布包：`PaperRelay-v0.1.0-source.zip`，已作为 Release asset 发布，不含论文样本或私有数据。
- 合规：自有代码 MIT；PyMuPDF AGPL/商业、edge-tts LGPL-3.0 说明见 `THIRD_PARTY_LICENSES.md`。论文 PDF/视频帧等再分发受限证据保存在私有归档，不进入公开仓库。
- 未完成：真实 GitHub Pages 部署和社交平台发布未执行，仍需单独人工授权。

## R4 后续演进交付（v0.1.1，2026-11-25）

- 环境自检：`GET /api/health/dependencies` + 设置页检查 Python / FFmpeg / Chromium / Edge TTS。
- 候选元数据：arXiv ID 与 OpenReview URL 查询只填入表单，不自动确认 venue。
- 文案复制 Markdown；项目主页生成 `share_long.png` 分享长图。
- 可选 PDF 引擎 `pypdf`（仅文本/链接，不含图裁切），默认仍为 PyMuPDF。
- 模型快速预设：Ollama / Magpie / OpenAI-compatible / vLLM / DeepSeek。
- GitHub Actions：`ci.yml` 跑 20 项回归测试；`pages.yml` 为带 Environment 审批的手动 Pages 部署。
- 社区：`CONTRIBUTING.md`、Issue 模板、PR 模板。
- 验证：`test_verify.py` 20 tests，0 failures；浏览器实测环境自检、Markdown 按钮、长图按钮均正常。
