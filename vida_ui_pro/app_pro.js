const $ = s => document.querySelector(s);
const $$ = s => document.querySelectorAll(s);

let course = null;
let state = null;
let currentActivity = null;
let actVideoTimer = null;
let sharedVideoTimer = null;
let videosMeta = null;
let identity = null;

/* ---------------- IDENTIDAD ---------------- */
async function loadIdentity() {
  try {
    const data = await getJSON("/api/me");
    identity = data.user || null;
    renderIdentity();
  } catch (err) {
    console.error("No se pudo cargar la identidad:", err);
  }
}

function renderIdentity() {
  const box = $("#identityBox");
  const icon = $("#identityIcon");
  const name = $("#identityName");
  const kind = $("#identityKind");
  const action = $("#identityAction");

  if (!box || !identity) return;

  const guest = identity.kind === "guest";

  icon.textContent = guest ? "👋" : "🔐";
  name.textContent = identity.display_name || identity.username || "Usuario";
  kind.textContent = guest
    ? "Explorador de VIDA"
    : "Aprendiz · Progreso guardado";

  action.hidden = false;
  action.textContent = guest ? "CREAR CUENTA" : "CERRAR SESIÓN";

  action.onclick = guest ? registerIdentity : logoutIdentity;

  box.title = guest
    ? "El progreso del invitado es temporal. Crea una cuenta para conservarlo."
    : "Sesión de usuario persistente.";
}

async function registerIdentity() {
  const username = prompt("Nombre de usuario:");
  if (!username) return;

  const displayName = prompt("Nombre para mostrar:");
  if (!displayName) return;

  const password = prompt("Contraseña (mínimo 8 caracteres):");
  if (!password) return;

  try {
    const data = await getJSON("/api/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username,
        display_name: displayName,
        password
      })
    });

    identity = {
      user_id: data.user_id,
      username: data.username,
      display_name: data.display_name,
      kind: data.kind
    };

    renderIdentity();

    await load();

    refresh();

    alert("✅ Cuenta creada. Tu progreso se conservó.");
  } catch (err) {
    alert("❌ No se pudo crear la cuenta: " + err.message);
  }
}

