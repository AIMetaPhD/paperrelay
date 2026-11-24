const S = {
  projects: [],
  project: null,
  settings: null,
  tab: "overview",
  pollTimer: null,
  lastVideoKey: "",
  wasPolling: false,
};

const $ = (sel) => document.querySelector(sel);
const main = $("#main");

const PLATFORM = {
  x_en: { label: "X / Twitter · English", hint: "3–5 条 thread，首帖独立可读" },
  x_zh: { label: "X / Twitter · 中文", hint: "中文短帖" },
  linkedin_en: { label: "LinkedIn · English", hint: "职业向介绍" },
  wechat_zh: { label: "微信公众号 · 中文", hint: "介绍稿，可粘贴" },
  xhs_zh: { label: "小红书 · 中文", hint: "带 emoji 的分享稿" },
};

const STATUS = {
  absent: "未生成", generating: "生成中", draft: "草稿", needs_review: "待核查",
  ready: "可发布", stale: "已过期", failed: "失败", queued: "排队中",
  running: "运行中", succeeded: "完成", parsed: "已解析", needs_input: "需补充",
  published: "已发布", live: "在线", superseded: "已被新版本取代",
  pending_verification: "待线上核验", manual: "手动发布",
};

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function pill(status) {
  return `<span class="pill ${esc(status)}">${esc(STATUS[status] || status)}</span>`;
}

function fmtTime(ts) {
  if (!ts) return "";
  const d = new Date(ts * 1000);
  return d.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const text = await response.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = { raw: text }; }
  if (!response.ok) {
    const message = data?.detail || data?.error || data?.raw || response.statusText;
    throw new Error(typeof message === "string" ? message : JSON.stringify(message));
  }
  return data;
}

function renderDiff(current, candidate) {
  const curLines = current.split("\n");
  const candLines = candidate.split("\n");
  const curSet = new Set(curLines);
  const candSet = new Set(candLines);
  const side = (lines, other) => lines
    .map((line) => `<div class="${other.has(line) ? "diff-same" : "diff-change"}">${esc(line) || "&nbsp;"}</div>`)
    .join("");
  return `<div class="diff-grid">
    <div><div class="small muted">当前稿</div><pre class="diff">${side(curLines, candSet)}</pre></div>
    <div><div class="small muted">候选稿（本次重新生成）</div><pre class="diff">${side(candLines, curSet)}</pre></div>
  </div>`;
}

function toast(message, error = false) {
  const el = $("#toast");
  el.textContent = message;
  el.className = `toast show${error ? " error" : ""}`;
  clearTimeout(el._timer);
  el._timer = setTimeout(() => { el.className = "toast"; }, 3800);
}

async function loadProjects() {
  S.projects = await api("/api/projects");
  renderSideProjects();
}

function renderSideProjects() {
  const box = $("#side-projects");
  if (!S.projects.length) {
    box.innerHTML = `<div class="small muted" style="padding:8px 10px">还没有项目</div>`;
    return;
  }
  box.innerHTML = S.projects.map((p) => {
    const active = S.project?.id === p.id ? "active" : "";
    const title = p.version?.title || p.name;
    return `<a class="${active}" href="#/project/${p.id}">${esc(title)}</a>`;
  }).join("");
}

async function loadProject(id, { silent = false } = {}) {
  S.project = await api(`/api/projects/${id}`);
  try { localStorage.setItem("paperrelay:last", id); } catch {}
  renderSideProjects();
  if (!silent || document.activeElement?.tagName !== "TEXTAREA") renderProject();
  schedulePoll();
}

function schedulePoll() {
  clearTimeout(S.pollTimer);
  if (!S.project) return;
  const active = (S.project.jobs || []).some((j) => ["queued", "running"].includes(j.status));
  if (!active) {
    if (S.wasPolling) {
      S.wasPolling = false;
      // A bundle just finished: redraw immediately so candidate compare and
      // newly ready artifacts appear without a manual refresh.
      renderProject();
    }
    return;
  }
  S.wasPolling = true;
  S.pollTimer = setTimeout(() => loadProject(S.project.id, { silent: true }).catch(() => {}), 2000);
}

function route() {
  const hash = location.hash || "#/";
  document.querySelectorAll("[data-nav]").forEach((a) => a.classList.remove("active"));
  if (hash.startsWith("#/project/")) {
    const id = hash.split("/")[2];
    document.querySelector('[data-nav="projects"]')?.classList.add("active");
    if (S.project?.id !== id) S.project = null;
    renderLoading();
    loadProject(id).catch((err) => renderError(err));
  } else if (hash.startsWith("#/settings")) {
    document.querySelector('[data-nav="settings"]')?.classList.add("active");
    renderSettings();
  } else {
    document.querySelector('[data-nav="projects"]')?.classList.add("active");
    renderHome();
  }
}

function renderLoading() {
  main.innerHTML = `<div class="empty"><strong>正在打开项目</strong><span class="muted">读取本地记录…</span></div>`;
}

function renderError(err) {
  main.innerHTML = `<div class="card card-pad"><h2>打不开这个项目</h2><p class="sub">${esc(err.message)}</p><a class="btn ghost mt" href="#/">返回项目列表</a></div>`;
}

