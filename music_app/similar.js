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
/* All three panels are visible by default and independent of each other — the
 * owner wants to see what is being compared and what is being shifted without
 * opening anything first. The buttons only fold a panel away; whatever is
 * folded is remembered, so the screen looks the same after a reload.
 * TWEAK: to start with a panel folded, add its id to the array below. */
const panels = { btnCompare: "panelCompare", btnShift: "panelShift", btnProfiles: "panelProfiles" };
const shutPanels = () => new Set(JSON.parse(localStorage.getItem("shutPanels") || "[]"));
function paintPanels() {
  const shut = shutPanels();
  Object.entries(panels).forEach(([btn, id]) => {
    $(id).classList.toggle("open", !shut.has(id));
    $(btn).classList.toggle("on", !shut.has(id));
  });
}
Object.entries(panels).forEach(([btn, id]) => $(btn).onclick = () => {
  const shut = shutPanels();
  shut.has(id) ? shut.delete(id) : shut.add(id);
  localStorage.setItem("shutPanels", JSON.stringify([...shut]));
  paintPanels();
});
paintPanels();

/* ---------------- readiness ---------------- */
let restored = false;
async function pollReady() {
  try {
    const s = await api("/api/similar/status");
    if (s.error) return $("status").textContent = "Chyba: " + s.error;
    if (s.ready) {
      $("status").textContent = `${s.tracks.toLocaleString()} zanalyzovaných`;
      if (!restored) { restored = true; restoreSeeds(); }   // once the engine can answer
      // Keep asking, slowly. It refreshes the count as tracks finish analysing,
      // and it is what tells the engine the app is still open so it does not
      // retire underneath it.
      return void setTimeout(pollReady, 30000);
    }
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
    const label = el.querySelector("span").textContent;
    // ⌘/Ctrl/Shift-click adds to the seed set instead of replacing it, and so
    // does the "＋ pridať track" button while it is lit.
    if (ev.metaKey || ev.ctrlKey || ev.shiftKey || $("btnAddSeed").classList.contains("on")) {
      $("btnAddSeed").classList.remove("on");
      $("search").value = "";
      return addSeed(el.dataset.id, label);
    }
    pick(el.dataset.id, label);
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

/* ---------------- seeds ----------------
 * The search can point at ONE track or at SEVERAL. More seeds is not "more
 * results" — it is a more specific question: the engine averages each seed's
 * opinion per signal, so whatever the seeds agree on drives the ranking and
 * whatever they disagree on cancels itself out. Two records that share a groove
 * but sit in different keys will therefore rank groove highly and ignore key.
 * HOW TO TWEAK: add seeds with "＋ pridať track" (or ⌘/Shift-click a hit), or
 * tick rows in the table and press "Použi vybrané ako seed". */
state.seeds = [];

function renderSeeds() {
  const box = $("seeds");
  box.innerHTML = state.seeds.length < 1 ? "" :
    '<span class="muted">Hľadám podľa:</span>' + state.seeds.map((s, i) =>
      `<span class="chipwrap"><button class="chip on" data-seed="${i}" title="${esc(s.label)}">${esc(s.label)}</button>`
      + `<button class="ghost" data-unseed="${i}" title="Odobrať">✕</button></span>`).join("");
  box.querySelectorAll("[data-unseed]").forEach(b => b.onclick = () => {
    state.seeds.splice(+b.dataset.unseed, 1);
    if (state.seeds.length) runSeeds(); else { state.rows = []; render(); renderSeeds(); $("ref").textContent = "Vyber track hore a nájdem najpodobnejšie."; }
  });
  box.querySelectorAll("[data-seed]").forEach(b => b.onclick = () => {
    const s = state.seeds[+b.dataset.seed]; setSeeds([s]);
  });
}

function setSeeds(list) {
  state.seeds = list.slice(0, 12);
  // Reopening the app lands back where the last set was left off, instead of
  // on an empty screen. TWEAK: clear it by removing every seed chip.
  try { localStorage.setItem("lastSeeds", JSON.stringify(state.seeds)); } catch {}
  runSeeds();
}

async function restoreSeeds() {
  try {
    const saved = JSON.parse(localStorage.getItem("lastSeeds") || "[]");
    if (!saved.length) return;
    // WAIT for the signal panel. Without this the restored query runs against
    // whatever checkboxes happen to exist yet, which is almost none of them.
    await (window.signalsReady || Promise.resolve());
    state.seeds = saved;
    $("search").value = saved[0].label || "";
    runSeeds();
  } catch {}
}
function addSeed(id, label) {
  if (state.seeds.some(s => s.id === id)) return runSeeds();
  setSeeds([...state.seeds, { id, label }]);
}

/* Kept for every existing caller (search hit, pivot, rerun): one track. */
async function pick(id, label) {
  $("hits").style.display = "none";
  setSeeds([{ id, label: label || $("search").value }]);
}

async function runSeeds() {
  $("hits").style.display = "none";
  const seeds = state.seeds;
  if (!seeds.length) return;
  state.refId = seeds[0].id;
  state.picked.clear(); state.lastClicked = -1;
  renderSeeds();
  const names = seeds.map(s => s.label).join(" + ");
  $("ref").innerHTML = "hľadám podobné k <b>" + esc(names) + "</b> …";
  $("body").innerHTML = "";
  try {
    const res = await api("/api/similar", { method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids: seeds.map(s => s.id), limit: +$("limit").value,
        spotify_only: $("spotifyOnly").checked,
        enabled: enabledSignals(), group_weights: groupWeights(),
        signal_weights: signalWeights(), signal_modes: signalModes(),
        key_rules: keyRules(), tag_rules: tagRules() }) });
    state.rows = res.results;
    render();
    const used = Object.entries(res.signals_used || {}).map(([g, n]) => `${n} ${g}`).join(", ");
    // With several seeds, say what they actually had in common — otherwise the
    // owner has no way to tell whether the combination meant what he intended.
    const common = (res.common || []).slice(0, 4)
      .map(c => `${c.type}: ${c.tags.slice(0, 3).join(", ")}`).join(" · ");
    $("ref").innerHTML = `<b>${esc(names)}</b> — ${res.results.length} najpodobnejších`
      + `<span class="muted"> · porovnané: ${esc(used)}</span>`
      + (common ? `<div class="muted" style="margin-top:3px">spoločné: ${esc(common)}</div>` : "");
    if ((res.seeds_missing || []).length)
      toast(`${res.seeds_missing.length} track(ov) nemá analýzu — vynechané`);
  } catch (e) { $("ref").innerHTML = `<span style="color:#ff8080">${esc(e.message)}</span>`; }
}
const rerun = () => { if (state.seeds.length) runSeeds(); };

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
    tr.onmousedown = e => { rowMouseDown(e, i); armNativeDrag(e, i); startDragSelect(e, i); };
    tr.onmouseenter = () => dragSelectOver(i);
    tr.onclick = e => e.stopPropagation();     // selection already happened on mousedown
    if (NATIVE) {
      tr.draggable = false;                  // the app owns the gesture, not WebKit
    } else {
      tr.ondragstart = e => dragToTraktor(e, i);
    }
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

