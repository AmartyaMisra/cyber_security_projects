# spiderman_passgen.py
# Single-file self-contained demo.
# - No external Python packages required
# - Writes an HTML file, starts a tiny HTTP server, opens browser
# - Interactive password derivation (PBKDF2 via WebCrypto in the browser)
# - Smooth 2D comic-style "Spidey" svg that swings outside the UI box,
#   occasionally shoots a web (temporary line + whoosh sound), and crawls.

import os
import tempfile
import webbrowser
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import math
import textwrap

HTML = textwrap.dedent(r"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
<title>SpideyPass — Password Atelier (local demo)</title>
  <style>
  /* Neon / hacker aesthetic */
    :root{
    --bg:#060710;
    --card:#08101b;
    --glass: rgba(255,255,255,0.03);
    --accent1:#00e5ff;
    --accent2:#ff3ea8;
    --muted:#92a0b3;
    --glow: 0 10px 30px rgba(0,230,255,0.06);
    --radius:14px;
  }
  html,body{height:100%;margin:0;background:linear-gradient(180deg,var(--bg),#04101a);color:#e6eef6;font-family:Inter,ui-sans-serif,system-ui,Helvetica,Arial;}
  .stage{position:fixed;inset:0;overflow:hidden;}
  /* centered UI card */
  .center{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:760px;max-width:calc(100% - 40px);}
  .card{background:linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01));border-radius:var(--radius);padding:22px;box-shadow:var(--glow);border:1px solid rgba(255,255,255,0.04);display:grid;grid-template-columns:1fr 280px;gap:18px;align-items:start;}
  h1{margin:0;font-size:20px;display:flex;align-items:center;gap:10px}
  .lead{color:var(--muted);font-size:13px;margin-top:6px}
  label{display:block;color:var(--muted);font-size:13px;margin-top:12px}
  input,select,textarea{width:100%;padding:10px;border-radius:8px;background:#061018;border:1px solid rgba(255,255,255,0.03);color:#e6eef6;box-sizing:border-box;font-size:14px}
  .controls{display:flex;gap:8px;margin-top:12px}
  button{background:linear-gradient(90deg,var(--accent1),var(--accent2));color:#021018;border:0;padding:10px 12px;border-radius:8px;cursor:pointer;font-weight:700}
  button.ghost{background:transparent;border:1px solid rgba(255,255,255,0.04);color:var(--accent1)}
  .output{background:rgba(255,255,255,0.01);border-radius:10px;padding:12px;border:1px solid rgba(255,255,255,0.02)}
  .pass{font-family:ui-monospace,Menlo,Monaco,monospace;font-size:16px;word-break:anywhere}
  .small{font-size:13px;color:var(--muted)}
  .rightcol{display:flex;flex-direction:column;gap:12px}
  .card-block{background:rgba(255,255,255,0.02);padding:12px;border-radius:10px;border:1px solid rgba(255,255,255,0.03)}
  .meter{height:8px;background:rgba(255,255,255,0.04);border-radius:99px;overflow:hidden}
  .meter > i{display:block;height:100%;width:0%;background:linear-gradient(90deg,#ff416c,#7c3aed);transition:width .25s}
  .muted{color:var(--muted)}
  footer.small{margin-top:8px;color:var(--muted)}
  /* animation layer */
  #animLayer{position:fixed;left:0;top:0;width:100vw;height:100vh;pointer-events:none;z-index:6}
  /* ensure card sits above anim layer so spider is outside: but we will still allow spider to draw over card edges when outside the safety margin */
  .center{z-index:7}
  /* responsive */
  @media (max-width:840px){
    .card{grid-template-columns:1fr}
  }
  </style>
</head>
<body>
<div class="stage">
  <!-- SVG animation layer for Spidey and webs -->
  <svg id="animLayer" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="none">
    <!-- temporary elements; JS will manipulate -->
    <defs>
      <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
        <feGaussianBlur stdDeviation="6" result="coloredBlur"/>
        <feMerge>
          <feMergeNode in="coloredBlur"/>
          <feMergeNode in="SourceGraphic"/>
        </feMerge>
      </filter>
    </defs>
    <g id="webGroup"></g>
    <g id="spiderGroup" transform="translate(0,0)"></g>
  </svg>

  <!-- Centered UI card -->
  <div class="center">
    <div class="card" id="card">
      <div>
        <h1>SpideyPass <span style="font-size:12px;color:var(--muted)">swing-mode</span></h1>
        <div class="lead">Answer a few micro-questions, generate deterministic passwords (PBKDF2-SHA256). Spidey swings outside — aesthetics + security.</div>

        <label for="q0">1) Memorable word</label>
        <input id="q0" placeholder="midnight-fox" autocomplete="off">

        <label for="q1">2) Favorite number</label>
        <input id="q1" type="number" placeholder="7 or 1999">

        <label for="q2">3) Symbol</label>
        <select id="q2">
          <option>!</option><option>@</option><option>#</option><option>$</option><option>%</option><option>*</option><option>~</option><option>?</option>
        </select>

        <label for="q3">4) Wild word</label>
        <input id="q3" placeholder="random word">

        <label for="q4">5) Style</label>
        <select id="q4">
          <option value="hybrid">Hybrid (readable + secure)</option>
          <option value="crypto">Crypto (base64-heavy)</option>
          <option value="dice">Diceware-ish (readable)</option>
        </select>

        <div class="controls">
          <button id="generate">Generate</button>
          <button class="ghost" id="regen">Regenerate</button>
          <button class="ghost" id="copyBtn">Copy</button>
        </div>

        <div style="margin-top:14px" class="output" aria-live="polite">
          <div class="small">Generated password</div>
          <div class="pass" id="generated">—</div>
          <div class="small" style="margin-top:8px">Strength</div>
          <div class="meter" style="margin-top:6px"><i id="meterbar"></i></div>
          <div class="small" id="spideyQuip" style="margin-top:10px;color:var(--muted)"></div>
        </div>

        <div style="margin-top:10px" class="small">Note: all derivation is done locally in your browser. Salt is shown on generation for deterministic regen (keep it safe).</div>
      </div>

      <div class="rightcol">
        <div class="card-block">
          <div class="small">Preview</div>
          <div id="preview" style="margin-top:8px;color:var(--muted)">Your choices will appear here</div>
        </div>

        <div class="card-block">
          <div class="small">Actions</div>
          <div style="display:flex;gap:8px;margin-top:8px">
            <button id="download">Download</button>
            <button id="reset" class="ghost">Reset</button>
          </div>
        </div>

        <div class="card-block">
          <div class="small">About</div>
          <div class="small" style="margin-top:8px;color:var(--muted)">Local demo: PBKDF2-SHA256 (client), 150k iterations (tuned for smoothness). Adjustable in code.</div>
      </div>
      </div>
    </div>

    <footer style="text-align:center;margin-top:12px" class="small">Press Generate — Spidey will react.</footer>
    </div>
  </div>