/* ---------- Home ---------- */
function renderHome() {
  const cards = S.projects.map((p) => {
    const v = p.version || {};
    return `<a class="card project-card" href="#/project/${p.id}">
      <div><h3>${esc(v.title || p.name)}</h3>
      <div class="project-meta">${esc(v.venue || "venue 未确认")} · ${esc((v.authors || []).slice(0, 3).join(", ") || "作者待解析")}</div></div>
      <div>${pill(v.status || "absent")}</div>
    </a>`;
  }).join("");

  main.innerHTML = `
    <div class="topbar">
      <div><div class="eyebrow">Local-first research communication</div>
      <h1>把一篇论文，变成一组可发布的材料。</h1>
      <p class="sub">上传 PDF，校对事实，一次生成中英文案、真实 MP4 和项目主页。所有文件与记录留在本机。</p></div>
    </div>
    <section class="card hero">
      <div class="eyebrow">Start here</div>
      <h2 style="margin-top:8px">拖入论文 PDF</h2>
      <p class="sub">支持有文本层的 PDF。解析后你会看到论文卡、事实与可编辑物料。</p>
      <div id="dropzone" class="dropzone">
        <strong>拖入 PDF，或点击选择文件</strong>
        <p>文件只保存在本机 data/projects 下</p>
        <input id="file-input" type="file" accept="application/pdf,.pdf" hidden>
        <button class="btn accent mt" id="pick-file" type="button">选择 PDF</button>
      </div>
    </section>
    <section class="mt-lg">
      <div class="topbar"><div><div class="eyebrow">Projects</div><h2>最近项目</h2></div></div>
      <div class="stack">${cards || `<div class="card empty"><strong>还没有项目</strong><span>上传第一篇论文开始。</span></div>`}</div>
    </section>`;

  const dz = $("#dropzone");
  const input = $("#file-input");
  $("#pick-file").onclick = () => input.click();
  input.onchange = () => input.files[0] && uploadFile(input.files[0]);
  dz.ondragover = (e) => { e.preventDefault(); dz.classList.add("drag"); };
  dz.ondragleave = () => dz.classList.remove("drag");
  dz.ondrop = (e) => {
    e.preventDefault(); dz.classList.remove("drag");
    const file = e.dataTransfer.files[0];
    if (file) uploadFile(file);
  };
}

async function uploadFile(file) {
  if (!file.name.toLowerCase().endsWith(".pdf")) { toast("只支持 PDF 文件", true); return; }
  const form = new FormData();
  form.append("file", file);
  toast("正在上传并解析…");
  try {
    const data = await api("/api/projects", { method: "POST", body: form });
    toast("已创建项目，正在解析");
    location.hash = `#/project/${data.project.id}`;
  } catch (err) { toast(err.message, true); }
}

/* ---------- Project ---------- */
function renderProject() {
  const p = S.project;
  if (!p) return;
  const v = p.version || {};
  const authors = (v.authors || []).join(", ");
  const activeJobs = (p.jobs || []).filter((j) => ["queued", "running"].includes(j.status));
  main.innerHTML = `
    <div class="topbar">
      <div>
        <div class="eyebrow">Project</div>
        <h1>${esc(v.title || p.name)}</h1>
        <div class="authors muted">${esc(authors || "作者待解析")}</div>
        <div class="chips">
          <span class="chip accent">${esc(v.venue || "venue 未确认")}</span>
          ${v.venue_source ? `<span class="chip" title="${esc(v.venue_source)}">来源已记录</span>` : `<span class="chip">venue 无来源</span>`}
          ${v.paper_url ? `<a class="chip" href="${esc(v.paper_url)}" target="_blank">论文</a>` : ""}
          ${v.code_url ? `<a class="chip" href="${esc(v.code_url)}" target="_blank">代码</a>` : ""}
        </div>
      </div>
      <div class="actions">
        ${activeJobs.length ? `<span class="pill running">${activeJobs.length} 个任务运行中</span>` : ""}
        <button class="btn ghost" id="export-btn">导出 ZIP</button>
        <button class="btn accent" id="generate-all" ${activeJobs.length ? "disabled" : ""}>生成全部材料</button>
      </div>
    </div>
    ${activeJobs.length ? renderJobProgress(activeJobs) : ""}
    <div class="tabs">
      ${tabButton("overview", "论文与事实")}
      ${tabButton("copy", "宣传文案")}
      ${tabButton("video", "介绍视频")}
      ${tabButton("page", "项目主页")}
      ${tabButton("matrix", "传播矩阵")}
    </div>
    <div id="tab-body">${renderTab()}</div>`;

  $("#generate-all").onclick = generateAll;
  $("#export-btn").onclick = () => { location.href = `/api/projects/${p.id}/export`; };
  document.querySelectorAll("[data-tab]").forEach((btn) => {
    btn.onclick = () => { S.tab = btn.dataset.tab; renderProject(); };
  });
  bindTab();
}

function tabButton(id, label) {
  return `<button data-tab="${id}" class="${S.tab === id ? "active" : ""}">${label}</button>`;
}

function renderJobProgress(jobs) {
  const job = jobs[jobs.length - 1];
  return `<div class="card card-pad" style="margin-bottom:18px">
    <div style="display:flex;justify-content:space-between"><strong>${esc(job.kind)}</strong><span class="muted small">${esc(job.message || job.status)}</span></div>
    <div class="progress"><span style="width:${Math.round((job.progress || 0) * 100)}%"></span></div>
  </div>`;
}

