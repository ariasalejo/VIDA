const $ = s => document.querySelector(s);
const $$ = s => document.querySelectorAll(s);

let course = null;
let state = null;
let currentActivity = null;
let actVideoTimer = null;
let sharedVideoTimer = null;
let videosMeta = null;
let AUTH = { authed: false, guest: false, user: null, slug: "" };

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
function fmtStamp(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return String(iso);
  const p = n => String(n).padStart(2, "0");
  return `${p(d.getDate())}.${p(d.getMonth() + 1)}.${d.getFullYear()} · ${p(d.getHours())}:${p(d.getMinutes())}`;
}
const EV_ICON = {
  ACTIVITY_COMPLETE: "📤", VIDEO_COMPLETE: "📼", CONCEPT_VERIFY: "◈", EVIDENCE_UPLOAD: "📎"
};
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
  dashboard: "Este es tu centro de mando VIDA. Aquí revisas el progreso operativo, el dominio, las evidencias, el puntaje de aprendizaje, el estado de tu certificado y el pódcast de estudio del curso activo.",
  actividades: "Esta es tu ruta de aprendizaje. Cada actividad tiene video de la sesión, material y una zona para subir tu entrega.",
  actividad: "Página de actividad. Mira el objetivo, reproduce la sesión y sube tu entrega como evidencia.",
  conocimiento: "Estos son los conceptos del curso. El dominio se verifica con evidencia; VIDA no asume que ya lo sabes.",
  evidencias: "Centro de evidencias. Es tu expediente verificable en vivo: VIDA solo registra lo que observa, nunca inventa evidencia. Puedes filtrar por entregas, sesiones, conceptos o archivos.",
  reglas: "Reglas del motor. Aquí puedes ver quién califica, con qué pesos y bajo qué condiciones se emite el certificado."
};
const VOZ_FEMENINA = /laura|helena|sabina|paulina|m[oó]nica|camila|marisol|luci|ximena|valentina|isabella|sof[aí]a|elena|paloma|palmira|samantha|karina|nuria|silvia|beatriz|marta|olga|andrea|daniela|mar[íi]a|google español|google espa|milena|alicia|emma|selma|rosa|tessa|linda|allison/i;
const VOZ_MASCULINA = /jorge|pedro|carlos|lucas|pablo|diego|david|miguel|juan|javier|antonio|raul|ram[oó]n|alberto|fernando|andres|andr[eé]s|thomas|alex|male|masculino|hombre/i;
const VOZ_NATURAL = /natural|neural|enhanced|premium|online|google|espa[nñ]a.*mujer|mujer|software upgrade|eloquence|aria|siri/i;

let vidaVoice = null;

function pickVoice() {
  const vs = speechSynthesis.getVoices();
  if (!vs.length) return null;

  const es = vs.filter(v => /^(es)(-|_|$)/i.test(v.lang || ""));
  const co = es.filter(v => /(^|[-_])CO($|[-_])/i.test(v.lang || ""));
  const pool = co.length ? co : (es.length ? es : vs);

  const natural = pool.filter(
    v => VOZ_NATURAL.test(v.name) && !VOZ_MASCULINA.test(v.name)
  );

  const female = pool.filter(
    v => VOZ_FEMENINA.test(v.name) && !VOZ_MASCULINA.test(v.name)
  );

  const neutral = pool.filter(
    v => !VOZ_MASCULINA.test(v.name) && !VOZ_FEMENINA.test(v.name)
  );

  vidaVoice =
    natural[0] ||
    female[0] ||
    neutral[0] ||
    pool[0] ||
    null;

  return vidaVoice;
}

if ("speechSynthesis" in window) {
  speechSynthesis.onvoiceschanged = () => pickVoice();
}

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

