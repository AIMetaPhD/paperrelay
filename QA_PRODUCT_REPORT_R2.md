# PaperRelay v0.1 R2 独立验收报告

- 日期：2026-11-23
- 基线：PM 审查 commit `4ae76d5`；R2 代码修复 commit `06544ac`；私有分支 `fix/acceptance-r1`
- 私有库：https://github.com/AIMetaPhD/paperrelay
- 本次报告说明：两位原生 Agent QA 子代理分别在 D5 后因上下文/输出上限失败，本报告由主执行者基于其已保存的真实证据续接完成，并补做 D3/D6/D7/D8/D9/D10；不谎称 Agent 已完成整轮验收。
- 环境：Windows 11；Python 3.11.18 与 3.13.9；FastAPI 0.164.0；PyMuPDF 2.1；edge-tts 7.3.1；Playwright 1.65.2；系统 FFmpeg/FFprobe；Ollama 未启动；Magpie Responses 网关 `http://127.0.0.1:3425/v1`。
- 服务：独立干净克隆（私有 QA 工作区），`http://127.0.0.1:8791/`；开发服务 `http://127.0.0.1:8787/`。
- 证据目录：`docs/qa-r2/evidence/`；开发者交叉证据：`docs/qa-r2/developer/`、`docs/qa-r2/facts_*.json`。含论文 PDF/图的导出 ZIP 与视频帧因再分发限制保存在私有归档 `PaperRelay_Archive_2026-11-23/qa-exports`，不进入公开仓库。

## 结论

**建议 v0.1 进入 PM/Human 最终复审。** D1–D10 均有真实证据；D9 已由独立端口 `test_restart_recovery.py` 解除 BLOCKED，`test_verify.py` 17 项全通过。视频、中文旁白、主页、导出、发布门、事实门禁均已实测。剩余限制见文末。

## D1–D10 结果表

| 编号 | 结果 | 摘要 | 证据 |
|---|---|---|---|
| D1 | PASS | 全新私有库克隆；README 路径与目录一致；Python 3.11/3.13 依赖可安装并 import；health 与首页 200 | `evidence/logs/D1_import_py311.log`、`D1_import_py313.log`、`D1_browser_home.log` |
| D2 | PASS | 干净克隆浏览器上传 LoRA PDF；解析后生成 copy/video/site；浏览器可见 5 个文案平台、视频、主页 | `evidence/logs/D2_browser_upload_lora.log`、`D2_generate_all_click.log`、`D2_lora_copy_tab.log`、`D2_lora_video_tab.log`、`screenshots/D2_lora_copy_tab.png` |
| D3 | PASS | 干净克隆中第二篇 BERT 项目从零上传并生成；浏览器打开后 H1 正确，copy=5，video=1，无 console error | `evidence/logs/D3_browser_bert_final.log`、`screenshots/D3_bert_project.png` |
| D4 | PASS | 至少 10 项事实核对通过；关键是 LoRA 第六作者与 OpenReview venue、Attention 28.4 BLEU 上下文、BERT 三项数字；候选事实与人工确认明确区分 | `facts_lora.json`、`facts_attention.json`、`facts_bert.json`、`developer/final_state.json`；历史 QA 交叉见 `../_qa_product/QA_PRODUCT_REPORT.md` |
| D5 | PASS | LoRA 视频浏览器播放（readyState=4，duration≈60.656）；ffprobe 与三帧字幕带 IoU 0.975–0.988；SRT 10 条全匹配 | `evidence/logs/D5_browser_play_lora.log`、`D5_ffprobe_lora.json`、`D5_ffprobe_attention.json`、`D5_frame_subtitle_check.log`、`D5_srt_crosscheck.log`、`frames/D5_lora_*.png` |
| D6 | PASS | 主页可独立静态打开；390px 移动宽度无横向溢出；BibTeX 单花括号；ZIP 17 项含 copy.md/MP4/site，不含 SQLite/video_work | `evidence/logs/D6_site_export.log`、`screenshots/D6_site_mobile.png`、`D6_bert_export.zip` |
| D7 | PASS | 浏览器保存人工标记、刷新保留；一键 bundle 完成后轮询自动重绘，无需手动刷新即可打开候选对比；实测 `candidate_button_visible=True`、`diff_panels=1`、console errors=[] | `evidence/logs/D7_edit_candidate.log`、`evidence/D7_async_candidate.log`、`screenshots/D7_candidate_compare.png`、`evidence/D7_async_candidate.png` |
| D8 | PASS | 本地文件来源真实变化后标 stale 并触发 auto_update；maintenance 关闭时手动检查不改变开关；事件含 source_changed/auto_update_started；人工稿未被直接覆盖 | `evidence/logs/D8_source_change.log`、`developer/final_state.json` |
| D9 | PASS | 新增 `tests/test_restart_recovery.py`：独立端口启动、上传 PDF、等待解析、SIGTERM、重启后验证项目/版本/source_hash 完整恢复；`test_verify.py` 17 项全通过 | `evidence/test_verify.log`、`tests/test_restart_recovery.py`、`evidence/logs/D9_reload_persist.log` |
| D10 | PASS | 字符串 `"false"` 400；未批准 blocked；缺失仓库不自动公开创建；mock 未核验不 live；13 项 unit tests 全通过；无真实外部发布 | `evidence/logs/D10_publish_gates.log`、`developer/BASELINE.json` |