/* SELECTION HAPPENS ON MOUSE-DOWN, exactly like Finder — and for the same
 * reason. It used to happen on click, i.e. on mouse-UP, so the moment the
 * pointer moved a few pixels the drag swallowed the gesture and nothing got
 * selected. Deciding on mouse-down makes it impossible to miss.
 *
 * Clicking an ALREADY selected row is the one case that has to wait: it must
 * still be draggable, so the row is only unselected on release, and only if no
 * drag happened in between. That is Finder's rule too. */
let pendingUnselect = -1, downAt = null, movedSinceDown = false;

function rowMouseDown(e, i) {
  if (e.button !== 0) return;
  if (e.target.closest("button, input, select, a")) return;
  downAt = { x: e.clientX, y: e.clientY };
  movedSinceDown = false;
  pendingUnselect = -1;

  if (e.shiftKey && state.lastClicked >= 0) {
    const [a, b] = [state.lastClicked, i].sort((x, y) => x - y);
    for (let k = a; k <= b; k++) setPicked(k, true);
    return;
  }
  if (!state.picked.has(state.rows[i].spotify_id)) {
    setPicked(i, true);
    state.lastClicked = i;
  } else {
    pendingUnselect = i;                    // decided on release, see above
  }
}

document.addEventListener("mousemove", e => {
  if (!downAt) return;
  if (Math.abs(e.clientX - downAt.x) > 5 || Math.abs(e.clientY - downAt.y) > 5) movedSinceDown = true;
});
document.addEventListener("mouseup", () => {
  if (pendingUnselect >= 0 && !movedSinceDown) {
    setPicked(pendingUnselect, false);
    state.lastClicked = pendingUnselect;
  }
  pendingUnselect = -1; downAt = null;
});

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
$("btnAddSeed").onclick = () => {
  $("btnAddSeed").classList.toggle("on");
  if ($("btnAddSeed").classList.contains("on")) { $("search").value = ""; $("search").focus(); }
};
$("btnSeedPicked").onclick = () => {
  const ids = pickedIds();
  if (!ids.length) return toast("Najprv zaškrtni tracky v tabuľke.");
  setSeeds(ids.map(id => {
    const r = state.rows.find(x => x.spotify_id === id);
    return { id, label: `${r.artist} — ${r.title}` };
  }));
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
/* ---------------- native drag ----------------
 * Inside the macOS app the drag is done by the app itself: a real
 * NSDraggingSession carrying file URLs, which is what Finder puts on the
 * pasteboard and what Traktor accepts. All the page does is say WHICH files are
 * under the pointer the moment the mouse goes down; the app notices the
 * movement and takes over from there.
 *
 * Finder's rule is kept: dragging a row that is part of the selection drags the
 * whole selection, dragging an unselected row drags just that one.
 *
 * The checkbox column is deliberately excluded — dragging across it still ticks
 * rows, which is how the owner selects a range with the mouse. */
const NATIVE = typeof window.NATIVE_HOST !== "undefined" && window.NATIVE_HOST;
const native = msg => { try { window.webkit.messageHandlers.native.postMessage(msg); } catch {} };

function armNativeDrag(e, i) {
  if (!NATIVE) return;
  if (e.button !== 0) return;
  if (e.target.closest(".c-pick, button, input, select, a")) return;   // selection & controls
  const row = state.rows[i];
  const ids = state.picked.has(row.spotify_id) ? pickedIds() : [row.spotify_id];
  const paths = ids.map(id => (state.rows.find(r => r.spotify_id === id) || {}).path).filter(Boolean);
  if (!paths.length) return;                     // Spotify-only track: nothing to drag
  native({ cmd: "armDrag", paths });
}
const nlog = text => native({ cmd: "log", text: String(text) });

/* MEDIA KEYS. macOS routes the keyboard's ▶❚❚ / ⏭ / ⏮ keys to whichever app is
 * currently the "now playing" one, and an app only becomes that by publishing
 * what it is playing. So the page keeps the app informed, the app publishes it
 * to the system, and the system's key presses come back through __mediaKey.
 * Works for both backends — the app never needs to know which is sounding. */
function nowPlayingToHost() {
  if (!NATIVE) return;
  const r = state.rows[state.index];
  if (!r) return;
  native({ cmd: "nowPlaying", title: r.title || "", artist: r.artist || "",
           duration: T.duration || 0, position: T.position || 0, paused: !!T.paused });
}
window.__reclaimMediaKeys = () => nowPlayingToHost();
window.__mediaKey = key => {
  if (key === "next") playIndex(state.index + 1);
  else if (key === "prev") playIndex(state.index - 1);
  else if (key === "play") { if (T.paused) T.toggle(); }
  else if (key === "pause") { if (!T.paused) T.toggle(); }
  else $("big").click();
};
if (NATIVE) {
  // One line in native/app.log on every start, so what the UI can and cannot do
  // inside the app is a fact on disk instead of a guess.
  window.addEventListener("load", () => {
    const a = document.createElement("audio");
    nlog(`UI loaded · setSinkId=${typeof a.setSinkId === "function"} `
       + `· enumerateDevices=${!!(navigator.mediaDevices && navigator.mediaDevices.enumerateDevices)} `
       + `· ua=${navigator.userAgent.slice(0, 40)}`);
  });
  window.addEventListener("error", e => nlog("JS ERROR: " + e.message + " @" + e.filename + ":" + e.lineno));
  window.addEventListener("mouseup", () => native({ cmd: "disarmDrag" }));
  window.addEventListener("blur", () => native({ cmd: "disarmDrag" }));
}

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
  setTimeout(nowPlayingToHost, 0);
  hideEmbed();                              // a previous Spotify frame must stop
  $("now").innerHTML = `${esc(r.artist)} — ${esc(r.title)}<br>`
    + `<small>${r.bpm ?? "?"} BPM · ${esc(r.key || "?")}${r.has_file ? "" : " · 30s ukážka"}</small>`;
  // Everything plays through OUR element, so one click starts it and the CUE
  // output applies to Spotify-only tracks exactly as it does to local files.
  P.src = r.has_file ? "/api/audio?id=" + encodeURIComponent(r.spotify_id)
                     : "/api/preview?id=" + encodeURIComponent(r.spotify_id);
  applySink($("sink").value);
  // If there is no local file AND no preview to fetch, fall back to Spotify's
  // own player rather than telling the owner it cannot be played. The rewrite
  // dropped that fallback, so a Spotify-only track with no Deezer match just
  // failed.
  P.play().then(() => $("big").textContent = "❚❚")
          .catch(() => { $("big").textContent = "▶"; showEmbed(r); });
}
/* ONE TRANSPORT, TWO BACKENDS. The buttons, the long seek bar and the clock
 * belong to the app, not to whatever is producing the sound. `backend` says who
 * is playing: our own <audio> element, or Spotify's embedded player driven
 * through its iFrame API. Everything below routes to the right one, so the
 * Spotify fallback scrubs on the same bar as a local file instead of being a
 * crippled little box in the corner. */
