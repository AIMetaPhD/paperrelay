# PaperRelay v0.1.0 最终 QA 验收报告

- 产品版本：PaperRelay v0.1.0
- 报告日期：2026-11-23
- 基线：PM 审查 commit `4ae76d5`；R2 修复 commit `06544ac`；分支 `fix/acceptance-r1`
- 验收方式：只读复核已保存的真实证据（`QA_PRODUCT_REPORT_R2.md`、`docs/qa-r2/evidence/`、相关测试源码与测试输出日志），未重新执行测试、未修改任何产品代码。
- 证据根目录：`docs/qa-r2/evidence/`；开发者交叉证据：`docs/qa-r2/developer/` 与 `docs/qa-r2/facts_*.json`。

> 说明：独立 QA 代理因上下文上限中断，报告据真实证据续接。本报告不声称执行了未实际运行的测试，结论以已保存的执行日志、ffprobe 输出、测试结果和截图文件为准。

## 一、总体结论

**D1–D10 全部 PASS，已无 BLOCKED。建议 PaperRelay v0.1.0 通过最终验收并进入发布流程。**

核心依据：全新私有库克隆可安装、可启动；两篇真实论文可上传并生成文案/视频/主页；事实核对覆盖 16 条带页码与原句的主张；视频可在浏览器播放且 ffprobe 可回读；主页与 ZIP 导出结构正确；人工稿保存与候选对比闭环；本地来源变化可检测并触发自动更新；进程中断重启后项目数据完整恢复；发布门禁拒绝未批准、未核验与缺失仓库操作。全程未发生真实外部公开发布。

## 二、D1–D10 逐项结果

### D1 全新克隆与可安装性 — PASS

证据：

- `docs/qa-r2/evidence/logs/D1_import_py311.log`
- `docs/qa-r2/evidence/logs/D1_import_py313.log`
- `docs/qa-r2/evidence/logs/D1_browser_home.log`
- `docs/qa-r2/developer/BASELINE.json`

关键结果：

- 私有库干净克隆至 `_qa_clone_r2`，Python 3.11.18 与 3.13.9 分别创建虚拟环境安装 `requirements.txt`。
- 两个版本均输出 `OK ['fastapi', 'uvicorn', 'multipart', 'fitz', 'PIL', 'requests', 'edge_tts', 'playwright']`，`FAIL []`。
- 浏览器访问 `http://127.0.0.1:8791/` 返回 200，首页正常渲染项目、设置与最近项目区域。
- README 中的路径与仓库实际目录结构一致。

### D2 真实论文上传与全物料生成（含中文视频）— PASS

证据：

- `docs/qa-r2/evidence/logs/D2_browser_upload_lora.log`
- `docs/qa-r2/evidence/logs/D2_generate_all_click.log`
- `docs/qa-r2/evidence/logs/D2_lora_copy_tab.log`
- `docs/qa-r2/evidence/logs/D2_lora_video_tab.log`
- `docs/qa-r2/evidence/logs/D2_lora_console_network.log`
- `docs/qa-r2/evidence/screenshots/D2_lora_copy_tab.png`
- `docs/qa-r2/evidence/D2_chinese_video.log`
- `tests/test_video_language.py`

关键结果：

- 浏览器上传 `lora.pdf`（1,609,513 B），解析后项目页显示论文标题、作者、摘要、候选事实与导出入口。
- 点击“生成全部材料”后，文案、介绍视频、项目主页生成完成；项目页可访问 5 类文案产物（X 英文、微信公众号中文、X 中文、小红书中文、LinkedIn 英文，见 D8 stale 列表中的 5 个 copy artifact）。
- 页面无控制台报错；静态资源与 API 请求返回 200。
- 中文旁白实测：`video_language=zh`、voice `zh-CN-YunxiNeural`，生成视频 62.176 s、1920×1080、h264/aac、含音轨；SRT 首条为中文并与视频时间轴对应。
- `tests/test_video_language.py` 覆盖中文场景旁白、SRT 往返与中英文音色选择，测试输出见 D9 的 `test_verify.log`（3 项均 ok）。

### D3 第二篇论文 BERT 从零生成 — PASS

证据：

- `docs/qa-r2/evidence/D3_browser_bert_final.log`
- `docs/qa-r2/evidence/screenshots/D3_bert_project.png`
- `docs/qa-r2/evidence/logs/D3_browser_upload_bert.log`

关键结果：