<script>
/* ---------- UI / Crypto logic (client-side PBKDF2) ---------- */
const wordlist = ["iron","echo","raven","void","flux","onyx","neon","drift","sigma","omega","zero","atlas","cinder","lumen","vapor","quartz"];
const q0 = document.getElementById('q0'), q1 = document.getElementById('q1'), q2 = document.getElementById('q2'), q3 = document.getElementById('q3'), q4 = document.getElementById('q4');
const generatedEl = document.getElementById('generated'), meterbar = document.getElementById('meterbar'), spideyQuip = document.getElementById('spideyQuip');
const preview = document.getElementById('preview');
let sessionSaltB64 = null, lastRaw = null, lastHuman = null;

function updatePreview(){
  preview.textContent = `word: "${q0.value || '—'}", num: ${q1.value || '—'}, sym: "${q2.value}", wild: "${q3.value || '—'}", style: ${q4.value}`;
}
['q0','q1','q2','q3','q4'].forEach(id => document.getElementById(id).addEventListener('input', ()=>{ updatePreview(); nudgeSpidey(0.5); }));
updatePreview();

function bytesToB64Url(bytes){
  let s = btoa(String.fromCharCode.apply(null, bytes));
  return s.replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
}
function b64ToBytes(b64){
  b64 = b64.replace(/-/g,'+').replace(/_/g,'/');
  // pad
  while(b64.length % 4) b64 += '=';
  const bin = atob(b64);
  const arr = new Uint8Array(bin.length);
  for(let i=0;i<bin.length;i++) arr[i] = bin.charCodeAt(i);
  return arr;
}

async function pbkdf2(seedStr, saltBytes, iterations=150000, dkLen=32){
  const enc = new TextEncoder();
  const keyMaterial = await crypto.subtle.importKey('raw', enc.encode(seedStr), {name:'PBKDF2'}, false, ['deriveBits']);
  const derived = await crypto.subtle.deriveBits({name:'PBKDF2', salt: saltBytes, iterations: iterations, hash: 'SHA-256'}, keyMaterial, dkLen * 8);
  return new Uint8Array(derived);
}

function mapHuman(keyBytes, choices=6){
  const words = [];
  for(let i=0;i<keyBytes.length && words.length<choices;i+=2){
    const idx = ((keyBytes[i]<<8) | (keyBytes[i+1])) % wordlist.length;
    words.push(wordlist[idx]);
  }
  return words.join('-');
}