function renderTab() {
  if (S.tab === "copy") return renderCopyTab();
  if (S.tab === "video") return renderVideoTab();
  if (S.tab === "page") return renderPageTab();
  if (S.tab === "matrix") return renderMatrixTab();
  return renderOverviewTab();
}

function bindTab() {
  if (S.tab === "overview") bindOverview();
  if (S.tab === "copy") bindCopy();
  if (S.tab === "video") bindVideo();
  if (S.tab === "page") bindPage();
  if (S.tab === "matrix") bindMatrix();
}

/* ---------- Overview ---------- */
function renderOverviewTab() {
  const p = S.project;
  const v = p.version || {};
  const claims = p.claims || [];
  const figures = v.figures || [];
  return `<div class="grid two">
    <section class="card card-pad">
      <div class="artifact-head"><div><div class="eyebrow">Paper card</div><h2 style="margin-top:8px">论文信息</h2></div><button class="btn small" id="meta-save">保存修改</button></div>
      <label class="field"><span>标题</span><input id="meta-title" type="text" value="${esc(v.title || p.name)}"></label>
      <label class="field"><span>作者（逗号分隔）</span><input id="meta-authors" type="text" value="${esc((v.authors || []).join(", "))}"></label>
      <label class="field"><span>摘要</span><textarea id="meta-abstract" style="width:100%;min-height:150px;resize:vertical;border:1px solid var(--line);border-radius:8px;padding:10px 11px;background:#fff">${esc(v.abstract || "")}</textarea></label>
      <div class="row">
        <label class="field"><span>Venue${v.venue && v.venue_source ? "" : "（未确认）"}</span><input id="meta-venue" type="text" value="${esc(v.venue || "")}" placeholder="留空表示未确认；填写时请同时填写来源"></label>
        <label class="field"><span>Venue 来源（填写后才算确认）</span><input id="meta-venue-source" type="text" value="${esc(v.venue_source || "")}" placeholder="OpenReview URL / arXiv Comments / 用户确认"></label>
      </div>
      <div class="row">
        <label class="field"><span>论文链接</span><input id="meta-paper" type="text" value="${esc(v.paper_url || "")}"></label>
        <label class="field"><span>代码链接${v.code_url && !v.code_url_confirmed ? "（自动抽取，未核实）" : ""}</span><input id="meta-code" type="text" value="${esc(v.code_url || "")}"></label>
      </div>
      <p class="small muted">${v.venue_source ? `venue 来源已记录。` : `venue 没有来源，因此视为未确认；文案、视频与主页不会写出会议名。`}
        ${v.code_url ? (v.code_url_confirmed ? " 代码链接已由你确认。" : ` 代码链接来源：${esc(v.code_url_source || "自动抽取")}；确认后才会进入文案与主页。`) : ""}
        元数据来源：${esc(v.metadata_source || "PDF 原文抽取")}。</p>
      ${v.code_url && !v.code_url_confirmed ? `<label class="small" style="display:flex;gap:8px;align-items:center;margin-bottom:10px"><input id="meta-code-confirm" type="checkbox" style="width:auto"> 我已核对，这个仓库属于本论文</label>` : ""}
      <div class="artifact-actions">
        <button class="btn ghost small" id="version-upload">上传论文新版本</button>
        <input id="version-file" type="file" accept="application/pdf,.pdf" hidden>
      </div>
    </section>
    <section class="card card-pad">
      <div class="eyebrow">Candidate facts</div>
      <h2 style="margin-top:8px">PDF 抽取的候选事实</h2>
      <p class="small muted">这些数值由正则从 PDF 原文抽取，带页码与原句，但还不是“已核验”。确认上下文后可逐条标记。</p>
      ${claims.length ? `<table><thead><tr><th>值</th><th>页</th><th>原句</th><th>状态</th></tr></thead><tbody>
        ${claims.map((c) => `<tr><td class="num"><strong>${esc(c.value)}</strong></td><td class="num">${c.source_page}</td><td class="small muted">${esc(c.source_quote)}</td>
          <td>${c.status === "verified" ? `<span class="pill ready">已核验</span>` : `<button class="btn ghost small" data-claim="${c.id}">标记已核验</button>`}</td></tr>`).join("")}
      </tbody></table>` : `<p class="muted">没有抽取到可用的数值事实（模型大小等无比较语境的数字已排除）。可以继续生成介绍性材料，但发布前需要人工核对。</p>`}
    </section>
  </div>
  <section class="card card-pad mt-lg">
    <div class="eyebrow">Figures</div><h2 style="margin-top:8px">论文图</h2>
    ${figures.length ? `<div class="figures">${figures.map((f) => `
      <figure><img src="/files/${p.id}/figures/${esc(f.file)}" alt=""><figcaption>${esc(f.caption || `Page ${f.page}`)}</figcaption></figure>`).join("")}</div>`
      : `<p class="muted">没有抽取到图。视频会使用版式化背景与文字，不伪造实验图。</p>`}
  </section>
  <section class="card card-pad mt-lg">
    <div class="eyebrow">Activity</div><h2 style="margin-top:8px">任务与事件</h2>
    ${(p.events || []).length ? p.events.map((e) => `<div class="event"><time>${fmtTime(e.created_at)}</time><span>${esc(e.type)}</span></div>`).join("") : `<p class="muted">还没有事件。</p>`}
  </section>`;
}

