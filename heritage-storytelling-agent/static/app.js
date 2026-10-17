/* ─────────────────────────────────────────────────────
   Heritage Storytelling Agent — Frontend App
   ───────────────────────────────────────────────────── */

const SAMPLE = `Court memorandum from Hampi, after the monsoon of 1521.

The stone-cutters of the Krishnadevaraya workshop report that the northern mandapa of the Vitthala temple is complete, save for the hanging stone chains on the eastern cornice. The queen's gift of two bronze lamps arrived from Chandragiri at dawn. They are to burn without fail during the evening harati, facing the Tungabhadra.

A singer from the village of Anegundi was detained at the bazaar gate for reciting a satire against a tax farmer. The temple trustees ask that he be released if he will instead teach the boatmen the older river hymn, the one that names each rapid between the coracle ghat and the stone bridge.

The bazaar still smells of wet tamarind and horse-sweat. Foreign merchants from Goa paid for pepper in silver, then asked to see the musical pillars. The keeper of the pillars says they may listen, but they may not strike the stone themselves.`;

/* ── DOM refs ── */
const form          = document.getElementById("archive-form");
const sampleBtn     = document.getElementById("sample-btn");
const runBtn        = document.getElementById("run-btn");
const sourceText    = document.getElementById("source-text");
const languageSelect = document.getElementById("target-language");
const progressSection = document.getElementById("progress-section");
const statusLine    = document.getElementById("status-line");
const emptyState    = document.getElementById("empty-state");
const workspace     = document.getElementById("workspace");
const archiveMeta   = document.getElementById("archive-meta");
const bannerLang    = document.getElementById("banner-lang");
const askForm       = document.getElementById("ask-form");
const askInput      = document.getElementById("ask-input");
const askThread     = document.getElementById("ask-thread");
const manuscriptInput = document.getElementById("manuscript-input");
const audioInput    = document.getElementById("audio-input");

let projectId = null;
let pollTimer = null;
let latest    = null;

/* ── File dropzone setup ── */
setupDropzone("manuscript-zone", "manuscript-input", "manuscript-name");
setupDropzone("audio-zone",      "audio-input",      "audio-name");

function setupDropzone(zoneId, inputId, nameId) {
  const zone  = document.getElementById(zoneId);
  const input = document.getElementById(inputId);
  const nameEl = document.getElementById(nameId);

  zone.addEventListener("dragover", e => {
    e.preventDefault();
    zone.classList.add("dragover");
  });
  zone.addEventListener("dragleave", () => zone.classList.remove("dragover"));
  zone.addEventListener("drop", e => {
    e.preventDefault();
    zone.classList.remove("dragover");
    const files = e.dataTransfer.files;
    if (files.length) {
      const dt = new DataTransfer();
      dt.items.add(files[0]);
      input.files = dt.files;
      showFileName(zone, nameEl, files[0].name);
    }
  });
  input.addEventListener("change", () => {
    if (input.files.length) showFileName(zone, nameEl, input.files[0].name);
    else { zone.classList.remove("has-file"); nameEl.textContent = ""; }
  });
}

function showFileName(zone, nameEl, filename) {
  zone.classList.add("has-file");
  nameEl.textContent = filename;
  nameEl.style.display = "block";
}

/* ── Sample button ── */
sampleBtn.addEventListener("click", () => {
  sourceText.value = SAMPLE;
  if (!languageSelect.value) languageSelect.value = "hi-IN";
  sourceText.style.height = "auto";
  sourceText.style.height = sourceText.scrollHeight + "px";
});

/* ── Tab navigation ── */
document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => switchTab(btn.dataset.view));
});

/* ── Form submit ── */
form.addEventListener("submit", async e => {
  e.preventDefault();
  runBtn.disabled = true;
  runBtn.classList.add("loading");
  progressSection.style.display = "block";
  statusLine.textContent = "Opening the archive…";
  resetPipeline();

  const data = new FormData(form);
  try {
    const res = await fetch("/api/projects", { method: "POST", body: data });
    const payload = await res.json();
    if (!res.ok) throw new Error(payload.detail || "Could not start");
    projectId = payload.id;
    poll();
  } catch (err) {
    statusLine.textContent = err.message;
    runBtn.disabled = false;
    runBtn.classList.remove("loading");
  }
});

