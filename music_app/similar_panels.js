/* The two setting panels, the profiles list, and on-demand analysis.
 * Kept apart from similar.js so neither file becomes the place where every
 * change lands.
 */
const GROUP_LABEL = { audio: "Zvuk (embeddingy)", tags: "Tagy", numbers: "Čísla", musical: "Hudobné" };
const GROUP_NOTE  = { audio: "ako to naozaj znie", tags: "každý typ tagu zvlášť",
                      numbers: "hľadá najbližšiu hodnotu", musical: "tempo a tónina" };
const GROUP_DEFAULT_W = { audio: 1.0, tags: 0.15, numbers: 0.12, musical: 0.3 };

/* ---------- COMPARE panel: what should be alike ---------- */
function renderCompare(signals) {
  const groups = {};
  signals.forEach(s => (groups[s.group] = groups[s.group] || []).push(s));
  $("cmpBody").innerHTML = Object.entries(groups).map(([g, list]) => `
    <div class="grp">
      <div class="grp-head">
        <span class="name">${esc(GROUP_LABEL[g] || g)}</span>
        <span class="muted">${esc(GROUP_NOTE[g] || "")}</span>
        <button data-all="${g}">všetko</button><button data-none="${g}">nič</button>
        <span class="muted">váha</span>
        <input type="range" min="0" max="2" step="0.05" style="width:90px"
               data-w="${g}" value="${GROUP_DEFAULT_W[g] ?? 0.5}">
        <span class="muted" data-wv="${g}">${(GROUP_DEFAULT_W[g] ?? 0.5).toFixed(2)}</span>
      </div>
      <div class="grid">
        ${list.map(s => `<label class="sig" title="${esc(s.note || "")} · ${s.coverage.toLocaleString()} trackov">
            <input type="checkbox" data-sig="${esc(s.id)}" ${s.default ? "checked" : ""}>
            <span class="nm">${esc(s.label)}</span>
            <span class="cov">${Math.round(s.coverage / 1000)}k</span>
            <input type="number" step="0.1" min="0" max="9" data-sw="${esc(s.id)}"
                   value="${(s.weight ?? 1).toFixed(1)}" title="Váha tohto signálu">
          </label>`).join("")}
      </div>
    </div>`).join("");

  $("cmpBody").querySelectorAll("[data-all]").forEach(b => b.onclick = () =>
    setGroup("#cmpBody", b.dataset.all, true));
  $("cmpBody").querySelectorAll("[data-none]").forEach(b => b.onclick = () =>
    setGroup("#cmpBody", b.dataset.none, false));
  $("cmpBody").querySelectorAll("[data-w]").forEach(sl => sl.oninput = () =>
    $("cmpBody").querySelector(`[data-wv="${sl.dataset.w}"]`).textContent = (+sl.value).toFixed(2));
  $("cmpBody").addEventListener("change", e => {
    if (e.target.dataset.sig || e.target.dataset.sw || e.target.dataset.w) rerun();
  });
}
function setGroup(scope, g, on) {
  document.querySelectorAll(`${scope} .grp`).forEach(div => {
    if (div.querySelector(`[data-all="${g}"],[data-none="${g}"]`))
      div.querySelectorAll("[data-sig]").forEach(cb => cb.checked = on);
  });
  rerun();
}

/* ---------- SHIFT panel: what should differ ---------- */
function renderShift(signals) {
  const shiftable = signals.filter(s => s.group !== "musical");
  const groups = {};
  shiftable.forEach(s => (groups[s.group] = groups[s.group] || []).push(s));
  $("shiftBody").innerHTML = `
    <div class="grp">
      <div class="grp-head"><span class="name">Harmonicky</span>
        <span class="muted">čo sa smie objaviť podľa tóniny (Camelot)</span></div>
      <div class="row">
        ${[["exact","rovnaká"],["relative","relatívna"],["step1","±1"],["step2","±2"],
           ["semitone","±7 (poltón)"]].map(([v, l]) =>
          `<label class="muted"><input type="checkbox" class="kr" value="${v}"> ${l}</label>`).join("")}
      </div>
    </div>` + Object.entries(groups).map(([g, list]) => `
    <div class="grp">
      <div class="grp-head"><span class="name">${esc(GROUP_LABEL[g] || g)}</span>
        <span class="muted">= rovnaké · ≠ odlišné${g === "numbers" ? " · → mier na hodnotu" : ""}</span></div>
      <div class="grid">
        ${list.map(s => `<label class="sig">
            <span class="nm">${esc(s.label)}</span>
            <select data-md="${esc(s.id)}">
              <option value="same">=</option><option value="diff">≠</option>
              ${g === "numbers" ? '<option value="target">→</option>' : ""}
            </select>
            ${g === "numbers" ? `<input type="number" step="0.05" style="width:52px"
                data-tg="${esc(s.id)}" placeholder="cieľ">` : ""}
          </label>`).join("")}
      </div>
    </div>`).join("");
  $("shiftBody").addEventListener("change", e => {
    if (e.target.dataset.md || e.target.dataset.tg || e.target.classList.contains("kr")) rerun();
  });
}

