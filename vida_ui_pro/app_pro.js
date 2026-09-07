const $ = s => document.querySelector(s);
const $$ = s => document.querySelectorAll(s);

let course = null;
let state = null;
let currentActivity = null;
let actVideoTimer = null;
let sharedVideoTimer = null;

const MIME = {
  pdf: "📕 PDF", png: "🖼 Imagen", jpg: "🖼 Imagen", jpeg: "🖼 Imagen",
  gif: "🖼 Imagen", webp: "🖼 Imagen", xlsx: "📊 Excel", xls: "📊 Excel",
  doc: "📄 Word", docx: "📄 Word", ppt: "📽 PowerPoint", pptx: "📽 PowerPoint",
  txt: "📃 Texto", zip: "🗜 Comprimido"
};

function esc(v) {
  return String(v).replaceAll("&", "&amp;").replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}
function fileType(name) {
  const ext = String(name || "").split(".").pop().toLowerCase();
  return MIME[ext] || "📎 Archivo";
}
function mediaUrl(file) {
  if (!file) return "";
  const v = String(file);
  if (/^https?:\/\//.test(v)) return v;
  if (v.startsWith("/")) return v;
  if (v.startsWith("media/")) return "/" + v;
  return "/media/videos/" + encodeURIComponent(v);
}
function fmtSize(n) {
  if (!n) return "";
  if (n < 1024) return n + " B";
  if (n < 1048576) return (n / 1024).toFixed(1) + " KB";
  return (n / 1048576).toFixed(1) + " MB";
}
async function getJSON(u, o) {
  const r = await fetch(u, o);
  let data = null;
  try { data = await r.json(); } catch (_) {}
  if (!r.ok) {
    const msg = (data && data.error) || ("Error HTTP " + r.status);
    throw new Error(msg);
  }
  return data;
}

/* ---------------- GUÍA POR VOZ ---------------- */
const VOICE_KEY = "vida_voice";
let voiceOn = localStorage.getItem(VOICE_KEY) !== "off";
const GUIDES = {
  dashboard: "Este es tu centro de mando VIDA. Aquí revisas el progreso operativo, el dominio, las evidencias y el puntaje de aprendizaje del curso activo.",
  actividades: "Esta es tu ruta de aprendizaje. Cada actividad tiene video de la sesión, material y una zona para subir tu entrega.",
  actividad: "Página de actividad. Mira el objetivo, reproduce la sesión y sube tu entrega como evidencia.",
  conocimiento: "Estos son los conceptos del curso. El dominio se verifica con evidencia; VIDA no asume que ya lo sabes.",
  evidencias: "Centro de evidencias. VIDA solo registra lo que observa; nunca inventa evidencia.",
  reglas: "Reglas del motor. Aquí puedes ver quién califica, con qué pesos y bajo qué condiciones se emite el certificado."
};
function speak(text) {
  if (!text || !voiceOn || !("speechSynthesis" in window)) return;
  try {
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "es-CO";
    u.rate = 0.96;
    const vs = speechSynthesis.getVoices();
    const v = vs.find((x) => x.lang.toLowerCase().startsWith("es"));
    if (v) u.voice = v;
    speechSynthesis.speak(u);
  } catch (_) {}
}
function setVoiceBtn() {
  const b = $("#voiceBtn");
  if (b) b.textContent = voiceOn ? "🔊" : "🔇";
  try { localStorage.setItem(VOICE_KEY, voiceOn ? "on" : "off"); } catch (_) {}
}

/* ---------------- CAMBIO DE CURSO ---------------- */
function certKey() {
  let k = sessionStorage.getItem("vida_key") || "";
  if (!k) {
    k = prompt("Clave del sistema VIDA (permiso para cambiar de curso):");
    if (k) sessionStorage.setItem("vida_key", k);
  }
  return k;
}
async function loadCourses() {
  const sel = $("#courseSel");
  if (!sel) return;
  const data = await getJSON("/api/courses");
  sel.innerHTML = "";
  data.courses.forEach((c) => {
    const o = document.createElement("option");
    o.value = c.id;
    o.textContent = c.title + (c.active ? " · ACTIVO" : "");
    if (c.active) o.selected = true;
    sel.appendChild(o);
  });
  const prev = sel.dataset.last;
  if (prev && prev !== data.active) refresh();
  sel.dataset.last = data.active;
}
async function activateCourse(cid) {
  try {
    await getJSON("/api/courses/" + encodeURIComponent(cid) + "/activate", {
      method: "POST",
      headers: { "X-Vida-Key": certKey() }
    });
  } catch (err) {
    sessionStorage.removeItem("vida_key");
    loadCourses();
    speak("Clave incorrecta. No se cambió el curso.");
    alert(err.message);
    return;
  }
  course = null;
  state = null;
  location.hash = "#/dashboard";
  await load();
  refresh();
}

/* ---------------- ROUTER ---------------- */
const routes = {
  "dashboard": renderDashboard,
  "actividades": renderActivities,
  "actividad": renderActivity,
  "conocimiento": renderKnowledge,
  "evidencias": renderEvidence,
  "reglas": renderRules
};

function parseHash() {
  const h = (location.hash || "#/dashboard").replace(/^#\//, "").split("/");
  return { name: h[0] || "dashboard", arg: h[1] || "" };
}

function router() {
  const { name, arg } = parseHash();
  $$(".view").forEach(v => v.classList.remove("active"));
  const view = $("#view-" + name) || $("#view-dashboard");
  view.classList.add("active");

  $$("aside a.nav").forEach(a => {
    const active = a.dataset.nav === name ||
      (name === "actividad" && a.dataset.nav === "actividades");
    a.classList.toggle("active", active);
  });

  const fn = routes[name === "actividad" && arg ? "actividad" : name] || renderDashboard;
  fn(arg);
  if (voiceOn) setTimeout(() => speak(GUIDES[name] || GUIDES.dashboard), 500);
}

window.addEventListener("hashchange", router);

/* ---------------- BOOT ---------------- */
async function load() {
  course = await getJSON("/api/course");
  $("#heroTitle").textContent = course.title;
  await loadCourses();
  await renderRoadmap();
  router();
}

/* ---------------- DASHBOARD ---------------- */
async function refresh() {
  state = await getJSON("/api/dashboard");
  $("#overall").textContent = (state.overall ?? 0) + "%";
  $("#overallbar").style.width = (state.overall ?? 0) + "%";
  $("#mastery").textContent = (state.mastery ?? 0) + "%";
  $("#masterybar").style.width = (state.mastery ?? 0) + "%";
  $("#evidence").textContent = state.evidence_count ?? 0;
  $("#evbar").style.width = Math.min(100, (state.evidence_count ?? 0) * 10) + "%";
  $("#lscore").textContent = (state.learning_score ?? 0).toFixed(0) + "%";
  $("#lscorebar").style.width = (state.learning_score ?? 0) + "%";
  renderConcepts();
  if (parseHash().name === "dashboard") renderDashboard();
}

function renderConcepts() {
  const box = $("#conceptList");
  if (!box) return;
  box.innerHTML = "";
  (course.concepts || []).forEach(c => {
    const el = document.createElement("div");
    el.className = "file-item";
    el.style.marginTop = "8px";
    el.innerHTML =
      `<div class="fi">◈</div>` +
      `<div class="fm"><b>${esc(c.title)}</b><small>${esc(c.definition)}</small></div>`;
    box.appendChild(el);
  });
}

function renderRoadmap() {
  const box = $("#timeline");
  if (!box) return;
  const steps = [
    ["01", "Fundamentos", "Contenido y vocabulario base del curso."],
    ["02", "Activos y valoración", "Componente formativo 1 · AA1."],
    ["03", "Amenazas y riesgo", "Mapa de amenazas y matriz de riesgo."],
    ["04", "Evidencias", "Demostrar lo comprendido y avanzar."]
  ];
  box.innerHTML = "";
  steps.forEach(([n, t, d]) => {
    const el = document.createElement("div");
    el.className = "file-item";
    el.style.marginTop = "8px";
    el.innerHTML =
      `<div class="fi" style="color:var(--gold2)">${n}</div>` +
      `<div class="fm"><b>${esc(t)}</b><small>${esc(d)}</small></div>`;
    box.appendChild(el);
  });
}

function renderDashboard() {
  initMediumVideo();
}

/* Shared session video (top-level course.videos) */
function initMediumVideo() {
  const vids = course.videos || [];
  const video = $("#player");
  if (!video || !vids.length) return;
  const first = vids[0];
  const src = mediaUrl(first.file);
  if (video.dataset.src === src) return;
  video.dataset.src = src;
  video.src = src;
  getJSON("/api/progress/" + first.id).then(d => {
    video.onloadedmetadata = () => {
      if (d.position > 5 && d.position < video.duration - 3) video.currentTime = d.position;
    };
  }).catch(() => {});
  video.ontimeupdate = () => {
    if (!video.duration) return;
    const n = Math.round(video.currentTime / video.duration * 100);
    $("#videoBar").style.width = n + "%";
    $("#videoState").textContent = n >= 95 ? "✅ COMPLETADO · evidencia observada" :
      "▶ " + n + "% · en progreso";
    saveVideo(first.id, video, (force) => {
      if (sharedVideoTimer) { clearTimeout(sharedVideoTimer); }
      sharedVideoTimer = setTimeout(() => force(), force ? 0 : 4000);
    });
  };
  video.onpause = () => saveVideo(first.id, video, f => f());
  video.onended = () => saveVideo(first.id, video, f => f());
}

async function saveVideo(id, video, schedule) {
  if (!video.duration) return;
  schedule(async () => {
    const completed = video.currentTime / video.duration >= 0.95 ? 1 : 0;
    try {
      await getJSON("/api/progress/" + id, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ position: video.currentTime, duration: video.duration, completed })
      });
    } catch (_) {}
  });
}

