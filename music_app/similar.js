/* Similarity browser — the DJ-facing screen.
 *
 * Split out of the HTML so the markup stays readable and this stays reviewable.
 * Three ideas run through it:
 *   COMPARE  what should be alike            -> panelCompare
 *   SHIFT    what should deliberately differ -> panelShift (modes + hard tag rules)
 *   ACT      audition, pivot, hand to Traktor
 */
const $ = id => document.getElementById(id);
const P = $("player");
const state = { rows: [], index: -1, refId: null, signals: [], presets: [],
                profiles: [], picked: new Set(), lastClicked: -1, tagValues: {} };

const esc = s => (s == null ? "" : String(s)).replace(/[<>&"]/g,
  c => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;" }[c]));
const mmss = s => (!isFinite(s) || s < 0) ? "0:00"
  : Math.floor(s / 60) + ":" + String(Math.floor(s % 60)).padStart(2, "0");
const toast = (html, ms = 7000) => { const t = $("toast"); t.innerHTML = html;
  t.style.display = "block"; clearTimeout(t._t); t._t = setTimeout(() => t.style.display = "none", ms); };

async function api(path, opts) {
  const r = await fetch(path, opts);
  const j = await r.json().catch(() => ({ error: "server neodpovedal" }));
  if (j.error) throw new Error(j.error);
  return j;
}

/* ---------------- panels ---------------- */
const panels = { btnCompare: "panelCompare", btnShift: "panelShift", btnProfiles: "panelProfiles" };
Object.entries(panels).forEach(([btn, id]) => $(btn).onclick = () => {
  const open = $(id).classList.contains("open");
  Object.values(panels).forEach(p => $(p).classList.remove("open"));
  if (!open) $(id).classList.add("open");
});

/* ---------------- readiness ---------------- */
async function pollReady() {
  try {
    const s = await api("/api/similar/status");
    if (s.error) return $("status").textContent = "Chyba: " + s.error;
    if (s.ready) return $("status").textContent = `${s.tracks.toLocaleString()} zanalyzovaných`;
    $("status").textContent = "načítavam odtlačky… (raz za spustenie)";
  } catch { $("status").textContent = "server nedostupný"; }
  setTimeout(pollReady, 2500);
}

/* ---------------- search ---------------- */
let timer;
$("search").oninput = () => { clearTimeout(timer); timer = setTimeout(doSearch, 250); };
$("search").onblur = () => setTimeout(() => $("hits").style.display = "none", 200);

async function doSearch() {
  const q = $("search").value.trim();
  if (q.length < 2) return $("hits").style.display = "none";
  const { results } = await api("/api/similar/search?q=" + encodeURIComponent(q));
  $("hits").innerHTML = results.length ? results.map(r => `
    <div data-id="${esc(r.spotify_id)}">
      <span>${esc(r.artist)} — ${esc(r.title)}</span>
      ${r.analysed === false ? '<span class="muted">bez analýzy</span>'
        + `<button data-an="${esc(r.spotify_id)}">Analyzuj</button>` : ""}
    </div>`).join("") : '<div class="no">nič sa nenašlo</div>';
  $("hits").style.display = "block";
  $("hits").querySelectorAll("div[data-id]").forEach(el => el.onclick = ev => {
    if (ev.target.dataset.an) return;
    pick(el.dataset.id, el.querySelector("span").textContent);
  });
  $("hits").querySelectorAll("[data-an]").forEach(b => b.onclick = ev => {
    ev.stopPropagation(); analyzeNow([b.dataset.an]);
  });
}

/* ---------------- the query ---------------- */
const enabledSignals = () => [...document.querySelectorAll("#cmpBody [data-sig]:checked")].map(c => c.dataset.sig);
const groupWeights = () => Object.fromEntries(
  [...document.querySelectorAll("#cmpBody [data-w]")].map(s => [s.dataset.w, +s.value]));
const signalWeights = () => Object.fromEntries(
  [...document.querySelectorAll("#cmpBody [data-sw]")].map(e => [e.dataset.sw, +e.value || 0]));

/* Shift panel: a signal is only "shifted" when its mode is not `same`. */
const signalModes = () => {
  const out = {};
  document.querySelectorAll("#shiftBody [data-md]").forEach(sel => {
    if (sel.value === "same") return;
    const id = sel.dataset.md;
    const tg = document.querySelector(`#shiftBody [data-tg="${CSS.escape(id)}"]`);
    out[id] = sel.value === "target" && tg && tg.value !== ""
      ? { mode: "target", target: +tg.value } : { mode: sel.value };
  });
  return out;
};
const tagRules = () => [...document.querySelectorAll("#rules .rule")].map(r => ({
  type: r.querySelector("[data-rt]").value,
  mode: r.querySelector("[data-rm]").value,
  value: r.querySelector("[data-rv]").value.trim(),
})).filter(r => r.value);

const keyRules = () => [...document.querySelectorAll("#shiftBody .kr:checked")].map(c => c.value);

async function pick(id, label) {
  $("hits").style.display = "none";
  if (label) $("search").value = label;
  state.refId = id;
  state.picked.clear(); state.lastClicked = -1;
  $("ref").innerHTML = "hľadám podobné k <b>" + esc($("search").value) + "</b> …";
  $("body").innerHTML = "";
  try {
    const res = await api("/api/similar", { method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, limit: +$("limit").value,
        spotify_only: $("spotifyOnly").checked,
        enabled: enabledSignals(), group_weights: groupWeights(),
        signal_weights: signalWeights(), signal_modes: signalModes(),
        key_rules: keyRules(), tag_rules: tagRules() }) });
    state.rows = res.results;
    render();
    const used = Object.entries(res.signals_used || {}).map(([g, n]) => `${n} ${g}`).join(", ");
    $("ref").innerHTML = `<b>${esc($("search").value)}</b> — ${res.results.length} najpodobnejších`
      + `<span class="muted"> · porovnané: ${esc(used)}</span>`;
  } catch (e) { $("ref").innerHTML = `<span style="color:#ff8080">${esc(e.message)}</span>`; }
}
const rerun = () => { if (state.refId) pick(state.refId, null); };