/* ---------- hard tag rules ---------- */
function addRule(preset) {
  const types = Object.keys(state.tagValues).sort();
  const div = document.createElement("div");
  div.className = "rule";
  div.innerHTML = `
    <select data-rt>${types.map(t => `<option>${esc(t)}</option>`).join("")}</select>
    <select data-rm><option value="must">musí obsahovať</option>
                    <option value="must_not">nesmie obsahovať</option></select>
    <input class="val" data-rv list="tagvals" placeholder="napr. drum and bass">
    <button class="ghost" data-rx>✕</button>`;
  $("rules").appendChild(div);
  if (preset) {
    div.querySelector("[data-rt]").value = preset.type || types[0];
    div.querySelector("[data-rm]").value = preset.mode || "must";
    div.querySelector("[data-rv]").value = preset.value || "";
  }
  const refreshList = () => {
    const vals = state.tagValues[div.querySelector("[data-rt]").value] || [];
    document.getElementById("tagvals").innerHTML =
      vals.slice(0, 300).map(v => `<option value="${esc(v)}">`).join("");
  };
  div.querySelector("[data-rt]").onchange = () => { refreshList(); rerun(); };
  div.querySelector("[data-rt]").onfocus = refreshList;
  div.querySelector("[data-rv]").onfocus = refreshList;
  div.querySelector("[data-rm]").onchange = rerun;
  div.querySelector("[data-rv]").onchange = rerun;
  div.querySelector("[data-rx]").onclick = () => { div.remove(); rerun(); };
}
$("addRule").onclick = () => addRule();

/* ---------- presets ---------- */
async function loadPresets() {
  const { presets } = await api("/api/similar/presets");
  state.presets = presets;
  renderPresets();
  applyPreset(0, false);
}

function renderPresets() {
  const hidden = hiddenPresets();
  $("presets").innerHTML = '<span class="muted">Režim:</span>' + state.presets.map((p, i) =>
    hidden.has(p.id) ? "" :
    `<span class="chipwrap"><button class="chip" data-p="${i}" title="${esc(p.note)}">${esc(p.label)}</button>`
    + `<button class="ghost" data-hide="${esc(p.id)}" title="Odopnúť z lišty">✕</button></span>`).join("")
    + (hidden.size ? `<button class="ghost" id="showHidden">+ ${hidden.size} skrytých</button>` : "");
  $("presets").querySelectorAll("[data-p]").forEach(b => b.onclick = () => applyPreset(+b.dataset.p));
  $("presets").querySelectorAll("[data-hide]").forEach(b => b.onclick = () => togglePreset(b.dataset.hide));
  const show = document.getElementById("showHidden");
  if (show) show.onclick = () => { localStorage.setItem("hiddenPresets", "[]"); renderPresets(); };
}

/* Pinned profiles sit on the same bar as the built-in modes — the owner asked
 * for them to look and behave the same, not to live inside a panel. */
function renderPins() {
  const pinned = (state.profiles || []).filter(p => p.pinned);
  $("pins").innerHTML = pinned.length
    ? '<span class="muted">Moje:</span>' + pinned.map(p =>
        `<span class="chipwrap"><button class="chip" data-open="${p.id}">${esc(p.name)}</button>`
        + `<button class="ghost" data-unpin="${p.id}" title="Odopnúť">✕</button></span>`).join("")
    : "";
  $("pins").querySelectorAll("[data-open]").forEach(b => b.onclick = () => {
    applySettings(state.profiles.find(x => x.id === b.dataset.open)); rerun();
    $("pins").querySelectorAll(".chip").forEach(c => c.classList.toggle("on", c === b));
    $("presets").querySelectorAll(".chip").forEach(c => c.classList.remove("on"));
  });
  $("pins").querySelectorAll("[data-unpin]").forEach(b => b.onclick = async () => {
    const p = state.profiles.find(x => x.id === b.dataset.unpin);
    await api("/api/profiles/save", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...p, pinned: false }) });
    loadProfiles();
  });
}
/* Which built-in modes the owner wants on the bar. They asked to be able to
 * unpin the system ones too, so hidden ids live beside the rest of the UI
 * state — in the browser, because it is a per-screen preference, not data. */
const hiddenPresets = () => new Set(JSON.parse(localStorage.getItem("hiddenPresets") || "[]"));
function togglePreset(id) {
  const h = hiddenPresets();
  h.has(id) ? h.delete(id) : h.add(id);
  localStorage.setItem("hiddenPresets", JSON.stringify([...h]));
  renderPresets(); renderPins();
}

