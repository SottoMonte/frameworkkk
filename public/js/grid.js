const canvas = document.getElementById('grid-canvas');
const ctx = canvas.getContext('2d');
let mouse = { x: -1000, y: -1000 }, globalAlpha = 0, lastMoveTime = Date.now();

// Configurazione
const GAP = 10, RADIUS = 350, DOT_SIZE = 0.4;
const COLOR_IDLE = '#000', COLOR_ACTIVE = '#1e293b';

function resize() {
    const dpr = window.devicePixelRatio || 1;
    canvas.style.width = window.innerWidth + 'px';
    canvas.style.height = window.innerHeight + 'px';
    canvas.width = window.innerWidth * dpr;
    canvas.height = window.innerHeight * dpr;
    ctx.scale(dpr, dpr);
}

window.addEventListener('resize', resize);
window.addEventListener('mousemove', (e) => {
    mouse.x = e.clientX;
    mouse.y = e.clientY;
    lastMoveTime = Date.now();
    if (globalAlpha < 1) globalAlpha += 0.08;
});

resize();

function draw() {
    // Usiamo window.innerWidth/Height per pulire correttamente l'area scalata
    ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);

    if (Date.now() - lastMoveTime > 100) globalAlpha -= 0.02;
    globalAlpha = Math.max(0, globalAlpha);

    for (let x = 0; x < window.innerWidth; x += GAP) {
        for (let y = 0; y < window.innerHeight; y += GAP) {
            const dist = Math.hypot(x - mouse.x, y - mouse.y);
            ctx.beginPath();

            if (dist < RADIUS && globalAlpha > 0) {
                let strength = Math.pow(1 - (dist / RADIUS), 2);
                ctx.fillStyle = COLOR_ACTIVE;
                ctx.globalAlpha = strength * globalAlpha;
                ctx.arc(x, y, DOT_SIZE * 1.2, 0, Math.PI * 2);
            } else {
                ctx.fillStyle = COLOR_IDLE;
                ctx.globalAlpha = 0.25;
                ctx.arc(x, y, DOT_SIZE, 0, Math.PI * 2);
            }
            ctx.fill();
        }
    }
    requestAnimationFrame(draw);
}

draw();