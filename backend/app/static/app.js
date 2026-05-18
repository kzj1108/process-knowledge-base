const API = "";
const STORAGE_KEY = "pkb_api_key";

function headers() {
  const h = { "Content-Type": "application/json" };
  const key = sessionStorage.getItem(STORAGE_KEY);
  if (key) h["X-API-Key"] = key;
  return h;
}

async function api(path, opts = {}) {
  const res = await fetch(API + path, { ...opts, headers: { ...headers(), ...opts.headers } });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  if (res.status === 204) return null;
  return res.json();
}

function toast(msg, isError = false) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.className = "toast" + (isError ? " error" : "");
  el.classList.remove("hidden");
  setTimeout(() => el.classList.add("hidden"), 3000);
}

function showPage(name) {
  document.querySelectorAll(".tab-page").forEach((p) => p.classList.remove("active"));
  document.querySelectorAll(".nav-btn").forEach((b) => b.classList.remove("active"));
  document.getElementById("page-" + name)?.classList.add("active");
  document.querySelector(`[data-page="${name}"]`)?.classList.add("active");
}

document.getElementById("login-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  try {
    const data = await api("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ username: fd.get("username"), password: fd.get("password") }),
    });
    sessionStorage.setItem(STORAGE_KEY, data.api_key);
    document.getElementById("login-screen").classList.add("hidden");
    document.getElementById("app").style.display = "grid";
    loadDashboard();
  } catch (err) {
    toast(err.message, true);
  }
});

document.getElementById("logout-btn")?.addEventListener("click", () => {
  sessionStorage.removeItem(STORAGE_KEY);
  location.reload();
});

document.querySelectorAll(".nav-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const page = btn.dataset.page;
    showPage(page);
    if (page === "dashboard") loadDashboard();
    if (page === "knowledge") loadKnowledge();
    if (page === "process") loadProcess();
    if (page === "parts") loadParts();
    if (page === "equipment") loadEquipment();
    if (page === "dynamic") loadDynamic();
    if (page === "upload") {
      /* handlers in app-extra.js */
    }
    if (page === "live" && typeof startLiveStream === "function") startLiveStream();
  });
});

async function loadDashboard() {
  const d = await api("/api/v1/stats/dashboard");
  const grid = document.getElementById("stats-grid");
  const labels = {
    parts: "零件",
    equipment: "设备",
    processes: "工序工艺",
    knowledge: "知识条目",
    realtime_records: "实时记录",
    optimization_runs: "优化记录",
  };
  grid.innerHTML = Object.entries(d.counts)
    .map(
      ([k, v]) =>
        `<div class="stat-card"><div class="num">${v}</div><div class="label">${labels[k] || k}</div></div>`
    )
    .join("");

  document.getElementById("recent-knowledge").innerHTML =
    d.recent_knowledge
      .map((k) => `<tr><td><span class="badge">${k.category}</span></td><td>${k.title}</td><td>${k.related_part_no || "-"}</td></tr>`)
      .join("") || "<tr><td colspan='3'>暂无</td></tr>";

  document.getElementById("recent-opt").innerHTML =
    d.recent_optimization
      .map(
        (o) =>
          `<tr><td>${o.equipment_code}</td><td>${o.part_no || "-"}</td><td>${o.pred_spindle}/${o.pred_depth}/${o.pred_feed}</td><td>${o.adopted ? "已采纳" : "未采纳"}</td></tr>`
      )
      .join("") || "<tr><td colspan='4'>暂无</td></tr>";
}

async function loadKnowledge() {
  const q = document.getElementById("k-search").value;
  const cat = document.getElementById("k-category").value;
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (cat) params.set("category", cat);
  const data = await api("/api/v1/knowledge?" + params);
  const tbody = document.getElementById("k-table");
  tbody.innerHTML = data.items
    .map(
      (k) => `<tr>
        <td>${k.id}</td>
        <td><span class="badge">${k.category}</span></td>
        <td>${k.title}</td>
        <td>${k.related_part_no || "-"}</td>
        <td>${k.status}</td>
        <td>
          <button class="secondary" data-edit-k="${k.id}">编辑</button>
          <button class="danger" data-del-k="${k.id}">删除</button>
        </td>
      </tr>`
    )
    .join("");
  tbody.querySelectorAll("[data-edit-k]").forEach((btn) => {
    btn.onclick = () => editKnowledge(btn.dataset.editK);
  });
  tbody.querySelectorAll("[data-del-k]").forEach((btn) => {
    btn.onclick = () => deleteKnowledge(btn.dataset.delK);
  });
}

