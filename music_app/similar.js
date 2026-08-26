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
/* ONE PANEL AT A TIME. They used to be independent and all open, which meant
 * four long panels stacked above the results and nothing to orient by. The
 * owner asked for tabs: opening one closes the others, clicking the open one
 * closes it. Which one was last open is remembered.
 * TWEAK: set "openPanel" in localStorage to "" to start with everything shut. */
const panels = { btnCompare: "panelCompare", btnShift: "panelShift",
                 btnShiftMeta: "panelShiftMeta", btnProfiles: "panelProfiles" };
function paintPanels() {
  const open = localStorage.getItem("openPanel");
  Object.entries(panels).forEach(([btn, id]) => {
    $(id).classList.toggle("open", id === open);
    $(btn).classList.toggle("on", id === open);
  });
}
Object.entries(panels).forEach(([btn, id]) => $(btn).onclick = () => {
  const open = localStorage.getItem("openPanel");
  localStorage.setItem("openPanel", open === id ? "" : id);
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
      // Which version of the app code this window is running. If this is older
      // than a change we just made, the window needs ⌘R (or a restart).
      if (s.build) {
        const stale = s.started && s.build > s.started + 2;
        $("status").title = `Kód z ${new Date(s.build * 1000).toLocaleString("sk")}`
          + (stale ? " · SERVER BEŽÍ SO STARŠÍM KÓDOM — reštartuj appku"
                   : " · ⌘R načíta najnovší");
        // Loud, not a tooltip: a stale server makes every recent change look
        // broken, and that has happened twice.
        $("status").classList.toggle("stale", !!stale);
        if (stale && !window.__staleWarned) {
          window.__staleWarned = true;
          toast("Server beží so starším kódom než je na disku — zavri a znova otvor appku.", 15000);
        }
      }
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
/* Read one shift panel. Two exist: the profile's own, and the META one that
 * survives a profile change. META is read LAST so it wins where both speak —
 * that is the whole point of it being "above" the profile. */
/* Slovak keyboards type a decimal COMMA. An <input type="number"> refuses it
 * outright — the value arrives as an empty string — which is why "valence 0,2"
 * silently did nothing at all. The boxes are plain text now and both separators
 * are accepted here. */
const dec = v => {
  const t = String(v ?? "").trim().replace(",", ".");
  return t === "" || !isFinite(+t) ? null : +t;
};

/* The operators a number can carry. "target" is a window around a value; the
 * rest are one-sided limits. Anything else means "no constraint". */
const OPS = new Set(["target", "gt", "gte", "lt", "lte"]);

function readShift(scope) {
  const out = {};
  const root = document.getElementById("shiftBody" + scope);
  if (!root) return out;
  root.querySelectorAll("[data-md]").forEach(sel => {
    const id = sel.dataset.md;
    const tg = root.querySelector(`[data-tg="${CSS.escape(id)}"]`);
    const tl = root.querySelector(`[data-tl="${CSS.escape(id)}"]`);
    const target = tg ? dec(tg.value) : null;
    if (sel.value === "diff") {
      out[id] = { mode: "diff" };
      // For a number, ± says how far away still counts as "different".
      const tol = tl ? dec(tl.value) : null;
      if (tol !== null) out[id].tol = Math.abs(tol);
      return;
    }
    // A typed number wins: something in the target box IS a demand, whatever
    // the dropdown says. If no operator was chosen, "→" is what was meant.
    if (target !== null) {
      const mode = OPS.has(sel.value) ? sel.value : "target";
      out[id] = { mode, target };
      if (mode === "target") {
        // A tolerance makes it a window. Left empty, the engine picks a
        // sensible one rather than decaying into a preference that loses.
        const tol = tl ? dec(tl.value) : null;
        if (tol !== null) out[id].tol = Math.abs(tol);
      }
    }
    // "=" with an empty target box says nothing at all, which is the default.
  });
  return out;
}
const signalModes = () => ({ ...readShift(""), ...readShift("Meta") });

/* MACROS — a whole mood, energy, rhythm or genre in one click.
 *
 * A macro is just a saved hard rule, kept apart from the hand-written ones so
 * it can be a toggle instead of a row. Two macros are two rules and rules AND
 * together, so picking "Veselé" and "Vysoká energia" gives cheerful AND
 * high-energy — combining them is the owner's job, which is why the macros
 * themselves are never combined for him.
 *
 * Each scope has its own set: the profile panel's macros belong to the profile,
 * the META panel's outlive it. */
state.macros = { "": new Set(), Meta: new Set() };

function macroRules(scope) {
  const on = state.macros[scope] || new Set();
  return (state.macroList || []).flatMap(g => g.items)
    .filter(m => on.has(m.id))
    // CARRY THE STRICTNESS. Without `match` and `min_conf` the engine fell back
    // to substring matching with no confidence floor, so a macro filtered far
    // more loosely than its own chip promised — Drum'n'bass said 3,094 tracks
    // and the query let 3,808 through, most of them 120 BPM house carrying a
    // stray low-confidence dnb tag.
    .map(m => ({ type: m.type, mode: "must", value: m.value,
                 match: m.match || "exact", min_conf: m.min_conf,
                 track_only: m.track_only !== false }));
}

function renderMacros(scope) {
  const box = document.getElementById("macros" + scope);
  if (!box || !state.macroList) return;
  const on = state.macros[scope];
  box.innerHTML = state.macroList.map(g => `
    <div class="mgrp">
      <span class="mname">${esc(g.group)}</span>
      ${g.items.map(m => `<button class="chip mac${on.has(m.id) ? " on" : ""}"
          data-mac="${esc(m.id)}"
          title="${esc(m.label)} — ${m.count.toLocaleString("sk")} trackov (${m.pct} % knižnice)&#10;${esc(m.type)} = ${esc(m.value)}"
        >${esc(m.label)}</button>`).join("")}
    </div>`).join("");
  box.querySelectorAll("[data-mac]").forEach(b => b.onclick = () => {
    const id = b.dataset.mac;
    on.has(id) ? on.delete(id) : on.add(id);
    renderMacros(scope);
    if (scope) { saveMetaShift(); paintMetaBadge(); }
    rerun();
  });
}

async function loadMacros() {
  try {
    const { macros } = await api("/api/similar/macros");
    state.macroList = macros;
    renderMacros(""); renderMacros("Meta");
  } catch { /* the panel simply shows no macros */ }
}

const readRules = scope => [...document.querySelectorAll(`#rules${scope} .rule`)].map(r => ({
  type: r.querySelector("[data-rt]").value,
  mode: r.querySelector("[data-rm]").value,
  value: r.querySelector("[data-rv]").value.trim(),
})).filter(r => r.value);
// Both sets of hard rules apply — META adds to the profile's, never replaces —
// and the macros of each scope are rules just like the hand-written ones.
const tagRules = () => [...readRules(""), ...macroRules(""),
                        ...readRules("Meta"), ...macroRules("Meta")];

/* META survives profile changes, so it lives in the browser, not in a profile. */
function saveMetaShift() {
  try {
    localStorage.setItem("metaShift", JSON.stringify(
      { modes: readShift("Meta"), rules: readRules("Meta"),
        macros: [...state.macros.Meta] }));
  } catch {}
}
function restoreMetaShift() {
  let saved;
  try { saved = JSON.parse(localStorage.getItem("metaShift") || "null"); } catch {}
  if (!saved) return;
  const root = document.getElementById("shiftBodyMeta");
  Object.entries(saved.modes || {}).forEach(([id, spec]) => {
    const sel = root && root.querySelector(`[data-md="${CSS.escape(id)}"]`);
    if (!sel) return;
    sel.value = spec.mode;
    const tg = root.querySelector(`[data-tg="${CSS.escape(id)}"]`);
    const tl = root.querySelector(`[data-tl="${CSS.escape(id)}"]`);
    if (tg && spec.target !== undefined) tg.value = spec.target;
    if (tl) tl.value = spec.tol ?? "";
  });
  const mb = document.querySelector('[data-basekey="Meta"]');
  if (mb && saved.baseKey) mb.value = saved.baseKey;
  (saved.rules || []).forEach(r => addRule(r, "Meta"));
  state.macros.Meta = new Set(saved.macros || []);
  renderMacros("Meta");
  paintMetaBadge();
}

/* Say out loud how many META rules are live, so an override is never invisible. */
function paintMetaBadge() {
  const n = Object.keys(readShift("Meta")).length + readRules("Meta").length
          + state.macros.Meta.size;
  const el = document.getElementById("metaCount");
  if (el) el.textContent = n ? `${n} aktívnych` : "nič";
  const btn = document.getElementById("btnShiftMeta");
  if (btn) btn.classList.toggle("lit", n > 0);
}

/* MIXED IN KEY — a switch that sits ABOVE the profiles.
 *
 * A profile carries its own harmonic rules, and switching profile replaces
 * them. This does not: while it is on, the four mixable relationships are
 * forced no matter which profile is loaded, and turning it off gives the
 * profile its own rules back untouched. That is why its state lives in the
 * browser and never in a profile.
 *
 * TWEAK: MIK_RULES is the set it forces. "relatívna" (relative major/minor) is
 * deliberately NOT in it — it was not among the four asked for. Add "relative"
 * to the list to include it. */
const MIK_RULES = ["exact", "step1", "step2", "semitone"];
const mikOn = () => $("mikOn").checked;

/* Which key the harmony is measured from. META wins when both name one; empty
 * means "the key of the track you picked", which is the normal case. */
const baseKey = () => {
  const meta = document.querySelector('[data-basekey="Meta"]');
  const own = document.querySelector('[data-basekey=""]');
  return (meta && meta.value) || (own && own.value) || "";
};

const keyRules = () => {
  if (mikOn()) return MIK_RULES.slice();
  // META first: if it names any harmonic rule, that is the answer.
  const meta = [...document.querySelectorAll("#shiftBodyMeta .krMeta:checked")].map(c => c.value);
  if (meta.length) return meta;
  return [...document.querySelectorAll("#shiftBody .kr:checked")].map(c => c.value);
};

/* Show the override in the panel too, so it is never a mystery why a profile's
 * own boxes are being ignored — and, just as important, give the profile its
 * own rules BACK when the switch goes off. The panel's checkboxes cannot be
 * that memory, because while the switch is on they are showing the forced set,
 * so the profile's own choice is kept here instead.
 *
 * `adopt` means "the boxes currently hold a profile's own rules, remember
 * them" — passed by whatever just loaded a profile or preset. */
let ownKeyRules = [];
function paintMik(opts = {}) {
  const on = mikOn();
  const boxes = [...document.querySelectorAll("#shiftBody .kr")];
  const metaBoxes = [...document.querySelectorAll("#shiftBodyMeta .krMeta")];
  if (opts.adopt || (!on && !opts.keep)) ownKeyRules = boxes.filter(c => c.checked).map(c => c.value);
  $("mikOn").closest("label").classList.toggle("on", on);
  localStorage.setItem("mikOn", on ? "1" : "0");
  boxes.forEach(c => {
    c.disabled = on;
    c.title = on ? "Prepísané prepínačom „Mixed in Key“ hore" : "";
    c.checked = on ? MIK_RULES.includes(c.value) : ownKeyRules.includes(c.value);
  });
  // The META panel's harmonic boxes are overridden by the switch too — greying
  // only one of the two would make the other look like it still had a say.
  metaBoxes.forEach(c => {
    c.disabled = on;
    c.title = on ? "Prepísané prepínačom „Mixed in Key“ hore" : "";
    if (on) c.checked = MIK_RULES.includes(c.value);
  });
}
/* BPM WINDOW — the second switch that sits above the profiles.
 *
 * Same idea as Mixed in Key: a hard limit on what may appear, expressed the way
 * a DJ says it ("± 3 BPM from the one I picked"), kept in the browser so it
 * survives every profile change. Absolute BPM, not a percentage: 3 % is a
 * different thing at 90 than at 174. */
const bpmTol = () => ($("bpmOn").checked ? Math.abs(dec($("bpmTol").value) || 0) : 0);
function paintBpm() {
  const on = $("bpmOn").checked;
  $("bpmOn").closest("label").classList.toggle("on", on);
  $("bpmTol").disabled = !on;
  localStorage.setItem("bpmOn", on ? "1" : "0");
  localStorage.setItem("bpmTol", $("bpmTol").value);
}
/* Both of these are read when a query is built, so without a handler they only
 * took effect the next time something else triggered a search — which reads as
 * a dead control. */
$("limit").onchange = () => rerun();
$("spotifyOnly").onchange = () => rerun();

$("bpmOn").checked = localStorage.getItem("bpmOn") === "1";
$("bpmTol").value = localStorage.getItem("bpmTol") || "3";
$("bpmOn").onchange = () => { paintBpm(); rerun(); };
$("bpmTol").onchange = () => { paintBpm(); if ($("bpmOn").checked) rerun(); };
paintBpm();

/* RESET — back to a clean slate WITHOUT losing the profile.
 *
 * It clears everything that sits ABOVE the profile: the whole META panel (its
 * modes, targets, hard rules and macros), the Mixed in Key switch and the BPM
 * window. The profile's own panels are deliberately left alone — that is what
 * "everything except the profile" means, and re-clicking a profile or a mode is
 * how you reset those.
 * HOW TO TWEAK: add anything new that lives above profiles to this function,
 * otherwise it quietly survives a reset and looks like a bug later. */
function resetMeta() {
  const meta = document.getElementById("shiftBodyMeta");
  if (meta) {
    meta.querySelectorAll("[data-md]").forEach(sel => sel.value = "same");
    meta.querySelectorAll("[data-tg]").forEach(t => t.value = "");
    meta.querySelectorAll("[data-tl]").forEach(t => { t.value = t.dataset.def ?? t.value; });
  }
  const rules = document.getElementById("rulesMeta");
  if (rules) rules.innerHTML = "";
  state.macros.Meta.clear();
  renderMacros("Meta");

  $("mikOn").checked = false; paintMik({ keep: true });
  $("bpmOn").checked = false; paintBpm();

  localStorage.removeItem("metaShift");
  saveMetaShift();
  paintMetaBadge();
  toast("Vyresetované — META panel, Mixed in Key aj BPM okno. Profil zostal.");
  rerun();
}
$("btnReset").onclick = () => {
  const n = Object.keys(readShift("Meta")).length + readRules("Meta").length
          + state.macros.Meta.size + (mikOn() ? 1 : 0) + ($("bpmOn").checked ? 1 : 0);
  if (!n) return toast("Niet čo resetovať — nad profilom nič nastavené nie je.");
  resetMeta();
};

$("mikOn").checked = localStorage.getItem("mikOn") === "1";
$("mikOn").onchange = () => {
  // Going ON must not adopt the forced set as "the profile's own"; going OFF
  // repaints the remembered ones. Both are just paintMik() without adopt.
  const boxes = [...document.querySelectorAll("#shiftBody .kr")];
  if (mikOn()) ownKeyRules = boxes.filter(c => c.checked).map(c => c.value);
  paintMik({ keep: true });
  rerun();
};

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
        key_rules: keyRules(), base_key: baseKey(),
        tag_rules: tagRules(), bpm_tol: bpmTol() }) });
    state.rows = res.results;
    state.ceiling = res.ceiling;
    render();
    const used = Object.entries(res.signals_used || {}).map(([g, n]) => `${n} ${g}`).join(", ");
    // With several seeds, say what they actually had in common — otherwise the
    // owner has no way to tell whether the combination meant what he intended.
    const common = (res.common || []).slice(0, 4)
      .map(c => `${c.type}: ${c.tags.slice(0, 3).join(", ")}`).join(" · ");
    // When a filter is on, the honest headline is not "100 results" but "the
    // best 100 of the N that passed" — with how close the best one actually is.
    const narrowed = res.pool != null && res.library && res.pool < res.library * 0.9;
    const best = res.results[0];
    const closeness = (best && res.ceiling)
      ? ` · najlepší sedí na ${Math.round(best.score / res.ceiling * 100)} % možnej zhody`
      : "";
    $("ref").innerHTML = `<b>${esc(names)}</b> — ${res.results.length} najpodobnejších`
      + (narrowed ? `<span class="muted"> z <b>${res.pool.toLocaleString("sk")}</b>, `
                  + `ktoré prešli filtrom${esc(closeness)}</span>` : "")
      + `<span class="muted"> · porovnané: ${esc(used)}</span>`
      + (common ? `<div class="muted" style="margin-top:3px">spoločné: ${esc(common)}</div>` : "")
      + ((res.skipped || []).length
          ? `<div class="warn">⚠ <b>${res.skipped.length} z ${res.asked} zaškrtnutých signálov `
            + `sa nedalo použiť</b> — zvolený track pre ne nemá dáta, takže do porovnania nevstúpili: `
            + esc(res.skipped.map(x => x.label).join(", "))
            + (res.skipped.some(x => x.id === "key" || x.id === "bpm")
                ? ` <button data-edit="${esc(res.seeds[0])}" data-field="key">✎ doplniť ručne</button>` : "")
            + `</div>`
          : "")
      + ((res.missing || []).length
          ? `<div class="alarm">` + res.missing.map(m =>
              `<b>Chýba ${esc(m.label)}.</b> ${esc(m.why)} `
              + m.tracks.map(t =>
                  `<button data-edit="${esc(t.id)}" data-field="${esc(m.field)}">`
                  + `✎ doplniť ${esc(m.label)} — ${esc(t.name)}</button>`).join(" ")
            ).join("<br>") + `</div>`
          : "")
      + ((res.notes || []).length
          ? `<div style="margin-top:3px;color:#e0a33e">${res.notes.map(esc).join(" · ")}</div>` : "");
    if ((res.seeds_missing || []).length)
      toast(`${res.seeds_missing.length} track(ov) nemá analýzu — vynechané`);
  } catch (e) { $("ref").innerHTML = `<span style="color:#ff8080">${esc(e.message)}</span>`; }
}
const rerun = () => { if (state.seeds.length) runSeeds(); };