function speak(text) {
  if (!text || !voiceOn || !("speechSynthesis" in window)) return;

  try {
    speechSynthesis.cancel();

    const partes = troceaVoz(text);
    if (!partes.length) return;

    const voz = pickVoice() || vidaVoice;
    let indice = 0;

    const siguiente = () => {
      if (!voiceOn || indice >= partes.length) return;

      const u = new SpeechSynthesisUtterance(partes[indice++]);

      if (voz) {
        u.voice = voz;
        u.lang = voz.lang || "es-CO";
      } else {
        u.lang = "es-CO";
      }

      // Ritmo más humano y menos acelerado.
      u.rate = 0.82;

      // Ligeramente cálida, evitando el tono excesivamente artificial.
      u.pitch = 1.06;

      u.volume = 1.0;

      u.onend = () => {
        if (!voiceOn) return;

        // Pausa respiratoria entre frases.
        window.setTimeout(siguiente, 280);
      };

      u.onerror = () => {
        if (indice < partes.length) {
          window.setTimeout(siguiente, 100);
        }
      };

      speechSynthesis.speak(u);
    };

    siguiente();
  } catch (_) {}
}

function setVoiceBtn() {
  const b = $("#voiceBtn");
  if (b) b.textContent = voiceOn ? "🔊" : "🔇";
  try { localStorage.setItem(VOICE_KEY, voiceOn ? "on" : "off"); } catch (_) {}
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
async function checkAuth() {
  try { AUTH = await getJSON("/api/auth/me"); } catch (_) {}
  if (!AUTH.authed && !AUTH.guest) { location.href = "/acceso"; return false; }
  return true;
}

function initAuthUI() {
  const ub = $("#userBtn");
  if (ub) ub.addEventListener("click", (e) => {
    const m = $("#userMenu");
    if (m) m.hidden = !m.hidden;
  });
  document.addEventListener("click", (e) => {
    const m = $("#userMenu");
    if (m && !m.hidden && !(e.target.closest && e.target.closest(".userbox"))) m.hidden = true;
  });
  const sp = $("#shareProfile");
  if (sp) sp.addEventListener("click", async () => {
    const url = location.origin + (AUTH.slug ? "/perfil/" + AUTH.slug : "/perfil");
    try { await navigator.clipboard.writeText(url); sp.textContent = "✅ Enlace copiado"; }
    catch (_) { window.prompt("Enlace de tu perfil:", url); }
    setTimeout(() => { sp.textContent = "📤 Compartir mi perfil"; }, 1800);
  });
  const lb = $("#logoutBtn");
  if (lb) lb.addEventListener("click", async () => {
    try { await fetch("/api/auth/logout", { method: "POST" }); } catch (_) {}
    location.href = "/acceso";
  });
}

function paintSecurity() {
  const chip = $("#secChip");
  getJSON("/api/security")
    .then((s) => {
      const on = s && s.evidence_encrypted;
      if (chip) {
        chip.innerHTML = on
          ? "<span>🛡</span> EVIDENCIAS CIFRADAS EN REPOSO · " + esc(s.encryption || "Fernet · AES-128")
          : "<span>🛡</span> cifrado en reposo DESACTIVADO · clave maestra pendiente";
      }
      const it = (s || {}).integrity || {};
      const set = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
      };
      set("secEncrypt", on ? "ACTIVO" : "PENDIENTE");
      set("secHash", it.evidence_hash ? it.evidence_hash.slice(0, 16) + "…" : "—");
      set("secUpdated", it.registry_updated_at ? fmtStamp(it.registry_updated_at) : "—");
      set("secHTTP", "NOSNIFF · CSP · HSTS");
    })
    .catch(() => {});
}