/* ---------------- ACTIVIDADES ---------------- */
async function renderActivities() {
  const list = await getJSON("/api/activities");
  $("#actCount").textContent = list.filter(a => a.completed).length + "/" + list.length + " COMPLETADAS";
  const box = $("#activityList");
  box.innerHTML = "";
  list.forEach(a => {
    const el = document.createElement("div");
    el.className = "activity-row" + (a.completed ? " done" : "");
    el.innerHTML =
      `<div class="st">${a.completed ? "✅" : "📋"}</div>` +
      `<div class="meta"><b>${esc(a.title)}</b>` +
      `<small>${a.due ? "cierre " + a.due : ""} · ${a.evidence_count} evidencias</small></div>` +
      `<span class="status-chip ${a.completed ? "on" : "off"}">${a.completed ? "ENTREGADA" : "PENDIENTE"}</span>` +
      `<span class="go">abrir →</span>`;
    el.addEventListener("click", () => { location.hash = "#/actividad/" + a.id; });
    box.appendChild(el);
  });
}

/* ---------------- ACTIVIDAD DETALLE ---------------- */
async function renderActivity(activityId) {
  if (!activityId) { location.hash = "#/actividades"; return; }
  currentActivity = await getJSON("/api/activity/" + activityId);

  $("#actTitle").textContent = currentActivity.title;
  $("#actDue").textContent = currentActivity.due ? "Cierre: " + currentActivity.due : "";
  $("#actBrief").textContent = currentActivity.brief || "";
  $("#actDeliverable").textContent = currentActivity.deliverable || "";

  const chip = $("#actStatusChip");
  chip.innerHTML = `<span class="status-chip ${currentActivity.completed ? "on" : "off"}">` +
    `${currentActivity.completed ? "✅ ENTREGADA" : "⏳ PENDIENTE"}</span>`;

  renderMaterials(currentActivity);
  renderEvidenceFiles();

  initActivityVideo(currentActivity);
}