function updateStrength(pw){
  const uniq = new Set(pw).size;
  const len = pw.length;
  const score = Math.min(100, Math.round((uniq*4 + len*3)));
  meterbar.style.width = score + '%';
}

const quips = [
  "That one's stickier than my webs.",
  "Strong enough to survive a city swing and some bad guys.",
  "If this gets cracked, I might actually eat my mask.",
  "Nicely balanced — like a good swing between skyscrapers.",
  "This one would make Dr. Octopus sweat.",
  "Aunt May would say 'good password!'"
];

function randQuip(){ return quips[Math.floor(Math.random()*quips.length)]; }

async function deriveAndShow({saltB64=null} = {}){
  const payloadSeed = `${q0.value||''}|${q1.value||''}|${q2.value||''}|${q3.value||''}|${q4.value||'hybrid'}`;
  let salt;
  if(saltB64){
    salt = b64ToBytes(saltB64);
  } else {
    salt = crypto.getRandomValues(new Uint8Array(16));
    saltB64 = bytesToB64Url(salt);
    sessionSaltB64 = saltB64;
  }
  // show a small UI cue
  generatedEl.textContent = 'deriving… (may take a moment)';
  const key = await pbkdf2(payloadSeed + '|' + (saltB64||''), salt, 150000, 32);
  const rawB64 = bytesToB64Url(key);
  const human = mapHuman(key, 6);
  lastRaw = rawB64; lastHuman = human;
  sessionSaltB64 = saltB64;
  let display;
  if(q4.value === 'crypto'){ display = rawB64.slice(0,28) + q2.value + rawB64.slice(28,48); }
  else if(q4.value === 'dice'){ display = human; }
  else { display = human + q2.value + rawB64.slice(0,12); }
  generatedEl.textContent = display;
  updateStrength(display);
  spideyQuip.textContent = randQuip() + (saltB64 ? ' (regenerated)' : '');
  // show salt in preview lightly
  preview.textContent = preview.textContent + ` • salt: ${saltB64}`;
  nudgeSpidey(1.0);
}

document.getElementById('generate').addEventListener('click', ()=> deriveAndShow({saltB64:null}));
document.getElementById('regen').addEventListener('click', ()=> {
  if(!sessionSaltB64){ alert('Generate first to get a salt.'); return;}
  deriveAndShow({saltB64: sessionSaltB64});
});
document.getElementById('copyBtn').addEventListener('click', async ()=>{
  const txt = generatedEl.textContent;
  if(!txt || txt==='—') return alert('nothing to copy');
  await navigator.clipboard.writeText(txt);
  alert('Copied to clipboard — nice.');
  nudgeSpidey(0.8);
});
document.getElementById('download').addEventListener('click', ()=>{
  const txt = generatedEl.textContent;
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([txt], {type:'text/plain'})); a.download = 'spideypass.txt'; a.click();
  nudgeSpidey(1.0);
});
document.getElementById('reset').addEventListener('click', ()=>{
  ['q0','q1','q3'].forEach(id => document.getElementById(id).value = '');
  document.getElementById('q2').value = '!';
  document.getElementById('q4').value = 'hybrid';
  generatedEl.textContent = '—';
  sessionSaltB64 = null; lastRaw = null; lastHuman = null;
  preview.textContent = 'Your choices will appear here';
  updateStrength('');
  nudgeSpidey(0.6);
});

/* ---------- Spidey animation (SVG) ---------- */
/* The spider is drawn as an SVG group and animated via requestAnimationFrame.
   The logic ensures the spider's swing path stays outside the UI card bounding rect.
   Behavior modes: 'swing', 'crawl', 'idle' (very small), 'shot' (shoot web visual).
*/

const svg = document.getElementById('animLayer');
const spiderGroup = document.getElementById('spiderGroup');
const webGroup = document.getElementById('webGroup');
const card = document.getElementById('card');
let persistentWebPath = null;

let W = window.innerWidth, H = window.innerHeight;
svg.setAttribute('width', W);
svg.setAttribute('height', H);