function bindOverview() {
  document.querySelectorAll("[data-claim]").forEach((btn) => {
    btn.onclick = async () => {
      try {
        await api(`/api/projects/${S.project.id}/claims/${btn.dataset.claim}/verify`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ verified: true }),
        });
        toast("已标记为已核验");
        await loadProject(S.project.id);
      } catch (err) { toast(err.message, true); }
    };
  });
  const uploadBtn = $("#version-upload");
  const fileInput = $("#version-file");
  if (uploadBtn && fileInput) {
    uploadBtn.onclick = () => fileInput.click();
    fileInput.onchange = async () => {
      const file = fileInput.files[0];
      if (!file) return;
      const form = new FormData();
      form.append("file", file);
      try {
        await api(`/api/projects/${S.project.id}/versions`, { method: "POST", body: form });
        toast("新版本已上传，正在重新解析；已有物料已标为过期");
        await loadProject(S.project.id);
      } catch (err) { toast(err.message, true); }
    };
  }
  const btn = $("#meta-save");
  if (!btn) return;
  btn.onclick = async () => {
    try {
      await api(`/api/projects/${S.project.id}/metadata`, {
        method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: $("#meta-title").value.trim(),
          authors: $("#meta-authors").value.trim(),
          abstract: $("#meta-abstract").value.trim(),
          venue: $("#meta-venue").value.trim(),
          venue_source: $("#meta-venue-source").value.trim(),
          paper_url: $("#meta-paper").value.trim(),
          code_url: $("#meta-code").value.trim(),
          code_url_confirmed: $("#meta-code-confirm") ? $("#meta-code-confirm").checked : undefined,
        }),
      });
      toast("论文信息已保存；已生成物料会在重新生成时使用新事实");
      await loadProject(S.project.id);
    } catch (err) { toast(err.message, true); }
  };
}

/* ---------- Copy ---------- */
function renderCopyTab() {
  const p = S.project;
  const copies = (p.artifacts || []).filter((a) => a.kind === "copy");
  if (!copies.length) {
    return `<div class="card empty"><strong>还没有文案</strong><span>点击“生成全部材料”，或先检查事实。</span></div>`;
  }
  return `<div class="stack">${copies.map((a) => {
    const meta = PLATFORM[a.platform] || { label: a.platform, hint: "" };
    const issues = a.issues || [];
    return `<section class="card artifact" data-artifact="${a.id}">
      <div class="artifact-head">
        <div><h3>${esc(meta.label)}</h3><div class="small muted">${esc(meta.hint)}</div></div>
        ${pill(a.status)}
      </div>
      <textarea data-content="${a.id}">${esc(a.content || "")}</textarea>
      ${issues.length ? `<div class="issues">${issues.map((i) => `<div>${esc(i.message || i.type)}</div>`).join("")}</div>` : ""}
      <div class="artifact-actions">
        <button class="btn small" data-save="${a.id}">保存修改</button>
        <button class="btn ghost small" data-regen="${a.id}">重新生成</button>
        <button class="btn ghost small" data-approve="${a.id}" ${["draft","needs_review","stale"].includes(a.status) ? "" : "disabled"}>标记可发布</button>
        <button class="btn ghost small" data-candidate="${a.id}">候选稿对比</button>
        <button class="btn ghost small" data-versions="${a.id}">历史版本</button>
      </div>
      <div data-candidate-box="${a.id}" hidden></div>
      <div data-version-list="${a.id}" hidden>
        <div class="small muted" style="margin:10px 0 6px">旧稿候选（来自上一次生成或你的修改）。选中后可取回内容。</div>
        <table class="version-table"><thead><tr><th>时间</th><th>来源</th><th>字数</th><th>操作</th></tr></thead><tbody></tbody></table>
      </div>
    </section>`;
  }).join("")}</div>`;
}