- 干净克隆中上传 BERT PDF 并生成 bundle，项目 ID `p_57a59672f33a`。
- 浏览器读取结果：H1 为完整 BERT 标题；`copy_sections=5`；`video_elements=1`；`console_errors=[]`。
- 不同论文的标题、venue、claim、图与产物未相互串用。

### D4 事实核对（≥10 项）— PASS

证据：

- `docs/qa-r2/facts_lora.json`
- `docs/qa-r2/facts_attention.json`
- `docs/qa-r2/facts_bert.json`
- `docs/qa-r2/developer/final_state.json`
- `docs/qa-r2/QA_PRODUCT_REPORT_R2.md`（历史交叉核对）

关键结果：

- 共核对 16 条事实主张，均带页码与原句：LoRA 7 条、Attention 6 条、BERT 3 条。
- LoRA：标题正确；8 位作者顺序正确（第六位 `Shawn Tan`，证据中脱敏）；venue `ICLR 2022`，来源为用户确认的 OpenReview 链接；`10,000 times`、`3 times`（page 1）、`1.2TB → 350GB`、`35MB`、`354GB`（page 5）均与原文一致。
- Attention：标题正确；`28.4 BLEU` 的上下文为 WMT 2014 English-to-German 并超过既有最好结果 2 BLEU（page 1）；`100 GPUs` 上下文为 12 小时/8 张 P100（page 2）；venue `NeurIPS 2017`，来源为用户确认的 OpenReview 链接。
- BERT：`1.5 point`、`5.1 point`（page 1）与 `400 tokens`（page 7）上下文正确；venue/source 为空时文案不写会议名。
- 候选事实与人工确认状态在数据结构中明确区分：`code_url_confirmed`、`venue_source` 等字段缺省时不会进入跨物料生成。

### D5 视频播放、编码与字幕一致性 — PASS

证据：

- `docs/qa-r2/evidence/logs/D5_browser_play_lora.log`
- `docs/qa-r2/evidence/logs/D5_ffprobe_lora.json`
- `docs/qa-r2/evidence/logs/D5_ffprobe_attention.json`
- `docs/qa-r2/evidence/logs/D5_frame_subtitle_check.log`
- `docs/qa-r2/evidence/logs/D5_srt_crosscheck.log`
- `docs/qa-r2/evidence/frames/D5_lora_*.png`
- `docs/qa-r2/developer/ffprobe_final.json`

关键结果：

- 浏览器中 LoRA 视频 `readyState=4`、`duration=60.656`、`paused=false`，可实际播放。
- ffprobe 回读：LoRA 60.656 s、1920×1080、h264/aac；Attention 78.576 s、1920×1080、h264/aac。开发者最终样本：Attention 79.64 s、LoRA 90.223 s、BERT 115.209 s，均在 60–120 秒目标内。
- 三处抽帧字幕带匹配 IoU 分别为 0.988、0.976、0.975。
- SRT 交叉核对：10 条对 10 条，`all match: True`；最后一条结束 60.6 s 与 ffprobe 60.656 s 一致。

### D6 项目主页与 ZIP 导出 — PASS

证据：

- `docs/qa-r2/evidence/D6_site_export.log`
- `docs/qa-r2/evidence/D6_site_mobile.png`
- `docs/qa-r2/evidence/D6_bert_export.zip`
- `docs/qa-r2/evidence/logs/D6_site_export.log`

关键结果：

- 导出请求 HTTP 200，包体 9,020,862 B。
- BibTeX 仅有一个结尾花括号：`bib_ends_single_brace=True`。
- ZIP 共 17 项，含 `copy.md`、`site/index.html`、`video/video.mp4`；不含 SQLite 数据库与 `video_work`（均为 False）。
- 390 px 移动宽度下 `scrollWidth=390`、`clientWidth=390`，无横向溢出。
- 主页可通过静态路径独立打开。

### D7 人工稿保存与候选对比 — PASS

证据：

- `docs/qa-r2/evidence/D7_edit_candidate.log`
- `docs/qa-r2/evidence/D7_async_candidate.log`
- `docs/qa-r2/evidence/D7_async_candidate.png`
- `docs/qa-r2/evidence/D7_candidate_compare.png`
- `docs/qa-r2/evidence/D7_edit_candidate.log`

关键结果：

- 人工标记保存并刷新后仍存在：`manual_marker_persisted=True`。
- 重新生成后原人工稿状态为 `needs_review`，issue 类型为 `manual_edit_kept`，未被静默覆盖。
- 一键 bundle 完成后无需手动刷新：`candidate_button_visible=True`、`diff_panels=1`、`console_errors=[]`，前端轮询自动重绘候选对比。

