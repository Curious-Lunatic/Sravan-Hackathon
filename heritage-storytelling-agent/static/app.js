const SAMPLE = `Court memorandum from Hampi, after the monsoon of 1521.

The stone-cutters of the Krishnadevaraya workshop report that the northern mandapa of the Vitthala temple is complete, save for the hanging stone chains on the eastern cornice. The queen's gift of two bronze lamps arrived from Chandragiri at dawn. They are to burn without fail during the evening harati, facing the Tungabhadra.

A singer from the village of Anegundi was detained at the bazaar gate for reciting a satire against a tax farmer. The temple trustees ask that he be released if he will instead teach the boatmen the older river hymn, the one that names each rapid between the coracle ghat and the stone bridge.

The bazaar still smells of wet tamarind and horse-sweat. Foreign merchants from Goa paid for pepper in silver, then asked to see the musical pillars. The keeper of the pillars says they may listen, but they may not strike the stone themselves.`;

const form = document.getElementById("archive-form");
const sampleBtn = document.getElementById("sample-btn");
const runBtn = document.getElementById("run-btn");
const sourceText = document.getElementById("source-text");
const languageSelect = document.getElementById("target-language");
const stepsEl = document.getElementById("steps");
const statusLine = document.getElementById("status-line");
const emptyState = document.getElementById("empty-state");
const workspace = document.getElementById("workspace");
const metaEl = document.getElementById("archive-meta");
const askForm = document.getElementById("ask-form");
const askInput = document.getElementById("ask-input");
const askThread = document.getElementById("ask-thread");

let projectId = null;
let pollTimer = null;
let latest = null;

sampleBtn.addEventListener("click", () => {
  sourceText.value = SAMPLE;
  if (!languageSelect.value) languageSelect.value = "hi-IN";
});

document.querySelectorAll(".folio").forEach((button) => {
  button.addEventListener("click", () => showView(button.dataset.view));
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  runBtn.disabled = true;
  stepsEl.hidden = false;
  statusLine.textContent = "Opening the archive…";
  const data = new FormData(form);
  try {
    const response = await fetch("/api/projects", { method: "POST", body: data });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "Could not start");
    projectId = payload.id;
    poll();
  } catch (error) {
    statusLine.textContent = error.message;
    runBtn.disabled = false;
  }
});

askForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!projectId || !askInput.value.trim()) return;
  const question = askInput.value.trim();
  askInput.value = "";
  askThread.insertAdjacentHTML("beforeend", `<p class="q">${escapeHtml(question)}</p>`);
  const response = await fetch(`/api/projects/${projectId}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  const payload = await response.json();
  const answer = response.ok ? payload.answer : payload.detail || "The archive could not answer.";
  askThread.insertAdjacentHTML("beforeend", `<p class="a">${escapeHtml(answer)}</p>`);
});

async function boot() {
  const languages = await fetch("/api/languages").then((res) => res.json());
  languageSelect.innerHTML = Object.entries(languages)
    .map(([code, name]) => `<option value="${code}">${name}</option>`)
    .join("");
  languageSelect.value = "hi-IN";
}

function poll() {
  clearTimeout(pollTimer);
  fetch(`/api/projects/${projectId}`)
    .then((res) => res.json())
    .then((job) => {
      latest = job;
      paintSteps(job);
      statusLine.textContent = job.error || job.log?.at(-1) || "";
      if (job.status === "ready") {
        runBtn.disabled = false;
        render(job);
        return;
      }
      if (job.status === "error") {
        runBtn.disabled = false;
        return;
      }
      pollTimer = setTimeout(poll, 1500);
    })
    .catch(() => {
      pollTimer = setTimeout(poll, 2500);
    });
}

function paintSteps(job) {
  document.querySelectorAll(".steps li").forEach((item) => {
    item.className = job.steps?.[item.dataset.step] || "";
  });
}

function render(job) {
  emptyState.hidden = true;
  workspace.hidden = false;
  const archive = job.experiences?.archive || {};
  metaEl.innerHTML = [
    archive.title,
    archive.place,
    archive.period,
    `${job.source_language || "?"} → ${job.target_language}`,
  ]
    .filter(Boolean)
    .map((item) => `<span class="chip">${escapeHtml(item)}</span>`)
    .join("");

  document.getElementById("view-source").innerHTML = `
    <p>${escapeHtml(archive.summary || "")}</p>
    <h3>Recovered source</h3>
    <div class="source-block">${escapeHtml(job.source_text || "")}</div>
    <h3>Told in the chosen language</h3>
    <div class="source-block">${escapeHtml(job.translated_text || "")}</div>
  `;

  const chapters = job.experiences?.story?.chapters || [];
  document.getElementById("view-story").innerHTML = `
    <h3>${escapeHtml(job.experiences?.story?.title || "Story")}</h3>
    ${chapters
      .map(
        (chapter, index) => `
      <article class="card">
        <h3>${escapeHtml(chapter.title)}</h3>
        <p>${escapeHtml(chapter.body)}</p>
        <p class="look">${escapeHtml(chapter.prompt || "")}</p>
        ${audioBlock("story", index, job)}
      </article>`
      )
      .join("")}
  `;

  const stops = job.experiences?.tour?.stops || [];
  document.getElementById("view-tour").innerHTML = `
    <h3>${escapeHtml(job.experiences?.tour?.title || "Tour")}</h3>
    ${stops
      .map(
        (stop, index) => `
      <article class="card">
        <h3>${index + 1}. ${escapeHtml(stop.title)}</h3>
        <p><strong>${escapeHtml(stop.place || "")}</strong></p>
        <p>${escapeHtml(stop.narration)}</p>
        <p class="look">Look for: ${escapeHtml(stop.look_for || "")}</p>
        ${audioBlock("tour", index, job)}
      </article>`
      )
      .join("")}
  `;

  const lines = job.experiences?.podcast?.lines || [];
  document.getElementById("view-podcast").innerHTML = `
    <h3>${escapeHtml(job.experiences?.podcast?.title || "Podcast")}</h3>
    ${lines
      .map(
        (line, index) => `
      <div class="podcast-line">
        <div class="role">${escapeHtml(line.speaker)}</div>
        <div>${escapeHtml(line.text)}</div>
        <div>${audioBlock("podcast", index, job)}</div>
      </div>`
      )
      .join("")}
  `;

  document.querySelectorAll("[data-narrate]").forEach((button) => {
    button.addEventListener("click", () => narrate(button.dataset.kind, Number(button.dataset.index)));
  });
  showView("story");
}

function audioBlock(kind, index, job) {
  const url = job.audio?.[`${kind}:${index}`];
  if (url) return `<audio controls src="${url}"></audio>`;
  return `<button type="button" class="speak" data-narrate data-kind="${kind}" data-index="${index}">Hear this</button>`;
}

async function narrate(kind, index) {
  const response = await fetch(`/api/projects/${projectId}/narrate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ kind, index }),
  });
  const payload = await response.json();
  if (!response.ok) {
    statusLine.textContent = payload.detail || "Narration failed";
    return;
  }
  latest.audio[`${kind}:${index}`] = payload.url;
  render(latest);
  showView(kind === "podcast" ? "podcast" : kind);
}

function showView(name) {
  document.querySelectorAll(".folio").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === name);
  });
  document.querySelectorAll(".view").forEach((view) => {
    view.hidden = view.id !== `view-${name}`;
  });
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

boot();