function bindCopy() {
  document.querySelectorAll("[data-save]").forEach((btn) => {
    btn.onclick = async () => {
      const id = btn.dataset.save;
      const content = document.querySelector(`[data-content="${id}"]`).value;
      try { await api(`/api/projects/${S.project.id}/artifacts/${id}`, {
        method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content })
      }); toast("已保存"); await loadProject(S.project.id, { silent: true }); renderProject(); }
      catch (err) { toast(err.message, true); }
    };
  });
  document.querySelectorAll("[data-regen]").forEach((btn) => {
    btn.onclick = async () => {
      try { await api(`/api/projects/${S.project.id}/artifacts/${btn.dataset.regen}/regenerate`, { method: "POST" }); toast("已开始重新生成"); await loadProject(S.project.id); }
      catch (err) { toast(err.message, true); }
    };
  });
  document.querySelectorAll("[data-approve]").forEach((btn) => {
    btn.onclick = async () => {
      try { await api(`/api/projects/${S.project.id}/artifacts/${btn.dataset.approve}/approve`, { method: "POST" }); toast("已标记可发布"); await loadProject(S.project.id); }
      catch (err) { toast(err.message, true); }
    };
  });
  document.querySelectorAll("[data-candidate]").forEach((btn) => {
    btn.onclick = async () => {
      const id = btn.dataset.candidate;
      const box = document.querySelector(`[data-candidate-box="${id}"]`);
      if (!box.hidden) { box.hidden = true; return; }
      box.hidden = false;
      box.innerHTML = `<div class="small muted" style="margin-top:10px">加载候选稿…</div>`;
      try {
        const data = await api(`/api/projects/${S.project.id}/artifacts/${id}/candidate`);
        if (!data.candidate) {
          box.innerHTML = `<div class="small muted" style="margin-top:10px">没有待处理的候选稿。重新生成后若保留人工修改，候选稿会出现在这里。</div>`;
          return;
        }
        box.innerHTML = `
          <div style="margin-top:12px">
            <div class="small muted" style="margin-bottom:6px">左侧是当前发布的稿件，右侧是本次重新生成得到的候选。不同行会高亮。</div>
            ${renderDiff(data.current.content || "", data.candidate.content || "")}
            <div class="artifact-actions">
              <button class="btn small" data-adopt="${id}" data-version="${data.candidate.id}">采用候选稿</button>
              <button class="btn ghost small" data-dismiss="${id}">保留当前稿</button>
            </div>
          </div>`;
        box.querySelector("[data-adopt]").onclick = async () => {
          try {
            await api(`/api/projects/${S.project.id}/artifacts/${id}/use-version`, {
              method: "POST", headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ version_id: data.candidate.id }),
            });
            toast("已采用候选稿，请检查后标记可发布");
            await loadProject(S.project.id);
          } catch (err) { toast(err.message, true); }
        };
        box.querySelector("[data-dismiss]").onclick = () => { box.hidden = true; };
      } catch (err) {
        box.innerHTML = `<div class="small muted" style="margin-top:10px">读取失败：${esc(err.message)}</div>`;
      }
    };
  });
  document.querySelectorAll("[data-versions]").forEach((btn) => {
    btn.onclick = async () => {
      const id = btn.dataset.versions;
      const box = document.querySelector(`[data-version-list="${id}"]`);
      if (!box.hidden) { box.hidden = true; return; }
      const body = box.querySelector("tbody");
      body.innerHTML = "<tr><td colspan=4 class='muted'>加载中…</td></tr>";
      box.hidden = false;
      try {
        const versions = await api(`/api/projects/${S.project.id}/artifacts/${id}/versions`);
        if (!versions.length) { body.innerHTML = "<tr><td colspan=4 class='muted'>还没有历史版本</td></tr>"; return; }
        body.innerHTML = "";
        for (const version of versions) {
          const tr = document.createElement("tr");
          const origin = version.source_version_id ? "生成候选" : "人工修改";
          tr.innerHTML = `<td class="small muted">${esc(fmtTime(version.created_at))}</td><td class="small">${origin}</td><td class="num small">${version.chars || 0}</td>`;
          const td = document.createElement("td");
          const view = document.createElement("button");
          view.className = "btn ghost small";
          view.textContent = "查看";
          view.onclick = async () => {
            const detail = await api(`/api/projects/${S.project.id}/artifacts/${id}/versions/${version.id}`);
            const area = document.querySelector(`[data-content="${id}"]`);
            area.value = detail.content;
            toast("已载入该版本到编辑框，确认后点“保存修改”");
          };
          const use = document.createElement("button");
          use.className = "btn small";
          use.textContent = "取回";
          use.onclick = async () => {
            try { await api(`/api/projects/${S.project.id}/artifacts/${id}/use-version`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ version_id: version.id }) }); toast("已取回该版本"); await loadProject(S.project.id); }
            catch (err) { toast(err.message, true); }
          };
          td.appendChild(view); td.appendChild(use);
          tr.appendChild(td);
          body.appendChild(tr);
        }
      } catch (err) { body.innerHTML = `<tr><td colspan=4 class="muted">${esc(err.message)}</td></tr>`; }
    };
  });
}

/* ---------- Video ---------- */
function renderVideoTab() {
  const p = S.project;
  const art = (p.artifacts || []).find((a) => a.kind === "video");
  if (!art || art.status === "absent") {
    return `<div class="card empty"><strong>还没有视频</strong><span>生成全部材料后，这里会出现真实 MP4。</span></div>`;
  }
  const job = (p.jobs || []).find((j) => j.kind === "video");
  const videoUrl = `/files/${p.id}/video/video.mp4`;
  const ready = ["ready", "needs_review", "published", "stale"].includes(art.status);
  return `<section class="card card-pad">
    <div class="artifact-head"><div><div class="eyebrow">Narrated walkthrough</div><h2 style="margin-top:8px">论文介绍视频</h2>
      <p class="sub">目标 60–120 秒 · 1080p · 旁白 + 烧录字幕 + 论文原图${art.status === "ready" || art.status === "needs_review" ? ` · 实际时长见下方播放器` : ""}</p></div>${pill(art.status)}</div>
    ${job && ["queued","running"].includes(job.status) ? `<div class="progress"><span style="width:${Math.round((job.progress||0)*100)}%"></span></div><p class="small muted">${esc(job.message)}</p>` : ""}
    ${ready ? `<video class="video-frame" controls preload="metadata" src="${videoUrl}?v=${encodeURIComponent(art.content_hash || "")}"></video>
      <div class="artifact-actions">
        <a class="btn small" href="${videoUrl}" download>下载 MP4</a>
        <a class="btn ghost small" href="/files/${p.id}/video/video.srt" download>下载 SRT</a>
        <button class="btn ghost small" data-video-regen>重新生成视频</button>
      </div>` : `<p class="muted">视频尚未完成。${job?.message ? esc(job.message) : ""}</p>`}
    ${(art.issues || []).length ? `<div class="issues">${art.issues.map((i) => `<div>${esc(i.message)}</div>`).join("")}</div>` : ""}
  </section>`;
}

