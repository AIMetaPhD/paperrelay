# PaperRelay 修复轮最终验收记录（R1）

- 时间：2026-11-20
- 环境：http://127.0.0.1:8787/，Chromium（Playwright），Magpie gateway `http://127.0.0.1:3425/v1` / Responses API
- 仓库：`AIMetaPhD/paperrelay`，分支 `fix/acceptance-r1`，保持 Private
- 说明：这是可复核的实测记录，不是模拟页面；没有执行任何公开仓库创建、公开 Release 或 AIMetaPhD 开源列表修改。

## 结论

**PASS（本地可试用，公开发布仍单独批准）**。R1 修复覆盖了事实门禁、发布门禁、候选稿对比、异步任务版本保护、传播矩阵自动候选、协议接入与许可说明。剩余限制见文末。

## 1. 模型接入

-  configs 中的 Magpie 网关：`base_url=http://127.0.0.1:3425/v1`，协议 `/responses`。
-  在 UI 设置页配置 `llm_wire_api=responses`、模型 `group/claude-desktop-priority`，点击“测试连接”。
-  实测结果：`连接成功（responses）：OK · 模型 group/claude-desktop-priority, group/openrouter, ...`
-  `/v1/chat/completions` 在该网关返回 404，因此不能只把 Base URL 从 Ollama 换成 Magpie；R1 增加了协议选项与自动探测提示。

## 2. 事实可靠性

-  Venue 只有在 `venue + venue_source` 同时存在时才算确认。未确认时，文案/视频/主页不会写会议名；模板里明确写“未确认”。
-  代码链接自动抽取需要语义证据。BERT 的 `tensorflow/tensor2tensor` 脚注链接不再被抽取；自动抽取的链接标记为未确认，只有用户在论文卡中勾选“我已核对”后才进入文案与主页。
-  事实过滤：无比较语境的模型大小（例如 trial 项目的 `384 MB`）不再作为数值 claim。BERT 的 3 条结果型 claim 保留。
-  文案、视频、主页共享 `backend/facts.py` 的确认事实视图。`384 MB` 不再出现在生成站点。
-  复测：
  - Attention：venue 有 OpenReview 来源；站点显示 `NeurIPS 2017`，视频状态 ready。
  - BERT：venue 空、来源空；站点不再出现 venue，生成文案中主动声明未确认；`tensorflow/tensor2tensor` 不再出现。
  - LoRA：venue 和代码链接均有人工确认来源；链接为 `https://github.com/microsoft/LoRA/releases`。

## 3. 发布安全

API 实测：

| 场景 | 结果 |
|---|---|
| 未勾选批准发布 | 200，blocked，不创建任何外部资源 |
| 对 stale 物料调用 approve | 409，明确要求重新生成 |
| 对 stale site 调用 publish(approve=true) | 409，不执行外部写入 |
| 对已 approved 的 copy 再 approve | 400，状态检查生效 |
| publish_site 推送成功但页面未上线 | 返回 `verified=false`，数据库状态 `pending_verification`，不标记 live |

发布前服务端会校验：目标物料当前版本、事实错误、stale 状态、项目主页文件/MP4 存在性。Pages 状态通过轮询构建与实际请求 URL 双重确认；只有页面内容匹配才写 `state=live`。

## 4. 完整产品体验（Chromium 实测）

-  首页 5 张项目卡；打开 BERT 项目后刷新，URL 与 H1 保持不变（修复“刷新后像丢失”的体验）。
-  5 个平台文案均呈现。
-  人工编辑 x_zh 后保存，刷新再次打开后 `QA-MANUAL-2026-11-20` 标记仍在。
-  候选稿 API 返回候选内容；UI 增加“候选稿对比”并排差异视图（当前环境因为 x_en 已 approved，页面未渲染待审核候选按钮；API 已验证）。
-  视频：`readyState=4`，`duration≈126.8s`，播放后 `currentTime≈2.47`，无 error；MP4/SRT/VTT 可下载。
-  项目主页 iframe `readyState=complete`；导出 ZIP 返回 200，约 9.8 MB，排除 `video_work` 中间文件。
-  设置页已显示协议选项，Magpie 测试连接通过。
-  浏览器 console errors：0。

## 5. 传播矩阵自动维护

-  来源变化时，变更源所涉及的物料先标记 stale。
-  若 `maintenance_auto_update=1`（默认），`_auto_update_candidates` 触发文案与主页后台重生成，人工修改保留，新结果进入候选/待审核，不自动覆盖人工稿。
-  UI 明确列出 X / LinkedIn / 微信公众号 / 小红书为“手动发布”，未冒充已自动发布。

## 6. 许可与复用

`THIRD_PARTY.md` 已按安装包 metadata 校正：

-  PyMuPDF 2.1：AGPL-3.0 或 Artifex 商业许可；给出三条公开发布路径（本地私有使用、商业授权、替换库）。
-  edge-tts 7.3.1：LGPL-3.0（不是之前记录的 GPL-3.0），说明保持独立可替换依赖与随附许可证的要求。
-  说明 ResearchStudio / pptx2video 未复用的具体原因（引入 notebook/Node runtime、状态与事实门禁架构不匹配），不泛泛而谈。

## 7. 剩余限制

1.  视频时长仍可能超过 120 秒（BERT 实测约 126.8 秒），当前只给 warning，不自动变速；不影响真实性，但需调整 UI 承诺或后续加入目标时长约束。
2.  Python 依赖未做 CVE 扫描，PyMuPDF/edge-tts 的公开分发义务仍需法务/商业 decision。
3.  三篇论文中的 Attention/BERT 外部元数据 API 可能限流；未确认字段一律留空，由用户在论文卡手工确认并填来源。
4.  候选稿对比 UI 只在有未采用候选且人工稿仍保留时显示；这符合设计，但需要保存人工稿后再重生成才会出现按钮。
5.  真实 GitHub Pages 发布没有执行（需要用户明确批准且会创建外部公开页面），代码路径通过未批准、stale 阻断与 verified 判定验证。

## 8. 补充证据（source change 与手工稿保留）

-  本地来源初次登记检查：`changed=false`。
-  修改来源文件后再次检查：`changed=true`，事件顺序为 `source_changed` → `auto_update_started`。
-  自动更新任务触发后，site 作业完成并在制品记录中回到 ready；copy 作业保留人工稿并把新生成内容写入候选版本，不直接覆盖。
-  三篇论文与用户试用论文的导出 ZIP 均返回 200，保存在 `docs/qa-r1/`。
-  浏览器截图保存在 `docs/qa-r1/`。
