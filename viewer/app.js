/* Viewer for the Freenove 4WD car and its electronics-bay cover.
 *
 * The car is car.glb, tessellated from Freenove's FNK0043 STEP by
 * tools/step2glb.py. STEP AP203 carries no colour, so every part arrives
 * untextured and gets one neutral material here.
 *
 * The cover is loaded from ../cover/freenove-top-cover.stl — THE SAME FILE the
 * printer gets. Nothing is re-modelled for the viewer, so what you rotate here
 * cannot drift from what you print.
 */

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

// Measured from the STEP; see cover/build_cover.py.
const DECK_Y = 0.0;          // deck top, in the car model's own coordinates
const STANDOFFS = [[24.5, 10.1], [-24.5, 10.1], [24.5, -47.9], [-24.5, -47.9]];
const STANDOFF_TOP = 15.75;
const CAM_SWEEP_R = 32.9, CAM_SWEEP_Z = 90.0;

const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
document.body.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x14161a);
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;

const camera = new THREE.PerspectiveCamera(38, innerWidth / innerHeight, 1, 8000);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.06;
controls.autoRotateSpeed = 0.9;
controls.autoRotate = true;

const key = new THREE.DirectionalLight(0xffffff, 2.4);
key.position.set(230, 340, 200);
key.castShadow = true;
key.shadow.mapSize.set(2048, 2048);
key.shadow.bias = -0.0012;
scene.add(key, new THREE.AmbientLight(0xffffff, 0.3));

/* The car model is recentred on load; the cover, the standoff markers and the
 * sweep envelope all live in the car's ORIGINAL coordinates, so they share one
 * parent that carries the same offset. Nothing gets positioned twice. */
const carFrame = new THREE.Group();
scene.add(carFrame);

let robot = null, cover = null, dims = null;
let standoffGroup = null, sweepGroup = null;

const loader = new GLTFLoader();
loader.load('./car.glb', (gltf) => {
  robot = gltf.scene;
  // OpenCASCADE models in mm; glTF's unit is the metre, so RWGltf_CafWriter
  // divides by 1000 on export. Undo it — every number here is in mm.
  robot.scale.setScalar(1000);
  robot.updateMatrixWorld(true);

  const neutral = new THREE.MeshPhysicalMaterial({
    color: 0xb9bec7, roughness: 0.42, metalness: 0.22, clearcoat: 0.2,
  });
  robot.traverse((o) => {
    if (!o.isMesh) return;
    o.material = neutral; o.castShadow = true; o.receiveShadow = true;
  });

  const box = new THREE.Box3().setFromObject(robot);
  const size = box.getSize(new THREE.Vector3());
  const centre = box.getCenter(new THREE.Vector3());
  dims = { w: size.x, h: size.y, l: size.z, floorY: box.min.y };

  carFrame.position.set(-centre.x, -box.min.y, -centre.z);
  carFrame.add(robot);
  robot.position.set(0, 0, 0);

  document.getElementById('dims').textContent =
    `car ${size.x.toFixed(0)} × ${size.z.toFixed(0)} × ${size.y.toFixed(0)} mm · deck at `
    + `${(DECK_Y - box.min.y).toFixed(1)} mm · 244 parts from Freenove's STEP`;

  buildFloor(size);
  buildStandoffs();
  buildSweep();
  loadCover();
  frameView();
  document.getElementById('loading').classList.add('gone');
}, (e) => {
  if (e.total) document.getElementById('loading').textContent =
    `loading the car — ${Math.round((e.loaded / e.total) * 100)}%`;
}, (err) => {
  document.getElementById('loading').textContent = 'could not load car.glb';
  console.error(err);
});

function loadCover() {
  new STLLoader().load('../cover/freenove-top-cover.stl', (geom) => {
    // The STL is in CadQuery space: x = width, y = length, z = height. The car
    // frame is x = width, y = height, z = length. Swapping y and z is a
    // reflection, so it is applied as a real rotation pair — roll -90 then yaw
    // 180 — which lands correctly because the cover is mirror-symmetric.
    // test_16 in the cover suite asserts that symmetry, so this stays honest.
    const mat = new THREE.MeshPhysicalMaterial({
      color: 0x4f9bf5, roughness: 0.55, metalness: 0.0,
      clearcoat: 0.5, transparent: true, opacity: 0.78,
    });
    cover = new THREE.Mesh(geom, mat);
    cover.rotation.x = -Math.PI / 2;
    cover.rotation.z = Math.PI;
    cover.castShadow = true;
    carFrame.add(cover);
    applyCoverUI();
  }, undefined, (err) => {
    document.getElementById('note').textContent =
      'cover STL not found — run cover/build_cover.py';
    console.error(err);
  });
}

