// THE AWAKENER — walkable Ayodhya, three.js, wired live to the narrative engine.
// The world RENDERS what the brain returns; it invents no lore. Aesthetic follows
// ART_DIRECTION.md: lit from within, gold as the body of consciousness.

import * as THREE from 'three';

const API = (location.port === '8000')
  ? '/api/game'                          // served by serve_slice (same origin)
  : 'http://localhost:8000/api/game';    // dev: client elsewhere, brain on :8000

// ---------- engine bridge ----------------------------------------------------
async function brainGET(path) {
  try { const r = await fetch(API + path); return r.ok ? r.json() : null; }
  catch (e) { return null; }
}
async function brainPOST(path, body) {
  try {
    const r = await fetch(API + path, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    return r.ok ? r.json() : null;
  } catch (e) { return null; }
}

// ---------- scene setup ------------------------------------------------------
const app = document.getElementById('app');
const scene = new THREE.Scene();
scene.fog = new THREE.FogExp2(0x2a1a30, 0.012);

const camera = new THREE.PerspectiveCamera(58, innerWidth / innerHeight, 0.1, 500);
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(innerWidth, innerHeight);
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.15;
app.appendChild(renderer.domElement);

// ---------- the light beyond light (corpus aesthetic) ------------------------
// a warm sourceless radiance from above — "the brilliance that illuminates all"
const hemi = new THREE.HemisphereLight(0xffe9b0, 0x3a2418, 0.9);
scene.add(hemi);
// the inner sun — gold key light, soft, casting long dusk shadows
const sun = new THREE.DirectionalLight(0xffcf76, 2.1);
sun.position.set(40, 55, -30);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
sun.shadow.camera.near = 1; sun.shadow.camera.far = 200;
sun.shadow.camera.left = -80; sun.shadow.camera.right = 80;
sun.shadow.camera.top = 80; sun.shadow.camera.bottom = -80;
scene.add(sun);
// a faint golden fill so nothing reads as cold/grimdark
scene.add(new THREE.AmbientLight(0xffd98a, 0.25));

// gradient sky dome (violet-umber ground for the brilliance)
{
  const sky = new THREE.Mesh(
    new THREE.SphereGeometry(250, 32, 16),
    new THREE.ShaderMaterial({
      side: THREE.BackSide,
      uniforms: { top: { value: new THREE.Color(0x2a1a3e) }, bot: { value: new THREE.Color(0xe0903a) } },
      vertexShader: `varying vec3 v; void main(){ v=position; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.); }`,
      fragmentShader: `varying vec3 v; uniform vec3 top; uniform vec3 bot;
        void main(){ float h=normalize(v).y*0.5+0.5; gl_FragColor=vec4(mix(bot,top,smoothstep(0.0,0.7,h)),1.); }`,
    }));
  scene.add(sky);
}
// the inner sun, drawn as a glowing disc
{
  const g = new THREE.Mesh(new THREE.CircleGeometry(14, 32),
    new THREE.MeshBasicMaterial({ color: 0xfff3cf, transparent: true, opacity: 0.92 }));
  g.position.copy(sun.position).multiplyScalar(2.2); g.lookAt(0, 0, 0); scene.add(g);
  const halo = new THREE.Mesh(new THREE.CircleGeometry(30, 32),
    new THREE.MeshBasicMaterial({ color: 0xffe49a, transparent: true, opacity: 0.18 }));
  halo.position.copy(g.position); halo.lookAt(0, 0, 0); scene.add(halo);
}

// ---------- the ground + the Sarayu ------------------------------------------
const GROUND = 200;
{
  const ground = new THREE.Mesh(
    new THREE.PlaneGeometry(GROUND, GROUND),
    new THREE.MeshStandardMaterial({ color: 0x6b4a2c, roughness: 0.95 }));
  ground.rotation.x = -Math.PI / 2; ground.receiveShadow = true; scene.add(ground);

  // the Sarayu — a band of gold-catching water across the far side
  const river = new THREE.Mesh(
    new THREE.PlaneGeometry(GROUND, 34),
    new THREE.MeshStandardMaterial({ color: 0xc99a4e, roughness: 0.25, metalness: 0.6,
      emissive: 0x4a2e10, emissiveIntensity: 0.4 }));
  river.rotation.x = -Math.PI / 2; river.position.set(0, 0.02, -52); river.receiveShadow = true;
  scene.add(river);
}

// ---------- Ayodhya — tiered gold city on the far bank -----------------------
// [REASONED EXTENSION per ART_DIRECTION.md — the silhouette is composed in the
//  corpus register; texts assert golden/prosperous, not the exact form.]
function shikhara(x, z, base, h) {
  const g = new THREE.Group();
  const body = new THREE.Mesh(new THREE.BoxGeometry(base, h, base),
    new THREE.MeshStandardMaterial({ color: 0xb9763e, roughness: 0.6, metalness: 0.2 }));
  body.position.y = h / 2; body.castShadow = body.receiveShadow = true; g.add(body);
  const spire = new THREE.Mesh(new THREE.ConeGeometry(base * 0.62, h * 0.5, 4),
    new THREE.MeshStandardMaterial({ color: 0xf2c879, roughness: 0.3, metalness: 0.7,
      emissive: 0xffce6e, emissiveIntensity: 0.45 }));
  spire.position.y = h + h * 0.25; spire.rotation.y = Math.PI / 4; spire.castShadow = true; g.add(spire);
  const finial = new THREE.Mesh(new THREE.SphereGeometry(base * 0.13, 12, 12),
    new THREE.MeshStandardMaterial({ color: 0xfff0c4, emissive: 0xffe49a, emissiveIntensity: 0.8 }));
  finial.position.y = h + h * 0.5 + base * 0.1; g.add(finial);
  g.position.set(x, 0, z); scene.add(g);
}
// a skyline of shikharas across the far bank, tiered
const skyline = [
  [-34, -70, 9, 16], [-22, -74, 7, 22], [-10, -72, 8, 28], [2, -76, 9, 34],
  [14, -73, 7, 26], [26, -75, 8, 20], [38, -71, 9, 15], [-46, -69, 8, 13],
  [50, -70, 7, 17],
];
skyline.forEach(([x, z, b, h]) => shikhara(x, z, b, h));

// the near-bank courtyard the player walks: a low gold-railed plaza
{
  const plaza = new THREE.Mesh(new THREE.CircleGeometry(22, 48),
    new THREE.MeshStandardMaterial({ color: 0x8a6a3c, roughness: 0.7, metalness: 0.3,
      emissive: 0x2a1c08, emissiveIntensity: 0.3 }));
  plaza.rotation.x = -Math.PI / 2; plaza.position.y = 0.03; plaza.receiveShadow = true; scene.add(plaza);
  // ring of low pillars
  for (let i = 0; i < 12; i++) {
    const a = (i / 12) * Math.PI * 2;
    const p = new THREE.Mesh(new THREE.CylinderGeometry(0.4, 0.5, 3, 10),
      new THREE.MeshStandardMaterial({ color: 0xe0b060, roughness: 0.4, metalness: 0.5,
        emissive: 0xffce6e, emissiveIntensity: 0.25 }));
    p.position.set(Math.cos(a) * 20, 1.5, Math.sin(a) * 20); p.castShadow = true; scene.add(p);
  }
}

// ---------- the player (third-person) ----------------------------------------
const player = new THREE.Group();
{
  const body = new THREE.Mesh(new THREE.CapsuleGeometry(0.5, 1.1, 6, 12),
    new THREE.MeshStandardMaterial({ color: 0xe8dcc0, roughness: 0.7 }));
  body.position.y = 1.3; body.castShadow = true; player.add(body);
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.42, 16, 16),
    new THREE.MeshStandardMaterial({ color: 0xcaa878, roughness: 0.6 }));
  head.position.y = 2.5; head.castShadow = true; player.add(head);
}
player.position.set(0, 0, 8); scene.add(player);