/* ── Ask form ── */
askForm.addEventListener("submit", async e => {
  e.preventDefault();
  const q = askInput.value.trim();
  if (!projectId || !q) return;
  askInput.value = "";

  appendMessage("question", q);
  const loadingEl = appendMessage("answer loading", "Consulting the archive…");

  try {
    const res = await fetch(`/api/projects/${projectId}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q }),
    });
    const payload = await res.json();
    const answer = res.ok ? payload.answer : (payload.detail || "The archive could not answer.");
    loadingEl.className = "ask-message answer";
    loadingEl.textContent = answer;
  } catch {
    loadingEl.className = "ask-message answer";
    loadingEl.textContent = "Connection error — please try again.";
  }
  askThread.scrollTop = askThread.scrollHeight;
});

function appendMessage(classNames, text) {
  const el = document.createElement("div");
  el.className = `ask-message ${classNames}`;
  el.textContent = text;
  askThread.appendChild(el);
  askThread.scrollTop = askThread.scrollHeight;
  return el;
}

/* ── Boot: load languages ── */
async function boot() {
  try {
    const languages = await fetch("/api/languages").then(r => r.json());
    languageSelect.innerHTML = Object.entries(languages)
      .map(([code, name]) => `<option value="${code}">${name}</option>`)
      .join("");
    languageSelect.value = "hi-IN";
  } catch {}
}

/* ── Poll loop ── */
function poll() {
  clearTimeout(pollTimer);
  fetch(`/api/projects/${projectId}`)
    .then(r => r.json())
    .then(job => {
      latest = job;
      updatePipeline(job);
      statusLine.textContent = job.error || job.log?.at(-1) || "";

      if (job.status === "ready") {
        runBtn.disabled = false;
        runBtn.classList.remove("loading");
        render(job);
        return;
      }
      if (job.status === "error") {
        runBtn.disabled = false;
        runBtn.classList.remove("loading");
        return;
      }
      pollTimer = setTimeout(poll, 1500);
    })
    .catch(() => { pollTimer = setTimeout(poll, 2500); });
}

/* ── Pipeline state ── */
function resetPipeline() {
  document.querySelectorAll(".pipeline-step").forEach(step => {
    step.removeAttribute("data-state");
  });
}

function updatePipeline(job) {
  document.querySelectorAll(".pipeline-step").forEach(step => {
    const state = job.steps?.[step.dataset.step];
    if (state) step.setAttribute("data-state", state);
    else step.removeAttribute("data-state");
  });
}

/* ── Render results ── */
function render(job) {
  emptyState.style.display = "none";
  workspace.style.display  = "block";

  const archive = job.experiences?.archive || {};

  /* Banner */
  archiveMeta.innerHTML = [
    archive.title
      ? `<span class="chip chip-title">${esc(archive.title)}</span>`
      : "",
    archive.place && archive.place !== "Unknown"
      ? `<span class="chip">📍 ${esc(archive.place)}</span>`
      : "",
    archive.period && archive.period !== "Unknown"
      ? `<span class="chip">🕰 ${esc(archive.period)}</span>`
      : "",
    (archive.people || []).slice(0, 3).map(p =>
      `<span class="chip">👤 ${esc(p)}</span>`).join(""),
  ].join("");

  bannerLang.textContent = `${job.source_language || "?"} → ${job.target_language}`;

  /* Source tab */
  document.getElementById("view-source").innerHTML = `
    ${archive.summary ? `<div class="source-summary">${esc(archive.summary)}</div>` : ""}
    <div class="source-section">
      <div class="source-label">Recovered source</div>
      <div class="source-block">${esc(job.source_text || "")}</div>
    </div>
    <div class="source-section">
      <div class="source-label">Translated text</div>
      <div class="source-block">${esc(job.translated_text || "")}</div>
    </div>
  `;

  /* Story tab */
  const chapters = job.experiences?.story?.chapters || [];
  document.getElementById("view-story").innerHTML = `
    <h2 class="view-title">${esc(job.experiences?.story?.title || "Story")}</h2>
    ${chapters.map((ch, i) => `
      <article class="card">
        <div class="card-num">Chapter ${i + 1}</div>
        <h3>${esc(ch.title)}</h3>
        <p>${esc(ch.body)}</p>
        ${ch.prompt ? `<p class="ponder">${esc(ch.prompt)}</p>` : ""}
        <div class="audio-row">${audioWidget("story", i, job)}</div>
      </article>
    `).join("")}
  `;

  /* Tour tab */
  const stops = job.experiences?.tour?.stops || [];
  document.getElementById("view-tour").innerHTML = `
    <h2 class="view-title">${esc(job.experiences?.tour?.title || "Guided Tour")}</h2>
    ${stops.map((stop, i) => `
      <div class="tour-stop">
        <div class="stop-marker">${i + 1}</div>
        <div class="stop-body">
          <div class="card">
            <div class="stop-place">${esc(stop.place || "")}</div>
            <h3>${esc(stop.title)}</h3>
            <p>${esc(stop.narration)}</p>
            ${stop.look_for ? `
              <div class="look-for">
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                ${esc(stop.look_for)}
              </div>` : ""}
            <div class="audio-row">${audioWidget("tour", i, job)}</div>
          </div>
        </div>
      </div>
    `).join("")}
  `;

  /* Podcast tab */
  const lines = job.experiences?.podcast?.lines || [];
  document.getElementById("view-podcast").innerHTML = `
    <h2 class="view-title">${esc(job.experiences?.podcast?.title || "Podcast")}</h2>
    <div class="podcast-track">
      ${lines.map((line, i) => `
        <div class="podcast-line ${line.speaker}">
          <div class="speaker-avatar">${line.speaker === "host" ? "H" : "G"}</div>
          <div>
            <div class="speech-bubble">${esc(line.text)}</div>
            <div class="audio-row">${audioWidget("podcast", i, job)}</div>
          </div>
        </div>
      `).join("")}
    </div>
  `;

  /* Wire up narration buttons */
  document.querySelectorAll("[data-narrate]").forEach(btn => {
    btn.addEventListener("click", () =>
      narrate(btn.dataset.kind, Number(btn.dataset.idx), btn)
    );
  });

  switchTab("story");
}

/* ── Audio widget ── */
function audioWidget(kind, index, job) {
  const url = job.audio?.[`${kind}:${index}`];
  if (url) {
    return `<audio controls src="${url}"></audio>`;
  }
  return `
    <button class="btn-narrate" data-narrate data-kind="${kind}" data-idx="${index}">
      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/></svg>
      Hear this
    </button>`;
}

/* ── On-demand narration ── */
async function narrate(kind, index, btn) {
  btn.classList.add("loading");
  btn.textContent = "Generating…";
  btn.disabled = true;

  try {
    const res = await fetch(`/api/projects/${projectId}/narrate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind, index }),
    });
    const payload = await res.json();
    if (!res.ok) {
      statusLine.textContent = payload.detail || "Narration failed";
      btn.classList.remove("loading");
      btn.textContent = "Hear this";
      btn.disabled = false;
      return;
    }
    latest.audio[`${kind}:${index}`] = payload.url;
    render(latest);
    switchTab(kind === "podcast" ? "podcast" : kind);
  } catch {
    btn.classList.remove("loading");
    btn.textContent = "Hear this";
    btn.disabled = false;
  }
}

/* ── Tab switching ── */
function switchTab(name) {
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.view === name);
    btn.setAttribute("aria-selected", btn.dataset.view === name ? "true" : "false");
  });
  document.querySelectorAll(".view").forEach(view => {
    const isActive = view.id === `view-${name}`;
    view.style.display = isActive ? "block" : "none";
    view.classList.toggle("active", isActive);
  });
}

/* ── Helpers ── */
function esc(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

boot();