/* ---------------- results table ---------------- */
function render() {
  // AN EMPTY TABLE MUST EXPLAIN ITSELF. A filter that nothing satisfies looked
  // identical to a broken app: a blank list and no reason given.
  if (!state.rows.length) {
    const constraints = [
      ...Object.entries(signalModes()).map(([id, m]) =>
        `${id.replace(/^(tag:|num:)/, "")} ${({ diff: "≠", target: "→", gt: ">", gte: "≥", lt: "<", lte: "≤" })[m.mode] || m.mode}`
        + (m.target != null ? ` ${m.target}` : "")),
      ...tagRules().map(r => `${r.type} ${r.mode === "must" ? "musí" : "nesmie"} obsahovať „${r.value}“`),
      ...(mikOn() ? ["Mixed in Key"] : []),
      ...(bpmTol() ? [`BPM ± ${bpmTol()}`] : []),
    ];
    $("body").innerHTML = `<tr><td colspan="9" class="empty">`
      + `<b>Nič neprešlo cez filtre.</b><br>`
      + (constraints.length
          ? `Aktívne podmienky: ${esc(constraints.join(" · "))}.<br>`
            + `Uvoľni niektorú — alebo skús ↺ Reset, ktorý zruší všetko nad profilom.`
          : `Zvolený track zrejme nemá dosť dát na porovnanie.`)
      + `</td></tr>`;
    updateSel();
    return;
  }
  // Scale against the best score the query could reach WITHOUT any filter, not
  // against the best of what survived one. Measuring against the survivor made
  // every filtered result look like a perfect match, which is exactly why
  // narrowing by a macro felt as if the similarity had been thrown away — it
  // never was, the pool was just smaller and further down the ranking.
  const max = state.ceiling || (state.rows.length ? Math.max(...state.rows.map(r => r.score)) : 1);
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
      <td class="c-num" title="${r.rank ? `V celom rebríčku podobnosti je tento track ${r.rank}. — filter len preskočil tie pred ním.` : ""}">${i + 1}${
        r.rank && r.rank > i + 2 ? `<span class="rk">${r.rank}</span>` : ""}</td>
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
/* ---------------- editing a track's values ----------------
 * Nothing may fail silently. When a filter cannot be answered because the seed
 * is missing a value, the app says which value, on which track, and offers to
 * fill it in right there. What is typed here outranks every provider and our
 * own analysis, and survives re-analysis.
 * HOW TO TWEAK the editable fields: EDITABLE in music_app/similar_api.py. */
const editBox = document.createElement("div");
editBox.id = "editPop";
editBox.hidden = true;
document.body.appendChild(editBox);

const hideEdit = () => { editBox.hidden = true; };

async function editTrack(id, focusField) {
  editBox.hidden = false;
  editBox.innerHTML = '<div class="muted">načítavam…</div>';
  try {
    const d = await api("/api/track/fields?id=" + encodeURIComponent(id));
    if (d.error) throw new Error(d.error);
    editBox.innerHTML = `<div class="hd">Upraviť hodnoty<button class="x">✕</button></div>`
      + `<div class="who">${esc(d.name)}</div>`
      + d.fields.map(f => {
          const cur = f.mine ?? "";
          const found = f.found.length
            ? `<div class="src">Nájdené inde: ${f.found.map(s =>
                `<button class="pick" data-f="${f.field}" data-v="${esc(String(s.value))}">`
                + `${esc(String(s.value))}<i>${esc(s.source)}</i></button>`).join("")}</div>`
            : `<div class="src none">Žiadny zdroj túto hodnotu nemá — napíš ju.</div>`;
          const opts = (f.choices || []).map(c =>
            `<button class="pick" data-f="${f.field}" data-v="${esc(c)}">${esc(c)}</button>`).join("");
          return `<div class="fld${f.field === focusField ? " focus" : ""}">
              <label>${esc(f.label)}${f.mine != null ? ' <em>vlastná hodnota</em>' : ""}</label>
              <div class="row">
                <input data-in="${f.field}" value="${esc(String(cur))}"
                       placeholder="napíš vlastnú hodnotu" inputmode="${f.kind === "number" ? "decimal" : "text"}">
                <button class="save" data-f="${f.field}">Ulož</button>
                ${f.mine != null ? `<button class="ghost clr" data-f="${f.field}">Zruš</button>` : ""}
              </div>
              <div class="note">${esc(f.note || "")}</div>
              ${found}
              ${opts ? `<div class="src opts">Bežné hodnoty: ${opts}</div>` : ""}
            </div>`;
        }).join("");
    editBox.querySelector(".x").onclick = hideEdit;
    editBox.querySelectorAll(".pick").forEach(b => b.onclick = () => {
      editBox.querySelector(`[data-in="${b.dataset.f}"]`).value = b.dataset.v;
    });
    editBox.querySelectorAll(".save").forEach(b => b.onclick = () =>
      saveField(id, b.dataset.f, editBox.querySelector(`[data-in="${b.dataset.f}"]`).value, focusField));
    editBox.querySelectorAll(".clr").forEach(b => b.onclick = () =>
      saveField(id, b.dataset.f, "", focusField));
    const first = editBox.querySelector(".fld.focus input") || editBox.querySelector("input");
    if (first) first.focus();
  } catch (e) {
    editBox.innerHTML = `<div class="hd">Nepodarilo sa<button class="x">✕</button></div>`
      + `<p>${esc(e.message)}</p>`;
    editBox.querySelector(".x").onclick = hideEdit;
  }
}

async function saveField(id, field, value, focusField) {
  try {
    const r = await api("/api/track/field", { method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, field, value }) });
    if (r.error) return toast(esc(r.error));
    toast(r.cleared ? "Vlastná hodnota zrušená — platí zase rozpoznaná."
                    : "Uložené. Platí nad všetkými zdrojmi a prežije novú analýzu.");
    await editTrack(id, focusField);
    rerun();
  } catch (e) { toast(esc(e.message)); }
}

