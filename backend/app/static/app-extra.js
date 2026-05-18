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
      document.getElementById("up-result").textContent = `成功导入 ${r.imported} 条`;
      toast(`已导入 ${r.imported} 条`);
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