// ---------- NPCs from the brain ----------------------------------------------
const npcMeshes = [];   // { group, name, kind, glow }
function makeNPC(name, kind, x, z) {
  const g = new THREE.Group();
  const body = new THREE.Mesh(new THREE.CapsuleGeometry(0.5, 1.1, 6, 12),
    new THREE.MeshStandardMaterial({ color: 0xb98a4a, roughness: 0.5, metalness: 0.3,
      emissive: 0xffce6e, emissiveIntensity: 0.35 }));   // golden aura — the Time-Conscious
  body.position.y = 1.3; body.castShadow = true; g.add(body);
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.42, 16, 16),
    new THREE.MeshStandardMaterial({ color: 0xd0a878, roughness: 0.5 }));
  head.position.y = 2.5; g.add(head);
  // a soft halo ring above — corpus-literal golden aura
  const halo = new THREE.Mesh(new THREE.TorusGeometry(0.5, 0.05, 8, 24),
    new THREE.MeshBasicMaterial({ color: 0xffe49a, transparent: true, opacity: 0.7 }));
  halo.rotation.x = Math.PI / 2; halo.position.y = 3.1; g.add(halo);
  g.position.set(x, 0, z); scene.add(g);
  npcMeshes.push({ group: g, name, kind, halo });
}