document.addEventListener("click", e => {
  const b = e.target.closest("[data-edit]");
  if (b) { e.preventDefault(); e.stopPropagation(); return editTrack(b.dataset.edit, b.dataset.field); }
  if (!e.target.closest("#editPop")) hideEdit();
});
document.addEventListener("keydown", e => { if (e.key === "Escape") hideEdit(); });

/* ---------------- the ⓘ explainer ----------------
 * One popover, reused. It asks the engine what a signal is: the prose comes
 * from similarity_help.py, the value lists and number ranges straight from the
 * library, so it can never describe data that is not there.
 * HOW TO TWEAK the wording: similarity_help.py, not here. */
const infoBox = document.createElement("div");
infoBox.id = "infoPop";
infoBox.hidden = true;
document.body.appendChild(infoBox);

const pct = (a, b) => b ? Math.round(a / b * 100) : 0;

async function showInfo(id, anchor) {
  infoBox.hidden = false;
  infoBox.innerHTML = '<div class="muted">načítavam…</div>';
  place(anchor);
  try {
    const d = await api("/api/similar/explain?id=" + encodeURIComponent(id));
    if (d.error) throw new Error(d.error);
    const cov = `<div class="cov">Pokrytie: <b>${d.coverage.toLocaleString("sk")}</b> `
      + `z ${d.library.toLocaleString("sk")} trackov (${pct(d.coverage, d.library)} %)`
      + `${d.default ? " · štandardne zapnuté" : ""}</div>`;
    let body = "";
    if (d.values) {
      body = `<div class="lbl">Najčastejšie hodnoty (${d.distinct.toLocaleString("sk")} rôznych)</div>`
        + `<div class="vals">${d.values.map(v =>
            `<span><b>${esc(v.value)}</b> ${v.count.toLocaleString("sk")}</span>`).join("")}</div>`;
    } else if (d.range) {
      const r = d.range;
      body = `<div class="lbl">Aké hodnoty tam sú</div>`
        + `<table class="rng"><tr><td>najnižšia</td><td>${r.min}</td><td>medián</td><td><b>${r.median}</b></td><td>najvyššia</td><td>${r.max}</td></tr>`
        + `<tr><td>5 %</td><td>${r.p5}</td><td>25 %</td><td>${r.p25}</td><td>75 %</td><td>${r.p75}</td></tr></table>`
        + (d.suggest ? `<div class="lbl">Čo skúsiť zadať</div><div class="vals">`
            + Object.entries(d.suggest).map(([k, v]) => `<span><b>${esc(k)}</b> ${v}</span>`).join("")
            + `</div>` : "")
        + (d.tol ? `<div class="cov">Predvolená tolerancia pri → je ± ${d.tol}</div>` : "");
    }
    infoBox.innerHTML = `<div class="hd">${esc(d.label)}<button class="x">✕</button></div>`
      + `<p>${esc(d.what)}</p>`
      + (d.how ? `<p class="how">${esc(d.how)}</p>` : "")
      + cov + body
      + `<p class="use">${esc(d.usage || "")}</p>`;
    infoBox.querySelector(".x").onclick = hideInfo;
    place(anchor);
  } catch (e) {
    infoBox.innerHTML = `<div class="hd">Nepodarilo sa<button class="x">✕</button></div>`
      + `<p>${esc(e.message)}</p>`;
    infoBox.querySelector(".x").onclick = hideInfo;
  }
}

