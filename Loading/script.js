// ════════════════════════════════════════════
//  ISOMETRIC LOADING SCREEN  — Canvas 2D
//  Matches the Spline reference image exactly
// ════════════════════════════════════════════

const CV  = document.getElementById('canvas');
const ctx = CV.getContext('2d');

let W = 0, H = 0;

function resize() {
    W = CV.width  = window.innerWidth;
    H = CV.height = window.innerHeight;
}
resize();
window.addEventListener('resize', resize);

// ── Isometric helpers ──────────────────────
// We use a standard isometric projection:
//   screenX = (ix - iz) * TILE_W / 2
//   screenY = (ix + iz) * TILE_H / 2  + ix_y_offset
// We convert world (x,z) → screen (sx,sy) then
// apply a global offset to center the scene.

const ISO = {
    tw: 90,   // tile width
    th: 46,   // tile height (= tw * tan(30°) ≈ tw * 0.577)
};

// scene origin on screen
let OX = 0, OY = 0;

function isoToScreen(ix, iy_slab, iz) {
    // ix, iz  →  horizontal isometric plane
    // iy_slab →  vertical lift (upward in screen = negative screen y)
    const sx = OX + (ix - iz) * (ISO.tw / 2);
    const sy = OY + (ix + iz) * (ISO.th / 2) - iy_slab * 22;
    return { sx, sy };
}

// ── Colours ────────────────────────────────
const C = {
    bg:     '#080714',
    grid:   'rgba(60, 80, 180, 0.18)',
    cyan:   '#00eeff',
    red:    '#ff4466',
    purple: '#cc55ff',
    green:  '#00ff88',
    white:  '#ffffff',
};

// ── Node definitions ──────────────────────
// ix, iz = isometric grid coords
// color key, label IDs
const NODES = [
    { ix: -4.5, iz:  0.5, color: 'cyan',   slabs: 3, lit: false, litAt: 0, flashAlpha: 0 },  // 0 left
    { ix: -0.5, iz: -3.5, color: 'red',    slabs: 3, lit: false, litAt: 0, flashAlpha: 0 },  // 1 top-center
    { ix:  1.5, iz:  0.5, color: 'cyan',   slabs: 3, lit: false, litAt: 0, flashAlpha: 0 },  // 2 center
    { ix:  1.5, iz:  4.0, color: 'purple', slabs: 3, lit: false, litAt: 0, flashAlpha: 0 },  // 3 bottom-left
    { ix:  5.5, iz: -0.5, color: 'green',  slabs: 3, lit: false, litAt: 0, flashAlpha: 0 },  // 4 right
];

// connections [fromIdx, toIdx]
const CONNS = [
    [0, 1],
    [1, 2],
    [2, 3],
    [3, 4],
];

// ── Compute screen positions ───────────────
function nodeScreen(n) {
    return isoToScreen(n.ix, 0, n.iz);
}

// ── Easing ────────────────────────────────
function easeInOut(t) {
    return t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;
}

function easeOutCubic(t) {
    return 1 - Math.pow(1 - t, 3);
}

// ── Ambient dust particles ─────────────────
const DUST = Array.from({ length: 55 }, () => ({
    x: Math.random() * 2 - 1,
    y: Math.random() * 2 - 1,
    r: 0.6 + Math.random() * 1.0,
    speed: 0.00008 + Math.random() * 0.00012,
    phase: Math.random() * Math.PI * 2,
    alpha: 0.08 + Math.random() * 0.18,
}));

function drawDust(t) {
    DUST.forEach(d => {
        const x = ((d.x + d.speed * t * 60 + 10) % 2) - 1;
        const y = d.y + Math.sin(t * 0.3 + d.phase) * 0.002;
        const sx = (x + 1) / 2 * W;
        const sy = (y + 1) / 2 * H;
        const flicker = 0.5 + 0.5 * Math.sin(t * 2.1 + d.phase);
        ctx.globalAlpha = d.alpha * flicker;
        ctx.fillStyle = '#8ac';
        ctx.beginPath();
        ctx.arc(sx, sy, d.r, 0, Math.PI * 2);
        ctx.fill();
    });
    ctx.globalAlpha = 1;
}