function makeSpiderSVG(){
  // small colorful comic-style sprite (not a photo)
  // body, head, eyes, small arm to indicate hand/web shooter
  const g = document.createElementNS('http://www.w3.org/2000/svg','g');
  g.setAttribute('id','spidey');
  g.setAttribute('transform','translate(0,0)');

  // shadow
  const sh = document.createElementNS('http://www.w3.org/2000/svg','ellipse');
  sh.setAttribute('cx','0'); sh.setAttribute('cy','14'); sh.setAttribute('rx','22'); sh.setAttribute('ry','8');
  sh.setAttribute('fill','rgba(0,0,0,0.2)');
  sh.setAttribute('transform','translate(0,0)');
  g.appendChild(sh);

  // body (slimmer silhouette)
  const body = document.createElementNS('http://www.w3.org/2000/svg','ellipse');
  body.setAttribute('cx','0'); body.setAttribute('cy','0'); body.setAttribute('rx','12'); body.setAttribute('ry','20');
  body.setAttribute('fill','#c80b2d'); body.setAttribute('stroke','#260b10'); body.setAttribute('stroke-width','1.2');
  g.appendChild(body);
  // blue torso underlay
  const torsoBlue = document.createElementNS('http://www.w3.org/2000/svg','ellipse');
  torsoBlue.setAttribute('cx','0'); torsoBlue.setAttribute('cy','6'); torsoBlue.setAttribute('rx','10'); torsoBlue.setAttribute('ry','8');
  torsoBlue.setAttribute('fill','#0b2a6b'); torsoBlue.setAttribute('opacity','0.85');
  g.appendChild(torsoBlue);

  // chest pattern (simple)
  const chest = document.createElementNS('http://www.w3.org/2000/svg','path');
  chest.setAttribute('d','M -10 -2 Q 0 -6 10 -2 Q 0 12 -10 -2 Z');
  chest.setAttribute('fill','#7b0620'); chest.setAttribute('opacity','0.9');
  g.appendChild(chest);

  // head
  const head = document.createElementNS('http://www.w3.org/2000/svg','circle');
  head.setAttribute('cx','0'); head.setAttribute('cy','-26'); head.setAttribute('r','10');
  head.setAttribute('fill','#b60b1f'); head.setAttribute('stroke','#260b10'); head.setAttribute('stroke-width','1');
  g.appendChild(head);

  // eyes (comic white shapes)
  const eyeL = document.createElementNS('http://www.w3.org/2000/svg','path');
  eyeL.setAttribute('d','M -6 -31 q 6 -4 10 0 q -6 6 -10 0 z');
  eyeL.setAttribute('fill','#fff');
  g.appendChild(eyeL);
  const eyeR = document.createElementNS('http://www.w3.org/2000/svg','path');
  eyeR.setAttribute('d','M 6 -31 q -6 -4 -10 0 q 6 6 10 0 z');
  eyeR.setAttribute('fill','#fff');
  g.appendChild(eyeR);
  // simple mask webbing
  const web1 = document.createElementNS('http://www.w3.org/2000/svg','path');
  web1.setAttribute('d','M -8 -28 Q 0 -24 8 -28'); web1.setAttribute('stroke','rgba(20,20,20,0.5)'); web1.setAttribute('fill','none'); web1.setAttribute('stroke-width','0.8');
  g.appendChild(web1);
  const web2 = document.createElementNS('http://www.w3.org/2000/svg','path');
  web2.setAttribute('d','M -9 -24 Q 0 -20 9 -24'); web2.setAttribute('stroke','rgba(20,20,20,0.5)'); web2.setAttribute('fill','none'); web2.setAttribute('stroke-width','0.8');
  g.appendChild(web2);
  const web3 = document.createElementNS('http://www.w3.org/2000/svg','path');
  web3.setAttribute('d','M 0 -36 L 0 -20'); web3.setAttribute('stroke','rgba(20,20,20,0.5)'); web3.setAttribute('fill','none'); web3.setAttribute('stroke-width','0.8');
  g.appendChild(web3);

  // right arm (hand) — used as web origin
  const arm = document.createElementNS('http://www.w3.org/2000/svg','path');
  arm.setAttribute('d','M 18 -2 q 14 -6 6 -18');
  arm.setAttribute('stroke','#b60b1f'); arm.setAttribute('stroke-width','2.6'); arm.setAttribute('fill','none'); arm.setAttribute('stroke-linecap','round');
  arm.setAttribute('id','handPath');
  g.appendChild(arm);

  // small accent circle at hand tip (web shooter point)
  const handTip = document.createElementNS('http://www.w3.org/2000/svg','circle');
  handTip.setAttribute('cx','24'); handTip.setAttribute('cy','-14'); handTip.setAttribute('r','3');
  handTip.setAttribute('fill','#ffd9e6'); handTip.setAttribute('id','handTip');
  g.appendChild(handTip);

  // left arm
  const armL = document.createElementNS('http://www.w3.org/2000/svg','path');
  armL.setAttribute('d','M -18 -2 q -14 -6 -6 -18');
  armL.setAttribute('stroke','#b60b1f'); armL.setAttribute('stroke-width','2.6'); armL.setAttribute('fill','none'); armL.setAttribute('stroke-linecap','round');
  g.appendChild(armL);
  const handTipL = document.createElementNS('http://www.w3.org/2000/svg','circle');
  handTipL.setAttribute('cx','-24'); handTipL.setAttribute('cy','-14'); handTipL.setAttribute('r','3');
  handTipL.setAttribute('fill','#ffd9e6');
  g.appendChild(handTipL);

  // legs
  const legL = document.createElementNS('http://www.w3.org/2000/svg','path');
  legL.setAttribute('d','M -6 12 q -10 18 -8 34');
  legL.setAttribute('stroke','#0b2a6b'); legL.setAttribute('stroke-width','3.0'); legL.setAttribute('fill','none'); legL.setAttribute('stroke-linecap','round');
  g.appendChild(legL);
  const legR = document.createElementNS('http://www.w3.org/2000/svg','path');
  legR.setAttribute('d','M 6 12 q 10 18 8 34');
  legR.setAttribute('stroke','#0b2a6b'); legR.setAttribute('stroke-width','3.0'); legR.setAttribute('fill','none'); legR.setAttribute('stroke-linecap','round');
  g.appendChild(legR);
  // boots
  const bootL = document.createElementNS('http://www.w3.org/2000/svg','circle'); bootL.setAttribute('cx','-12'); bootL.setAttribute('cy','46'); bootL.setAttribute('r','2.4'); bootL.setAttribute('fill','#0b2a6b'); g.appendChild(bootL);
  const bootR = document.createElementNS('http://www.w3.org/2000/svg','circle'); bootR.setAttribute('cx','12'); bootR.setAttribute('cy','46'); bootR.setAttribute('r','2.4'); bootR.setAttribute('fill','#0b2a6b'); g.appendChild(bootR);

  return g;
}
spiderGroup.appendChild(makeSpiderSVG());