function renderMaterials(activity) {
  const box = $("#actMaterials");
  box.innerHTML = "";
  const mats = (activity.materials || []).filter(m => m && m.name);
  if (!mats.length) {
    box.innerHTML = `<div class="hint">Sesión sincrónica ${esc(activity.id.toUpperCase())} guardada en <code>media/videos/</code>.<br>` +
      `Puedes añadir guías y material propio en <code>media/materials/</code>.</div>`;
    return;
  }
  mats.forEach(m => {
    const el = document.createElement("div");
    el.className = "file-item";
    el.innerHTML = `<div class="fi">📚</div>` +
      `<div class="fm"><b>${esc(m.name)}</b></div>` +
      `<a href="${esc(m.file)}" target="_blank">abrir →</a>`;
    box.appendChild(el);
  });
}

function renderEvidenceFiles() {
  const list = $("#evList");
  list.innerHTML = "";
  (currentActivity.evidence_files || []).forEach(f => {
    const el = document.createElement("div");
    el.className = "file-item";
    el.innerHTML = `<div class="fi">${fileType(f.name).split(" ")[0]}</div>` +
      `<div class="fm"><b>${esc(f.name)}</b><small>${fmtSize(f.size)}</small></div>` +
      `<a href="${esc(f.url)}" target="_blank">ver →</a>`;
    list.appendChild(el);
  });
}