function paintCertificate() {
  const chip = $("#certChip");
  const chip2 = $("#certChip2");
  getJSON("/api/certificate")
    .then((c) => {
      const emitted = !!(c && c.certificate_id);
      if (chip) {
        chip.textContent = emitted ? "🏆 EMITIDO" : "🏆 PENDIENTE";
        chip.className = "cert-chip " + (emitted ? "on" : "off");
      }
      if (chip2) chip2.textContent = emitted ? "EMITIDO · VERIFICABLE" : "NO EMITIDO";
      const st = $("#certStatus");
      const keys = $("#certKeys");
      if (!st || !keys) return;
      const st0 = state || {};
      const checks = [
        { ok: (st0.overall ?? 0) >= 100, label: "PROGRESO OPERATIVO", val: (st0.overall ?? 0) + "%" },
        { ok: (st0.mastery ?? 0) >= 100, label: "DOMINIO VERIFICADO", val: (st0.mastery ?? 0) + "%" },
        { ok: (st0.evidence_count ?? 0) > 0, label: "EVIDENCIA OBSERVADA", val: (st0.evidence_count ?? 0) + " obs." }
      ];
      keys.innerHTML = "";
      checks.forEach(chk => {
        const el = document.createElement("div");
        el.className = "ck" + (chk.ok ? " ok" : " no");
        el.innerHTML = `<span>${chk.ok ? "✅" : "⭕"}</span><b>${esc(chk.label)}</b><i>${esc(chk.val)}</i>`;
        keys.appendChild(el);
      });
      if (emitted) {
        const url = c.verification_url || ("/verificar/" + c.certificate_id);
        st.innerHTML =
          `<div class="cert-emitted"><span class="status-chip on">✓ EMITIDO · UNA SOLA VEZ</span>` +
          `<div class="cert-id" title="Identificador con huella SHA-256">${esc(c.certificate_id)}</div>` +
          `<a class="cert-verify-btn" href="${esc(url)}" target="_blank">Verificar en línea ⇢</a></div>`;
      } else {
        st.innerHTML =
          `<div class="cert-pending"><span class="status-chip off">⏳ NO EMITIDO TODAVÍA</span>` +
          `<small>El motor lo emite en cuanto los tres criterios de abajo se cumplan y el aprendiz lo confirme.</small></div>`;
      }
    })
    .catch(() => {});
}

async function renderPodcast() {
  const box = $("#podcastList");
  if (!box) return;
  box.innerHTML = "";
  let data;
  try { data = await getJSON("/api/podcast"); } catch (_) { data = { episodes: [] }; }
  const eps = data.episodes || [];
  if (!eps.length) {
    box.innerHTML = `<div class="ev-empty">🎙 El pódcast se prepara… coloca el MP3 en <code>podcast_audio/</code> para que aparezca aquí.</div>`;
    return;
  }
  eps.forEach(ep => {
    const el = document.createElement("div");
    el.className = "ep-item";
    el.innerHTML =
      `<div class="ep-ico">🎙</div>` +
      `<div class="fm"><b>${esc(ep.title)}</b><small>${Math.round(ep.minutes || 0)} min · ${fmtSize(ep.size)} · MP3</small></div>` +
      `<audio class="ep-audio" controls preload="none" src="${esc(ep.file)}"></audio>`;
    box.appendChild(el);
  });
}

function renderZone() {
  const card = $("#zoneCard");
  const box = $("#zoneList");
  if (!card || !box) return;
  const items = [
    { t: "Matriz de riesgo interactiva", s: "EN MONTAJE", c: "trabajo" },
    { t: "Perfil público del aprendiz", s: "EN MONTAJE", c: "trabajo" },
    { t: "Pódcast por lección", s: "AUDIO LISTO", c: "listo" },
    { t: "Certificado en formato PDF", s: "EN DISEÑO", c: "diseno" },
    { t: "Versión en inglés técnico", s: "IDEA", c: "idea" }
  ];
  card.hidden = false;
  box.innerHTML = "";
  items.forEach(it => {
    const el = document.createElement("div");
    el.className = "zone-item " + it.c;
    el.innerHTML = `<b>${esc(it.t)}</b><span>${esc(it.s)}</span>`;
    box.appendChild(el);
  });
}