let backend = "audio";
const T = {
  get duration() { return backend === "spotify" ? sp.duration : (isFinite(P.duration) ? P.duration : 0); },
  get position() { return backend === "spotify" ? sp.position : P.currentTime; },
  get paused()   { return backend === "spotify" ? sp.paused : P.paused; },
  toggle() { backend === "spotify" ? sp.controller && sp.controller.togglePlay() : (P.paused ? P.play() : P.pause()); },
  seekTo(sec) {
    if (backend === "spotify") { sp.position = sec; sp.controller && sp.controller.seek(sec); }
    else if (isFinite(P.duration)) P.currentTime = sec;
    paintTransport();
  },
  nudge(sec) { T.seekTo(Math.max(0, Math.min(T.duration || 0, T.position + sec))); },
};

function paintTransport() {
  const d = T.duration, pos = T.position;
  $("big").textContent = T.paused ? "▶" : "❚❚";
  $("dur").textContent = mmss(d);
  if (seeking) return;
  $("seek").value = d ? Math.round(pos / d * 1000) : 0;
  $("cur").textContent = mmss(pos);
}

$("big").onclick = () => { if (backend === "audio" && !P.src) return playIndex(0); T.toggle(); };
$("prev").onclick = () => playIndex(state.index - 1);
$("next").onclick = () => playIndex(state.index + 1);
P.onended = () => playIndex(state.index + 1);
P.onplay = () => { paintTransport(); nowPlayingToHost(); };
P.onpause = () => { paintTransport(); nowPlayingToHost(); };
let seeking = false;
let lastPush = 0;
P.ontimeupdate = () => {
  if (backend !== "audio") return;
  paintTransport();
  // Refresh the system's idea of the position, but not sixty times a second.
  if (Date.now() - lastPush > 2000) { lastPush = Date.now(); nowPlayingToHost(); }
};
P.onloadedmetadata = () => { if (backend === "audio") paintTransport(); };
$("seek").oninput = () => { seeking = true; $("cur").textContent = mmss($("seek").value / 1000 * T.duration); };
$("seek").onchange = () => { const to = $("seek").value / 1000 * T.duration; seeking = false; T.seekTo(to); };
$("vol").oninput = () => P.volume = +$("vol").value;
document.onkeydown = e => {
  if (/^(INPUT|SELECT|TEXTAREA)$/.test(e.target.tagName)) return;
  if (e.code === "Space") { e.preventDefault(); $("big").click(); }
  else if (e.code === "ArrowRight") T.nudge(10);
  else if (e.code === "ArrowLeft") T.nudge(-10);
  else if (e.code === "ArrowDown") { e.preventDefault(); playIndex(state.index + 1); }
  else if (e.code === "ArrowUp") { e.preventDefault(); playIndex(state.index - 1); }
};