async function logoutIdentity() {
  try {
    await getJSON("/api/logout", {
      method: "POST"
    });

    identity = null;

    await loadIdentity();
    await load();
    refresh();

    alert("👤 Sesión cerrada. Ahora estás como invitado.");
  } catch (err) {
    alert("❌ No se pudo cerrar sesión: " + err.message);
  }
}

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
function animNum(el, to, suffix = "", decimals = 0) {
  if (!el) return;
  const start = performance.now();
  const dur = 750;
  function tick(now) {
    const k = Math.min(1, (now - start) / dur);
    const eased = 1 - Math.pow(1 - k, 3);
    el.textContent = (to * eased).toFixed(decimals) + suffix;
    if (k < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
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

/* ---------------- GUÍA POR VOZ · PIPER ---------------- */
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

const VIDA_VOICE_ENGINE = "Piper";
const VIDA_VOICE_MODEL = "es_ES-sharvard-medium";

let vidaAudio = null;

function limpiaVoz(text) {
  return String(text || "")
    .replace(/https?:\/\/\S+/g, "")
    .replace(/[|*_=<>`#]/g, " ")
    .replace(/\b(ONLINE|ENGINE|DASHBOARD|KNOWLEDGE|MEDIA|EVIDENCE|INTEL)\b/gi, " ")
    .replace(/[^\w\s.,;:áéíóúÁÉÍÓÚñÑ¿?¡!()'"-]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function troceaVoz(text, max = 180) {
  const limpio = limpiaVoz(text);
  if (!limpio) return [];

  const frases = limpio
    .match(/[^.!?;:]+[.!?;:]?/g)
    ?.map(x => x.trim())
    .filter(Boolean) || [];

  const resultado = [];

  for (const frase of frases) {
    if (frase.length <= max) {
      resultado.push(frase);
      continue;
    }

    const palabras = frase.split(/\s+/);
    let actual = "";

    for (const palabra of palabras) {
      const candidato = actual
        ? `${actual} ${palabra}`
        : palabra;

      if (candidato.length > max && actual) {
        resultado.push(actual);
        actual = palabra;
      } else {
        actual = candidato;
      }
    }

    if (actual) resultado.push(actual);
  }

  return resultado;
}

function detenerVoz() {
  if (vidaAudio) {
    try {
      vidaAudio.pause();
      vidaAudio.currentTime = 0;
    } catch (_) {}
    vidaAudio = null;
  }
}

async function reproducirPiper(text) {
  const response = await fetch("/api/voice", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ text })
  });

  if (!response.ok) {
    let message = "No se pudo generar la voz de VIDA.";
    try {
      const data = await response.json();
      if (data.error) message = data.error;
    } catch (_) {}
    throw new Error(message);
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);

  const audio = new Audio(url);
  vidaAudio = audio;

  audio.volume = 1.0;

  audio.onended = () => {
    URL.revokeObjectURL(url);
    if (vidaAudio === audio) vidaAudio = null;
  };

  audio.onerror = () => {
    URL.revokeObjectURL(url);
    if (vidaAudio === audio) vidaAudio = null;
  };

  await audio.play();
}

async function speak(text) {
  if (!text || !voiceOn) return;

  try {
    detenerVoz();

    const limpio = limpiaVoz(text);
    if (!limpio) return;

    await reproducirPiper(limpio);
  } catch (err) {
    console.error(
      `[VIDA VOICE] ${VIDA_VOICE_ENGINE}/${VIDA_VOICE_MODEL}:`,
      err
    );
  }
}

function setVoiceBtn() {
  const b = $("#voiceBtn");
  if (b) {
    b.textContent = voiceOn ? "🔊" : "🔇";
    b.title = voiceOn
      ? "Guía por voz · Piper · VIDA Local"
      : "Guía por voz desactivada";
  }

  try {
    localStorage.setItem(
      VOICE_KEY,
      voiceOn ? "on" : "off"
    );
  } catch (_) {}
}

/* ---------------- MEDIA: AVAILABILITY ---------------- */
async function loadVideosMeta() {
  try { videosMeta = await getJSON("/api/videos"); }
  catch (_) { videosMeta = { videos: [] }; }
  return videosMeta;
}
function videoById(id) {
  return ((videosMeta || {}).videos || []).find(v => v.id === id) || null;
}
function setVideoState(el, text, warn) {
  if (!el) return;
  el.textContent = text;
  el.classList.toggle("warn", !!warn);
}
function showOverlay(overlay, show) {
  if (!overlay) return;
  overlay.hidden = !show;
}
function markVideoMissing(video, overlay, id) {
  const meta = videoById(id);
  if (meta == null) return true; // sin metadata conocida: no bloqueamos la reproducción
  const missing = meta.available !== true;
  showOverlay(overlay, missing);
  if (missing) video.removeAttribute("src");
  video.classList.toggle("offline", missing);
  return !missing;
}
function bindVideoFallback(video, overlay, id, stateEl, okText) {
  if (!video) return;
  video.onerror = () => {
    showOverlay(overlay, true);
    video.classList.add("offline");
    setVideoState(stateEl, "⛔ El recurso no se encontró en el servidor", true);
  };
  video.onloadedmetadata = () => {
    video.classList.remove("offline");
  };
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

  // Detener cualquier reproducción al cambiar de página.
  $$("video").forEach(v => {
    try {
      v.pause();
      v.currentTime = v.currentTime;
    } catch (_) {}
  });

  if (actVideoTimer) {
    clearInterval(actVideoTimer);
    actVideoTimer = null;
  }

  if (sharedVideoTimer) {
    clearInterval(sharedVideoTimer);
    sharedVideoTimer = null;
  }

  $$(".view").forEach(v => v.classList.remove("active"));

  // El HTML usa view-activity, mientras la ruta pública es /actividad/AA1.
  const viewName = name === "actividad" ? "activity" : name;
  const view = $("#view-" + viewName) || $("#view-dashboard");
  view.classList.add("active");

  $$("aside a.nav").forEach(a => {
    const active = a.dataset.nav === name ||
      (name === "actividad" && a.dataset.nav === "actividades");
    a.classList.toggle("active", active);
  });

  const fn = routes[name === "actividad" && arg ? "actividad" : name] || renderDashboard;
  fn(arg);

  if (voiceOn) {
    setTimeout(() => speak(GUIDES[name] || GUIDES.dashboard), 500);
  }
}

window.addEventListener("hashchange", router);

/* ---------------- BOOT ---------------- */
async function load() {
  course = await getJSON("/api/course");
  $("#heroTitle").textContent = course.title;
  const i = $("#chipInst"); if (i) i.textContent = "🏛 " + (course.provider || "") + " · " + (course.platform || "");
  const h = $("#chipHours"); if (h) h.textContent = "⏱ " + (course.hours || 0) + " horas";
  document.title = "VIDA · " + (course.title || "");
  await loadVideosMeta();
  await loadCourses();
  await renderRoadmap();
  await refresh();
  router();
}

/* ---------------- DASHBOARD ---------------- */
async function refresh() {
  state = await getJSON("/api/dashboard");
  animNum($("#overall"), state.overall ?? 0, "%");
  $("#overallbar").style.width = (state.overall ?? 0) + "%";
  animNum($("#mastery"), state.mastery ?? 0, "%");
  $("#masterybar").style.width = (state.mastery ?? 0) + "%";
  animNum($("#evidence"), state.evidence_count ?? 0);
  $("#evbar").style.width = Math.min(100, (state.evidence_count ?? 0) * 10) + "%";
  animNum($("#lscore"), state.learning_score ?? 0, "%", 0);
  $("#lscorebar").style.width = (state.learning_score ?? 0) + "%";
  renderComponents(state);
  const sm = $("#studyMinutes");
  if (sm) sm.textContent = (state.study_minutes ?? 0) + " MIN";
  renderConcepts();
  if (parseHash().name === "dashboard") {
    renderDashboard();
    renderSignals(state);
    renderNextActions(state);
  }
}

function renderComponents(st) {
  const set = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.style.width = Math.max(0, Math.min(100, (val ?? 0) * 100)) + "%";
  };
  const setLbl = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.textContent = Math.round((val ?? 0) * 100) + "%";
  };
  const v = st.video_progress ?? 0, a = st.activity_progress ?? 0, c = st.concept_progress ?? 0;
  setLbl("compVideo", v); set("compVideoBar", v);
  setLbl("compActivity", a); set("compActivityBar", a);
  setLbl("compConcept", c); set("compConceptBar", c);
}

function renderSignals(st) {
  const box = $("#intelSignals");
  if (!box) return;
  const meta = {
    observed: { tag: "OBSERVADO", cls: "sig-observed" },
    inferred: { tag: "INFERIDO", cls: "sig-inferred" },
    predicted: { tag: "PREDICHO", cls: "sig-predicted" }
  };
  box.innerHTML = "";
  (st.signals || []).forEach(s => {
    const el = document.createElement("div");
    el.className = "sig-row";
    const m = meta[s.kind] || meta.observed;
    const pct = Math.round((s.value ?? 0) * 100);
    el.innerHTML =
      `<div class="sig-top"><b>${esc(s.name.replace(/_/g, " "))}</b>` +
      `<span class="sig-chip ${m.cls}">${m.tag}</span></div>` +
      `<div class="sig-bar"><i style="width:${pct}%"></i></div>` +
      `<small>${pct}% · <code>${esc(s.source)}</code></small>`;
    box.appendChild(el);
  });
}

function renderNextActions(st) {
  const box = $("#intelActions");
  if (!box) return;
  box.innerHTML = "";
  const acts = st.next_actions || [];
  if (!acts.length) {
    box.innerHTML = `<div class="ev-empty">🎉 Sin pasos pendientes: has demostrado todo lo requerido.</div>`;
    return;
  }
  const ico = { activity: "📝", video: "📼", concept: "◈", evidence: "📤" };
  acts.forEach((a, i) => {
    const el = document.createElement("div");
    el.className = "action-row";
    el.innerHTML =
      `<div class="ar-ico">${ico[a.type] || "▶"}</div>` +
      `<div class="ar-body"><b>${esc(a.title || a.type)}</b>` +
      `<small>${esc(a.reason || "")}</small></div>` +
      `<span class="ar-prio ${a.priority === "high" ? "hi" : "lo"}">${esc(String(a.priority || "high").toUpperCase())}</span>`;
    box.appendChild(el);
  });
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

async function renderRoadmap() {
  const box = $("#timeline");
  if (!box) return;
  const acts = (course.items || []).filter(x => x.kind === "activity");
  box.innerHTML = "";
  if (!acts.length) {
    box.innerHTML = `<div class="ev-empty">Sin actividades registradas aún.</div>`;
    return;
  }
  const actsState = await getJSON("/api/activities").catch(() => []);
  const nd = $("#nextDue");
  if (nd) {
    const closed = acts.filter(a => a.due).sort((a, b) => String(b.due).localeCompare(String(a.due)))[0];
    nd.textContent = closed
      ? "📅 curso finalizado · cierre " + closed.due
      : "📅 curso finalizado";
  }
  acts.forEach((a, i) => {
    const stA = actsState.find(x => x.id === a.id) || {};
    const el = document.createElement("div");
    el.className = "file-item";
    el.style.marginTop = "8px";
    el.style.cursor = "pointer";
    el.innerHTML =
      `<div class="fi" style="color:${stA.completed ? "var(--green)" : "var(--gold2)"}">${i + 1}</div>` +
      `<div class="fm"><b>${esc(a.title)}</b>` +
      `<small>${a.due ? "cierre " + a.due + " · " : ""}${stA.evidence_count || 0} evidencia${(stA.evidence_count || 0) === 1 ? "" : "s"}</small></div>` +
      `<span class="status-chip ${stA.completed ? "on" : "off"}">${stA.completed ? "ENTREGADA" : "PENDIENTE"}</span>`;
    el.addEventListener("click", () => { location.hash = "#/actividad/" + a.id; });
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
  const first = vids.find(video => video.id === "video_dashboard") || vids[0];
  const src = mediaUrl(first.file);
  if (video.dataset.src === src) return;
  video.dataset.src = src;

  const ok = markVideoMissing(video, $("#playerOverlay"), first.id);
  if (!ok) {
    setVideoState($("#videoState"),
      "⛔ RECURSO NO ENCONTRADO · coloca el MP4 en media/videos/", true);
    return;
  }
  bindVideoFallback(video, $("#playerOverlay"), first.id,
    $("#videoState"), "▶ reproduciendo");

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
  const details = await Promise.all(
    list.map(a => getJSON("/api/activity/" + a.id).catch(() => null))
  );
  list.forEach((a, i) => {
    const det = details[i] || {};
    const vidPct = det.video_progress && det.video_progress.duration
      ? Math.min(100, Math.round((det.video_progress.position / det.video_progress.duration) * 100))
      : 0;
    const el = document.createElement("div");
    el.className = "activity-row" + (a.completed ? " done" : "");
    el.innerHTML =
      `<div class="st">${a.completed ? "✅" : String(i + 1).padStart(2, "0")}</div>` +
      `<div class="meta"><b>${esc(a.title)}</b>` +
      `<small>${det.deliverable ? esc(det.deliverable) : ""}</small>` +
      `<small class="meta-line">${a.due ? "cierre " + a.due : "sin cierre"}` +
      ` · 📼 ${vidPct}% visto · ${a.evidence_count} evidencia${a.evidence_count === 1 ? "" : "s"}</small></div>` +
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
  const id = "video:" + activity.id;

  if (activity.video_available === false) {
    video.removeAttribute("src");
    video.classList.add("offline");
    showOverlay($("#actOverlay"), true);
    setVideoState($("#actVideoState"), "⛔ SESIÓN NO DISPONIBLE · agrega el MP4", true);
    return;
  }
  bindVideoFallback(video, $("#actOverlay"), id, $("#actVideoState"), "▶ reproduciendo");

  video.src = src;
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
  zone.addEventListener("keydown", e => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); }
  });
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

  if (!state) state = await getJSON("/api/dashboard");

  const verified = new Set(state.verified_concept_ids || []);
  const total = (course.concepts || []).length;
  const verifiedCount = (course.concepts || []).filter(c => verified.has(c.id)).length;

  const cnt = $("#conceptCount");
  if (cnt) {
    cnt.textContent = verifiedCount + "/" + total + " VERIFICADOS";
  }

  box.innerHTML = "";

  (course.concepts || []).forEach(c => {
    const ok = verified.has(c.id);
    const el = document.createElement("article");

    el.className = "concept knowledge-card" + (ok ? " verified" : "");
    el.tabIndex = 0;
    el.setAttribute("role", "button");
    el.setAttribute("aria-label", "Abrir concepto " + c.title);

    const extras = [];

    if (Array.isArray(c.examples) && c.examples.length) {
      extras.push(`<div class="knowledge-mini"><b>Ejemplos:</b> ${c.examples.slice(0, 3).map(esc).join(" · ")}</div>`);
    }

    if (Array.isArray(c.controls) && c.controls.length) {
      extras.push(`<div class="knowledge-mini"><b>Controles:</b> ${c.controls.slice(0, 3).map(esc).join(" · ")}</div>`);
    }

    if (c.formula) {
      extras.push(`<div class="knowledge-formula">${esc(c.formula)}</div>`);
    }

    el.innerHTML =
      `<div class="concept-head">` +
        `<strong>◈ ${esc(c.title)}</strong>` +
        `<span class="status-chip ${ok ? "on" : "off"}">${ok ? "VERIFICADO" : "PENDIENTE"}</span>` +
      `</div>` +
      `<p>${esc(c.definition || "")}</p>` +
      (c.content ? `<p class="concept-det">${esc(c.content)}</p>` : "") +
      extras.join("") +
      `<div class="knowledge-open">ABRIR CONCEPTO →</div>`;

    el.addEventListener("click", () => openConcept(c.id));
    el.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openConcept(c.id);
      }
    });

    box.appendChild(el);
  });
}

function conceptById(id) {
  return (course.concepts || []).find(c => String(c.id) === String(id)) || null;
}

function closeConcept() {
  const modal = $("#conceptModal");
  if (!modal) return;

  modal.hidden = true;
  document.body.classList.remove("concept-modal-open");
}

function renderConceptModal(concept) {
  const modal = $("#conceptModal");
  if (!modal || !concept) return;

  const verified = new Set((state && state.verified_concept_ids) || []);
  const isVerified = verified.has(concept.id);

  const examples = Array.isArray(concept.examples)
    ? `<section class="knowledge-section">
         <h3>Ejemplos</h3>
         <ul>${concept.examples.map(x => `<li>${esc(x)}</li>`).join("")}</ul>
       </section>`
    : "";

  const controls = Array.isArray(concept.controls)
    ? `<section class="knowledge-section">
         <h3>Controles relacionados</h3>
         <ul>${concept.controls.map(x => `<li>${esc(x)}</li>`).join("")}</ul>
       </section>`
    : "";

  const questions = Array.isArray(concept.questions)
    ? `<section class="knowledge-section">
         <h3>Preguntas para estudiar</h3>
         <ul>${concept.questions.map(x => `<li>${esc(x)}</li>`).join("")}</ul>
       </section>`
    : "";

  const options = Array.isArray(concept.options)
    ? `<section class="knowledge-section">
         <h3>Opciones de tratamiento</h3>
         <div class="knowledge-tags">${concept.options.map(x => `<span>${esc(x)}</span>`).join("")}</div>
       </section>`
    : "";

  const workflow = Array.isArray(concept.workflow)
    ? `<section class="knowledge-section">
         <h3>Proceso</h3>
         <ol>${concept.workflow.map(x => `<li>${esc(x)}</li>`).join("")}</ol>
       </section>`
    : "";

  const chain = Array.isArray(concept.chain)
    ? `<section class="knowledge-section">
         <h3>Cadena conceptual</h3>
         <div class="knowledge-chain">${concept.chain.map(x => `<span>${esc(x)}</span>`).join("<b>→</b>")}</div>
       </section>`
    : "";

  const formula = concept.formula
    ? `<div class="knowledge-formula knowledge-formula-big">${esc(concept.formula)}</div>`
    : "";

  modal.innerHTML = `
    <div class="concept-modal-backdrop" data-concept-close></div>
    <div class="concept-modal-panel" role="dialog" aria-modal="true" aria-labelledby="conceptModalTitle">
      <header class="concept-modal-header">
        <div>
          <small>KNOWLEDGE ENGINE · CONCEPTO</small>
          <h2 id="conceptModalTitle">◈ ${esc(concept.title)}</h2>
        </div>
        <button class="concept-close" type="button" id="conceptClose" aria-label="Cerrar">×</button>
      </header>

      <div class="concept-modal-body">
        <div class="concept-modal-status ${isVerified ? "verified" : ""}">
          <span>${isVerified ? "✓ CONCEPTO VERIFICADO" : "○ CONCEPTO PENDIENTE"}</span>
        </div>

        <section class="knowledge-section">
          <h3>Definición</h3>
          <p>${esc(concept.definition || "")}</p>
        </section>

        ${concept.content ? `
          <section class="knowledge-section">
            <h3>Contenido</h3>
            <p>${esc(concept.content)}</p>
          </section>` : ""}

        ${formula}
        ${chain}
        ${examples}
        ${controls}
        ${questions}
        ${options}
        ${workflow}

        ${Array.isArray(concept.cycle) ? `
          <section class="knowledge-section">
            <h3>Ciclo</h3>
            <div class="knowledge-chain">${concept.cycle.map(x => `<span>${esc(x)}</span>`).join("<b>→</b>")}</div>
          </section>` : ""}

        ${Array.isArray(concept.related_activities) ? `
          <section class="knowledge-section">
            <h3>Actividades relacionadas</h3>
            <div class="knowledge-tags">${concept.related_activities.map(x => `<span>${esc(x.toUpperCase())}</span>`).join("")}</div>
          </section>` : ""}

        <div class="concept-modal-message" id="conceptModalMessage"></div>
      </div>

      <footer class="concept-modal-footer">
        ${
          isVerified
          ? `<span class="concept-done">✓ Este concepto ya está verificado.</span>`
          : `
            <button class="btn-secondary" type="button" id="conceptStudyBtn">
              📖 REGISTRAR ESTUDIO
            </button>
            <button class="btn-primary" type="button" id="conceptVerifyBtn" disabled>
              ✓ VERIFICAR CONCEPTO
            </button>
          `
        }
      </footer>
    </div>
  `;

  modal.hidden = false;
  document.body.classList.add("concept-modal-open");

  const close = $("#conceptClose");
  if (close) close.addEventListener("click", closeConcept);

  const backdrop = modal.querySelector("[data-concept-close]");
  if (backdrop) backdrop.addEventListener("click", closeConcept);

  const studyBtn = $("#conceptStudyBtn");
  const verifyBtn = $("#conceptVerifyBtn");
  const message = $("#conceptModalMessage");

  if (studyBtn && verifyBtn) {
    studyBtn.addEventListener("click", async () => {
      studyBtn.disabled = true;
      studyBtn.textContent = "REGISTRANDO ESTUDIO…";

      try {
        const response = await fetch(
          "/api/concept/" + encodeURIComponent(concept.id) + "/study",
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ minutes: 1 })
          }
        );

        const data = await response.json();

        if (!response.ok) {
          throw new Error(data.error || "No se pudo registrar el estudio.");
        }

        message.textContent =
          "✓ Estudio registrado. Ahora puedes verificar este concepto.";

        verifyBtn.disabled = false;
        studyBtn.textContent = "✓ ESTUDIO REGISTRADO";
      } catch (error) {
        message.textContent = "⚠ " + esc(error.message);
        studyBtn.disabled = false;
        studyBtn.textContent = "📖 REGISTRAR ESTUDIO";
      }
    });

    verifyBtn.addEventListener("click", async () => {
      verifyBtn.disabled = true;
      verifyBtn.textContent = "VERIFICANDO…";

      try {
        const response = await fetch(
          "/api/concept/" + encodeURIComponent(concept.id) + "/verify",
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({})
          }
        );

        const data = await response.json();

        if (!response.ok) {
          throw new Error(data.error || "No se pudo verificar el concepto.");
        }

        message.textContent =
          "✓ Concepto verificado. Actualizando Mastery…";

        state = await getJSON("/api/dashboard");
        await renderKnowledge();
        renderConceptModal(concept);
        refresh();
      } catch (error) {
        message.textContent = "⚠ " + esc(error.message);
        verifyBtn.disabled = false;
        verifyBtn.textContent = "✓ VERIFICAR CONCEPTO";
      }
    });
  }
}

function openConcept(conceptId) {
  const concept = conceptById(conceptId);
  if (!concept) return;
  renderConceptModal(concept);
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
  const comps = g.components || [];
  const compNames = Array.isArray(comps)
    ? comps
    : Object.keys(comps).filter(c => comps[c] && comps[c].enabled);
  const compStr = compNames.map(c => esc(c)).join(" · ");
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
function tickClock() {
  const el = $("#liveClock");
  if (!el) return;
  const d = new Date();
  const p = n => String(n).padStart(2, "0");
  const days = ["DOM", "LUN", "MAR", "MIÉ", "JUE", "VIE", "SÁB"];
  el.textContent = `${days[d.getDay()]} ${p(d.getDate())}.${p(d.getMonth() + 1)} · ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}
document.addEventListener("DOMContentLoaded", () => {
  console.log("[VIDA] DOMContentLoaded");

  const sync = $("#sync");
  if (sync) {
    sync.addEventListener("click", async () => {
      try {
        await loadVideosMeta();
        await refresh();
      } catch (err) {
        console.error("[VIDA] Error en sincronización:", err);
      }
    });
  }

  const actBack = $("#actBack");
  if (actBack) {
    actBack.addEventListener("click", () => {
      location.hash = "#/actividades";
    });
  }

  const vb = $("#voiceBtn");
  if (vb) {
    vb.addEventListener("click", () => {
      voiceOn = !voiceOn;
      setVoiceBtn();
      if (voiceOn) speak(GUIDES[parseHash().name] || GUIDES.dashboard);
    });
  }

  const cs = $("#courseSel");
  if (cs) {
    cs.addEventListener("change", () => {
      if (!cs.value) return;
      if (cs.value === cs.dataset.last) return;
      activateCourse(cs.value);
    });
  }

  try {
    setVoiceBtn();
  } catch (err) {
    console.error("[VIDA] Error setVoiceBtn:", err);
  }

  try {
    initDropzone();
  } catch (err) {
    console.error("[VIDA] Error initDropzone:", err);
  }

  tickClock();
  setInterval(tickClock, 1000);

  loadIdentity().catch(err => {
    console.error("[VIDA] Error loadIdentity:", err);
  });

  load().then(() => {
    console.log("[VIDA] LOAD OK");
  }).catch(err => {
    console.error("[VIDA] LOAD ERROR:", err);
  });

  setInterval(() => {
    if (document.visibilityState === "visible") {
      refresh().catch(err => {
        console.error("[VIDA] REFRESH ERROR:", err);
      });
    }
  }, 20000);
});