/* ---------------- results table ---------------- */
function render() {
  const max = state.rows.length ? Math.max(...state.rows.map(r => r.score)) : 1;
  $("body").innerHTML = state.rows.map((r, i) => {
    const why = (r.why || []).filter(x => !["key", "bpm", "Tónina", "BPM"].includes(x)).slice(0, 3);
    if (r.key_rel && r.key_rel !== "rovnaká") why.unshift(r.key_rel);
    const label = r.has_file ? "▶" : (r.preview ? "▶" : "▶");
    return `<tr data-i="${i}" draggable="true">
      <td class="c-pick"><input type="checkbox" class="rowsel"></td>
      <td class="c-act">
        <button class="play" title="Prehrať">${label}</button>
        <button class="pivot ghost" title="Nájdi podobné na tento track">⇄</button>
        <button class="rev ghost" title="Ukáž vo Finderi">⇱</button>
      </td>
      <td class="c-num">${i + 1}</td>
      <td class="c-art" title="${esc(r.artist)}">${esc(r.artist)}</td>
      <td class="c-tit" title="${esc(r.title)}">${esc(r.title)}</td>
      <td class="c-match"><span class="bar"><i style="width:${Math.max(4, Math.round(r.score / max * 100))}%"></i></span></td>
      <td class="c-why" title="${esc(why.join(" · "))}">${esc(why.join(" · "))}</td>
      <td class="c-bpm">${r.bpm ?? ""}</td>
      <td class="c-key">${esc(r.key || "")}</td>
    </tr>`;
  }).join("");
  wireRows();
  updateSel();
}

function wireRows() {
  $("body").querySelectorAll("tr").forEach(tr => {
    const i = +tr.dataset.i, row = state.rows[i];
    tr.querySelector(".play").onclick = e => { e.stopPropagation(); playIndex(i); };
    tr.querySelector(".pivot").onclick = e => { e.stopPropagation(); pivotTo(row); };
    tr.querySelector(".rev").onclick = e => { e.stopPropagation(); reveal([row.spotify_id]); };
    const box = tr.querySelector(".rowsel");
    box.checked = state.picked.has(row.spotify_id);
    box.onclick = e => e.stopPropagation();
    box.onchange = () => { setPicked(i, box.checked); state.lastClicked = i; };
    tr.onmousedown = e => startDragSelect(e, i);
    tr.onmouseenter = () => dragSelectOver(i);
    tr.onclick = e => rowClick(e, i);
    tr.ondragstart = e => dragToTraktor(e, i);
  });
}