/* Web sound (tiny synthesized whoosh) */
let audioCtx = null;
function playWhoosh(){
  try {
    if(!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const ctx = audioCtx;
    const o = ctx.createOscillator();
    const g = ctx.createGain();
    o.type = 'sine';
    o.frequency.setValueAtTime(800, ctx.currentTime);
    o.frequency.exponentialRampToValueAtTime(200, ctx.currentTime + 0.25);
    g.gain.setValueAtTime(0.001, ctx.currentTime);
    g.gain.exponentialRampToValueAtTime(0.12, ctx.currentTime + 0.04);
    g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.35);
    o.connect(g); g.connect(ctx.destination);
    o.start();
    o.stop(ctx.currentTime + 0.45);
  } catch(e){ /* ignore on unsupported */ }
}

/* animation state */
let state = {
  mode: 'swing', // swing | crawl | idle
  anchor: {x: 0, y: 0},
  L: 140,
  thetaAmp: 1.0,
  omega: 1.2,
  phase: 0,
  t0: performance.now()/1000,
  spiderPos: {x: 0, y: 0},
  lastSwitch: performance.now(),
  switchEvery: 3500 + Math.random()*3500
};

function rnd(min,max){ return min + Math.random()*(max-min); }

function layoutUpdate(){
  W = window.innerWidth; H = window.innerHeight;
  svg.setAttribute('width', W); svg.setAttribute('height', H);
}
window.addEventListener('resize', ()=> {
  layoutUpdate();
  chooseAnchor(true);
});

/* ensure spider path stays outside the card: choose anchor distance such that anchorDistance - L >= halfDiagonal+margin */
function chooseAnchor(force=false){
  const rect = card.getBoundingClientRect();
  const cx = rect.left + rect.width/2, cy = rect.top + rect.height/2;
  const halfDiag = Math.sqrt((rect.width/2)**2 + (rect.height/2)**2);
  // pick L small-ish sometimes, larger other times
  const L = rnd(80, 160);
  const margin = 36 + Math.random()*40;
  const dMin = halfDiag + L + margin;
  // choose d somewhere between dMin and min viewport radius
  const maxPossible = Math.max(window.innerWidth, window.innerHeight) * 0.8;
  const d = Math.min(maxPossible*0.9, dMin + rnd(40, 140));
  const ang = rnd(0, Math.PI*2);
  const ax = cx + d * Math.cos(ang);
  const ay = cy + d * Math.sin(ang);
  state.anchor.x = ax; state.anchor.y = ay;
  state.L = L;
  state.thetaAmp = rnd(0.6, 1.3);
  state.omega = rnd(0.9, 1.6);
  state.phase = rnd(0, Math.PI*2);
  state.t0 = performance.now()/1000;
  // change switch timing
  state.switchEvery = 3500 + Math.random()*4500;
  state.lastSwitch = performance.now();
}

