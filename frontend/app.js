const $ = (s, r = document) => r.querySelector(s);
const main = $("#main");

function base() {
  const v = $("#apiBase").value.trim();
  return v || window.location.origin;
}

function headers() {
  const h = { "Content-Type": "application/json" };
  const key = $("#apiKey").value.trim();
  if (key) h["X-API-Key"] = key;
  return h;
}

async function api(path, opts = {}) {
  const res = await fetch(base() + path, { ...opts, headers: { ...headers(), ...opts.headers } });
  const text = await res.text();
  let data;
  try { data = JSON.parse(text); } catch { data = { raw: text }; }
  if (!res.ok) throw new Error(data.detail || res.statusText || text);
  return data;
}

function renderOverview(data) {
  const pct = data.progress_percent || 0;
  main.innerHTML = `
    <h2>综合看板</h2>
    <p class="hint">实施方案5 · 5万条数据建设进度：有效合计 ${data.effective_total} / ${data.target_total}（${pct}%）</p>
    <div class="progress"><div class="progress-bar" style="width:${pct}%"></div></div>
    <div class="cards">
      <div class="card"><div class="num">${data.parts}</div><div class="lbl">零件</div></div>
      <div class="card"><div class="num">${data.process_steps}</div><div class="lbl">工序工艺</div></div>
      <div class="card"><div class="num">${data.knowledge_items}</div><div class="lbl">知识条目</div></div>
      <div class="card"><div class="num">${data.equipment}</div><div class="lbl">设备</div></div>
      <div class="card"><div class="num">${data.resources || 0}</div><div class="lbl">资源(刀/工装)</div></div>
      <div class="card"><div class="num">${data.quality_records}</div><div class="lbl">质量记录</div></div>
      <div class="card"><div class="num">${data.optimization_records}</div><div class="lbl">优化记录</div></div>
      <div class="card"><div class="num">${data.recommendation_results}</div><div class="lbl">推荐记录</div></div>
    </div>
    <h3>最近知识条目</h3>
    <table><tr><th>ID</th><th>类别</th><th>标题</th><th>零件</th></tr>
    ${(data.recent_knowledge || []).map(k => `<tr><td>${k.id}</td><td>${k.category}</td><td>${k.title}</td><td>${k.part_no || ""}</td></tr>`).join("")}
    </table>`;
}

function renderRecommend() {
  main.innerHTML = `
    <h2>工艺方案推荐</h2>
    <p class="hint">§4.11 输入轴类/齿轮类零件特征，规则+案例匹配（需工艺人员确认）</p>
    <div class="form-grid">
      <input id="r_part_no" placeholder="零件号（可选）" value="GH-2024-088" />
      <input id="r_material" placeholder="材料" value="20CrMnTi" />
      <input id="r_module" type="number" step="0.1" placeholder="模数" value="2.5" />
      <input id="r_teeth" type="number" placeholder="齿数" value="32" />
      <input id="r_grade" placeholder="精度等级" value="6级" />
      <input id="r_heat" placeholder="热处理" value="渗碳淬火" />
    </div>
    <button class="btn" id="btnRecommend">生成推荐</button>
    <pre class="result" id="recResult">等待请求…</pre>`;
  $("#btnRecommend").onclick = async () => {
    const body = {
      part_no: $("#r_part_no").value || null,
      material: $("#r_material").value || null,
      module_m: parseFloat($("#r_module").value) || null,
      teeth_z: parseInt($("#r_teeth").value, 10) || null,
      accuracy_grade: $("#r_grade").value || null,
      heat_treatment: $("#r_heat").value || null,
      part_type: "齿轮",
    };
    try {
      const data = await api("/api/v1/recommendations/process", { method: "POST", body: JSON.stringify(body) });
      $("#recResult").textContent = JSON.stringify(data, null, 2);
    } catch (e) {
      $("#recResult").textContent = "错误: " + e.message + "\n请填写 Render 环境变量 PKB_API_KEY";
    }
  };
}

function renderParts() {
  main.innerHTML = `
    <h2>零件查询</h2>
    <input id="pno" placeholder="零件号" value="GH-2024-088" style="padding:0.5rem;width:240px" />
    <button class="btn" id="btnPart">查询</button>
    <pre class="result" id="partResult"></pre>`;
  $("#btnPart").onclick = async () => {
    try {
      const data = await api("/api/v1/parts/" + encodeURIComponent($("#pno").value));
      $("#partResult").textContent = JSON.stringify(data, null, 2);
    } catch (e) { $("#partResult").textContent = e.message; }
  };
}