/* ---------------- Spotify backend ----------------
 * Used when a track is neither on disk nor available as a 30-second preview.
 * It is driven through Spotify's official iFrame API rather than dropped in as
 * a bare <iframe>, which is what lets the app's own long seek bar scrub it:
 * the API reports position and duration (in MILLISECONDS) and takes seek() in
 * SECONDS. Docs: developer.spotify.com/documentation/embeds/references/iframe-api
 *
 * HONEST LIMIT: an embedded player cannot be pointed at the CUE device, so this
 * one comes out of the default output. It also plays a 30-second preview unless
 * Spotify is logged in inside this window — logging in once from the embed is
 * remembered, after which it plays the whole track.
 *
 * HOW TO TWEAK: API_TIMEOUT is how long to wait for Spotify's script before
 * giving up and saying so. */
const API_TIMEOUT = 15000;
const sp = { api: null, controller: null, duration: 0, position: 0, paused: true,
             lastUpdate: 0, ticker: null };

function spotifyApi() {
  if (sp.api) return sp.api;
  sp.api = new Promise((resolve, reject) => {
    window.onSpotifyIframeApiReady = api => resolve(api);
    const tag = document.createElement("script");
    tag.src = "https://open.spotify.com/embed/iframe-api/v1";
    tag.async = true;
    tag.onerror = () => reject(new Error("Spotify sa nepodarilo načítať"));
    document.head.appendChild(tag);
    setTimeout(() => reject(new Error("Spotify neodpovedá")), API_TIMEOUT);
  });
  return sp.api;
}