async function load() {
  if (!(await checkAuth())) return;
  initAuthUI();
  if (AUTH.guest) {
    const cs = $("#courseSel"); if (cs) cs.disabled = true;
    const sy = $("#sync"); if (sy) sy.disabled = true;
  }
  course = await getJSON("/api/course");
  $("#heroTitle").textContent = course.title;
  const i = $("#chipInst"); if (i) i.textContent = "🏛 " + (course.provider || "") + " · " + (course.platform || "");
  const h = $("#chipHours"); if (h) h.textContent = "⏱ " + (course.hours || 0) + " horas";
  document.title = "VIDA · " + (course.title || "");
  await loadVideosMeta();
  await loadCourses();
  await renderRoadmap();
  await refresh();
  renderZone();
  renderPodcast();
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
  paintCertificate();
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
  if (AUTH.guest) return;
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
  if (AUTH.guest) return;
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
  if (AUTH.guest) { msg.textContent = "🔒 Modo invitado: solo lectura."; return; }
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
  if (!state) state = await getJSON("/api/dashboard");
  const verified = new Set(state.verified_concept_ids || []);
  const total = (course.concepts || []).length;
  const cnt = $("#conceptCount");
  if (cnt) cnt.textContent = (course.concepts || []).filter(c => verified.has(c.id)).length + "/" + total + " VERIFICADOS";
  (course.concepts || []).forEach(c => {
    const ok = verified.has(c.id);
    const el = document.createElement("article");
    el.className = "concept" + (ok ? " verified" : "");
    el.innerHTML =
      `<div class="concept-head"><strong>◈ ${esc(c.title)}</strong>` +
      `<span class="status-chip ${ok ? "on" : "off"}">${ok ? "VERIFICADO" : "PENDIENTE"}</span></div>` +
      `<p>${esc(c.definition)}</p>` +
      (c.content ? `<p class="concept-det">${esc(c.content)}</p>` : "");
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

/* ---------------- EVIDENCIAS: EXPEDIENTE VERIFICABLE ---------------- */
let evData = null;
let evFilter = "all";
let evQuery = "";
const EV_MESES = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"];
const EV_LABEL = {
  ACTIVITY_COMPLETE: "ENTREGA",
  VIDEO_COMPLETE: "SESIÓN",
  CONCEPT_VERIFY: "CONCEPTO",
};

function evDay(iso) {
  const d = new Date(iso);
  if (isNaN(d.getTime()) || !iso) return { d: "—", m: "" };
  return { d: String(d.getDate()).padStart(2, "0"), m: EV_MESES[d.getMonth()] };
}

async function renderEvidence() {
  const box = $("#evidenceGroups");
  evData = null;
  if (box) box.innerHTML = '<div class="ev-loading">🛡 Leyendo el expediente de VIDA…</div>';
  paintEvLedgerFoot();

  let data = null;
  for (let i = 0; i < 5; i++) {
    try {
      data = await getJSON("/api/evidence");
    } catch (e) {
      data = null;
    }
    if (data && Array.isArray(data.groups) &&
        data.groups.some(g => (g.records || []).length || (g.files || []).length)) break;
    await new Promise(r => setTimeout(r, 1200));
  }

  evData = {
    payload: data || {},
    groups: data && Array.isArray(data.groups) ? data.groups : [],
  };
  renderEvidenceList();
}

function evClearAll() {
  evFilter = "all";
  evQuery = "";
  const s = $("#evSearch");
  if (s) s.value = "";
  const fs = $("#evFilters");
  if (fs) fs.querySelectorAll(".ev-f").forEach(x => x.classList.toggle("on", x.dataset.f === "all"));
  const reset = $("#evReset");
  if (reset) reset.hidden = true;
  if (evData) renderEvidenceList();
}

function renderEvidenceList() {
  const groups = (evData || { groups: [] }).groups;
  const payload = (evData || {}).payload || {};
  const box = $("#evidenceGroups");
  if (!box) return;

  const total = payload.total_records ?? groups.reduce((n, g) => n + (g.records || []).length, 0);
  const files = payload.total_files ?? groups.reduce((n, g) => n + (g.files || []).length, 0);
  const q = evQuery;

  const resetBtn = $("#evReset");
  if (resetBtn) resetBtn.hidden = evFilter === "all" && !q;

  const match = (r) => {
    if (!q) return true;
    const ctx = r.context || {};
    const hay = [ctx.title, r.evidence_id, r.source, r.method, r.event_type]
      .filter(Boolean).join(" ").toLowerCase();
    return hay.includes(q);
  };

  const showOnlyFiles = evFilter === "files";
  const filteredGroups = groups.map(g => ({
    ...g,
    records: showOnlyFiles ? [] : (g.records || []).filter(r =>
      (evFilter === "all" || r.event_type === evFilter) && match(r)),
    files: evFilter === "all" || evFilter === "files" ? (g.files || []).filter(f => match({ evidence_id: f.name, context: {} })) : []
  })).filter(g => (g.records || []).length || (g.files || []).length);

  const shownRecs = filteredGroups.reduce((n, g) => n + g.records.length + g.files.length, 0);
  const cnt = $("#evCount");
  if (cnt) cnt.textContent = (evFilter === "all" && !q) ? total + " OBSERVADAS" : shownRecs + " RESULTADOS";

  box.innerHTML = "";

  const resumen = document.createElement("div");
  resumen.className = "ev-summary";
  resumen.innerHTML =
    `<div class="ev-stat"><b>${esc(String(total))}</b><small>OBSERVACIONES<br>REGISTRADAS</small></div>` +
    `<div class="ev-stat"><b>${esc(String(files))}</b><small>ARCHIVOS<br>SUBIDOS</small></div>` +
    `<div class="ev-stat"><b>${esc(String(groups.length))}</b><small>ACTIVIDADES<br>RELACIONADAS</small></div>` +
    `<div class="ev-ledger" title="Trazabilidad verificable"><span>🛡</span> OBSERVADO ≠ INFERIDO<br><small>nada se asume, todo se demuestra</small></div>`;
  box.appendChild(resumen);

  const legend = document.createElement("div");
  legend.className = "ev-legend";
  legend.innerHTML =
    `<span class="lg a">● entregas</span>` +
    `<span class="lg b">● sesiones</span>` +
    `<span class="lg c">● conceptos</span>` +
    `<span class="lg d">● archivos</span>`;
  box.appendChild(legend);

  if (!filteredGroups.length) {
    const empty = document.createElement("div");
    empty.className = "ev-empty";
    empty.innerHTML =
      `<b>Sin coincidencias</b>` +
      `<span>El filtro o la búsqueda no encuentra observaciones en el expediente.</span>` +
      `<button type="button" onclick="evClearAll()">Mostrar todo el expediente</button>`;
    box.appendChild(empty);
    return;
  }

  filteredGroups.forEach(g => {
    const el = document.createElement("div");
    el.className = "ev-group";
    const head = document.createElement("h3");
    head.innerHTML = `${g.records.length ? "✅" : "📎"} ${esc(g.title)} ` +
      `<span>${g.records.length} observaci${g.records.length === 1 ? "ón" : "ones"}` +
      `${g.files.length ? " · " + g.files.length + " archivo" + (g.files.length === 1 ? "" : "s") : ""}</span>`;
    el.appendChild(head);

    g.records.slice().reverse().forEach(r => {
      const ctx = r.context || {};
      const day = evDay(r.observed_at);
      const row = document.createElement("div");
      row.className = "ev-record";
      row.dataset.etype = r.event_type || "";
      row.innerHTML =
        `<div class="ev-date" aria-hidden="true"><b>${esc(day.d)}</b><i>${esc(day.m)}</i></div>` +
        `<div class="ev-ico">${EV_ICON[r.event_type] || "◇"}</div>` +
        `<span class="er-k">${esc(EV_LABEL[r.event_type] || "OBSERVACIÓN")}</span>` +
        `<div class="er-body"><b>${esc(ctx.title || r.source || r.evidence_id)}</b>` +
        `<small><code>${esc(r.evidence_id)}</code> · ${esc((r.method || "").replace(/_/g, " "))} · ${esc(fmtStamp(r.observed_at))}</small></div>` +
        `<span class="er-chip ${r.result.includes("VERIFIED") || r.result === "DELIVERED" ? "on" : "off"}">${esc(r.result.replace(/_/g, " "))}</span>`;
      el.appendChild(row);
    });

    if (g.files.length) {
      const filesHead = document.createElement("div");
      filesHead.className = "ev-files-label";
      filesHead.textContent = "ARCHIVOS SUBIDOS";
      el.appendChild(filesHead);
      g.files.forEach(f => {
        const r = g.records.find(x => (x.context || {}).file === f.name);
        const fi = document.createElement("div");
        fi.className = "file-item";
        fi.innerHTML = `<div class="fi">${fileType(f.name).split(" ")[0]}</div>` +
          `<div class="fm"><b>${esc(f.name)}</b><small>${fmtSize(f.size)}${r ? " · " + esc(r.evidence_id) : ""}</small></div>` +
          `<a href="${esc(f.url)}" target="_blank">ver →</a>`;
        el.appendChild(fi);
      });
    }

    box.appendChild(el);
  });
}

function bindEvidenceToolbar() {
  const s = $("#evSearch");
  if (s) {
    s.addEventListener("input", () => {
      evQuery = s.value.trim().toLowerCase();
      if (evData) renderEvidenceList();
    });
    s.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        evQuery = s.value.trim().toLowerCase();
        if (evData) renderEvidenceList();
      } else if (e.key === "Escape") {
        evClearAll();
      }
    });
  }
  const fs = $("#evFilters");
  if (fs) fs.addEventListener("click", (e) => {
    const b = e.target.closest(".ev-f");
    if (!b) return;
    evFilter = b.dataset.f;
    fs.querySelectorAll(".ev-f").forEach(x => x.classList.toggle("on", x === b));
    if (evData) renderEvidenceList();
  });
  const reset = $("#evReset");
  if (reset) reset.addEventListener("click", evClearAll);
}