// ---------- controls ---------------------------------------------------------
const keys = {};
addEventListener('keydown', e => keys[e.code] = true);
addEventListener('keyup', e => keys[e.code] = false);
let yaw = 0, pitch = 0.15, locked = false;
renderer.domElement.addEventListener('click', () => renderer.domElement.requestPointerLock());
document.addEventListener('pointerlockchange', () => locked = document.pointerLockElement === renderer.domElement);
addEventListener('mousemove', e => {
  if (!locked) return;
  yaw -= e.movementX * 0.0024;
  pitch = Math.max(-0.3, Math.min(0.6, pitch - e.movementY * 0.0024));
});

// ---------- interaction: approach a being -> its saga ------------------------
let nearNPC = null, panelOpen = false;
const panel = document.getElementById('panel');

function strandHTML(title, edges) {
  if (!edges || !edges.length) return '';
  const rows = edges.slice(0, 5).map(e =>
    `<div class="edge">${e.subject} <span class="rel">${e.relation.replace(/_/g, ' ')}</span> ${e.object}</div>`
  ).join('');
  return `<div class="strand"><h3>${title}</h3>${rows}</div>`;
}

async function openSaga(name, kind) {
  panel.classList.add('open'); panelOpen = true;
  document.getElementById('p-name').textContent = name;
  document.getElementById('p-kind').textContent = kind || '';
  document.getElementById('p-headline').textContent = 'consulting the texts…';
  document.getElementById('p-strands').innerHTML = '';
  document.getElementById('fightlog').innerHTML = '';

  const r = await brainPOST('/saga', { name });
  if (!r || !r.success) {
    document.getElementById('p-headline').textContent = 'The texts are silent on this one.';
    return;
  }
  const d = r.data, s = d.strands;
  document.getElementById('p-headline').textContent = d.headline;
  document.getElementById('p-strands').innerHTML =
    strandHTML('what they are', s.identity) +
    strandHTML('weapons', s.weapons) +
    strandHTML('vows & curses', s.vows_and_curses) +
    strandHTML('lineage', s.lineage) +
    strandHTML('deeds', s.deeds);
  // any character can be a sparring partner for the astra demo
  document.getElementById('p-fight').style.display = 'block';
  window._foe = name;
}
window.closePanel = () => { panel.classList.remove('open'); panelOpen = false; };