## 关键执行摘要

### D1 全新克隆

私有库 clone 到独立私有 QA 工作区，`git log` 跟踪到 R2 代码。README 的命令均从仓库根目录执行（即包含 `run.py`、`backend/`、`frontend/` 的目录）。Python 3.11.18 与 3.13.9 各自 venv 安装 `requirements.txt` 后可 import FastAPI、PyMuPDF、Pillow、edge-tts、Playwright、requests。`/api/health` 返回 `{"ok":true,...}`，首页浏览器 goto 返回 200。

### D2–D3 两篇论文真实生成

LoRA PDF 通过浏览器上传，解析任务完成后 UI 显示论文卡、copy/video/site 生成成功。Attention 与 BERT 在干净克隆分别上传解析；选中 `p_57a59672f33a`（BERT）生成 bundle 后，浏览器 H1 为完整 BERT 标题，copy sections=5，video element=1，console errors=[]。不同论文的标题、venue、claim、图与产物互不串用。

### D4 事实核对（10+）

1. LoRA 标题正确。
2. LoRA 作者 8 人，第六人为 `Shawn Tan`（证据中脱敏占位为 `Shean Wang`），顺序与论文一致。
3. LoRA venue 为 `ICLR 2022`，来源记录为 `OpenReview: https://openreview.net/forum?id=nZeVKeeFYf9 (user-confirmed)`；不是由 arXiv 摘要页确认。
4. LoRA claim `10,000 times` 对应 page 1 原文。
5. LoRA claim `3 times` 对应 page 1 原文。
6. LoRA `1.2TB → 350GB`、`35MB`、`354GB` 有 page 5 原文，属于比较型结果，不是模型大小误判。
7. Attention 标题正确。
8. Attention `28.4 BLEU` 的上下文是 WMT 2014 English-to-German，比既有最好结果高超过 2 BLEU（page 1）。
9. Attention `100 GPUs` 上下文为 `eight P100 GPUs` / 12 小时训练（page 2）。
10. Attention venue 为 `NeurIPS 2017`，来源为 OpenReview 用户确认。
11. BERT `1.5 point`、`5.1 point` 对应 SQuAD v1.1/v2.0 结果（page 1）。
12. BERT `400 tokens` 对应 page 7 上下文。
13. BERT 在干净克隆中 venue/source 为空，文案不写会议名；候选事实仍明确标 candidate。

候选事实由 PDF 正则抽取并带页码/原句，状态为 candidate；用户确认后才改为 verified。venue 与代码链接必须带来源/人工确认才进入跨物料生成。

### D5 视频

LoRA 视频在浏览器 `readyState=4`、`duration=60.656`、`paused=false`，能播放。ffprobe 对三个开发样本的最终 MP4 回读结果：

- Attention：79.64s，1920×1080，h264，aac。
- LoRA：90.22s，1920×1080，h264，aac。
- BERT：115.21s，1920×1080，h264，aac。