function paintEvLedgerFoot() {
  const foot = $("#evLedgerFoot");
  if (!foot) return;
  foot.textContent = "🛡 Verificando integridad…";
  getJSON("/api/security")
    .then((s) => {
      const it = (s || {}).integrity || {};
      foot.innerHTML = `<span>🛡</span> Expediente cifrado en reposo · huella SHA-256 ` +
        `<code>${esc((it.evidence_hash || "—").slice(0, 16))}…</code>` +
        ` · ${esc(it.evidence_count ?? 0)} observaciones` +
        (it.registry_updated_at ? ` · última: ${esc(fmtStamp(it.registry_updated_at))}` : "");
    })
    .catch(() => {
      foot.textContent = "🛡 La verificación de integridad no está disponible en este momento.";
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
  $("#sync").addEventListener("click", () => { loadVideosMeta(); refresh(); });
  $("#actBack").addEventListener("click", () => { location.hash = "#/actividades"; });
  const vb = $("#voiceBtn");
  if (vb) vb.addEventListener("click", () => {
    voiceOn = !voiceOn;
setVoiceBtn();
  if ("speechSynthesis" in window) {
    pickVoice();
    const refreshVoz = () => pickVoice();
    if (speechSynthesis.addEventListener) speechSynthesis.addEventListener("voiceschanged", refreshVoz);
    else speechSynthesis.onvoiceschanged = refreshVoz;
  }
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
  bindEvidenceToolbar();
  tickClock();
  setInterval(tickClock, 1000);
load();
  paintSecurity();
  setInterval(() => { if (document.visibilityState === "visible") refresh(); }, 20000);
});