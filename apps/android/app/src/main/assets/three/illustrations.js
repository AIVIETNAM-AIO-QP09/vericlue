import * as THREE from './vendor/three.module.min.js';

export const SCENES = Object.freeze(['card', 'face', 'eyes', 'turn', 'voice', 'privacy', 'success', 'backdrop']);
const clamp = value => Math.max(0, Math.min(1, value));
const ease = value => 1 - Math.pow(1 - clamp(value), 3);
const smooth = value => { const p = clamp(value); return p * p * (3 - 2 * p); };
const arrive = value => {
  const p = clamp(value) - 1;
  return 1 + 2.15 * p * p * p + 1.15 * p * p;
};

// Original procedural sculptures. Each instance owns and releases all its GPU resources.
export function createIllustration(mode, dark) {
  const root = new THREE.Group(), body = new THREE.Group(), resources = new Set();
  root.add(body);
  const keep = value => { resources.add(value); return value; };
  const material = (color, metalness = 0.15, roughness = 0.32) => keep(new THREE.MeshStandardMaterial({ color, metalness, roughness }));
  const ivory = material(0xfaf8f5), blue = material(0x246bdf, 0.4), gold = material(0xe2b86e, 0.65);
  const green = material(0x1e8a5a, 0.25), ink = material(0x0c2345), silver = material(0x8db8d2, 0.5);
  const wire = keep(new THREE.MeshBasicMaterial({ color: dark ? 0x8cc8ff : 0x0b5fa5, transparent: true, opacity: 0.55 }));
  const mesh = (geometry, surface, parent = body, x = 0, y = 0, z = 0) => {
    const result = new THREE.Mesh(keep(geometry), surface); result.position.set(x, y, z); parent.add(result); return result;
  };
  const shape = (width, height, radius) => {
    const s = new THREE.Shape(), x = -width / 2, y = -height / 2;
    s.moveTo(x + radius, y); s.lineTo(x + width - radius, y);
    s.quadraticCurveTo(x + width, y, x + width, y + radius); s.lineTo(x + width, y + height - radius);
    s.quadraticCurveTo(x + width, y + height, x + width - radius, y + height); s.lineTo(x + radius, y + height);
    s.quadraticCurveTo(x, y + height, x, y + height - radius); s.lineTo(x, y + radius);
    s.quadraticCurveTo(x, y, x + radius, y); return s;
  };
  const extrude = (s, depth) => new THREE.ExtrudeGeometry(s, { depth, bevelEnabled: true, bevelSize: 0.025,
    bevelThickness: 0.025, bevelSegments: 2, curveSegments: 12 });
  const plate = (w, h, r, d, mat, parent = body, x = 0, y = 0, z = 0) => mesh(extrude(shape(w, h, r), d), mat, parent, x, y, z);
  const sphere = (r, mat, parent = body, x = 0, y = 0, z = 0) => mesh(new THREE.SphereGeometry(r, 24, 16), mat, parent, x, y, z);
  const line = (points, mat, parent = body, radius = 0.025) => mesh(new THREE.TubeGeometry(
    new THREE.CatmullRomCurve3(points.map(p => new THREE.Vector3(...p))), 32, radius, 8, false), mat, parent);
  const orbitGroup = new THREE.Group(); root.add(orbitGroup);
  const orbit = mesh(new THREE.TorusGeometry(1.5, 0.012, 6, 80), wire, orbitGroup, 0, 0, -0.55);
  orbit.scale.y = 0.84;
  let articulate = () => {};

  if (mode === 'card') {
    plate(2.45, 1.55, 0.16, 0.085, ivory);
    const back = plate(2.45, 1.55, 0.16, 0.07, blue, body, 0.12, 0.12, -0.18); back.rotation.z = 0.09;
    plate(0.42, 0.31, 0.05, 0.02, gold, body, -0.77, 0.32, 0.13);
    [1.05, 0.78, 0.9].forEach((width, i) => plate(width, 0.06, 0.025, 0.006, silver, body, -0.39, -0.12 - i * 0.2, 0.13));
    const portrait = mesh(new THREE.CylinderGeometry(0.4, 0.4, 0.09, 40), blue, body, 0.7, 0.12, 0.18);
    portrait.rotation.x = Math.PI / 2;
    sphere(0.105, ivory, body, 0.7, 0.23, 0.25);
    plate(0.38, 0.17, 0.08, 0.02, ivory, body, 0.7, -0.03, 0.25);
    articulate = t => {
      // Separate planes briefly reveal physical depth, then align as a single identity card.
      const reveal = ease((t - 0.12) / 1.05);
      back.position.set(0.12 + 0.24 * (1 - reveal), 0.12 + 0.16 * (1 - reveal), -0.18 - 0.42 * (1 - reveal));
      back.rotation.z = 0.09 + 0.18 * (1 - reveal);
      portrait.scale.setScalar(0.72 + 0.28 * arrive((t - 0.28) / 0.65));
    };
  } else if (['face', 'eyes', 'turn'].includes(mode)) {
    // A stylised mannequin, never a reconstruction of the user's face.
    const head = new THREE.Group(); body.add(head);
    const skull = sphere(0.62, ivory, head, 0, 0.26); skull.scale.set(0.83, 1.12, 0.78);
    const nose = sphere(0.10, ivory, head, 0, 0.19, 0.48); nose.scale.set(0.75, 1.3, 1);
    sphere(0.12, ivory, head, -0.51, 0.26); sphere(0.12, ivory, head, 0.51, 0.26);
    const eyes = [-0.20, 0.20].map(x => sphere(0.046, ink, head, x, 0.40, 0.45));
    line([[-0.13, -0.02, 0.45], [0, -0.05, 0.49], [0.13, -0.02, 0.45]], silver, head, 0.012);
    mesh(new THREE.CylinderGeometry(0.16, 0.22, 0.35, 24), ivory, body, 0, -0.46);
    const shoulders = sphere(0.65, blue, body, 0, -0.89, -0.06); shoulders.scale.set(1.32, 0.48, 0.65);
    const frame = mesh(new THREE.TorusGeometry(1.0, 0.022, 8, 64), wire, root, 0, 0.08, -0.2); frame.scale.set(0.79, 1.22, 1);
    const gaze = sphere(0.07, gold, root, 0, 0.4, 0.9); gaze.visible = mode === 'eyes';
    articulate = t => {
      head.rotation.y = mode === 'turn' ? Math.sin(t * Math.PI * 2 / 3) * 0.55
        : mode === 'face' ? -0.28 * (1 - ease(t / 1.2)) : 0;
      const x = mode === 'eyes' ? Math.sin(t * Math.PI * 2 / 3) * 0.65 : 0;
      gaze.position.x = x;
      eyes.forEach((eye, i) => { eye.position.x = (i ? 0.20 : -0.20) + x * 0.045; });
    };
  } else if (mode === 'voice') {
    plate(0.68, 1.25, 0.32, 0.27, blue, body, 0, 0.3);
    // Repeated grille details and sound bars use instancing, not one draw call each.
    const grille = keep(new THREE.InstancedMesh(keep(new THREE.SphereGeometry(0.022, 8, 6)), ivory, 24));
    body.add(grille);
    const transform = new THREE.Object3D();
    for (let i = 0; i < 24; i++) {
      transform.position.set((i % 4 - 1.5) * 0.11, 0.05 + Math.floor(i / 4) * 0.11, 0.3);
      transform.updateMatrix(); grille.setMatrixAt(i, transform.matrix);
    }
    line([[-0.5, 0.38, 0.08], [-0.5, -0.23, 0.08], [0, -0.48, 0.08], [0.5, -0.23, 0.08], [0.5, 0.38, 0.08]], gold, body, 0.045);
    mesh(new THREE.CylinderGeometry(0.04, 0.04, 0.45, 16), gold, body, 0, -0.7, 0.08);
    plate(0.72, 0.08, 0.035, 0.15, blue, body, 0, -0.96);
    const bars = keep(new THREE.InstancedMesh(keep(new THREE.BoxGeometry(0.045, 1, 0.06)), silver, 20)); body.add(bars);
    bars.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    articulate = t => {
      for (let i = 0; i < 20; i++) {
        const side = i < 10 ? -1 : 1, j = i % 10;
        transform.position.set(side * (0.78 + j * 0.065), 0, -0.1);
        transform.scale.set(1, 0.12 + (Math.sin(t * 2.4 + j * 0.6) + 1) * 0.20, 1);
        transform.updateMatrix(); bars.setMatrixAt(i, transform.matrix);
      }
      bars.instanceMatrix.needsUpdate = true;
    };
  } else if (mode === 'privacy') {
    const shield = new THREE.Shape(); shield.moveTo(0, 1.05);
    shield.lineTo(0.88, 0.7); shield.lineTo(0.73, -0.25); shield.quadraticCurveTo(0.58, -0.77, 0, -1.08);
    shield.quadraticCurveTo(-0.58, -0.77, -0.73, -0.25); shield.lineTo(-0.88, 0.7); shield.closePath();
    mesh(extrude(shield, 0.16), blue);
    const shackle = mesh(new THREE.TorusGeometry(0.25, 0.055, 12, 32, Math.PI), gold, body, 0, 0.24, 0.29);
    plate(0.72, 0.55, 0.1, 0.12, ivory, body, 0, -0.08, 0.23);
    sphere(0.06, ink, body, 0, -0.05, 0.40);
    plate(0.04, 0.12, 0.015, 0.01, ink, body, 0, -0.13, 0.39);
    articulate = t => {
      // The lock settles visibly into place; it is illustration, never a security verdict.
      shackle.position.y = 0.24 + 0.28 * (1 - arrive((t - 0.3) / 0.75));
    };
  } else if (mode === 'success') {
    const seal = mesh(new THREE.CylinderGeometry(0.83, 0.83, 0.18, 64), green); seal.rotation.x = Math.PI / 2;
    mesh(new THREE.TorusGeometry(0.87, 0.035, 10, 64), gold, body, 0, 0, 0.10);
    const check = new THREE.Shape(); check.moveTo(-0.43, 0.0); check.lineTo(-0.12, -0.31);
    check.lineTo(0.47, 0.33); check.lineTo(0.35, 0.45); check.lineTo(-0.13, -0.08); check.lineTo(-0.31, 0.12); check.closePath();
    mesh(extrude(check, 0.04), ivory, body, 0, 0, 0.13);
    const sparks = keep(new THREE.InstancedMesh(keep(new THREE.OctahedronGeometry(0.055)), gold, 16)); root.add(sparks);
    const transform = new THREE.Object3D();
    articulate = t => {
      const reveal = 1 - Math.pow(1 - Math.min(t / 1.4, 1), 3);
      for (let i = 0; i < 16; i++) {
        const angle = i / 16 * Math.PI * 2, radius = 0.95 + reveal * 0.35;
        transform.position.set(Math.cos(angle) * radius, Math.sin(angle) * radius, -0.1);
        transform.scale.setScalar(0.4 + 0.6 * Math.sin(Math.PI * reveal));
        transform.rotation.set(angle, t * 0.2, angle); transform.updateMatrix(); sparks.setMatrixAt(i, transform.matrix);
      }
      sparks.instanceMatrix.needsUpdate = true;
    };
  } else if (mode === 'backdrop') {
    // Full-screen login stage in screen units (width 3.65, y up). Always the navy stage palette.
    // The broken ring repeats the four reflection-challenge colours; it is ornament, not a challenge.
    orbitGroup.visible = false;
    const glass = material(0x3f7ff0, 0.2, 0.16), deep = material(0x1d4fb8, 0.3, 0.24);
    const pill = (w, h, d, surface, x, y, z, turn) => {
      const p = plate(w, h, h / 2 - 0.03, d, surface, body, x, y, z); p.rotation.z = turn; return p;
    };
    const slabs = [
      [pill(3.6, 1.05, 0.55, glass, 1.45, 3.55, -1.2, -0.42), [1.4, 0.9, 0]],
      [pill(3.0, 0.95, 0.5, deep, -1.75, 1.75, -1.4, 0.36), [-1.3, -0.4, 0]],
      [pill(2.4, 0.8, 0.45, glass, 1.75, -2.6, -1.2, 0.5), [1.0, -0.8, 0]],
    ].map(([slab, from]) => ({ slab, from, x: slab.position.x, y: slab.position.y, turn: slab.rotation.z }));
    // The identity card sits inside the liveness ring: the product in one image.
    const card = plate(0.96, 0.6, 0.08, 0.05, ivory, body, 0.7, 2.5, 0.1);
    plate(0.18, 0.13, 0.025, 0.012, gold, card, -0.28, 0.13, 0.055);
    [0.46, 0.34].forEach((width, i) => plate(width, 0.04, 0.016, 0.005, silver, card, 0.1, -0.05 - i * 0.11, 0.055));
    const ring = new THREE.Group(); body.add(ring); ring.position.set(0.7, 2.5, 0.2);
    [0x3f86ff, 0xff7cc4, 0xffc94d, 0x3fd890].forEach((color, i) => {
      const glow = keep(new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 0.12, metalness: 0.05, roughness: 0.4 }));
      const arc = mesh(new THREE.TorusGeometry(0.72, 0.04, 10, 40, Math.PI / 2 - 0.2), glow, ring);
      arc.rotation.z = i * Math.PI / 2 + 0.1;
    });
    // Slabs start off-stage; keep them drawable so GPU allocations match on every scene switch.
    body.traverse(node => { node.frustumCulled = false; });
    articulate = t => {
      // Slabs glide in from off-stage, the card turns to face the viewer, the ring locks into place.
      slabs.forEach(({ slab, from, x, y, turn }, i) => {
        const p = arrive((t - i * 0.18) / 1.6);
        slab.position.x = x + from[0] * (1 - p); slab.position.y = y + from[1] * (1 - p);
        slab.rotation.z = turn + 0.25 * (1 - p);
      });
      const turnIn = ease((t - 0.45) / 1.4);
      card.rotation.set(0.32 * (1 - turnIn) + 0.12, -0.9 * (1 - turnIn) - 0.28, -0.17);
      card.position.y = 2.5 - 0.5 * (1 - turnIn);
      ring.rotation.z = -1.6 * (1 - ease((t - 0.2) / 2.2));
      ring.scale.setScalar(0.6 + 0.4 * arrive((t - 0.2) / 1.2));
    };
  }
  // Small orbit markers add depth without textures, bloom passes or transparency stacks.
  [0.4, 2.5, 4.6].forEach((angle, i) => sphere(0.045, [gold, silver, blue][i], orbitGroup,
    Math.cos(angle) * 1.5, Math.sin(angle) * 1.5 * 0.84, -0.55));
  return {
    root,
    pose(t, animate = true) {
      // All channels share an exact resting pose. Reduced motion skips the entrance entirely.
      const time = animate ? Math.max(0, Math.min(3, t)) : 3;
      if (mode === 'backdrop') { articulate(time); return; }
      const enter = ease(time / 1.15), rest = smooth((time - 1.5) / 1.5);
      const face = ['face', 'eyes', 'turn'].includes(mode);
      const drift = Math.sin(time * 2.1) * (1 - rest);
      body.rotation.set(
        (face ? 0 : 0.10) + 0.26 * (1 - enter),
        (face ? 0 : -0.18) - (face ? 0.12 : 0.62) * (1 - enter) + drift * 0.10,
        (face ? 0 : -0.06) - 0.12 * (1 - enter),
      );
      body.position.y = -0.18 * (1 - enter) + drift * 0.06;
      root.scale.setScalar(0.76 + 0.24 * arrive(time / 0.95));
      orbitGroup.rotation.set(0.22 * (1 - rest), -0.25 * (1 - rest), -0.35 * (1 - enter) + drift * 0.18);
      orbitGroup.scale.setScalar(0.82 + 0.18 * ease(time / 1.25));
      articulate(time);
    },
    dispose() { resources.forEach(resource => resource.dispose()); resources.clear(); },
  };
}
