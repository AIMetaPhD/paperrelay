# R1 API evidence

| Check | HTTP | Evidence |
|---|---|---|
| `/api/health` | 200 | `{"ok":true,"app":"PaperRelay","version":"0.1.0"}` |
| settings/test with Magpie Responses | 200 | `{"ok":true,"reply":"OK","wire":"responses"}` (UI showed model groups) |
| reparse trial | 200 | produced a new parse job |
| artifact candidate endpoint | 200 | `has_candidate=true`, `candidate_chars=794` |
| approve current x_en | 200 | status became ready |
| approve already-ready artifact | 400 | `Cannot approve from status ready` |
| publish with `approve=false` | 200 | `blocked=true`, no external action |
| approve stale artifact | 409 | `This artifact is stale. Regenerate it before approving.` |
| publish stale site with approve=true | 409 | `The project page is 'stale'. Approve it before publishing.` |
| BERT generation | jobs succeeded | copy/video/site all succeeded; video readyState=4, duration≈126.8s, playback advanced |
| Attention generation | jobs succeeded | site shows confirmed venue; video succeeded |
| LoRA generation | jobs succeeded | site has user-confirmed code link; no tensor2tensor |
| Trial generation | jobs succeeded | no unsupported numeric claim; no code link; no venue |
| export ZIP | 200 | 9,842,427 bytes; `video_work` excluded |