function bindVideo() {
  const btn = document.querySelector("[data-video-regen]");
  if (btn) btn.onclick = async () => {
    const art = S.project.artifacts.find((a) => a.kind === "video");
    try { await api(`/api/projects/${S.project.id}/artifacts/${art.id}/regenerate`, { method: "POST" }); toast("已开始重新生成视频"); await loadProject(S.project.id); }
    catch (err) { toast(err.message, true); }
  };
}

/* ---------- Page ---------- */
function renderPageTab() {
  const p = S.project;
  const art = (p.artifacts || []).find((a) => a.kind === "site");
  if (!art || art.status === "absent") {
    return `<div class="card empty"><strong>还没有项目主页</strong><span>生成全部材料后，这里会出现可部署的 index.html。</span></div>`;
  }
  const siteUrl = `/files/${p.id}/site/index.html`;
  const canPublish = ["ready", "published"].includes(art.status);
  return `<section class="card card-pad">
    <div class="artifact-head"><div><div class="eyebrow">Deployable page</div><h2 style="margin-top:8px">项目主页</h2>
      <p class="sub">响应式静态页，含论文/代码链接、结果、视频与 BibTeX。只有“可发布”状态的页面才能发布。</p></div>${pill(art.status)}</div>
    <iframe class="site-frame" src="${siteUrl}?v=${encodeURIComponent(art.content_hash || "")}" title="项目主页预览"></iframe>
    <div class="artifact-actions">
      <a class="btn small" href="${siteUrl}" target="_blank">打开页面</a>
      <a class="btn ghost small" href="/api/projects/${p.id}/export">导出 ZIP</a>
      <button class="btn ghost small" data-site-regen>重新生成主页</button>
    </div>
  </section>
  <section class="card card-pad mt-lg">
    <div class="eyebrow">GitHub Pages</div><h2 style="margin-top:8px">发布（需要你批准）</h2>
    <p class="sub">发布是外部写入。确认页面内容后勾选批准；服务端会再校验事实、版本与物料状态。推送成功后只有线上页面真实可访问，才会标记为“在线”。</p>
    ${canPublish ? "" : `<p class="small" style="color:var(--red)">当前页面状态为“${esc(STATUS[art.status] || art.status)}”，需先重新生成并在“项目主页”标记可发布。</p>`}
    <div class="row mt">
      <label class="field" style="flex:2"><span>目标仓库 owner/name</span><input id="gh-repo" type="text" placeholder="AIMetaPhD/paper-page-demo" value="${esc(S.settings?.github_repo || "")}"></label>
      <label class="field" style="flex:1"><span>批准</span><select id="gh-approve"><option value="0">未批准</option><option value="1">我已核对并批准</option></select></label>
      <button class="btn accent" id="gh-publish" style="margin-bottom:14px" ${canPublish ? "" : "disabled"}>发布到 GitHub Pages</button>
    </div>
    <div id="gh-result" class="small muted"></div>
    ${(p.publications || []).length ? `<table class="mt"><thead><tr><th>目标</th><th>状态</th><th>URL</th></tr></thead><tbody>${p.publications.map((pub) => `<tr><td>${esc(pub.target)}</td><td>${pill(pub.state)}</td><td>${pub.remote_url ? `<a href="${esc(pub.remote_url)}" target="_blank">${esc(pub.remote_url)}</a>` : "—"}</td></tr>`).join("")}</tbody></table>` : ""}
  </section>`;
}

function bindPage() {
  const regen = document.querySelector("[data-site-regen]");
  if (regen) regen.onclick = async () => {
    const art = S.project.artifacts.find((a) => a.kind === "site");
    try { await api(`/api/projects/${S.project.id}/artifacts/${art.id}/regenerate`, { method: "POST" }); toast("已开始重新生成主页"); await loadProject(S.project.id); }
    catch (err) { toast(err.message, true); }
  };
  const btn = $("#gh-publish");
  if (!btn) return;
  btn.onclick = async () => {
    const repo = $("#gh-repo").value.trim();
    const approve = $("#gh-approve").value === "1";
    if (!approve) { toast("请先勾选批准", true); return; }
    btn.disabled = true;
    $("#gh-result").textContent = "正在发布…";
    try {
      const result = await api(`/api/projects/${S.project.id}/publish/github`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ repo, approve })
      });
      $("#gh-result").innerHTML = result.ok
        ? (result.verified
            ? `已上线并核验：<a href="${esc(result.url)}" target="_blank">${esc(result.url)}</a>`
            : `已推送但线上尚未核验：<a href="${esc(result.url)}" target="_blank">${esc(result.url)}</a> · ${esc(result.message || "")}`)
        : `未发布：${esc(result.error || "")}`;
      if (result.ok) await loadProject(S.project.id);
    } catch (err) { $("#gh-result").textContent = err.message; }
    btn.disabled = false;
  };
}