function initActivityVideo(activity) {
  const video = $("#actVideo");
  if (!video) return;
  const src = mediaUrl(activity.video || "Und_Bien.mp4");
  video.src = src;
  const id = "video:" + activity.id;

  getJSON("/api/progress/" + id).then(d => {
    video.onloadedmetadata = () => {
      if (d.position > 5 && d.position < video.duration - 3) video.currentTime = d.position;
      $("#actVideoState").textContent = d.completed ? "✅ evidencia observada" : "▶ reproduciendo sesión";
    };
  }).catch(() => {});

  video.ontimeupdate = () => {
    if (!video.duration) return;
    const n = Math.round(video.currentTime / video.duration * 100);
    $("#actVideoBar").style.width = n + "%";
    $("#actVideoState").textContent = n >= 95 ? "✅ SESIÓN COMPLETADA · evidencia observada" :
      "▶ " + n + "% · en progreso";
    saveActivityVideo(id, video);
  };
}

function saveActivityVideo(id, video) {
  if (!video.duration) return;
  if (actVideoTimer) { clearTimeout(actVideoTimer); }
  actVideoTimer = setTimeout(async () => {
    const completed = video.currentTime / video.duration >= 0.95 ? 1 : 0;
    try {
      await getJSON("/api/progress/" + id, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ position: video.currentTime, duration: video.duration, completed })
      });
    } catch (_) {}
  }, 4000);
}