chooseAnchor(true);

/* Utility: set spider group transform based on x,y and rotation */
function setSpiderTransform(x,y,rot){
  const g = document.getElementById('spidey');
  g.setAttribute('transform', `translate(${x},${y}) rotate(${rot})`);
  // adjust shadow ellipse (first child) position
  // also move handTip if needed (we offset in SVG coordinates)
}

/* draw web (temporary). from anchor -> hand tip position */
function drawWeb(anchorX, anchorY, handX, handY, duration=500){
  // create a path in webGroup and animate stroke dashoffset
  const path = document.createElementNS('http://www.w3.org/2000/svg','path');
  const mx = (anchorX + handX)/2, my = (anchorY + handY)/2 - 16; // slight sag
  path.setAttribute('d', `M ${anchorX} ${anchorY} Q ${mx} ${my} ${handX} ${handY}`);
  path.setAttribute('stroke','rgba(240,240,255,0.95)');
  path.setAttribute('stroke-width','2.2');
  path.setAttribute('stroke-linecap','round');
  path.setAttribute('fill','none');
  path.setAttribute('opacity','0.0');
  path.setAttribute('stroke-dasharray','6 5');
  webGroup.appendChild(path);
  // fade in/out
  const start = performance.now();
  function anim(){
    const now = performance.now();
    const dt = now - start;
    const p = Math.min(1, dt/duration);
    // ease
    const easeInOut = (p<0.5)?(2*p*p):( -1 + (4 - 2*p)*p );
    path.setAttribute('opacity', String(0.95 * (1 - Math.pow(Math.abs(p-0.5)*2, 1.4))));
    // remove eventually
    if(p<1) requestAnimationFrame(anim);
    else { try{ webGroup.removeChild(path);}catch(e){} }
  }
  playWhoosh();
  requestAnimationFrame(anim);
}

/* persistent swing rope: drawn during swing so web is always visible */
function ensurePersistentWeb(){
  if(!persistentWebPath){
    persistentWebPath = document.createElementNS('http://www.w3.org/2000/svg','path');
    persistentWebPath.setAttribute('stroke','rgba(240,240,255,0.9)');
    persistentWebPath.setAttribute('stroke-width','2.0');
    persistentWebPath.setAttribute('stroke-linecap','round');
    persistentWebPath.setAttribute('fill','none');
    persistentWebPath.setAttribute('stroke-dasharray','6 5');
    webGroup.appendChild(persistentWebPath);
  }
}
function removePersistentWeb(){
  if(persistentWebPath){
    try { webGroup.removeChild(persistentWebPath); } catch(e){}
    persistentWebPath = null;
  }
}
function lineSegsIntersect(ax,ay,bx,by,cx,cy,dx,dy){
  function orient(px,py,qx,qy,rx,ry){ return (qx-px)*(ry-py) - (qy-py)*(rx-px); }
  const o1 = orient(ax,ay,bx,by,cx,cy);
  const o2 = orient(ax,ay,bx,by,dx,dy);
  const o3 = orient(cx,cy,dx,dy,ax,ay);
  const o4 = orient(cx,cy,dx,dy,bx,by);
  if(((o1>0&&o2<0)||(o1<0&&o2>0)) && ((o3>0&&o4<0)||(o3<0&&o4>0))) return true;
  return false;
}
function segmentIntersectsRect(ax,ay,bx,by,rect,margin=16){
  const r = { left: rect.left - margin, top: rect.top - margin, right: rect.right + margin, bottom: rect.bottom + margin };
  // quick reject
  if(Math.max(ax,bx) < r.left || Math.min(ax,bx) > r.right || Math.max(ay,by) < r.top || Math.min(ay,by) > r.bottom){
    return false;
  }
  // edges
  const edges = [
    [r.left, r.top, r.right, r.top],
    [r.right, r.top, r.right, r.bottom],
    [r.right, r.bottom, r.left, r.bottom],
    [r.left, r.bottom, r.left, r.top]
  ];
  for(const e of edges){ if(lineSegsIntersect(ax,ay,bx,by, e[0],e[1],e[2],e[3])) return true; }
  // also check if both points are inside (shouldn't happen for us)
  const inside = (x,y)=> x>r.left && x<r.right && y>r.top && y<r.bottom;
  if(inside(ax,ay) || inside(bx,by)) return true;
  return false;
}