/* ---------------- selection: click, shift-range, drag across ---------------- */
let dragSelecting = false, dragValue = true;
function startDragSelect(e, i) {
  if (e.target.closest("button")) return;
  if (e.target.classList.contains("rowsel")) {
    dragSelecting = true;
    dragValue = !state.picked.has(state.rows[i].spotify_id);
    setPicked(i, dragValue);      // the row the drag STARTS on counts too
    state.lastClicked = i;
  }
}
document.addEventListener("mouseup", () => dragSelecting = false);
function dragSelectOver(i) { if (dragSelecting) setPicked(i, dragValue); }

function rowClick(e, i) {
  if (e.target.closest("button") || e.target.classList.contains("rowsel")) return;
  if (e.shiftKey && state.lastClicked >= 0) {
    const [a, b] = [state.lastClicked, i].sort((x, y) => x - y);
    for (let k = a; k <= b; k++) setPicked(k, true);
  } else {
    setPicked(i, !state.picked.has(state.rows[i].spotify_id));
    state.lastClicked = i;
  }
}

function setPicked(i, on) {
  const row = state.rows[i]; if (!row) return;
  on ? state.picked.add(row.spotify_id) : state.picked.delete(row.spotify_id);
  const tr = $("body").querySelector(`tr[data-i="${i}"]`);
  if (tr) { tr.classList.toggle("sel", on); tr.querySelector(".rowsel").checked = on; }
  updateSel();
}

function updateSel() {
  const n = state.picked.size;
  $("selCount").textContent = `${n} označených`;
  $("selbar").classList.toggle("on", n > 0);
  $("selAll").checked = n > 0 && n === state.rows.length;
}
$("selAll").onchange = () => {
  // Read the box ONCE. updateSel() rewrites selAll.checked after every row, so
  // reading it inside the loop turned "select all" into "select the first row
  // and then unselect it again".
  const on = $("selAll").checked;
  state.rows.forEach((_, i) => setPicked(i, on));
  $("selAll").checked = on;
};
$("btnClear").onclick = () => { state.rows.forEach((_, i) => setPicked(i, false)); };
const pickedIds = () => state.rows.filter(r => state.picked.has(r.spotify_id)).map(r => r.spotify_id);

/* ---------------- drag into Traktor ----------------
 * A page cannot hand a native app a filesystem path, but Chrome's DownloadURL
 * flavour lets a drag carry a real file, and file:// URIs in text/uri-list are
 * what most macOS apps read. Both are offered; whichever Traktor understands
 * wins. Dragging an unselected row drags that row, otherwise the whole
 * selection — the same rule Finder uses.
 */
async function dragToTraktor(e, i) {
  const row = state.rows[i];
  const ids = state.picked.has(row.spotify_id) ? pickedIds() : [row.spotify_id];
  try {
    const info = await fetch("/api/traktor/paths", { method: "POST",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ids }) })
      .then(r => r.json());
    const files = info.files || [];
    if (!files.length) return;
    const uris = files.map(f => "file://" + encodeURI(f.path)).join("\r\n");
    e.dataTransfer.setData("text/uri-list", uris);
    e.dataTransfer.setData("text/plain", files.map(f => f.path).join("\n"));
    if (files.length === 1) {
      e.dataTransfer.setData("DownloadURL",
        `audio/mpeg:${files[0].name}:${location.origin}/api/audio?id=${encodeURIComponent(files[0].id)}`);
    }
    e.dataTransfer.effectAllowed = "copy";
  } catch { /* drag simply carries nothing */ }
}

/* ---------------- actions ---------------- */
async function reveal(ids) {
  try { await api("/api/traktor/reveal", { method: "POST",
    headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ids }) }); }
  catch (e) { toast(esc(e.message)); }
}
$("btnReveal").onclick = () => { const ids = pickedIds(); if (ids.length) reveal(ids); };
$("btnPlaylist").onclick = async () => {
  const ids = pickedIds(); if (!ids.length) return;
  try {
    const res = await api("/api/traktor/playlist", { method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids, name: $("search").value.slice(0, 40) }) });
    toast(`Playlist s ${res.count} trackmi je vo Finderi — pusti ho do Traktora`
      + (res.skipped ? ` (${res.skipped} bez súboru)` : ""), 11000);
  } catch (e) { toast(esc(e.message)); }
};
$("btnAnalyze").onclick = () => { const ids = pickedIds(); if (ids.length) analyzeNow(ids); };