/* ---------------- EVIDENCIA: SUBIDA ---------------- */
function initDropzone() {
  const zone = $("#dropZone");
  const input = $("#evFile");
  if (!zone) return;
  zone.addEventListener("click", () => input.click());
  zone.addEventListener("dragover", e => { e.preventDefault(); zone.classList.add("over"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("over"));
  zone.addEventListener("drop", e => {
    e.preventDefault(); zone.classList.remove("over");
    if (e.dataTransfer.files.length) uploadEvidence(e.dataTransfer.files[0]);
  });
  input.addEventListener("change", () => {
    if (input.files.length) uploadEvidence(input.files[0]);
    input.value = "";
  });
}

async function uploadEvidence(file) {
  const msg = $("#evMsg");
  msg.textContent = "Subiendo " + esc(file.name) + "…";
  const form = new FormData();
  form.append("file", file);
  try {
    const r = await fetch("/api/evidence/" + currentActivity.id, { method: "POST", body: form });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || "Error al subir");
    msg.textContent = "✅ " + data.evidence_id + " · evidencia registrada";
    currentActivity = await getJSON("/api/activity/" + currentActivity.id);
    renderEvidenceFiles();
    const chip = $("#actStatusChip");
    chip.innerHTML = `<span class="status-chip on">✅ ENTREGADA</span>`;
    refresh();
  } catch (e) {
    msg.textContent = "⚠️ " + esc(e.message);
  }
}

/* ---------------- CONOCIMIENTO ---------------- */
async function renderKnowledge() {
  const box = $("#conceptFullList");
  if (!box) return;
  box.innerHTML = "";
  (course.concepts || []).forEach(c => {
    const el = document.createElement("article");
    el.className = "concept";
    el.innerHTML = `<strong>◈ ${esc(c.title)}</strong><p>${esc(c.definition)}</p>`;
    box.appendChild(el);
  });
}

/* ---------------- REGLAS ---------------- */
async function renderRules() {
  const data = await getJSON("/api/rules");

  const grading = $("#gradingList");
  grading.innerHTML = "";
  const g = data.grading || {};
  const gcard = document.createElement("div");
  gcard.className = "concept";
  const rows = Object.entries(g.weights || {}).map(([k, w]) =>
    `<div class="grad-row"><span>${esc(String(k).toUpperCase())}</span><b>${((w || 0) * 100).toFixed(0)}%</b></div>`).join("");
  const comps = (g.components || {});
  const compStr = Object.keys(comps).filter(c => comps[c].enabled).map(c => esc(c)).join(" · ");
  gcard.innerHTML =
    `<strong>⚙ Pesos del curso: ${esc((data.course || {}).title || (data.course || {}).id || "curso")}</strong>` +
    `<div class="grad-sums">${rows}</div>` +
    `<p>${esc(g.formula || "")}</p>` +
    `<p style="color:#8aa8ba">Componentes activos: ${compStr}<br>Motores: ${(g.engines || []).join(" · ")}</p>` +
    `<p style="color:#c8d8e2">Nadie califica "a mano": VIDA aplica estas reglas a los <b>hechos</b> que usted sube (evidencias, reproducción de sesiones, verificación de conceptos).</p>`;
  grading.appendChild(gcard);

  const prin = $("#principlesList");
  prin.innerHTML = "";
  (data.principles || []).forEach(p => {
    const el = document.createElement("div");
    el.className = "file-item";
    el.innerHTML = `<div class="fi" style="color:var(--gold2)">⚖</div>` +
      `<div class="fm"><b style="font-size:12px;color:var(--text)">${esc(p.replace(/_/g, " ").toLowerCase())}</b></div>`;
    prin.appendChild(el);
  });

  const labs = {
    operational_100: ["Progreso operativo al 100%", "operational"],
    mastery_100: ["Dominio verificado al 100%", "mastery"],
    evidence_present: ["Existe evidencia registrada", "evidence_count"],
    videos_complete: ["Todos los videos requeridos completos", "completed_videos/required_videos"],
    activities_complete: ["Todas las actividades requeridas completas", "completed_activities/required_activities"],
    concepts_verified: ["Todos los conceptos verificados", "verified_concepts/required_concepts"],
    no_unknown_required: ["Ninguna carencia sin demostrar", "unknown_count"],
    user_confirmation: ["Confirmación del aprendiz", "código de integridad"]
  };
  const elig = $("#eligibilityList");
  elig.innerHTML = "";
  const checks = data.eligibility || {};
  Object.keys(checks.checks || {}).forEach(key => {
    const ok = checks.checks[key];
    const [label, ref] = labs[key] || [key.replace(/_/g, " "), ""];
    const el = document.createElement("div");
    el.className = "file-item";
    el.style.marginTop = "8px";
    el.innerHTML =
      `<div class="fi">${ok ? "✅" : "⭕"}</div>` +
      `<div class="fm"><b style="font-size:13px">${esc(label)}</b>` +
      `<small>${esc(ref)}</small></div>` +
      `<span class="status-chip ${ok ? "on" : "off"}">${ok ? "CUMPLE" : "PENDIENTE"}</span>`;
    elig.appendChild(el);
  });
  const allOk = checks.eligible;
  const footer = document.createElement("div");
  footer.style.cssText = "margin-top:14px;padding:14px 16px;border-radius:12px;font-size:13px;border:1px solid " +
    (allOk ? "rgba(71,224,183,.4)" : "rgba(247,198,90,.4)") + ";color:" + (allOk ? "var(--green)" : "var(--warn)");
  footer.textContent = allOk
    ? "✔ Todas las condiciones se cumplen · el motor puede emitir el certificado."
    : "⏳ Aún hay condiciones pendientes · VIDA es honesto: no emite sin demostración.";
  elig.appendChild(footer);

  const rules = $("#rulesList");
  rules.innerHTML = "";
  const dataRules = [].concat(data.rules ? data.rules : []);
  if (dataRules.length === 0) {
    dataRules.push({ id: "R-001", name: "Video completion", condition: "playback >= 95%", result: "VERIFIED_VIDEO" });
    dataRules.push({ id: "R-002", name: "Mastery", condition: "explicit verification evidence", result: "VERIFIED_MASTERY" });
    dataRules.push({ id: "R-003", name: "Unknown", condition: "required evidence missing", result: "UNKNOWN" });
    dataRules.push({ id: "R-004", name: "Certificate", condition: "all certificate policy conditions satisfied", result: "ISSUE_ONCE" });
  }
  dataRules.forEach(r => {
    const el = document.createElement("article");
    el.className = "concept";
    el.innerHTML = `<strong>${esc(r.id)} · ${esc(r.name)}</strong>` +
      `<p>Si: ${esc(r.condition)} → <b style="color:var(--gold2)">${esc(r.result)}</b></p>`;
    rules.appendChild(el);
  });
}

/* ---------------- EVIDENCIAS ---------------- */
async function renderEvidence() {
  const groups = await getJSON("/api/evidence");
  const box = $("#evidenceGroups");
  box.innerHTML = "";
  groups.forEach(g => {
    const total = g.records.length;
    const el = document.createElement("div");
    el.className = "ev-group";
    el.innerHTML = `<h3>${total ? "✅" : "○"} ${esc(g.title)} <span>${total} registro${total === 1 ? "" : "s"}</span></h3>`;
    if (!g.files.length) {
      el.innerHTML += `<div class="ev-empty">Sin archivos subidos todavía.</div>`;
    } else {
      g.files.forEach(f => {
        const r = g.records.find(x => (x.context || {}).file === f.name);
        el.innerHTML += `<div class="file-item"><div class="fi">${fileType(f.name).split(" ")[0]}</div>` +
          `<div class="fm"><b>${esc(f.name)}</b><small>${fmtSize(f.size)}${r ? " · " + esc(r.evidence_id) : ""}</small></div>` +
          `<a href="${esc(f.url)}" target="_blank">ver →</a></div>`;
      });
    }
    box.appendChild(el);
  });
}

/* ---------------- INIT ---------------- */
document.addEventListener("DOMContentLoaded", () => {
  $("#sync").addEventListener("click", refresh);
  $("#actBack").addEventListener("click", () => { location.hash = "#/actividades"; });
  const vb = $("#voiceBtn");
  if (vb) vb.addEventListener("click", () => {
    voiceOn = !voiceOn;
    setVoiceBtn();
    if (voiceOn) speak(GUIDES[parseHash().name] || GUIDES.dashboard);
  });
  const cs = $("#courseSel");
  if (cs) cs.addEventListener("change", () => {
    if (!cs.value) return;
    if (cs.value === cs.dataset.last) return;
    activateCourse(cs.value);
  });
  setVoiceBtn();
  initDropzone();
  load();
  setInterval(() => { if (document.visibilityState === "visible") refresh(); }, 20000);
});