// ── Film grain ─────────────────────────────
function drawGrain() {
    ctx.save();
    ctx.globalCompositeOperation = 'screen';
    for (let i = 0; i < 120; i++) {
        const x = Math.random() * W;
        const y = Math.random() * H;
        const r = Math.random() * 1.5;
        const a = Math.random() * 0.04;
        ctx.globalAlpha = a;
        ctx.fillStyle = '#ffffff';
        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.fill();
    }
    ctx.restore();
}

// ── Grid ──────────────────────────────────
function drawGrid() {
    const range = 14;
    ctx.lineWidth = 1;

    for (let i = -range; i <= range; i++) {
        // Distance-based fade: lines near center are brighter
        const fade = 1 - Math.abs(i) / range;
        ctx.strokeStyle = `rgba(60, 80, 180, ${0.06 + fade * 0.14})`;

        const a = isoToScreen(i, 0, -range);
        const b = isoToScreen(i, 0,  range);
        ctx.beginPath();
        ctx.moveTo(a.sx, a.sy);
        ctx.lineTo(b.sx, b.sy);
        ctx.stroke();

        const c = isoToScreen(-range, 0, i);
        const d = isoToScreen( range, 0, i);
        ctx.beginPath();
        ctx.moveTo(c.sx, c.sy);
        ctx.lineTo(d.sx, d.sy);
        ctx.stroke();
    }
}

// ── Draw one isometric slab ────────────────
//  A slab is a flat box: top face + right face + left face
function drawSlab(cx, cy, w, h, d, color, alpha = 1) {
    // w = half-width in px, h = height in px, d = depth offset
    // We draw manually for a crisp isometric look

    const col = color;
    const darker = shadeColor(col, -40);
    const darkest = shadeColor(col, -65);

    ctx.globalAlpha = alpha;

    // TOP face (parallelogram)
    ctx.beginPath();
    ctx.moveTo(cx,     cy - d);
    ctx.lineTo(cx + w, cy + w * 0.5 - d);
    ctx.lineTo(cx,     cy + w - d);
    ctx.lineTo(cx - w, cy + w * 0.5 - d);
    ctx.closePath();
    ctx.fillStyle = col;
    ctx.fill();
    ctx.strokeStyle = 'rgba(255,255,255,0.18)';
    ctx.lineWidth = 0.8;
    ctx.stroke();

    // RIGHT face
    ctx.beginPath();
    ctx.moveTo(cx + w, cy + w * 0.5 - d);
    ctx.lineTo(cx + w, cy + w * 0.5);
    ctx.lineTo(cx,     cy + w);
    ctx.lineTo(cx,     cy + w - d);
    ctx.closePath();
    ctx.fillStyle = darker;
    ctx.fill();
    ctx.strokeStyle = 'rgba(255,255,255,0.08)';
    ctx.stroke();

    // LEFT face
    ctx.beginPath();
    ctx.moveTo(cx - w, cy + w * 0.5 - d);
    ctx.lineTo(cx - w, cy + w * 0.5);
    ctx.lineTo(cx,     cy + w);
    ctx.lineTo(cx,     cy + w - d);
    ctx.closePath();
    ctx.fillStyle = darkest;
    ctx.fill();
    ctx.strokeStyle = 'rgba(0,0,0,0.3)';
    ctx.stroke();

    ctx.globalAlpha = 1;
}