function renderProcess() {
  main.innerHTML = `
    <h2>工艺流程</h2>
    <input id="pno2" value="GH-2024-088" style="padding:0.5rem;width:240px" />
    <button class="btn" id="btnProc">查询工序</button>
    <pre class="result" id="procResult"></pre>`;
  $("#btnProc").onclick = async () => {
    try {
      const data = await api("/api/v1/process/static?part_no=" + encodeURIComponent($("#pno2").value));
      $("#procResult").textContent = JSON.stringify(data, null, 2);
    } catch (e) { $("#procResult").textContent = e.message; }
  };
}

function renderKnowledge() {
  main.innerHTML = `
    <h2>工艺知识</h2>
    <input id="kw" placeholder="关键词" style="padding:0.5rem;width:160px" />
    <input id="kpart" placeholder="零件号" value="GH-2024-088" style="padding:0.5rem;width:160px" />
    <button class="btn" id="btnKnow">搜索</button>
    <pre class="result" id="knowResult"></pre>`;
  $("#btnKnow").onclick = async () => {
    const q = new URLSearchParams();
    if ($("#kpart").value) q.set("part_no", $("#kpart").value);
    if ($("#kw").value) q.set("keyword", $("#kw").value);
    try {
      const data = await api("/api/v1/knowledge?" + q.toString());
      $("#knowResult").textContent = JSON.stringify(data, null, 2);
    } catch (e) { $("#knowResult").textContent = e.message; }
  };
}

function renderQuality() {
  main.innerHTML = `
    <h2>质量追溯</h2>
    <input id="qpart" placeholder="零件号" value="GH-2024-088" style="padding:0.5rem;width:240px" />
    <button class="btn" id="btnQual">查询</button>
    <pre class="result" id="qualResult"></pre>`;
  $("#btnQual").onclick = async () => {
    const q = $("#qpart").value ? "?part_no=" + encodeURIComponent($("#qpart").value) : "";
    try {
      const data = await api("/api/v1/quality-records" + q);
      $("#qualResult").textContent = JSON.stringify(data, null, 2);
    } catch (e) { $("#qualResult").textContent = e.message; }
  };
}

function renderIntegration() {
  main.innerHTML = `
    <h2>平台对接</h2>
    <p class="hint">数制平台 / 数字孪生通过 HTTPS + X-API-Key 调用下列接口</p>
    <button class="btn" id="btnCat">加载对接目录</button>
    <a class="btn link" href="${base()}/docs" target="_blank">打开 API 文档</a>
    <pre class="result" id="intResult">点击加载…</pre>`;
  $("#btnCat").onclick = async () => {
    try {
      const data = await api("/api/v1/integration/catalog");
      $("#intResult").textContent = JSON.stringify(data, null, 2);
    } catch (e) { $("#intResult").textContent = e.message; }
  };
}

function renderImport() {
  main.innerHTML = `
    <h2>数据上传</h2>
    <p class="hint">支持 CSV：parts / process / knowledge / equipment / quality</p>
    <p><a href="#" id="tplLink">下载 CSV 模板</a></p>
    <select id="kind">
      <option value="process">process</option>
      <option value="parts">parts</option>
      <option value="knowledge">knowledge</option>
      <option value="equipment">equipment</option>
      <option value="quality">quality</option>
    </select>
    <input type="file" id="csvFile" accept=".csv" />
    <button class="btn" id="btnImport">上传</button>
    <pre class="result" id="impResult"></pre>`;
  $("#tplLink").onclick = (e) => {
    e.preventDefault();
    window.open(base() + "/api/v1/import/template/" + $("#kind").value, "_blank");
  };
  $("#btnImport").onclick = async () => {
    const f = $("#csvFile").files[0];
    if (!f) return;
    const fd = new FormData();
    fd.append("file", f);
    const key = $("#apiKey").value.trim();
    const h = {};
    if (key) h["X-API-Key"] = key;
    try {
      const res = await fetch(base() + "/api/v1/import/csv/" + $("#kind").value, { method: "POST", headers: h, body: fd });
      $("#impResult").textContent = await res.text();
    } catch (e) { $("#impResult").textContent = e.message; }
  };
}

const VIEWS = {
  overview: () => api("/api/v1/overview").then(renderOverview),
  recommend: renderRecommend,
  parts: renderParts,
  process: renderProcess,
  knowledge: renderKnowledge,
  quality: renderQuality,
  integration: renderIntegration,
  import: renderImport,
};

async function loadView(name) {
  document.querySelectorAll(".nav").forEach(b => b.classList.toggle("active", b.dataset.view === name));
  try {
    if (name === "overview") await VIEWS.overview();
    else if (VIEWS[name]) VIEWS[name]();
  } catch (e) {
    main.innerHTML = `<h2>提示</h2><p>请先填写 API Key（Render → Environment → PKB_API_KEY）</p><p>${e.message}</p>`;
  }
}

document.querySelectorAll(".nav").forEach(b => b.addEventListener("click", () => loadView(b.dataset.view)));
loadView("overview");