/* ---------- Matrix ---------- */
function renderMatrixTab() {
  const p = S.project;
  const arts = p.artifacts || [];
  return `<div class="grid two">
    <section class="card card-pad">
      <div class="eyebrow">Artifacts</div><h2 style="margin-top:8px">物料状态</h2>
      <table><thead><tr><th>物料</th><th>状态</th><th>更新时间</th></tr></thead><tbody>
        ${arts.map((a) => `<tr><td>${esc(a.kind === "copy" ? (PLATFORM[a.platform]?.label || a.platform) : a.kind)}</td><td>${pill(a.status)}</td><td class="small muted">${fmtTime(a.updated_at)}</td></tr>`).join("") || `<tr><td colspan="3" class="muted">还没有物料</td></tr>`}
      </tbody></table>
    </section>
    <section class="card card-pad">
      <div class="eyebrow">Sources</div><h2 style="margin-top:8px">来源检查</h2>
      <p class="small muted">登记 arXiv / GitHub / 本地文件 / URL。定时检查变化，变化后把已生成物料标记为过期。</p>
      <div class="row">
        <label class="field"><span>类型</span><select id="src-kind"><option value="arxiv">arXiv ID</option><option value="github">GitHub owner/repo</option><option value="local_file">本地文件路径</option><option value="url">URL</option></select></label>
        <label class="field" style="flex:2"><span>位置</span><input id="src-locator" type="text" placeholder="2106.09685 或 microsoft/LoRA"></label>
        <label class="field" style="max-width:120px"><span>间隔(分)</span><input id="src-interval" type="number" value="30" min="1"></label>
      </div>
      <button class="btn small" id="src-add">登记来源</button>
      <button class="btn ghost small" id="src-check">立即检查</button>
      <div class="mt">${(p.sources || []).map((s) => `<div class="event"><time>${s.enabled ? "启用" : "停用"}</time><span>${esc(s.kind)} · ${esc(s.locator)} · 每 ${s.interval_min} 分钟${s.last_checked_at ? ` · 上次 ${fmtTime(s.last_checked_at)}` : ""}</span></div>`).join("") || `<p class="muted small">还没有登记来源。</p>`}</div>
    </section>
  </div>
  <section class="card card-pad mt-lg">
    <div class="eyebrow">Manual channels</div><h2 style="margin-top:8px">手动发布渠道</h2>
    <p class="sub">这些渠道没有稳定的个人自动发布接口，产品只提供文案与复制，不会标记为已自动发布。</p>
    <table><thead><tr><th>渠道</th><th>使用方式</th><th>状态</th></tr></thead><tbody>
      ${["X / Twitter", "LinkedIn", "微信公众号", "小红书"].map((name) => `<tr><td>${name}</td><td class="small muted">复制“宣传文案”页签中的对应稿件，手动粘贴发布</td><td>${pill("manual")}</td></tr>`).join("")}
    </tbody></table>
  </section>
  <section class="card card-pad mt-lg">
    <div class="eyebrow">Publishing</div><h2 style="margin-top:8px">已发布目标</h2>
    ${(p.publications || []).length ? `<table><thead><tr><th>目标</th><th>状态</th><th>URL</th><th>最近核对</th></tr></thead><tbody>${p.publications.map((pub) => `<tr><td>${esc(pub.target)}</td><td>${pill(pub.state)}</td><td>${pub.remote_url ? `<a href="${esc(pub.remote_url)}" target="_blank">${esc(pub.remote_url)}</a>` : "—"}</td><td class="small muted">${pub.last_verified_at ? fmtTime(pub.last_verified_at) : "未核对"}</td></tr>`).join("")}</tbody></table>` : `<p class="muted">还没有真实发布。GitHub Pages 需要在项目主页页签里批准。</p>`}
  </section>`;
}

function bindMatrix() {
  $("#src-add").onclick = async () => {
    try {
      await api(`/api/projects/${S.project.id}/sources`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ kind: $("#src-kind").value, locator: $("#src-locator").value.trim(), interval_min: Number($("#src-interval").value || 30) })
      });
      toast("已登记来源"); await loadProject(S.project.id);
    } catch (err) { toast(err.message, true); }
  };
  $("#src-check").onclick = async () => {
    try {
      const result = await api(`/api/projects/${S.project.id}/sources/check`, { method: "POST" });
      toast(`检查完成：${(result.results || []).filter((r) => r.changed).length} 个来源有变化`);
      await loadProject(S.project.id);
    } catch (err) { toast(err.message, true); }
  };
}