function applyPreset(i, run = true) {
  const p = state.presets[i]; if (!p) return;
  $("presets").querySelectorAll("[data-p]").forEach(b => b.classList.toggle("on", +b.dataset.p === i));
  const want = new Set(p.enabled);
  document.querySelectorAll("#cmpBody [data-sig]").forEach(cb => cb.checked = want.has(cb.dataset.sig));
  Object.entries(p.group_weights || {}).forEach(([g, w]) => {
    const sl = document.querySelector(`#cmpBody [data-w="${g}"]`);
    if (sl) { sl.value = w; document.querySelector(`#cmpBody [data-wv="${g}"]`).textContent = (+w).toFixed(2); }
  });
  const f = p.filters || {};
  const kr = new Set(f.same_key ? ["exact"] : []);
  document.querySelectorAll("#shiftBody .kr").forEach(c => c.checked = kr.has(c.value));
  if (run) rerun();
}

/* ---------- profiles ---------- */
function currentSettings() {
  return { enabled: enabledSignals(), group_weights: groupWeights(),
           signal_weights: signalWeights(), signal_modes: signalModes(),
           filters: { key_rules: keyRules(), tag_rules: tagRules(),
                      limit: +$("limit").value, spotify_only: $("spotifyOnly").checked } };
}
function applySettings(s) {
  const want = new Set(s.enabled || []);
  document.querySelectorAll("#cmpBody [data-sig]").forEach(cb => cb.checked = want.has(cb.dataset.sig));
  Object.entries(s.group_weights || {}).forEach(([g, w]) => {
    const sl = document.querySelector(`#cmpBody [data-w="${g}"]`);
    if (sl) { sl.value = w; document.querySelector(`#cmpBody [data-wv="${g}"]`).textContent = (+w).toFixed(2); }
  });
  Object.entries(s.signal_weights || {}).forEach(([id, w]) => {
    const el = document.querySelector(`#cmpBody [data-sw="${CSS.escape(id)}"]`);
    if (el) el.value = w;
  });
  document.querySelectorAll("#shiftBody [data-md]").forEach(sel => sel.value = "same");
  document.querySelectorAll("#shiftBody [data-tg]").forEach(t => t.value = "");
  Object.entries(s.signal_modes || {}).forEach(([id, spec]) => {
    const sel = document.querySelector(`#shiftBody [data-md="${CSS.escape(id)}"]`);
    if (!sel) return;
    sel.value = spec.mode;
    if (spec.mode === "target") {
      const tg = document.querySelector(`#shiftBody [data-tg="${CSS.escape(id)}"]`);
      if (tg && spec.target != null) tg.value = spec.target;
    }
  });
  const f = s.filters || {};
  const kr = new Set(f.key_rules || []);
  document.querySelectorAll("#shiftBody .kr").forEach(c => c.checked = kr.has(c.value));
  $("rules").innerHTML = "";
  (f.tag_rules || []).forEach(r => addRule(r));
  if (f.limit) $("limit").value = f.limit;
  if (f.spotify_only != null) $("spotifyOnly").checked = !!f.spotify_only;
}