async function editKnowledge(id) {
  const k = await api(`/api/v1/knowledge/${id}`);
  document.getElementById("k-id").value = k.id;
  document.getElementById("k-title").value = k.title;
  document.getElementById("k-category-form").value = k.category;
  document.getElementById("k-content").value = k.content;
  document.getElementById("k-tags").value = k.tags || "";
  document.getElementById("k-part").value = k.related_part_no || "";
  document.getElementById("k-op").value = k.related_op_no || "";
  document.getElementById("k-author").value = k.author || "";
}

async function deleteKnowledge(id) {
  if (!confirm("确认删除该知识条目？")) return;
  await api(`/api/v1/knowledge/${id}`, { method: "DELETE" });
  toast("已删除");
  loadKnowledge();
}

document.getElementById("k-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const id = document.getElementById("k-id").value;
  const body = {
    category: document.getElementById("k-category-form").value,
    title: document.getElementById("k-title").value,
    content: document.getElementById("k-content").value,
    tags: document.getElementById("k-tags").value,
    related_part_no: document.getElementById("k-part").value || null,
    related_op_no: parseInt(document.getElementById("k-op").value, 10) || null,
    author: document.getElementById("k-author").value,
    status: "PUBLISHED",
  };
  try {
    if (id) {
      await api(`/api/v1/knowledge/${id}`, { method: "PUT", body: JSON.stringify(body) });
      toast("已更新");
    } else {
      await api("/api/v1/knowledge", { method: "POST", body: JSON.stringify(body) });
      toast("已创建");
    }
    e.target.reset();
    document.getElementById("k-id").value = "";
    loadKnowledge();
  } catch (err) {
    toast(err.message, true);
  }
});

document.getElementById("k-search-btn")?.addEventListener("click", loadKnowledge);

async function loadProcess() {
  const part = document.getElementById("p-filter-part").value;
  const params = new URLSearchParams();
  if (part) params.set("part_no", part);
  const data = await api("/api/v1/process/list?" + params);
  document.getElementById("p-table").innerHTML = data.items
    .map(
      (p) => `<tr>
        <td>${p.id}</td>
        <td>${p.part_no}</td>
        <td>${p.operation_no}</td>
        <td>${p.operation_name}</td>
        <td>${p.spindle_speed}/${p.cutting_depth}/${p.feed_rate}</td>
        <td>${p.equipment_code || "-"}</td>
        <td><button class="danger" data-del-p="${p.id}">停用</button></td>
      </tr>`
    )
    .join("");
  document.querySelectorAll("[data-del-p]").forEach((btn) => {
    btn.onclick = async () => {
      await api(`/api/v1/process/${btn.dataset.delP}?soft=true`, { method: "DELETE" });
      toast("已停用");
      loadProcess();
    };
  });
}

document.getElementById("p-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = {
    part_no: document.getElementById("p-part").value,
    part_name: document.getElementById("p-partname").value,
    material: document.getElementById("p-material").value,
    operation_no: parseInt(document.getElementById("p-opno").value, 10),
    operation_name: document.getElementById("p-opname").value,
    equipment_code: document.getElementById("p-equip").value,
    tool_code: document.getElementById("p-tool").value,
    spindle_speed: parseFloat(document.getElementById("p-speed").value),
    cutting_depth: parseFloat(document.getElementById("p-depth").value),
    feed_rate: parseFloat(document.getElementById("p-feed").value),
    speed_min: parseFloat(document.getElementById("p-speed-min").value) || null,
    speed_max: parseFloat(document.getElementById("p-speed-max").value) || null,
    approved_by: document.getElementById("p-approver").value,
  };
  try {
    await api("/api/v1/process/static", { method: "POST", body: JSON.stringify(body) });
    toast("工艺已添加");
    e.target.reset();
    loadProcess();
  } catch (err) {
    toast(err.message, true);
  }
});