/* obtaining hand tip screen coordinates given spider group transform values:
   our spider's internal hand tip in SVG coordinates: (24, -14) — transform applied later in setSpiderTransform
*/
function handTipPosFor(x,y,rot){
  // rotate point (24,-14) by rot degrees around origin, then translate
  const r = rot * Math.PI/180;
  const hx = 24 * Math.cos(r) - (-14) * Math.sin(r);
  const hy = 24 * Math.sin(r) + (-14) * Math.cos(r);
  return {x: x + hx, y: y + hy};
}

/* Crawl along card edge: pick an edge and move from one corner to the other slowly */
function beginCrawl(){
  const rect = card.getBoundingClientRect();
  const edges = ['top','bottom','left','right'];
  const edge = edges[Math.floor(Math.random()*edges.length)];
  let start, end;
  const margin = 36; // keep spider fully clear of card
  if(edge === 'top'){
    start = {x: rect.left - margin*1.2, y: rect.top - margin};
    end = {x: rect.right + margin*1.2, y: rect.top - margin};
  } else if(edge === 'bottom'){
    start = {x: rect.right + margin*1.2, y: rect.bottom + margin};
    end = {x: rect.left - margin*1.2, y: rect.bottom + margin};
  } else if(edge === 'left'){
    start = {x: rect.left - margin, y: rect.bottom + margin*1.2};
    end = {x: rect.left - margin, y: rect.top - margin*1.2};
  } else {
    start = {x: rect.right + margin, y: rect.top - margin*1.2};
    end = {x: rect.right + margin, y: rect.bottom + margin*1.2};
  }
  return {start, end, edge};
}

/* animation loop */
let lastTime = performance.now();
let crawlPlan = null;
let crawlStartT = 0, crawlDur = 3000 + Math.random()*3000;

function animateLoop(now){
  const t = now/1000;
  const dt = now - lastTime;
  lastTime = now;

  const elapsedSinceSwitch = now - state.lastSwitch;
  // maybe switch behavior occasionally
  if(elapsedSinceSwitch > state.switchEvery){
    state.lastSwitch = now;
    // weighted random: mostly swing, occasionally crawl or shot
    const r = Math.random();
    if(r < 0.55){
      state.mode = 'swing';
      chooseAnchor();
    } else if(r < 0.95){
      state.mode = 'crawl';
      crawlPlan = beginCrawl();
      crawlStartT = now;
      crawlDur = 2600 + Math.random()*3200;
    } else {
      state.mode = 'shot';
      chooseAnchor();
    }
  }

  let x=0,y=0,rot=0;

  if(state.mode === 'swing'){
    const tt = t - state.t0;
    const theta = state.phase + state.thetaAmp * Math.sin(state.omega * tt);
    x = state.anchor.x + state.L * Math.sin(theta);
    y = state.anchor.y + state.L * Math.cos(theta);
    rot = theta * (180/Math.PI) * 0.75;
    // keep in camera: if x/y might exit screen, re-anchor
    if(x < -40 || x > W + 40 || y < -40 || y > H + 40){ chooseAnchor(); }
    // persistent web rope from anchor to hand tip, but don't cross card
    ensurePersistentWeb();
    const hand = handTipPosFor(x,y,rot);
    const rx = (state.anchor.x + hand.x)/2, ry = (state.anchor.y + hand.y)/2 - 16;
    // if line segment crosses card, gently shorten rope by moving anchor along line away from center of card
    const rectNow = card.getBoundingClientRect();
    let ax = state.anchor.x, ay = state.anchor.y, hx = hand.x, hy = hand.y;
    if(segmentIntersectsRect(ax,ay,hx,hy,rectNow,12)){
      const cx = rectNow.left + rectNow.width/2, cy = rectNow.top + rectNow.height/2;
      const vx = ax - cx, vy = ay - cy; const vlen = Math.hypot(vx,vy) || 1;
      ax += (vx / vlen) * 22; ay += (vy / vlen) * 22;
    }
    persistentWebPath.setAttribute('d', `M ${ax} ${ay} Q ${rx} ${ry} ${hx} ${hy}`);
    // occasionally small idle bob
  } else if(state.mode === 'crawl' && crawlPlan){
    const p = Math.min(1, (now - crawlStartT) / crawlDur);
    // eased
    const ep = p < 0.5 ? 2*p*p : -1 + (4 - 2*p)*p;
    x = crawlPlan.start.x + (crawlPlan.end.x - crawlPlan.start.x) * ep;
    y = crawlPlan.start.y + (crawlPlan.end.y - crawlPlan.start.y) * ep;
    // rotation along travel direction
    rot = Math.atan2(crawlPlan.end.y - crawlPlan.start.y, crawlPlan.end.x - crawlPlan.start.x) * 180/Math.PI;
    if(p >= 1) { state.mode = 'swing'; chooseAnchor(); }
  } else if(state.mode === 'shot'){
    // similar to swing but trigger a web shot on start
    const tt = t - state.t0;
    const theta = state.phase + state.thetaAmp * Math.sin(state.omega * tt * 1.1);
    x = state.anchor.x + state.L * Math.sin(theta);
    y = state.anchor.y + state.L * Math.cos(theta);
    rot = theta * (180/Math.PI) * 0.75;
    if(x < -40 || x > W + 40 || y < -40 || y > H + 40){ chooseAnchor(); }
    // trigger web shot only once per mode entry
    if(!state._shotFired){
      state._shotFired = true;
      // compute hand tip and anchor
      const hand = handTipPosFor(x,y,rot);
      // prevent shot crossing the card
      const rectNow = card.getBoundingClientRect();
      let ax = state.anchor.x, ay = state.anchor.y, hx = hand.x, hy = hand.y;
      if(segmentIntersectsRect(ax,ay,hx,hy,rectNow,12)){
        const cx = rectNow.left + rectNow.width/2, cy = rectNow.top + rectNow.height/2;
        const vx = ax - cx, vy = ay - cy; const vlen = Math.hypot(vx,vy) || 1;
        ax += (vx / vlen) * 22; ay += (vy / vlen) * 22;
      }
      drawWeb(ax, ay, hx, hy, 620);
      setTimeout(()=>{ state._shotFired = false; state.mode = 'swing'; chooseAnchor(); }, 700 + Math.random()*600);
    }
  } else {
    // idle fallback
    const tt = t - state.t0;
    x = state.anchor.x + state.L * Math.sin( state.phase + 0.2 * Math.sin(tt*0.8) );
    y = state.anchor.y + state.L * Math.cos( state.phase + 0.2 * Math.sin(tt*0.8) );
    rot = Math.sin(tt*0.8) * 10;
  }

  // Keep spider entirely outside the card (safety clamp): if computed position would be inside card rect, nudge anchor
  const rect = card.getBoundingClientRect();
  if(x > rect.left - 28 && x < rect.right + 28 && y > rect.top - 28 && y < rect.bottom + 28){
    // reposition anchor to safe place
    chooseAnchor();
  }

  setSpiderTransform(x, y, rot);
  if(state.mode !== 'swing'){ removePersistentWeb(); }

  requestAnimationFrame(animateLoop);
}