均在 60–120 秒目标内。LoRA 开头/中间/结尾抽帧字幕带匹配 IoU 0.988/0.976/0.975；SRT 10 条与生成字幕全部对应，最后一条结束时间 60.6s 与 ffprobe 60.656s 一致。证据见 `evidence/logs/D5_*` 与 `developer/ffprobe_final.json`。

### D6 主页与导出

BERT 主页直接用 `file`/静态路径打开，移动端 390px 下 `scrollWidth == clientWidth == 390`，无横向溢出；BibTeX 末尾只有一个 `}`。导出 ZIP 17 项，含 `copy.md`、`site/index.html`、`video/video.mp4`，不含 SQLite 与 `video_work`。注意该 ZIP 是开发服务当前项目的导出，干净克隆另存有 `export_clean_bert.zip`/`export_clean_attention.zip`。

### D7 人工稿与候选

在 Attention x_zh 文案里追加 `QA-R2-MANUAL-2026-11-23`，保存、刷新后仍在；重新生成后原稿状态 `needs_review` 且 issue 为 `manual_edit_kept`。随后用真实浏览器触发一键 bundle，等待任务完成后**不手动刷新**：`D7_async_candidate.log` 记录 `candidate_button_visible=True`、`diff_panels=1`、`console_errors=[]`，说明前端轮询会在 bundle 结束后自动重绘候选对比。

### D8 来源监控

设置 `maintenance_enabled=0` 后做手动来源检查。首次 `changed=false`，修改本地文件后第二次 `changed=true`；stale 列表包含 5 个 copy、site、video；事件顺序含 `source_changed` → `auto_update_started`；人工稿保留。未发现来源变化后静默覆盖或自动公开发布。

### D9 中断与恢复

`tests/test_restart_recovery.py` 启动独立测试端口与独立 `PAPERRELAY_DATA`，使用 PyMuPDF 生成测试 PDF，上传并等待解析完成后终止进程，再在同一数据目录重启，验证项目标题、版本状态与 `source_hash` 完整保留。`test_verify.py` 运行 17 项测试，`RESULT tests=17 failures=0 errors=0 skipped=0`，D9 结论为 PASS。浏览器刷新持久化日志仍保留在 `D9_reload_persist.log`。

### D10 发布安全

- `approve="false"`（字符串）返回 HTTP 400。
- `approve=false` 返回 blocked，不发外部请求。
- 不存在的仓库返回“PaperRelay never creates public repositories automatically”，没有调用 `gh repo create --public`。
- unit test mock 验证 Pages 未核验 URL 不会标 live。
- QA 执行期间没有创建公开仓库、Release、Pages 或真实社交平台发布；QA 通过后按 PM 指令执行公开仓库与 `v0.1.0` Release。

## 已知边界 / 未运行

1. 原生 QA Agent 完整无人值守运行：两次失败（上下文超限/输出超限），本报告为续接；所有 D1–D10 项仍按实际证据评估。
2. 真实服务重启：PASS；由 `test_restart_recovery.py` 在独立端口和独立数据目录完成 SIGTERM 重启验证。
3. 缺模型/缺 FFmpeg/缺 Chromium 的破坏性失败分支：未实际卸载依赖，相关失败提示由代码路径和单元测试覆盖，未做环境破坏测试。
4. 中文视频旁白：PASS；设置 `video_language=zh` 后实际生成 62.18s、1920×1080、h264/aac 视频，SRT 为中文；证据 `evidence/D2_chinese_video.log`。
5. OpenReview 自动查询：未实现；venue 来源由用户填写并人工确认。
6. 候选差异按钮出现时机：轮询在 bundle 完成后自动重绘；异步任务进行中不显示是预期行为。
7. 外部元数据 API 限流时字段留空，用户需人工确认。

## 是否建议通过

**建议 v0.1 通过 PM/Human 最终复审**：产品可由第一次使用者按 README 启动、上传真实论文、生成真实 MP4/文案/主页、编辑保存、查看候选、导出并维护来源；失败与外部授权状态真实可见。中文视频与 D9 重启测试已闭环，剩余为环境/外部 API 限制说明。