document.getElementById("p-filter-btn")?.addEventListener("click", loadProcess);

async function loadParts() {
  const q = (document.getElementById("parts-search")?.value || "").trim();
  const params = q ? `?q=${encodeURIComponent(q)}` : "";
  const data = await api("/api/v1/parts" + params);
  const hint = document.getElementById("parts-search-hint");
  if (hint) {
    hint.textContent = q
      ? `共 ${data.length} 条匹配「${q}」`
      : data.length
        ? `共 ${data.length} 条`
        : "";
  }
  const tbody = document.getElementById("parts-table");
  if (!data.length) {
    tbody.innerHTML = `<tr><td colspan="5">${q ? "未找到匹配的零件，请换个关键词" : "暂无零件数据"}</td></tr>`;
    return;
  }
  tbody.innerHTML = data
    .map(
      (p) => `<tr>
        <td>${p.part_no}</td>
        <td>${p.part_name}</td>
        <td>${p.material || "-"}</td>
        <td>${p.category || "-"}</td>
        <td><button class="secondary" data-view-part="${p.part_no}">详情</button></td>
      </tr>`
    )
    .join("");
  document.querySelectorAll("[data-view-part]").forEach((btn) => {
    btn.onclick = () => openPartDetail(btn.dataset.viewPart);
  });
}

document.getElementById("parts-search-btn")?.addEventListener("click", loadParts);
document.getElementById("parts-search-clear")?.addEventListener("click", () => {
  const input = document.getElementById("parts-search");
  if (input) input.value = "";
  loadParts();
});
document.getElementById("parts-search")?.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    loadParts();
  }
});

document.getElementById("part-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = {
    part_no: document.getElementById("part-no").value,
    part_name: document.getElementById("part-name").value,
    material: document.getElementById("part-mat").value,
    category: document.getElementById("part-cat").value,
  };
  try {
    await api("/api/v1/parts", { method: "POST", body: JSON.stringify(body) });
    toast("零件已添加");
    e.target.reset();
    loadParts();
  } catch (err) {
    toast(err.message, true);
  }
});

async function loadEquipment() {
  const data = await api("/api/v1/equipment");
  document.getElementById("equip-table").innerHTML = data
    .map(
      (e) => `<tr>
        <td>${e.code}</td>
        <td>${e.name}</td>
        <td>${e.type}</td>
        <td>${e.model || "-"}</td>
        <td>${e.workshop || "-"}</td>
      </tr>`
    )
    .join("");
}

document.getElementById("equip-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = {
    code: document.getElementById("eq-code").value,
    name: document.getElementById("eq-name").value,
    type: document.getElementById("eq-type").value,
    model: document.getElementById("eq-model").value,
    workshop: document.getElementById("eq-shop").value,
  };
  try {
    await api("/api/v1/equipment", { method: "POST", body: JSON.stringify(body) });
    toast("设备已添加");
    e.target.reset();
    loadEquipment();
  } catch (err) {
    toast(err.message, true);
  }
});

async function loadDynamic() {
  const eq = document.getElementById("dyn-equip").value || "CNC-01";
  try {
    const rt = await api(`/api/v1/machining/realtime/latest?equipment_code=${encodeURIComponent(eq)}`);
    document.getElementById("dyn-realtime").textContent = JSON.stringify(rt, null, 2);
  } catch {
    document.getElementById("dyn-realtime").textContent = "无实时数据";
  }
  const hist = await api(`/api/v1/optimization/history?equipment_code=${encodeURIComponent(eq)}&limit=20`);
  document.getElementById("dyn-opt-table").innerHTML = hist
    .map(
      (o) => `<tr>
        <td>${o.id}</td>
        <td>${o.part_no || "-"}</td>
        <td>${o.pred_spindle} / ${o.pred_depth} / ${o.pred_feed}</td>
        <td>${o.model_version}</td>
        <td>${o.adopted ? "是" : "否"}</td>
        <td>${o.created_at}</td>
      </tr>`
    )
    .join("");
}

document.getElementById("dyn-refresh")?.addEventListener("click", loadDynamic);

if (sessionStorage.getItem(STORAGE_KEY)) {
  document.getElementById("login-screen").classList.add("hidden");
  document.getElementById("app").style.display = "grid";
  loadDashboard();
}
