function closeDetailModal() {
  const modal = document.getElementById("detail-modal");
  if (modal) {
    modal.classList.add("hidden");
    modal.setAttribute("aria-hidden", "true");
  }
}

function esc(s) {
  if (s == null) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderPartDetailHtml(d) {
  const procs = d.processes || [];
  const know = d.knowledge || [];
  const opts = d.optimizations || [];

  const procRows = procs.length
    ? procs
        .map(
          (p) => `<tr>
            <td>${p.operation_no}</td>
            <td>${esc(p.operation_name)}</td>
            <td>${esc(p.equipment_code || "-")}</td>
            <td>${esc(p.tool_code || "-")}</td>
            <td>${p.spindle_speed ?? "-"}</td>
            <td>${p.cutting_depth ?? "-"}</td>
            <td>${p.feed_rate ?? "-"}</td>
          </tr>`
        )
        .join("")
    : "";

  const knowHtml = know.length
    ? know
        .map(
          (k) => `<div class="knowledge-card">
            <div class="kt"><span class="badge">${esc(k.category)}</span> ${esc(k.title)}</div>
            <div class="kc">${esc(k.content)}</div>
            <div style="font-size:0.75rem;margin-top:6px;color:var(--muted)">工序 ${k.related_op_no || "-"} · ${esc(k.author || "")} · ${esc(k.source || "")}</div>
          </div>`
        )
        .join("")
    : '<p class="detail-empty">暂无关联工艺知识（可在「数据上传」或知识条目页添加）</p>';

  const optRows = opts.length
    ? opts
        .map(
          (o) => `<tr>
            <td>${esc(o.equipment_code)}</td>
            <td>${o.operation_no ?? "-"}</td>
            <td>${o.pred_spindle}/${o.pred_depth}/${o.pred_feed}</td>
            <td>${esc(o.model_version)}</td>
            <td>${o.adopted ? "是" : "否"}</td>
          </tr>`
        )
        .join("")
    : "";

  return `
    <div class="detail-meta">
      <div class="item"><div class="k">零件号</div><div class="v">${esc(d.part_no)}</div></div>
      <div class="item"><div class="k">名称</div><div class="v">${esc(d.part_name)}</div></div>
      <div class="item"><div class="k">材料</div><div class="v">${esc(d.material || "-")}</div></div>
      <div class="item"><div class="k">图号</div><div class="v">${esc(d.drawing_no || "-")}</div></div>
      <div class="item"><div class="k">分类</div><div class="v">${esc(d.category || "-")}</div></div>
      <div class="item"><div class="k">备注</div><div class="v">${esc(d.remark || "-")}</div></div>
      <div class="item"><div class="k">工序数</div><div class="v">${procs.length}</div></div>
      <div class="item"><div class="k">知识条目</div><div class="v">${know.length}</div></div>
    </div>

    <div class="detail-section">
      <h3>工序工艺（${procs.length}）</h3>
      <div class="detail-table-wrap">
        ${
          procs.length
            ? `<table><thead><tr><th>工序</th><th>名称</th><th>设备</th><th>刀具</th><th>转速</th><th>切深</th><th>进给</th></tr></thead><tbody>${procRows}</tbody></table>`
            : '<p class="detail-empty">暂无工序，请在「静态工艺」或 CSV 导入</p>'
        }
      </div>
    </div>

    <div class="detail-section">
      <h3>工艺知识（${know.length}）</h3>
      ${knowHtml}
    </div>

  ${
    opts.length
      ? `<div class="detail-section">
      <h3>优化记录（${opts.length}）</h3>
      <div class="detail-table-wrap">
        <table><thead><tr><th>设备</th><th>工序</th><th>推荐参数</th><th>模型</th><th>采纳</th></tr></thead><tbody>${optRows}</tbody></table>
      </div>
    </div>`
      : ""
  }
  `;
}

async function openPartDetail(partNo) {
  const modal = document.getElementById("detail-modal");
  const body = document.getElementById("detail-modal-body");
  const title = document.getElementById("detail-modal-title");
  if (!modal || !body) return;

  modal.classList.remove("hidden");
  modal.setAttribute("aria-hidden", "false");
  title.textContent = "加载中…";
  body.innerHTML = '<p class="detail-empty">正在加载零件详情…</p>';

  try {
    const d = await api(`/api/v1/parts/${encodeURIComponent(partNo)}`);
    title.textContent = `${d.part_no} · ${d.part_name || ""}`;
    body.innerHTML = renderPartDetailHtml(d);
  } catch (e) {
    title.textContent = "加载失败";
    body.innerHTML = `<p class="detail-empty">${esc(e.message)}</p>`;
  }
}

function initDetailModal() {
  document.getElementById("detail-modal-close")?.addEventListener("click", closeDetailModal);
  document.getElementById("detail-modal-backdrop")?.addEventListener("click", closeDetailModal);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeDetailModal();
  });
}