// ── Ground light spill (color projected onto grid plane) ─
function drawGroundSpill(sx, sy, color, intensity) {
    // A wide, soft ellipse on the ground plane
    const gx = sx;
    const gy = sy + 55;
    const rx = 110 * intensity;
    const ry = 40 * intensity;
    const g = ctx.createRadialGradient(gx, gy, 0, gx, gy, rx);
    g.addColorStop(0, hexAlpha(color, 0.22 * intensity));
    g.addColorStop(0.4, hexAlpha(color, 0.08 * intensity));
    g.addColorStop(1, hexAlpha(color, 0));
    ctx.save();
    ctx.scale(1, ry / rx);
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.arc(gx, gy * (rx / ry), rx, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
}

// ── Draw glow under node ───────────────────
function drawGlow(sx, sy, color, intensity) {
    const r = ctx.createRadialGradient(sx, sy + 42, 0, sx, sy + 42, 60);
    r.addColorStop(0, hexAlpha(color, 0.5 * intensity));
    r.addColorStop(0.5, hexAlpha(color, 0.18 * intensity));
    r.addColorStop(1, hexAlpha(color, 0));
    ctx.fillStyle = r;
    ctx.beginPath();
    ctx.ellipse(sx, sy + 42, 60, 24, 0, 0, Math.PI * 2);
    ctx.fill();
}

// ── Activation ring pulse ─────────────────
function drawActivationRing(sx, sy, color, age) {
    // age = seconds since activation, ring expands then fades
    if (age > 1.2) return;
    const progress = age / 1.2;
    const radius = 20 + progress * 100;
    const alpha = (1 - progress) * 0.6;
    ctx.save();
    ctx.strokeStyle = hexAlpha(color, alpha);
    ctx.shadowColor = color;
    ctx.shadowBlur = 20 * (1 - progress);
    ctx.lineWidth = 2.5 * (1 - progress * 0.8);
    ctx.beginPath();
    ctx.ellipse(sx, sy + 30, radius, radius * 0.38, 0, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();
}

// ── Draw a full stacked node ───────────────
function drawNode(n, t) {
    if (!n.lit) return;
    const { sx, sy } = nodeScreen(n);
    const col = C[n.color];
    const age = t - n.litAt;

    // Spring-like bob: starts with a slight overshoot then settles
    const springBob = age < 0.8
        ? Math.sin(age * Math.PI * 2.5) * 6 * Math.exp(-age * 4)
        : Math.sin(t * 1.4 + n.ix * 0.8) * 2.5;
    const bsy = sy + springBob;

    // Ground light spill — projects colored light onto grid surface
    const pulse = 0.7 + 0.3 * Math.sin(t * 1.8 + n.ix);
    drawGroundSpill(sx, bsy, col, pulse);

    // Under-glow
    drawGlow(sx, bsy, col, pulse);

    // Activation ring pulse (expands outward once on activation)
    drawActivationRing(sx, bsy, col, age);

    // Activation flash — node briefly over-brightens on spawn
    const flashPower = age < 0.4 ? Math.exp(-age * 8) : 0;

    if (flashPower > 0.01) {
        ctx.save();
        ctx.globalAlpha = flashPower * 0.8;
        ctx.shadowColor = col;
        ctx.shadowBlur = 60;
        ctx.fillStyle = col;
        ctx.beginPath();
        ctx.ellipse(sx, bsy + 10, 50, 20, 0, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
    }

    // Slab 1 — base (dark blue-grey)
    drawSlab(sx, bsy - 0, 40, 0, 14, '#1e1d3a');

    // Slab 2 — middle
    drawSlab(sx, bsy - 14, 33, 0, 11, '#2d2b55');

    // Slab 3 — top (colored), brightens in flash
    const topBright = flashPower > 0 ? shadeColor(col, Math.round(flashPower * 60)) : col;
    drawSlab(sx, bsy - 28, 27, 0, 10, topBright);

    // Top face ambient glow
    ctx.globalAlpha = (0.2 + flashPower * 0.5) * pulse;
    ctx.beginPath();
    ctx.moveTo(sx,      bsy - 38);
    ctx.lineTo(sx + 27, bsy - 38 + 27 * 0.5);
    ctx.lineTo(sx,      bsy - 38 + 27);
    ctx.lineTo(sx - 27, bsy - 38 + 27 * 0.5);
    ctx.closePath();
    ctx.fillStyle = col;
    ctx.fill();
    ctx.globalAlpha = 1;
}

// ── Connection lines (L-shaped, isometric) ─
// Each connection goes node A → midpoint → node B
// using horizontal then vertical isometric lines

function getConnColor(i) {
    const [a, b] = CONNS[i];
    const ca = C[NODES[a].color];
    const cb = C[NODES[b].color];
    return ca; // just use from-node color
}

function connPath(i) {
    const [ai, bi] = CONNS[i];
    const na = NODES[ai], nb = NODES[bi];
    // mid point: share iz of A, ix of B (L-shape in iso space)
    const mid = { ix: nb.ix, iz: na.iz };
    const pa  = isoToScreen(na.ix, 0, na.iz);
    const pm  = isoToScreen(mid.ix, 0, mid.iz);
    const pb  = isoToScreen(nb.ix, 0, nb.iz);
    return [pa, pm, pb];
}

function lerpAlongPath(path, t) {
    if (t <= 0.5) {
        const u = t / 0.5;
        return {
            x: path[0].sx + (path[1].sx - path[0].sx) * u,
            y: path[0].sy + (path[1].sy - path[0].sy) * u,
        };
    } else {
        const u = (t - 0.5) / 0.5;
        return {
            x: path[1].sx + (path[2].sx - path[1].sx) * u,
            y: path[1].sy + (path[2].sy - path[1].sy) * u,
        };
    }
}

function drawComet(ctx, path, u, length, color) {
    if (u <= 0) return;
    const tailU = Math.max(0, u - length);
    
    ctx.beginPath();
    const start = lerpAlongPath(path, tailU);
    ctx.moveTo(start.x, start.y);
    
    if (tailU < 0.5 && u > 0.5) {
        ctx.lineTo(path[1].sx, path[1].sy);
    }
    
    const end = lerpAlongPath(path, u);
    ctx.lineTo(end.x, end.y);
    
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    
    ctx.shadowColor = color;
    ctx.shadowBlur = 12;
    ctx.strokeStyle = color;
    ctx.lineWidth = 4;
    ctx.stroke();
    
    ctx.shadowBlur = 0;
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 2.5;
    ctx.stroke();
    
    ctx.lineCap = 'butt';
    ctx.lineJoin = 'miter';
}

function drawConnections(t) {
    const elapsed = Date.now() - t0;

    CONNS.forEach((pair, i) => {
        const [ai, bi] = pair;
        
        const tStart = 600 + ai * 900;
        const tEnd = 600 + bi * 900;
        
        if (elapsed < tStart) return;
        
        // Ease-in-out the line draw so it accelerates then decelerates
        let pRaw = (elapsed - tStart) / (tEnd - tStart);
        if (pRaw > 1) pRaw = 1;
        const p = easeInOut(pRaw);

        const path  = connPath(i);
        const color = getConnColor(i);

        ctx.beginPath();
        ctx.moveTo(path[0].sx, path[0].sy);
        if (p > 0.5) {
            ctx.lineTo(path[1].sx, path[1].sy);
        }
        const currentEnd = lerpAlongPath(path, p);
        ctx.lineTo(currentEnd.x, currentEnd.y);
        
        // ── Organic neon flicker ──
        const flicker = 0.82 + 0.18 * Math.sin(Date.now() * 0.011 + i * 1.7);
        const flicker2 = 0.88 + 0.12 * Math.sin(Date.now() * 0.017 + i * 2.3);

        // Layer 1: Wide bloom spread, flickering
        ctx.shadowColor = color;
        ctx.shadowBlur  = 28 * flicker;
        ctx.strokeStyle = hexAlpha(color, 0.4 * flicker);
        ctx.lineWidth   = 6;
        ctx.stroke();

        // Layer 2: Mid glow
        ctx.shadowBlur  = 12 * flicker2;
        ctx.strokeStyle = hexAlpha(color, 0.7 * flicker2);
        ctx.lineWidth   = 2.5;
        ctx.stroke();

        // Layer 3: White-hot core — very thin, very bright
        ctx.shadowBlur  = 4;
        ctx.shadowColor = '#fff';
        ctx.strokeStyle = `rgba(255,255,255,${0.85 * flicker})`;
        ctx.lineWidth   = 1.0;
        ctx.stroke();
        ctx.shadowBlur  = 0;

        // ── Stream of moving pulses (comets/dashes) ──
        const timeSinceLit = elapsed - tStart;
        for (let j = 0; j < 4; j++) {
            let u = (timeSinceLit / 900) - (j * 0.25);
            if (u < 0) continue;
            u = u % 1; // Seamless infinite looping
            
            // Pulse only visible if it hasn't overtaken the drawn portion
            if (u <= p + 0.001) {
                drawComet(ctx, path, u, 0.06, color);
            }
        }
    });
}

// ── Label positioning ──────────────────────
const LABEL_CFG = [
    // [main label id, offset_x, offset_y, sub-label id (optional), sub_ox, sub_oy]
    { id: 'l0',  ox: -80,  oy: -60, sub: null },
    { id: 'l1',  ox:  10,  oy: -55, sub: null },
    { id: 'l2',  ox:  90,  oy: -55, sub: null },
    { id: 'l3',  ox: -30,  oy:  20, sub: null },
    { id: 'l4',  ox:  20,  oy: -60, sub: null },
];

function updateLabels() {
    NODES.forEach((n, i) => {
        const { sx, sy } = nodeScreen(n);
        const cfg = LABEL_CFG[i];
        const el  = document.getElementById(cfg.id);
        if (!el) return;

        el.style.left = (sx + cfg.ox) + 'px';
        el.style.top  = (sy + cfg.oy) + 'px';

        if (n.lit && !el.classList.contains('on')) {
            setTimeout(() => el.classList.add('on'), 200);
        }

        if (cfg.sub) {
            const sel = document.getElementById(cfg.sub);
            if (sel) {
                sel.style.left = (sx + cfg.sox) + 'px';
                sel.style.top  = (sy + cfg.soy) + 'px';
                if (n.lit && !sel.classList.contains('on')) {
                    setTimeout(() => sel.classList.add('on'), 400);
                }
            }
        }
    });
}

// ── Sequential node activation ─────────────

NODES.forEach((n, i) => {
    setTimeout(() => {
        n.lit = true;
        n.litAt = performance.now() / 1000;
    }, 600 + i * 900);
});

// ── Progress bar ───────────────────────────
const TOTAL_MS = 4000;
const t0 = Date.now();

function tickProgress() {
    const pct = Math.min(100, ((Date.now() - t0) / TOTAL_MS) * 100);

    if (pct < 100) {
        requestAnimationFrame(tickProgress);
    } else {
        setTimeout(() => {
            document.getElementById('loader').classList.add('done');
        }, 1500);
    }
}
setTimeout(() => requestAnimationFrame(tickProgress), 300);

// ── Scanlines ──────────────────────────────
function drawScanlines() {
    ctx.save();
    ctx.globalCompositeOperation = 'multiply';
    for (let y = 0; y < H; y += 4) {
        ctx.fillStyle = 'rgba(0,0,0,0.18)';
        ctx.fillRect(0, y, W, 2);
    }
    ctx.restore();
}

// ── Main render loop ───────────────────────
function render(ts) {
    const t = ts / 1000;

    // ── Breathing camera drift ─────────────
    // Very slow, independent X and Y oscillation — like a tripod breathing
    const camX = Math.sin(t * 0.11) * 6 + Math.sin(t * 0.07) * 3;
    const camY = Math.sin(t * 0.09) * 4 + Math.cos(t * 0.13) * 2;
    OX = W * 0.5 + camX;
    OY = H * 0.44 + camY;

    // Background
    ctx.fillStyle = C.bg;
    ctx.fillRect(0, 0, W, H);

    // Vignette — slightly animated breathe
    const vigR = Math.max(W, H) * (0.62 + Math.sin(t * 0.15) * 0.03);
    const vig = ctx.createRadialGradient(W/2, H/2, 0, W/2, H/2, vigR);
    vig.addColorStop(0, 'rgba(8,7,20,0)');
    vig.addColorStop(0.6, 'rgba(6,5,18,0.3)');
    vig.addColorStop(1, 'rgba(2,1,10,0.96)');
    ctx.fillStyle = vig;
    ctx.fillRect(0, 0, W, H);

    // Ambient floating dust
    drawDust(t);

    // Grid
    drawGrid();

    // Draw connections (below nodes)
    drawConnections(t);

    // Draw nodes (on top)
    NODES.forEach(n => drawNode(n, t));

    // Scanlines — subtle monitor/screen feel
    drawScanlines();

    // Update label positions (each frame to support resize)
    updateLabels();

    // Film grain overlay
    drawGrain();

    requestAnimationFrame(render);
}

requestAnimationFrame(render);

// ── Utilities ──────────────────────────────
function hexAlpha(hex, a) {
    const r = parseInt(hex.slice(1,3),16);
    const g = parseInt(hex.slice(3,5),16);
    const b = parseInt(hex.slice(5,7),16);
    return `rgba(${r},${g},${b},${a})`;
}

function shadeColor(hex, amount) {
    let r = parseInt(hex.slice(1,3),16);
    let g = parseInt(hex.slice(3,5),16);
    let b = parseInt(hex.slice(5,7),16);
    r = Math.max(0, Math.min(255, r + amount));
    g = Math.max(0, Math.min(255, g + amount));
    b = Math.max(0, Math.min(255, b + amount));
    return `rgb(${r},${g},${b})`;
}
