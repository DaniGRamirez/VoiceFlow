// =======================================================
// Canvas setup
// =======================================================
const canvas = document.getElementById("c");
const ctx = canvas.getContext("2d");

function resize() {
  canvas.width = innerWidth;
  canvas.height = innerHeight;
}
addEventListener("resize", resize);
resize();

// =======================================================
// Utils
// =======================================================
const lerp = (a, b, t) => a + (b - a) * t;
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

// Simple 1D value noise
function hash(n) {
  return (Math.sin(n) * 43758.5453123) % 1;
}
function smooth(t) {
  return t * t * (3 - 2 * t);
}
function noise1(x) {
  const i = Math.floor(x);
  const f = x - i;
  return lerp(hash(i), hash(i + 1), smooth(f)); // 0..1
}

// Superelipse base (pill / rounded-rect orgánico)
function superellipseRadius(theta, a, b, n) {
  const c = Math.cos(theta);
  const s = Math.sin(theta);
  const ac = Math.pow(Math.abs(c) / a, n);
  const bs = Math.pow(Math.abs(s) / b, n);
  return Math.pow(ac + bs, -1 / n);
}

// =======================================================
// Audio (RMS + envelope follower)
// =======================================================
let audioEnergy = 0;  // 0..1 suavizado
let audioSmooth = 0;  // suavizado extra para evitar “picos ameba”
let listening = false;

async function startMic() {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const ac = new (window.AudioContext || window.webkitAudioContext)();
  const src = ac.createMediaStreamSource(stream);
  const analyser = ac.createAnalyser();
  analyser.fftSize = 1024;
  src.connect(analyser);

  const buf = new Float32Array(analyser.fftSize);

  let env = 0;
  const attack = 0.25;
  const release = 0.08;

  function tickAudio() {
    analyser.getFloatTimeDomainData(buf);
    let sum = 0;
    for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i];
    const rms = Math.sqrt(sum / buf.length); // ~0..0.2
    const x = Math.min(1, rms * 6.0);

    if (x > env) env += (x - env) * attack;
    else env += (x - env) * release;

    audioEnergy = env;
    audioSmooth += (audioEnergy - audioSmooth) * 0.12;

    requestAnimationFrame(tickAudio);
  }
  tickAudio();
}

// Click para permiso mic
addEventListener(
  "pointerdown",
  () => {
    if (!listening) {
      listening = true;
      startMic().catch(console.error);
      setState("dictating");
    }
  },
  { once: true }
);

// =======================================================
// States
// =======================================================
let stateT = 0;       // 0 idle, 1 dictating
let stateTarget = 0;

function setState(s) {
  stateTarget = s === "dictating" ? 1 : 0;
}

// Teclas de test
addEventListener("keydown", (e) => {
  if (e.key.toLowerCase() === "i") setState("idle");
  if (e.key.toLowerCase() === "d") setState("dictating");
});

// =======================================================
// Shape builder (base fill + deformed stroke)
// =======================================================
const N = 160;
let t = 0;

function buildPath(cx, cy, baseR, A, B, nShape, roundBlend, deformFn) {
  ctx.beginPath();
  for (let i = 0; i <= N; i++) {
    const ang = (i / N) * Math.PI * 2;

    // Base pill radius (superellipse)
    const pillR = superellipseRadius(ang, A, B, nShape);

    // Perfect circle radius (==1) for rounding blend (anti “flat sides”)
    const circR = superellipseRadius(ang, 1.0, 1.0, 2.0);

    // Blend a bit towards circle ONLY in idle to get the exact “capsule” look
    const baseShapeR = lerp(pillR, circR, roundBlend);

    const base = baseR * baseShapeR;
    const d = deformFn ? deformFn(i, ang) : 0;

    const rr = base + d;

    const x = cx + Math.cos(ang) * rr;
    const y = cy + Math.sin(ang) * rr;

    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.closePath();
}

// =======================================================
// Render loop
// =======================================================
function draw() {
  t += 0.016;

  // Blend de estados
  stateT += (stateTarget - stateT) * 0.12;

  const cx = innerWidth * 0.5;
  const cy = innerHeight * 0.5;

  // =========================
  // IDLE capsule (como tu imagen)
  // =========================
  const baseRIdle = 18;   // pequeño
  const nIdle = 4.2;      // suave, nada recto
  const aIdle = 2.05;     // ancho
  const bIdle = 0.72;     // fino pero no “línea”

  // Dictation circle
  const baseRDict = 30;
  const nDict = 2.0;
  const aDict = 1.0;
  const bDict = 1.0;

  const baseR = lerp(baseRIdle, baseRDict, stateT);
  const nShape = lerp(nIdle, nDict, stateT);
  const A = lerp(aIdle, aDict, stateT);
  const B = lerp(bIdle, bDict, stateT);

  // Solo en idle mezclamos un poco hacia círculo para matar cualquier planitud
  const roundBlend = 0.22 * (1 - stateT);

  // =========================
  // Colors (idle negro + borde plata / dictado rojizo)
  // =========================
  const fillIdle = "#000000";
  const fillDict = "#180000";
  const fill = stateT < 0.5 ? fillIdle : fillDict;

  const strokeIdle = "rgba(220,220,230,0.86)";
  const strokeDict = "rgba(255,120,120,0.55)";
  const stroke = stateT < 0.5 ? strokeIdle : strokeDict;

  // =========================
  // Deformation control
  // =========================
  // Idle: vivo pero MUY sutil (solo borde)
  const idleAmp = 0.28;
  const idleSpd = 0.22;

  // Dictado: mantener círculo siempre reconocible
  const dictAmpMaxRatio = 0.07; // 7% del radio -> sigue siendo círculo
  const dictNoiseAmp = 0.55;    // textura del borde
  const dictSpd = 0.95;

  const E = clamp(audioSmooth, 0, 1);

  // Cap absoluto en dictado (relativo al radio)
  const dictCapAbs = baseRDict * dictAmpMaxRatio;

  // =========================
  // Clear background
  // =========================
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // =========================
  // 1) FILL: base estable (sin deform)
  // =========================
  buildPath(cx, cy, baseR, A, B, nShape, roundBlend, null);
  ctx.fillStyle = fill;
  ctx.fill();

  // =========================
  // 2) STROKE: borde vivo (deformado)
  // =========================
  ctx.lineWidth = lerp(1.8, 1.6, stateT);
  ctx.strokeStyle = stroke;

  buildPath(cx, cy, baseR, A, B, nShape, roundBlend, (i, ang) => {
    const spd = lerp(idleSpd, dictSpd, stateT);

    // Noise 2 capas (fluido)
    const n1 = noise1(i * 0.18 + t * spd);
    const n2 = noise1(i * 0.06 + t * spd * 0.55 + 10);
    const dn = ((n1 * 0.65 + n2 * 0.35) - 0.5) * 2; // -1..1

    // Idle: vida constante sutil
    const idleDeform = dn * idleAmp;

    // Dictado: deformación por energía + detalle, capada
    // Queremos “borde reactivo” pero sin ameba
    const detail = dn * dictNoiseAmp;

    // Un empuje suave “tipo respiración” ligado a la voz (no picos)
    const audioPush = (0.35 + 0.65 * Math.sin(ang * 4 + t * 4) * 0.5 + 0.65) * E;

    const raw = (detail * 3.2 + audioPush * 2.2) * 1.0;

    const dictDeform = clamp(raw, -dictCapAbs, dictCapAbs);

    return lerp(idleDeform, dictDeform, stateT);
  });

  ctx.stroke();

  requestAnimationFrame(draw);
}

draw();