async function showEmbed(r) {
  const box = $("embed");
  backend = "spotify";
  box.classList.add("on");
  document.querySelector("footer").classList.add("embed");
  $("now").innerHTML = `${esc(r.artist)} — ${esc(r.title)}<br>`
    + `<small>Spotify · mimo slúchadiel</small>`;
  if (!box.querySelector(".lbl")) {
    box.innerHTML = `<div class="lbl">▶ hrá cez <b>SPOTIFY</b> — nemáme súbor ani 30s ukážku`
      + `<span>· ide do predvoleného výstupu, nie do slúchadiel</span></div><div id="spHost"></div>`;
  }
  const uri = "spotify:track:" + r.spotify_id;
  try {
    const api = await spotifyApi();
    if (!sp.controller) {
      await new Promise(done => api.createController(
        $("spHost"), { uri, width: "100%", height: 80 },
        c => {
          sp.controller = c;
          c.addListener("playback_update", e => onSpotifyUpdate(e.data));
          c.addListener("ready", () => c.resume());
          done();
        }));
    } else {
      sp.controller.loadUri(uri);
      sp.controller.resume();
    }
    startSpotifyTicker();
  } catch (err) {
    box.innerHTML = `<div class="lbl" style="color:#ff8080">${esc(err.message)}</div>`;
    toast("Spotify prehrávač sa nenačítal — skontroluj pripojenie.");
  }
}

/* playback_update arrives only when something changes, which would make the bar
 * jump once a second at best. Between updates the position is advanced locally
 * so the bar moves smoothly, and every real update snaps it back to the truth. */
function onSpotifyUpdate(d) {
  sp.duration = (d.duration || 0) / 1000;
  sp.position = (d.position || 0) / 1000;
  sp.paused = !!d.isPaused;
  sp.lastUpdate = Date.now();
  paintTransport();
  nowPlayingToHost();
}

function startSpotifyTicker() {
  clearInterval(sp.ticker);
  sp.ticker = setInterval(() => {
    if (backend !== "spotify" || sp.paused) return;
    const drift = (Date.now() - sp.lastUpdate) / 1000;
    if (drift > 0.2 && drift < 3) { sp.position += 0.25; sp.lastUpdate += 250; paintTransport(); }
  }, 250);
}

function hideEmbed() {
  const box = $("embed");
  clearInterval(sp.ticker);
  if (sp.controller) { try { sp.controller.pause(); } catch {} }
  backend = "audio";
  if (!box.classList.contains("on")) return;
  box.classList.remove("on");
  document.querySelector("footer").classList.remove("embed");
}

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