function place(anchor) {
  const r = anchor.getBoundingClientRect();
  const w = 340;
  infoBox.style.left = Math.max(8, Math.min(window.innerWidth - w - 8, r.left - w / 2 + r.width / 2)) + "px";
  const below = window.innerHeight - r.bottom;
  if (below > 260 || below > r.top) {
    infoBox.style.top = (r.bottom + 8) + "px"; infoBox.style.bottom = "auto";
  } else {
    infoBox.style.bottom = (window.innerHeight - r.top + 8) + "px"; infoBox.style.top = "auto";
  }
}
const hideInfo = () => { infoBox.hidden = true; };
document.addEventListener("click", e => {
  const btn = e.target.closest("[data-info]");
  if (btn) { e.preventDefault(); e.stopPropagation(); return showInfo(btn.dataset.info, btn); }
  if (!e.target.closest("#infoPop")) hideInfo();
});
document.addEventListener("keydown", e => { if (e.key === "Escape") hideInfo(); });

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
  toggle() {
    if (backend !== "spotify") return P.paused ? P.play() : P.pause();
    if (sp.mode === "sdk" && sp.player) return sp.player.togglePlay();
    if (sp.controller) sp.controller.togglePlay();
  },
  seekTo(sec) {
    if (backend === "spotify") {
      sp.position = sec;
      // SDK takes MILLISECONDS, the embed takes SECONDS. Same bar, two units.
      if (sp.mode === "sdk" && sp.player) sp.player.seek(Math.round(sec * 1000));
      else if (sp.controller) sp.controller.seek(sec);
    } else if (isFinite(P.duration)) P.currentTime = sec;
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
/* The slider used to set the volume of OUR audio element only, so while a
 * Spotify track was playing it did nothing at all. */
$("vol").oninput = () => {
  const v = +$("vol").value;
  P.volume = v;
  if (sp.mode === "sdk" && sp.player) { try { sp.player.setVolume(v); } catch {} }
};
document.onkeydown = e => {
  if (/^(INPUT|SELECT|TEXTAREA)$/.test(e.target.tagName)) return;
  if (e.code === "Space") { e.preventDefault(); $("big").click(); }
  else if (e.code === "ArrowRight") T.nudge(10);
  else if (e.code === "ArrowLeft") T.nudge(-10);
  else if (e.code === "ArrowDown") { e.preventDefault(); playIndex(state.index + 1); }
  else if (e.code === "ArrowUp") { e.preventDefault(); playIndex(state.index - 1); }
};

/* ---------------- Spotify backend ----------------
 * Two ways to play a track we have neither on disk nor as a 30-second preview,
 * and the app always tries the good one first:
 *
 *  1. WEB PLAYBACK SDK — the WHOLE track, and the app's own transport drives
 *     it: the long seek bar scrubs it, the buttons control it. Needs Spotify
 *     Premium and the `streaming` permission (spotify_authorize.py grants it).
 *
 *  2. EMBED — Spotify's own little player through the iFrame API, 30 seconds
 *     only. Used when the SDK is unavailable.
 *
 * NEITHER CAN GO TO THE CUE HEADPHONES, and it is worth being exact about why,
 * because it looked achievable and is not. The SDK does NOT put an <audio>
 * element in this page — verified in the running app, which reported
 * `audio=[player] iframes=[https://sdk.scdn.co/embedded/index.html]`. The sound
 * is produced inside a cross-origin frame belonging to Spotify, and setSinkId
 * only ever applies to a media element this document owns. There is no way
 * around that from inside the app; per-app output routing on macOS needs a
 * system tool such as Loopback or Audio Hijack. Local files and the 30-second
 * previews DO follow the CUE device, because those play through our own
 * element.
 *
 * Docs: developer.spotify.com/documentation/web-playback-sdk (SDK, seek takes
 * MILLISECONDS) and .../embeds/references/iframe-api (embed, seek takes
 * SECONDS). The units differ; that is not a typo below. */
const API_TIMEOUT = 15000;
const sp = { api: null, controller: null, duration: 0, position: 0, paused: true,
             lastUpdate: 0, ticker: null,
             sdk: null, player: null, device: null, streaming: null, cued: false };

async function spotifyAuth() {
  const r = await api("/api/spotify/token");
  if (r.error) throw new Error(r.error);
  sp.streaming = !!r.streaming;
  return r.token;
}

/* ---- 1. the good one: full tracks, our audio element, CUE works ---- */
function loadSdk() {
  if (sp.sdk) return sp.sdk;
  sp.sdk = new Promise((resolve, reject) => {
    window.onSpotifyWebPlaybackSDKReady = () => resolve(window.Spotify);
    const tag = document.createElement("script");
    tag.src = "https://sdk.scdn.co/spotify-player.js";
    tag.async = true;
    tag.onerror = () => reject(new Error("Spotify SDK sa nenačítal"));
    document.head.appendChild(tag);
    setTimeout(() => reject(new Error("Spotify SDK neodpovedá")), API_TIMEOUT);
  });
  return sp.sdk;
}

async function sdkReady() {
  if (sp.device) return true;
  const token = await spotifyAuth();
  if (!sp.streaming) return false;              // permission not granted yet
  const Spotify = await loadSdk();
  const player = new Spotify.Player({
    name: "Similar Tracks",
    getOAuthToken: cb => spotifyAuth().then(cb).catch(() => {}),
    volume: +$("vol").value,
  });
  sp.player = player;
  player.addListener("player_state_changed", st => {
    if (!st) return;
    sp.duration = (st.duration || 0) / 1000;
    sp.position = (st.position || 0) / 1000;
    sp.paused = !!st.paused;
    sp.lastUpdate = Date.now();
    paintTransport();
    nowPlayingToHost();
    routeSpotifyToCue();
  });
  ["initialization_error", "authentication_error", "account_error",
   "playback_error"].forEach(kind =>
    player.addListener(kind, ({ message }) => nlog(`SDK ${kind}: ${message}`)));

  const ok = await new Promise(resolve => {
    player.addListener("ready", ({ device_id }) => { sp.device = device_id; resolve(true); });
    player.addListener("not_ready", () => resolve(false));
    player.connect().then(c => { if (!c) resolve(false); });
    setTimeout(() => resolve(!!sp.device), API_TIMEOUT);
  });
  return ok;
}

/* Kept deliberately as a no-op with an explanation, so nobody re-adds it: the
 * SDK's audio is inside Spotify's own cross-origin frame and cannot be pointed
 * at another output device from here. Our own player is handled by applySink(). */
function routeSpotifyToCue() { /* not possible — see the note above */ }

/* ---- 2. the fallback: 30 seconds, Spotify's own frame, no CUE ---- */
async function embedFallback(r) {
  const box = $("embed");
  box.classList.add("on");
  document.querySelector("footer").classList.add("embed");
  if (!box.querySelector(".lbl")) {
    box.innerHTML = `<div class="lbl">▶ hrá cez <b>SPOTIFY</b> — 30s ukážka`
      + `<span>· ide do predvoleného výstupu, nie do slúchadiel</span></div><div id="spHost"></div>`;
  }
  const uri = "spotify:track:" + r.spotify_id;
  if (!sp.api) {
    sp.api = new Promise((resolve, reject) => {
      window.onSpotifyIframeApiReady = a => resolve(a);
      const tag = document.createElement("script");
      tag.src = "https://open.spotify.com/embed/iframe-api/v1";
      tag.async = true;
      tag.onerror = () => reject(new Error("Spotify sa nepodarilo načítať"));
      document.head.appendChild(tag);
      setTimeout(() => reject(new Error("Spotify neodpovedá")), API_TIMEOUT);
    });
  }
  const a = await sp.api;
  if (!sp.controller) {
    await new Promise(done => a.createController($("spHost"),
      { uri, width: "100%", height: 80 }, c => {
        sp.controller = c;
        // The embed reports MILLISECONDS but takes seek() in SECONDS.
        c.addListener("playback_update", e => {
          sp.duration = (e.data.duration || 0) / 1000;
          sp.position = (e.data.position || 0) / 1000;
          sp.paused = !!e.data.isPaused;
          sp.lastUpdate = Date.now();
          paintTransport(); nowPlayingToHost();
        });
        c.addListener("ready", () => c.resume());
        done();
      }));
  } else { sp.controller.loadUri(uri); sp.controller.resume(); }
  startSpotifyTicker();
}

/* The one the player calls. */
async function showEmbed(r) {
  backend = "spotify";
  $("now").innerHTML = `${esc(r.artist)} — ${esc(r.title)}<br><small>Spotify…</small>`;
  try {
    if (await sdkReady()) {
      sp.mode = "sdk";
      hideEmbedBox();
      const res = await api("/api/spotify/play", { method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: r.spotify_id, device_id: sp.device }) });
      if (res.error) throw new Error(res.error);
      $("now").innerHTML = `${esc(r.artist)} — ${esc(r.title)}<br>`
        + `<small>SPOTIFY · celá skladba`
        + `${$("sink").value ? " · <b>nejde do slúchadiel</b>" : ""}</small>`;
      startSpotifyTicker();
      return;
    }
    sp.mode = "embed";
    await embedFallback(r);
    if (sp.streaming === false) {
      toast("Spotify hrá len 30s ukážku. Celé skladby zapneš raz cez "
          + "<b>python3 spotify_authorize.py</b> (chýba povolenie „streaming“).", 12000);
    }
  } catch (err) {
    $("embed").classList.add("on");
    $("embed").innerHTML = `<div class="lbl" style="color:#ff8080">${esc(err.message)}</div>`;
    toast("Spotify prehrávanie zlyhalo: " + esc(err.message));
  }
}