initDetailModal();

function showAccessUrl() {
  const host = location.hostname || "127.0.0.1";
  const port = location.port || "8090";
  const local = `http://127.0.0.1:${port}/`;
  const lan = host !== "127.0.0.1" && host !== "localhost" ? `http://${host}:${port}/` : null;
  const el = document.getElementById("access-url");
  if (!el) return;
  let html = `本机 <a href="${local}" target="_blank">${local}</a>`;
  if (lan) html += `<br>局域网 <a href="${lan}" target="_blank">${lan}</a>`;
  el.innerHTML = html;
}

let liveSource = null;

function stopLiveStream() {
  if (liveSource) {
    liveSource.close();
    liveSource = null;
  }
}

function renderLiveData(data) {
  const status = document.getElementById("live-status");
  const raw = document.getElementById("live-raw");
  const metrics = document.getElementById("live-metrics");
  if (!raw || !metrics) return;

  if (data.status === "NO_DATA") {
    status.textContent = "无数据";
    raw.textContent = "等待实时上报...";
    metrics.innerHTML = "";
    return;
  }

  status.textContent = data.status || "RUN";
  raw.textContent = JSON.stringify(data, null, 2);

  const items = [
    ["转速 rpm", data.spindle_speed],
    ["切深 mm", data.cutting_depth],
    ["进给", data.feed_rate],
    ["X轴", data.axis_x],
    ["Y轴", data.axis_y],
    ["Z轴", data.axis_z],
  ];
  metrics.innerHTML = items
    .map(
      ([k, v]) =>
        `<div class="metric-item"><div class="v">${v != null ? v : "-"}</div><div class="k">${k}</div></div>`
    )
    .join("");
}

function startLiveStream() {
  stopLiveStream();
  const auto = document.getElementById("live-auto");
  if (auto && !auto.checked) return;

  const eq = document.getElementById("live-equip")?.value || "CNC-01";
  const url = `/api/v1/stream/realtime?equipment_code=${encodeURIComponent(eq)}&interval_ms=1000`;
  liveSource = new EventSource(url);
  liveSource.onmessage = (ev) => {
    try {
      renderLiveData(JSON.parse(ev.data));
    } catch (e) {
      console.warn(e);
    }
  };
  liveSource.onerror = () => {
    const status = document.getElementById("live-status");
    if (status) status.textContent = "连接中断";
  };
}

