import * as THREE from "three";

type Options = {
  working: boolean;
  reduced: boolean;
  activity: () => string;
  onReady: () => void;
  onUnavailable: () => void;
};

/** Procedural models: no downloaded assets, tracking, or model requests. */
export function mountBees(host: HTMLElement, options: Options) {
  const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: "low-power" });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
  renderer.setClearColor(0x000000, 0);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  host.appendChild(renderer.domElement);
  const scene = new THREE.Scene();
  const camera = new THREE.OrthographicCamera(-3, 3, 1.8, -1.8, .1, 30);
  camera.position.set(0, 1.3, 9);
  camera.lookAt(0, 0, 0);
  scene.add(new THREE.HemisphereLight(0xfffcf1, 0x7d552d, 2.7));
  const key = new THREE.DirectionalLight(0xfff1cd, 3.8);
  key.position.set(-3, 6, 6); scene.add(key);
  const rim = new THREE.DirectionalLight(0xffffff, 2.5);
  rim.position.set(3, 2, -3); scene.add(rim);
  const geometries = new Set<THREE.BufferGeometry>();
  const materials = new Set<THREE.Material>();
  const textures = new Set<THREE.Texture>();
  const sphere = new THREE.SphereGeometry(1, 32, 24); geometries.add(sphere);
  function material(color: string, roughness = .4, metalness = .08) {
    const value = new THREE.MeshStandardMaterial({ color, roughness, metalness });
    materials.add(value); return value;
  }
  const gold = material("#e8a62b", .32, .2);
  const dark = material("#30291f", .3, .15);
  const eye = material("#131615", .12, .1);
  const white = material("#fffdf1", .2);
  const wingMaterial = new THREE.MeshStandardMaterial({
    color: "#fffaf0", transparent: true, opacity: .72,
    metalness: .15, roughness: .2, side: THREE.DoubleSide, depthWrite: false,
  });
  materials.add(wingMaterial);
  const stripeCanvas = document.createElement("canvas");
  stripeCanvas.width = 256; stripeCanvas.height = 256;
  const ctx = stripeCanvas.getContext("2d")!;
  ctx.fillStyle = "#e5a522"; ctx.fillRect(0, 0, 256, 256);
  ctx.fillStyle = "#332a20";
  ctx.fillRect(0, 65, 256, 32); ctx.fillRect(0, 131, 256, 33); ctx.fillRect(0, 199, 256, 35);
  const stripes = new THREE.CanvasTexture(stripeCanvas); stripes.colorSpace = THREE.SRGBColorSpace; textures.add(stripes);
  const abdomenMaterial = new THREE.MeshStandardMaterial({ map: stripes, roughness: .35, metalness: .12 });
  materials.add(abdomenMaterial);

  function ellipsoid(parent: THREE.Object3D, mat: THREE.Material, pos: number[], scale: number[]) {
    const mesh = new THREE.Mesh(sphere, mat);
    mesh.position.set(pos[0], pos[1], pos[2]); mesh.scale.set(scale[0], scale[1], scale[2]);
    parent.add(mesh); return mesh;
  }
  function tube(parent: THREE.Object3D, points: THREE.Vector3[], radius = .025) {
    const geometry = new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points), 12, radius, 6, false);
    geometries.add(geometry); const mesh = new THREE.Mesh(geometry, dark); parent.add(mesh);
  }
  function createBee() {
    const bee = new THREE.Group();
    const body = ellipsoid(bee, abdomenMaterial, [.15, 0, 0], [.7, .43, .45]);
    body.rotation.z = Math.PI / 2; body.scale.set(.43, .7, .45);
    ellipsoid(bee, gold, [-.4, .04, .015], [.36, .36, .36]);
    ellipsoid(bee, gold, [-.74, .10, .02], [.33, .32, .32]);
    for (const z of [-.26, .28]) {
      ellipsoid(bee, eye, [-.85, .17, z], [.12, .145, .065]);
      ellipsoid(bee, white, [-.88, .21, z + (z > 0 ? .05 : -.05)], [.035, .043, .02]);
      tube(bee, [new THREE.Vector3(-.85, .32, z*.55), new THREE.Vector3(-1.0, .58, z*.7), new THREE.Vector3(-.91, .72, z*.85)]);
      ellipsoid(bee, dark, [-.91, .72, z*.85], [.055, .055, .055]);
    }
    for (const x of [-.3, .05, .38]) for (const sign of [-1, 1]) {
      tube(bee, [new THREE.Vector3(x, -.23, sign*.18), new THREE.Vector3(x+.13, -.49, sign*.31), new THREE.Vector3(x-.01, -.6, sign*.42)], .021);
    }
    const wings: THREE.Group[] = [];
    for (const sign of [-1, 1]) {
      const hinge = new THREE.Group(); hinge.position.set(-.18, .29, sign * .12);
      const wing = ellipsoid(hinge, wingMaterial, [.16, .4, sign*.22], [.25, .62, .033]);
      wing.rotation.z = -.38; wing.rotation.x = sign * .5;
      bee.add(hinge); wings.push(hinge);
    }
    const stingerGeometry = new THREE.ConeGeometry(.08, .22, 10); geometries.add(stingerGeometry);
    const stinger = new THREE.Mesh(stingerGeometry, dark); stinger.rotation.z = -Math.PI/2; stinger.position.set(.86, 0, 0); bee.add(stinger);
    scene.add(bee);
    return { bee, wings };
  }

  // Three shallow hexagonal work cells give the bees a purposeful destination.
  const cells = new THREE.Group(); cells.rotation.x = -.28; cells.position.set(.2, -.5, -.7);
  const cellMat = material("#e7bd6a", .38, .35);
  const cellGeometry = new THREE.CylinderGeometry(.46, .46, .075, 6); geometries.add(cellGeometry);
  const insetGeometry = new THREE.CylinderGeometry(.37, .37, .08, 6); geometries.add(insetGeometry);
  const insetMat = material("#fff1cf", .7, .02);
  for (const [x, y] of [[-.83, 0], [0, .48], [.83, 0]]) {
    const cell = new THREE.Mesh(cellGeometry, cellMat); cell.rotation.x = Math.PI/2; cell.rotation.y = Math.PI/6; cell.position.set(x,y,0); cells.add(cell);
    const inset = new THREE.Mesh(insetGeometry, insetMat); inset.rotation.copy(cell.rotation); inset.position.set(x,y,.045); cells.add(inset);
  }
  scene.add(cells);
  const bees = [createBee(), createBee(), createBee()];
  const base = [[-.35,.3,.3, .9], [1.28,.2,-.3,.5], [-1.45,-.05,-.5,.4]];
  let frame = 0; let visible = true; let lost = false; let disposed = false; let last = 0; let time = 0;
  const target = new THREE.Vector2(); const eased = new THREE.Vector2();
  function draw(t: number) {
    const moving = !options.reduced;
    const task = [...options.activity()].reduce((n,c)=>n+c.charCodeAt(0),0) % 7;
    eased.lerp(target, .035);
    bees.forEach(({bee,wings}, i) => {
      const [x,y,z,scale] = base[i];
      const phase = t * (options.working ? 1.15 : .65) + i * 2.1;
      const flutter = moving ? Math.sin(t * 35 + i) : .3;
      bee.position.set(x + (moving ? Math.sin(phase)*.12 : 0) + eased.x*.1,
        y + (moving ? Math.sin(phase*1.5)*.1 : 0), z);
      bee.rotation.set(.04 + eased.y*.06, -.3 + (moving ? Math.sin(phase*.65)*.15 : 0),
        -.12 + (moving ? Math.sin(phase)*.06 : 0));
      bee.scale.setScalar(scale);
      wings[0].rotation.x = -.3 + flutter*.55;
      wings[1].rotation.x = .3 - flutter*.55;
      if (options.working && i === 0) bee.rotation.z += Math.sin(task)*.05;
    });
    renderer.render(scene, camera);
  }
  function animate(now: number) {
    frame = 0;
    if (disposed || !visible || document.hidden || lost || options.reduced) return;
    if (now-last >= 1000/45) {
      time += Math.min((now-last)/1000, .05); last=now; draw(time);
    }
    frame = requestAnimationFrame(animate);
  }
  function resume() {
    if (!frame && visible && !document.hidden && !lost && !options.reduced) {
      last = performance.now(); frame = requestAnimationFrame(animate);
    }
  }
  function resize() {
    const {width,height} = host.getBoundingClientRect();
    if (!width || !height) return;
    renderer.setSize(width,height);
    const aspect=width/height; camera.left=-1.65*aspect; camera.right=1.65*aspect;
    camera.top=1.65; camera.bottom=-1.65; camera.updateProjectionMatrix(); draw(time);
  }
  const size = new ResizeObserver(resize); size.observe(host);
  const visibility = new IntersectionObserver(([entry]) => { visible=entry.isIntersecting; if (visible) resume(); else { cancelAnimationFrame(frame); frame=0; } });
  visibility.observe(host);
  function pageVisibility() { if (document.hidden) {cancelAnimationFrame(frame);frame=0;} else resume(); }
  function pointer(event: PointerEvent) {
    const r=host.getBoundingClientRect();
    target.set(((event.clientX-r.left)/r.width-.5)*2, ((event.clientY-r.top)/r.height-.5)*2);
  }
  function resetPointer() { target.set(0,0); }
  function contextLost(event: Event) { event.preventDefault(); lost=true;cancelAnimationFrame(frame);frame=0;options.onUnavailable(); }
  function contextRestored() { lost=false; resize();options.onReady();resume(); }
  document.addEventListener("visibilitychange",pageVisibility);
  host.addEventListener("pointermove",pointer); host.addEventListener("pointerleave",resetPointer);
  renderer.domElement.addEventListener("webglcontextlost",contextLost);
  renderer.domElement.addEventListener("webglcontextrestored",contextRestored);
  resize(); options.onReady(); resume();
  return () => {
    disposed=true; cancelAnimationFrame(frame); size.disconnect(); visibility.disconnect();
    document.removeEventListener("visibilitychange",pageVisibility);
    host.removeEventListener("pointermove",pointer);host.removeEventListener("pointerleave",resetPointer);
    renderer.domElement.removeEventListener("webglcontextlost",contextLost);
    renderer.domElement.removeEventListener("webglcontextrestored",contextRestored);
    geometries.forEach(g=>g.dispose()); materials.forEach(m=>m.dispose()); textures.forEach(t=>t.dispose());
    renderer.dispose(); renderer.domElement.remove();
  };
}
