# 既有交付材料核对（PM 指令第 2 节）

核对时间：2026-11-21。只做存在性与来源核对，不把旧文件当成 R2 新产物。

| 材料 | 状态 | 路径 | 说明 |
|---|---|---|---|
| 原始 QA 报告 | AVAILABLE | ../_qa_product/QA_PRODUCT_REPORT.md | 2026-11-19 独立 QA，结论 NOT ACCEPT，D1–D10 旧编号在该文件中定义；本轮 R2 报告不改写旧结论 |
| 构建测试目录与截图 | AVAILABLE | ../_build_test/ | 含 attention.pdf、copy_all*.md、export.zip、project.json、pw*.png；另有 chrome-profile 浏览器缓存，属临时物，不纳入正式证据包 |
| LoRA 原始 PDF | AVAILABLE | ../_g0/paper/LoRA_2106.09685.pdf；../_qa_fixtures/lora.pdf | 本地测试样本 |
| LoRA MP4/SRT/主页 | AVAILABLE | data/projects/p_7f4294920255/video/video.mp4；.../video.srt；.../site/index.html | 既有开发态产物，非本轮干净克隆产物 |
| Attention MP4/SRT/主页 | AVAILABLE | data/projects/p_57ffd75ed97b/... | 既有开发态产物 |
| BERT MP4/SRT/主页 | AVAILABLE | data/projects/p_823c288e1cb8/... | 既有开发态产物 |
| 第三篇论文证据 | AVAILABLE | ../_qa_product/QA_PRODUCT_REPORT.md、../_qa_product/screenshots/、../_qa_product/frames/、data/projects/p_823c288e1cb8/ | 第三篇为 BERT；旧 QA 报告第 1/2 节有真实 UI 上传与产物记录；R2 干净克隆也重新上传了 Attention 与 BERT |
| IMPLICIT_STATE_MACHINES.md | AVAILABLE | ../IMPLICIT_STATE_MACHINES.md | 30 KB，仅作背景文档，未实现为运行时框架 |
| 既有旧的交付 ZIP | AVAILABLE | ../PaperRelay_G0_Handoff_2026-11-16.zip、../PaperRelay_Handoff_2026-11-19_v2.zip、../PaperRelay_R1_Handoff_2026-11-20.zip | 仅核对存在性；R2 交付包单独生成 |

结论：PM 要求查找的材料本机均存在。旧材料没有提交到 Git，但未丢失。R2 独立 QA 报告将只引用这些文件作为“历史材料核对”，不把它们当作 R2 干净环境新生成结果。