requestAnimationFrame(animateLoop);

/* nudge function to restart animation flare (called on UI interactions) */
function nudgeSpidey(force=1.0){
  // little visual flare: temporarily increase theta amplitude and maybe trigger a whoosh
  state.thetaAmp = Math.min(1.8, state.thetaAmp + 0.2 * force);
  state.omega = Math.min(2.2, state.omega + 0.12 * force);
  // brief web flicker sometimes for show
  if(Math.random() < 0.18){
    // compute current spider pos for a quick web draw
    // read current transform
    const g = document.getElementById('spidey');
    const tr = g.getAttribute('transform') || 'translate(0,0)';
    // attempt to parse translate(x,y)
    const m = tr.match(/translate\(([-0-9\.]+),\s*([-0-9\.]+)\)\s*rotate\(([-0-9\.]+)\)/);
    let sx=0, sy=0, rot=0;
    if(m){ sx = parseFloat(m[1]); sy = parseFloat(m[2]); rot = parseFloat(m[3]); }
    const hand = handTipPosFor(sx, sy, rot);
    drawWeb(state.anchor.x, state.anchor.y, hand.x, hand.y, 420);
  }
}

/* initial gentle nudge */
setTimeout(()=> nudgeSpidey(0.6), 900);

/* ensure SVG spider group exists in DOM before animation uses it */
(function ensureSpiderPlaced(){
  // initial placement: place off to left/top until chooseAnchor runs
  const g = document.getElementById('spidey');
  if(!g) return;
  // place offscreen then choose anchor
  setSpiderTransform(-200,-200,0);
  chooseAnchor(true);
})();

</script>
</body>
</html>
""")

def write_and_serve():
    tmpdir = tempfile.mkdtemp(prefix="spidey_demo_")
    filename = "spiderman_spideypass.html"
    path = os.path.join(tmpdir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(HTML)
    port = 0  # 0 => pick free port
    os.chdir(tmpdir)
    handler = SimpleHTTPRequestHandler
    # ThreadingHTTPServer for concurrent handling (and allow_reuse_address default True)
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    sa = server.socket.getsockname()
    url = f"http://127.0.0.1:{sa[1]}/{filename}"
    print("Serving demo at:", url)
    print("Open the URL in your browser (it should open automatically). Press Ctrl+C to stop the server.")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        server.shutdown()

if __name__ == "__main__":
    write_and_serve()