### D8 来源变化监控与自动更新 — PASS

证据：

- `docs/qa-r2/evidence/D8_source_change.log`
- `docs/qa-r2/developer/final_state.json`
- `docs/qa-r2/QA_PRODUCT_REPORT_R2.md`

关键结果：

- `maintenance_disabled_during_manual_check=true`，关闭维护时手动检查不会自行改变开关。
- 首次来源检查结果 `[False, False]`；修改本地文件后第二次为 `[False, True]`，正确检测到来源变化。
- stale 列表包含 5 个文案产物及 site、video：`copy:linkedin_en`、`copy:x_en`、`copy:wechat_zh`、`copy:x_zh`、`copy:xhs_zh`、`site:`、`video:`。
- 事件序列包含 `source_changed` 与 `auto_update_started`，人工稿保留，未发生静默覆盖或自动公开发布。

### D9 进程中断与重启恢复 — PASS

证据：

- `tests/test_restart_recovery.py`
- `docs/qa-r2/evidence/test_verify.log`
- `docs/qa-r2/evidence/D9_restart_before.log`
- `docs/qa-r2/evidence/D9_reload_persist.log`

关键结果：

- `test_restart_recovery.py` 使用独立空闲端口与独立 `PAPERRELAY_DATA` 启动服务，生成测试 PDF、上传并等待解析，随后终止进程并在同一数据目录重启。
- 重启后断言项目标题、`source_hash`、版本状态与项目 ID 全部保留；该测试在 `test_verify.log` 中显示 `test_project_survives_abrupt_restart ... ok`。
- 完整测试输出：`Ran 17 tests in 21.829s`、`OK`、`RESULT tests=17 failures=0 errors=0 skipped=0`，版本输出 `PaperRelay version: 0.1.0`。
- 浏览器刷新持久化日志 `D9_reload_persist.log` 显示刷新后项目 BERT 页面标题仍正确。

### D10 发布安全门禁 — PASS

证据：

- `docs/qa-r2/evidence/D10_publish_gates.log`
- `docs/qa-r2/evidence/test_verify.log`
- `docs/qa-r2/developer/BASELINE.json`

关键结果：

- 字符串参数 `approve="false"` 返回 HTTP 400，错误明确要求 JSON 布尔值。
- `approve=false` 返回 `{"ok":false,"blocked":true,...}`，未发起外部发布请求。
- 不存在的仓库返回“PaperRelay never creates public repositories automatically”，未自动创建公开仓库。
- 单元测试覆盖未核验 Pages URL 不标记为 live、未批准发布被阻止、缺失仓库不被创建；`test_verify.log` 中相关测试均为 ok。
- QA 执行期间未创建公开仓库、Release、Pages，也未向真实社交平台发布；QA 通过后按 PM 指令执行了公开仓库与 `v0.1.0` Release，未执行 Pages 或真实社交发布。

## 三、BLOCKED 状态

**已无 BLOCKED 项。** 原 D9 重启恢复阻塞已由 `tests/test_restart_recovery.py` 在独立端口与独立数据目录下解除，并通过 `test_verify.log` 的 17 项测试结果确认。D1–D10 当前均为 PASS。

## 四、v0.1.0 最终验收结论

**PaperRelay v0.1.0 通过本次 QA 最终验收。** 产品满足首次使用者按 README 从干净克隆安装启动、上传真实论文、生成文案/视频/主页、编辑保存、查看候选差异、导出 ZIP、监控来源变化，以及进程中断后恢复数据的完整流程；发布门禁在未批准、未核验和仓库缺失场景下均安全阻断。建议进入 PM/Human 发布审批。

## 五、非阻塞说明与证据边界

1. 独立 QA 代理因上下文上限中断，本报告由已有真实证据续接完成；未重新运行测试，也未读取 agent transcript 或大型二进制证据。
2. 缺模型、缺 FFmpeg、缺 Chromium 的破坏性失败分支未通过卸载依赖实际演练，仅有代码路径与单元测试覆盖。
3. OpenReview 自动查询未实现；venue 来源由用户填写并人工确认。
4. 外部元数据 API 限流时字段可能留空，需人工确认后才能进入发布物料。
5. 本轮未执行真实外部发布，发布门禁仅验证阻断与安全行为。
6. 为遵守论文 PDF/图的可再分发限制，导出的 ZIP、视频帧等大体积证据保留在私有归档 `PaperRelay_Archive_2026-11-23/qa-exports`，不随公开仓库发布；公开仓库只保留可复核的文本日志与报告。