// combat — true to the texts, with the canon/draft honesty rendered
window.fight = async (astra, action) => {
  const log = document.getElementById('fightlog');
  log.innerHTML = 'the astra flies…';
  const r = await brainPOST('/combat/encounter',
    { astra, defender: window._foe || 'a foe', defender_action: action });
  if (!r || !r.success) { log.innerHTML = 'the engine did not answer.'; return; }
  const d = r.data, res = d.resolution;
  const banner = d.is_canon
    ? '<span class="canon">✦ CANON</span>'
    : '<span class="draft">◌ EARLY DRAFT</span>';
  let html = `<b>${astra}</b> → <b>${res.outcome}</b><br>${res.reason || ''}<br>${banner} · grounding: ${d.grounding.confidence}`;
  (d.draft_warnings || []).forEach(w =>
    html += `<span class="warn">${w.severity === 'blocking' ? '⚠' : '·'} ${w.message}</span>`);
  log.innerHTML = html;
};

// ---------- boot: connect, load the scene ------------------------------------
async function boot() {
  const conn = document.getElementById('connlabel');
  const dot = document.querySelector('#conn .dot');
  const health = await brainGET('/meta/health');
  if (health && health.success) {
    conn.textContent = `brain online · ${health.data.n_entities} entities`;
    dot.style.background = '#9ad29a';
  } else {
    conn.textContent = 'brain offline — run serve_slice';
    dot.style.background = '#d27a7a';
  }

  // who is in Ayodhya? — the brain decides, we render
  const sc = await brainPOST('/scene', { location: 'Ayodhya' });
  if (sc && sc.success) {
    const npcs = sc.data.surroundings.npcs || [];
    npcs.slice(0, 8).forEach((n, i) => {
      const a = (i / Math.max(npcs.length, 1)) * Math.PI * 2;
      makeNPC(n.name, n.kind, Math.cos(a) * 11, Math.sin(a) * 11 - 2);
    });
    if (!npcs.length) makeNPC('Dasharatha', 'king', 0, -4); // fallback so the plaza isn't empty
  } else {
    makeNPC('Dasharatha', 'king', 0, -4);
  }

  document.getElementById('loading').classList.add('gone');
}

// ---------- loop -------------------------------------------------------------
const clock = new THREE.Clock();
function tick() {
  requestAnimationFrame(tick);
  const dt = Math.min(clock.getDelta(), 0.05);

  // movement relative to facing
  const speed = 7 * dt;
  const fwd = new THREE.Vector3(-Math.sin(yaw), 0, -Math.cos(yaw));
  const right = new THREE.Vector3(Math.cos(yaw), 0, -Math.sin(yaw));
  const move = new THREE.Vector3();
  if (keys['KeyW']) move.add(fwd);
  if (keys['KeyS']) move.sub(fwd);
  if (keys['KeyD']) move.add(right);
  if (keys['KeyA']) move.sub(right);
  if (move.lengthSq() > 0) {
    move.normalize().multiplyScalar(speed);
    player.position.add(move);
    const r = 26; // keep on the near bank / plaza
    player.position.x = Math.max(-r, Math.min(r, player.position.x));
    player.position.z = Math.max(-r, Math.min(r + 6, player.position.z));
    player.rotation.y = Math.atan2(move.x, move.z);
  }

  // third-person camera
  const camDist = 7, camH = 4;
  const cx = player.position.x + Math.sin(yaw) * camDist;
  const cz = player.position.z + Math.cos(yaw) * camDist;
  camera.position.set(cx, player.position.y + camH + pitch * 4, cz);
  camera.lookAt(player.position.x, player.position.y + 2, player.position.z);

  // proximity to NPCs -> open their saga
  let closest = null, cd = 4.5;
  for (const n of npcMeshes) {
    n.halo.rotation.z += dt * 0.6;
    n.group.lookAt(player.position.x, n.group.position.y, player.position.z);
    const d = n.group.position.distanceTo(player.position);
    if (d < cd) { cd = d; closest = n; }
  }
  if (closest && closest !== nearNPC) {
    nearNPC = closest;
    openSaga(closest.name, closest.kind);
  } else if (!closest && nearNPC && panelOpen) {
    nearNPC = null; closePanel();
  }

  renderer.render(scene, camera);
}

addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});

boot();
tick();