/* ---------- Settings ---------- */
async function renderSettings() {
  try { S.settings = await api("/api/settings"); } catch (err) { renderError(err); return; }
  const s = S.settings;
  main.innerHTML = `
    <div class="topbar"><div><div class="eyebrow">Settings</div><h1>设置</h1><p class="sub">模型、语音、来源检查与 GitHub 连接。凭证只保存在本机数据库，不出现在导出物里。</p></div></div>
    <div class="grid two">
      <section class="card card-pad">
        <div class="eyebrow">LLM</div><h2 style="margin-top:8px">模型连接</h2>
        <label class="field"><span>OpenAI 兼容 Base URL</span><input id="set-base" type="text" value="${esc(s.llm_base_url || "")}" placeholder="http://127.0.0.1:11434/v1 或 http://127.0.0.1:3425/v1"></label>
        <label class="field"><span>API 协议</span><select id="set-wire">
          <option value="chat" ${(s.llm_wire_api || "chat") === "chat" ? "selected" : ""}>/chat/completions（Ollama、OpenAI、vLLM）</option>
          <option value="responses" ${s.llm_wire_api === "responses" ? "selected" : ""}>/responses（Magpie 等网关）</option>
        </select></label>
        <label class="field"><span>模型</span><input id="set-model" type="text" value="${esc(s.llm_model || "")}"></label>
        <label class="field"><span>API Key</span><input id="set-key" type="password" value="${esc(s.llm_api_key || "")}" placeholder="sk-..."></label>
        <div class="row"><button class="btn small" id="save-settings">保存</button><button class="btn ghost small" id="test-model">测试连接</button></div>
        <div id="model-result" class="small muted mt"></div>
      </section>
      <section class="card card-pad">
        <div class="eyebrow">Video</div><h2 style="margin-top:8px">旁白与导出</h2>
        <label class="field"><span>视频语言</span><select id="set-video-language">
          <option value="en" ${(s.video_language || "en") === "en" ? "selected" : ""}>English</option>
          <option value="zh" ${s.video_language === "zh" ? "selected" : ""}>中文</option>
        </select></label>
        <label class="field"><span>英文旁白音色</span><input id="set-voice-en" type="text" value="${esc(s.voice_en || "")}"></label>
        <label class="field"><span>中文旁白音色</span><input id="set-voice-zh" type="text" value="${esc(s.voice_zh || "")}"></label>
        <p class="small muted">默认使用 Edge TTS（需要网络）。视频渲染使用本机 ffmpeg；未安装时会在任务里给出明确错误。</p>
      </section>
    </div>
    <section class="card card-pad mt-lg">
      <div class="eyebrow">Maintenance</div><h2 style="margin-top:8px">来源检查</h2>
      <div class="row">
        <label class="field"><span>启用定时检查</span><select id="set-maint"><option value="0" ${s.maintenance_enabled === "0" ? "selected" : ""}>关闭</option><option value="1" ${s.maintenance_enabled === "1" ? "selected" : ""}>开启</option></select></label>
        <label class="field"><span>默认间隔（分钟）</span><input id="set-interval" type="number" min="1" value="${esc(s.maintenance_interval_min || "30")}"></label>
      </div>
      <p class="small muted">每个项目在“传播矩阵”里登记具体来源。定时器只在本地服务运行时工作；重启后配置保留。</p>
    </section>
    <section class="card card-pad mt-lg">
      <div class="eyebrow">GitHub</div><h2 style="margin-top:8px">连接状态</h2>
      <p class="small">${s.github?.ok ? `已登录：<strong>${esc(s.github.account || "已授权")}</strong>` : `未连接：${esc(s.github?.error || "gh 未登录")}`}</p>
      <label class="field"><span>默认目标仓库</span><input id="set-repo" type="text" value="${esc(s.github_repo || "")}" placeholder="owner/name"></label>
      <button class="btn small" id="save-github">保存仓库</button>
    </section>`;

  $("#save-settings").onclick = async () => {
    try {
      await api("/api/settings", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({
        llm_base_url: $("#set-base").value.trim(), llm_wire_api: $("#set-wire").value,
        llm_model: $("#set-model").value.trim(),
        llm_api_key: $("#set-key").value.trim(), video_language: $("#set-video-language").value,
        voice_en: $("#set-voice-en").value.trim(), voice_zh: $("#set-voice-zh").value.trim()
      }) });
      toast("设置已保存"); renderSettings();
    } catch (err) { toast(err.message, true); }
  };
  $("#test-model").onclick = async () => {
    $("#model-result").textContent = "测试中…";
    try {
      const r = await api("/api/settings/test", { method: "POST" });
      $("#model-result").textContent = r.ok
        ? `连接成功（${r.wire || "chat"}）：${r.reply || "OK"} · 模型 ${(r.models || []).slice(0, 4).join(", ")}${r.hint ? ` · ${r.hint}` : ""}`
        : `失败：${r.error}${r.hint ? ` · ${r.hint}` : ""}`;
    }
    catch (err) { $("#model-result").textContent = err.message; }
  };
  $("#save-github").onclick = async () => {
    try { await api("/api/settings", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ github_repo: $("#set-repo").value.trim(), maintenance_enabled: $("#set-maint").value, maintenance_interval_min: $("#set-interval").value }) }); toast("已保存"); renderSettings(); }
    catch (err) { toast(err.message, true); }
  };
}

async function generateAll() {
  const btn = $("#generate-all");
  if (btn) btn.disabled = true;
  try {
    await api(`/api/projects/${S.project.id}/generate`, { method: "POST" });
    toast("已开始生成文案、视频和主页");
    await loadProject(S.project.id);
  } catch (err) {
    toast(err.message, true);
    if (btn) btn.disabled = false;
  }
}

window.addEventListener("hashchange", route);
(async function boot() {
  try {
    if (!location.hash) {
      const last = localStorage.getItem("paperrelay:last");
      if (last) location.hash = `#/project/${last}`;
    }
    await loadProjects();
    await route();
  } catch (err) {
    main.innerHTML = `<div class="card card-pad"><h2>无法连接本地服务</h2><p class="sub">${esc(err.message)}</p></div>`;
  }
})();