async function loadProfiles() {
  const { profiles } = await api("/api/profiles");
  state.profiles = profiles;
  renderPins();

  // Folders are stored as a path ("Techno/Peak/Vocal"), so the tree is built by
  // splitting on "/" — one flat list renders at any depth, and a folder can be
  // collapsed like anywhere else.
  const root = { kids: {}, items: [] };
  profiles.forEach(p => {
    let node = root;
    (p.folder || "").split("/").filter(Boolean).forEach(part => {
      node.kids[part] = node.kids[part] || { kids: {}, items: [] };
      node = node.kids[part];
    });
    node.items.push(p);
  });

  const collapsed = new Set(JSON.parse(localStorage.getItem("collapsedFolders") || "[]"));
  const rowHtml = p => `
    <div class="rule">
      <button class="chip" data-open="${p.id}">${esc(p.name)}</button>
      <span class="muted">${(p.enabled || []).length} signálov</span>
      <button class="ghost" data-pin="${p.id}" title="${p.pinned ? "Odopnúť" : "Pripnúť na lištu"}">${p.pinned ? "📌" : "📍"}</button>
      <button class="ghost" data-edit="${p.id}" title="Premenovať / presunúť">✎</button>
      <button class="ghost" data-upd="${p.id}" title="Prepíš aktuálnym nastavením">⟳</button>
      <button class="ghost" data-del="${p.id}" title="Zmazať">✕</button>
    </div>`;
  const nodeHtml = (node, path) => {
    const folders = Object.keys(node.kids).sort().map(name => {
      const full = path ? `${path}/${name}` : name;
      const shut = collapsed.has(full);
      return `<div>
          <div class="tree-folder" data-folder="${esc(full)}">
            <span class="caret">${shut ? "▸" : "▾"}</span>📁 ${esc(name)}
          </div>
          <div class="tree-kids ${shut ? "hidden" : ""}">${nodeHtml(node.kids[name], full)}</div>
        </div>`;
    }).join("");
    return folders + node.items.map(rowHtml).join("");
  };
  $("profiles").innerHTML = profiles.length ? nodeHtml(root, "")
    : '<span class="muted">Zatiaľ žiadne profily.</span>';

  $("profiles").querySelectorAll(".tree-folder").forEach(el => el.onclick = () => {
    const full = el.dataset.folder;
    const c = new Set(JSON.parse(localStorage.getItem("collapsedFolders") || "[]"));
    c.has(full) ? c.delete(full) : c.add(full);
    localStorage.setItem("collapsedFolders", JSON.stringify([...c]));
    loadProfiles();
  });

  const find = id => state.profiles.find(x => x.id === id);
  $("profiles").querySelectorAll("[data-open]").forEach(b => b.onclick = () => {
    applySettings(find(b.dataset.open)); rerun(); });
  $("profiles").querySelectorAll("[data-pin]").forEach(b => b.onclick = async () => {
    const p = find(b.dataset.pin);
    await api("/api/profiles/save", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...p, pinned: !p.pinned }) }); loadProfiles(); });
  $("profiles").querySelectorAll("[data-del]").forEach(b => b.onclick = async () => {
    const p = find(b.dataset.del);
    if (!confirm(`Zmazať profil "${p.name}"?`)) return;
    await api("/api/profiles/delete", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: p.id }) }); loadProfiles(); });
  $("profiles").querySelectorAll("[data-edit]").forEach(b => b.onclick = async () => {
    const p = find(b.dataset.edit);
    const name = prompt("Názov profilu:", p.name); if (name === null) return;
    const folder = prompt("Priečinok (lomítko = podpriečinok):", p.folder || ""); if (folder === null) return;
    await api("/api/profiles/save", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...p, name, folder }) }); loadProfiles(); });
  $("profiles").querySelectorAll("[data-upd]").forEach(b => b.onclick = async () => {
    const p = find(b.dataset.upd);
    if (!confirm(`Prepísať "${p.name}" tým, čo je teraz nastavené?`)) return;
    await api("/api/profiles/save", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...p, ...currentSettings() }) }); loadProfiles(); });
}

$("btnSave").onclick = async () => {
  const name = prompt("Názov profilu:"); if (!name) return;
  const folder = prompt("Priečinok (nepovinné):", "") || "";
  await api("/api/profiles/save", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, folder, ...currentSettings() }) });
  // Unfold the profiles panel if it happened to be folded away, so the
  // freshly saved profile is visible where it landed.
  const shut = shutPanels(); shut.delete("panelProfiles");
  localStorage.setItem("shutPanels", JSON.stringify([...shut])); paintPanels();
  loadProfiles();
};

/* ---------- on-demand analysis ---------- */
async function analyzeNow(ids) {
  if (!ids.length) return;
  $("job").classList.add("on");
  $("job").textContent = `spúšťam analýzu ${ids.length} track(ov)…`;
  try {
    const job = await api("/api/analyze", { method: "POST",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ids }) });
    pollJob(job.id);
  } catch (e) { $("job").innerHTML = `<span style="color:#ff8080">${esc(e.message)}</span>`; }
}
async function pollJob(id) {
  try {
    const j = await api("/api/analyze/status?job=" + encodeURIComponent(id));
    const last = (j.lines || []).slice(-1)[0] || "";
    const mins = ((Date.now() / 1000 - j.started) / 60).toFixed(1);
    if (j.state === "running") {
      $("job").textContent = `Analyzujem ${j.total} · ${mins} min · ${last}`;
      return setTimeout(() => pollJob(id), 3000);
    }
    $("job").textContent = j.state === "done"
      ? `Hotovo — ${j.total} track(ov) za ${mins} min. Dáta sú uložené v databáze.`
      : `Nepodarilo sa — ${last}`;
  } catch { $("job").textContent = "chyba pri sledovaní úlohy"; }
}

/* ---------- boot ---------- */
(async function boot() {
  pollReady();
  loadSinks();
  const dl = document.createElement("datalist"); dl.id = "tagvals"; document.body.appendChild(dl);
  const [{ signals }, vals] = await Promise.all([
    api("/api/similar/signals"),
    api("/api/similar/tag-values").catch(() => ({ values: {} })),
  ]);
  state.signals = signals;
  state.tagValues = vals.values || {};
  renderCompare(signals);
  renderShift(signals);
  await loadPresets();
  await loadProfiles();
})();