function pivotTo(row) {
  state.refId = row.spotify_id;
  $("search").value = `${row.artist} — ${row.title}`;
  pick(row.spotify_id, null);
}

/* ---------------- player ---------------- */
function playIndex(i) {
  if (i < 0 || i >= state.rows.length) return;
  state.index = i;
  const r = state.rows[i];
  document.querySelectorAll("tr.playing").forEach(e => e.classList.remove("playing"));
  const tr = $("body").querySelector(`tr[data-i="${i}"]`);
  if (tr) { tr.classList.add("playing"); tr.scrollIntoView({ block: "nearest" }); }
  $("now").innerHTML = `${esc(r.artist)} — ${esc(r.title)}<br>`
    + `<small>${r.bpm ?? "?"} BPM · ${esc(r.key || "?")}${r.has_file ? "" : " · 30s ukážka"}</small>`;
  // Everything plays through OUR element, so one click starts it and the CUE
  // output applies to Spotify-only tracks exactly as it does to local files.
  P.src = r.has_file ? "/api/audio?id=" + encodeURIComponent(r.spotify_id)
                     : "/api/preview?id=" + encodeURIComponent(r.spotify_id);
  applySink($("sink").value);
  P.play().then(() => $("big").textContent = "❚❚")
          .catch(() => { $("big").textContent = "▶"; toast("Tento track sa nedá prehrať"); });
}
$("big").onclick = () => { if (!P.src) return playIndex(0);
  P.paused ? P.play() : P.pause(); };
$("prev").onclick = () => playIndex(state.index - 1);
$("next").onclick = () => playIndex(state.index + 1);
P.onended = () => playIndex(state.index + 1);
P.onplay = () => $("big").textContent = "❚❚";
P.onpause = () => $("big").textContent = "▶";
let seeking = false;
P.ontimeupdate = () => { if (seeking || !isFinite(P.duration)) return;
  $("seek").value = Math.round(P.currentTime / P.duration * 1000); $("cur").textContent = mmss(P.currentTime); };
P.onloadedmetadata = () => { $("dur").textContent = mmss(P.duration); };
$("seek").oninput = () => { seeking = true; $("cur").textContent = mmss($("seek").value / 1000 * P.duration); };
$("seek").onchange = () => { if (isFinite(P.duration)) P.currentTime = $("seek").value / 1000 * P.duration; seeking = false; };
$("vol").oninput = () => P.volume = +$("vol").value;
document.onkeydown = e => {
  if (/^(INPUT|SELECT|TEXTAREA)$/.test(e.target.tagName)) return;
  if (e.code === "Space") { e.preventDefault(); $("big").click(); }
  else if (e.code === "ArrowRight") P.currentTime = Math.min(P.duration || 0, P.currentTime + 10);
  else if (e.code === "ArrowLeft") P.currentTime = Math.max(0, P.currentTime - 10);
  else if (e.code === "ArrowDown") { e.preventDefault(); playIndex(state.index + 1); }
  else if (e.code === "ArrowUp") { e.preventDefault(); playIndex(state.index - 1); }
};

/* ---------------- CUE output ---------------- */
async function applySink(id) { if (P.setSinkId) { try { await P.setSinkId(id || "default"); } catch {} } }
async function loadSinks() {
  try {
    await navigator.mediaDevices.getUserMedia({ audio: true })
      .then(s => s.getTracks().forEach(t => t.stop())).catch(() => {});
    const outs = (await navigator.mediaDevices.enumerateDevices()).filter(d => d.kind === "audiooutput");
    $("sink").innerHTML = '<option value="">predvolený</option>' +
      outs.map(d => `<option value="${esc(d.deviceId)}">${esc(d.label || "výstup")}</option>`).join("");
    const saved = localStorage.getItem("cueSink");
    if (saved && outs.some(d => d.deviceId === saved)) { $("sink").value = saved; applySink(saved); }
  } catch {}
}
$("sink").onchange = () => { localStorage.setItem("cueSink", $("sink").value); applySink($("sink").value); };