async function apiUpload(path, formData) {
  const key = sessionStorage.getItem(STORAGE_KEY);
  const res = await fetch(path, {
    method: "POST",
    headers: key ? { "X-API-Key": key } : {},
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

function initUploadPage() {
  document.getElementById("up-template")?.addEventListener("click", () => {
    const kind = document.getElementById("up-kind").value;
    window.open(`/api/v1/import/template/${kind}`, "_blank");
  });

  document.getElementById("up-submit")?.addEventListener("click", async () => {
    const file = document.getElementById("up-file").files[0];
    if (!file) {
      toast("请选择 CSV 文件", true);
      return;
    }
    const kind = document.getElementById("up-kind").value;
    const fd = new FormData();
    fd.append("file", file);
    try {
      const r = await apiUpload(`/api/v1/import/csv/${kind}`, fd);
      let msg = `成功导入 ${r.imported ?? 0} 条`;
      if (r.skipped != null) msg += `，跳过 ${r.skipped} 条（重复或缺字段）`;
      if (r.hint) msg += `。${r.hint}`;
      document.getElementById("up-result").textContent = msg;
      toast(r.imported > 0 ? `已导入 ${r.imported} 条` : msg, !r.imported && (r.skipped || r.hint));
      loadDashboard();
    } catch (e) {
      toast(e.message, true);
    }
  });

  document.getElementById("up-json-btn")?.addEventListener("click", async () => {
    const text = document.getElementById("up-json").value.trim();
    if (!text) return;
    try {
      const payload = JSON.parse(text);
      const r = await api("/api/v1/import/json", { method: "POST", body: JSON.stringify(payload) });
      toast("JSON 导入完成: " + JSON.stringify(r.imported));
      loadDashboard();
    } catch (e) {
      toast(e.message || "JSON 格式错误", true);
    }
  });

  document.getElementById("rt-quick-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const body = {
      equipment_code: document.getElementById("rt-eq").value,
      part_no: document.getElementById("rt-part").value,
      spindle_speed: parseFloat(document.getElementById("rt-speed").value),
      cutting_depth: parseFloat(document.getElementById("rt-depth").value),
      feed_rate: parseFloat(document.getElementById("rt-feed").value),
      status: "RUN",
    };
    try {
      await api("/api/v1/machining/realtime", { method: "POST", body: JSON.stringify(body) });
      toast("实时数据已上报");
    } catch (err) {
      toast(err.message, true);
    }
  });
}

function initLivePage() {
  document.getElementById("live-equip")?.addEventListener("change", startLiveStream);
  document.getElementById("live-auto")?.addEventListener("change", () => {
    if (document.getElementById("live-auto").checked) startLiveStream();
    else stopLiveStream();
  });
}

// hook nav
const _navBtns = document.querySelectorAll(".nav-btn");
_navBtns.forEach((btn) => {
  btn.addEventListener("click", () => {
    const page = btn.dataset.page;
    if (page === "live") startLiveStream();
    else stopLiveStream();
    if (page === "upload") {
      /* no-op */
    }
  });
});

initUploadPage();
initLivePage();

const _origLogin = document.getElementById("login-form");
if (_origLogin) {
  _origLogin.addEventListener("submit", () => setTimeout(showAccessUrl, 500));
}

document.getElementById("btn-seed-3000")?.addEventListener("click", async () => {
  if (!confirm("将向数据库写入约 3000 条批量数据（零件+工序+知识+优化），可能需要 10–30 秒，继续？")) return;
  const btn = document.getElementById("btn-seed-3000");
  if (btn) btn.disabled = true;
  try {
    toast("正在导入，请稍候…");
    const r = await api("/api/v1/import/seed-bulk?total=3000", { method: "POST", body: "{}" });
    toast(`完成：共 ${r.imported.total} 条（零件 ${r.imported.parts} / 工序 ${r.imported.processes} / 知识 ${r.imported.knowledge} / 优化 ${r.imported.optimization}）`);
    loadDashboard();
  } catch (e) {
    toast(e.message, true);
  } finally {
    if (btn) btn.disabled = false;
  }
});

document.getElementById("btn-reseed")?.addEventListener("click", async () => {
  if (!confirm("合并导入演示数据（不删除已有数据）？")) return;
  try {
    await api("/api/v1/import/reseed", { method: "POST", body: "{}" });
    toast("演示数据已加载");
    loadDashboard();
  } catch (e) {
    toast(e.message, true);
  }
});

if (sessionStorage.getItem(STORAGE_KEY)) {
  showAccessUrl();
}