/* State updates are sparse; between them the position is advanced locally so
 * the bar moves smoothly, and every real update snaps it back to the truth. */
function startSpotifyTicker() {
  clearInterval(sp.ticker);
  sp.ticker = setInterval(() => {
    if (backend !== "spotify" || sp.paused) return;
    const drift = (Date.now() - sp.lastUpdate) / 1000;
    if (drift > 0.2 && drift < 3) { sp.position += 0.25; sp.lastUpdate += 250; paintTransport(); }
  }, 250);
}

function hideEmbedBox() {
  const box = $("embed");
  box.classList.remove("on");
  document.querySelector("footer").classList.remove("embed");
}

function hideEmbed() {
  clearInterval(sp.ticker);
  if (sp.mode === "sdk" && sp.player) { try { sp.player.pause(); } catch {} }
  if (sp.mode === "embed" && sp.controller) { try { sp.controller.pause(); } catch {} }
  backend = "audio";
  hideEmbedBox();
}

/* ---------------- CUE output ---------------- */
async function applySink(id) {
  if (P.setSinkId) { try { await P.setSinkId(id || "default"); } catch {} }
  // Spotify's own audio element lives in this page too when the SDK is used,
  // so the CUE device applies to it as well — that is the whole point.
  routeSpotifyToCue();
}
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