function buildFloor(size) {
  const r = Math.max(size.x, size.z);
  const grid = new THREE.GridHelper(r * 6, 48, 0x39404c, 0x262b33);
  grid.material.transparent = true; grid.material.opacity = 0.65;
  scene.add(grid);
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(r * 6, r * 6),
    new THREE.ShadowMaterial({ opacity: 0.34 }));
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = 0.2;
  floor.receiveShadow = true;
  scene.add(floor);
}

function buildStandoffs() {
  // The four the cover bolts to. Their tops measured 15.75 mm on all four,
  // spread 0.00 — which is why a 4-point mount is possible at all.
  standoffGroup = new THREE.Group();
  standoffGroup.visible = false;
  const mat = new THREE.MeshBasicMaterial({ color: 0xffc46b });
  for (const [x, z] of STANDOFFS) {
    const m = new THREE.Mesh(
      new THREE.CylinderGeometry(2.31, 2.31, STANDOFF_TOP, 20), mat);
    m.position.set(x, DECK_Y + STANDOFF_TOP / 2, z);
    standoffGroup.add(m);
  }
  carFrame.add(standoffGroup);
}

function buildSweep() {
  // What the camera head sweeps when it pans. The cover's front face must stay
  // out of this; it stops 5.7 mm short.
  sweepGroup = new THREE.Group();
  sweepGroup.visible = false;
  const m = new THREE.Mesh(
    new THREE.CylinderGeometry(CAM_SWEEP_R, CAM_SWEEP_R, 26, 48, 1, true),
    new THREE.MeshBasicMaterial({
      color: 0x7fb2ff, transparent: true, opacity: 0.18,
      side: THREE.DoubleSide, depthWrite: false,
    }));
  m.position.set(0, DECK_Y + 58, CAM_SWEEP_Z);
  sweepGroup.add(m);
  carFrame.add(sweepGroup);
}

function frameView() {
  const r = Math.max(dims.w, dims.l, dims.h);
  camera.position.set(r * 1.3, r * 0.85, r * 1.7);
  controls.target.set(0, dims.h * 0.3, 0);
  controls.update();
}

/* ---- UI ---- */

function applyCoverUI() {
  if (!cover) return;
  cover.visible = document.getElementById('shell').checked;
  const v = Number(document.getElementById('op').value) / 100;
  cover.material.opacity = v;
  cover.material.transparent = v < 1;
  cover.material.depthWrite = v > 0.92;
  cover.position.y = Number(document.getElementById('lift').value);
}

const on = (id, ev, fn) => document.getElementById(id).addEventListener(ev, fn);
on('shell', 'change', applyCoverUI);
on('op', 'input', (e) => {
  document.getElementById('opv').textContent = `${e.target.value}%`;
  applyCoverUI();
});
on('lift', 'input', (e) => {
  document.getElementById('liftv').textContent = `${e.target.value} mm`;
  applyCoverUI();
});
on('bot', 'change', (e) => { if (robot) robot.visible = e.target.checked; });
on('mounts', 'change', (e) => { if (standoffGroup) standoffGroup.visible = e.target.checked; });
on('sweep', 'change', (e) => { if (sweepGroup) sweepGroup.visible = e.target.checked; });
on('spin', 'change', (e) => { controls.autoRotate = e.target.checked; });
on('reset', 'click', () => { if (dims) frameView(); });
on('shot', 'click', () => {
  renderer.render(scene, camera);
  const a = document.createElement('a');
  a.download = 'freenove-cover.png';
  a.href = renderer.domElement.toDataURL('image/png');
  a.click();
});

addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});

renderer.setAnimationLoop(() => {
  controls.update();
  renderer.render(scene, camera);
});
