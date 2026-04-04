// API base: same tab on port 8008 uses relative URLs; Live Server / file:// → FastAPI on 8008
(function initNexusApiRoot() {
    const meta = document.querySelector('meta[name="nexus-api-root"]');
    if (meta && meta.getAttribute('content') && meta.getAttribute('content').trim()) {
        window.NEXUS_API_ROOT = meta.getAttribute('content').trim().replace(/\/$/, '');
        return;
    }
    const u = window.location;
    if (u.protocol === 'file:') {
        window.NEXUS_API_ROOT = 'http://127.0.0.1:8008';
        return;
    }
    if (u.port === '8008') {
        window.NEXUS_API_ROOT = '';
        return;
    }
    if ((u.hostname === '127.0.0.1' || u.hostname === 'localhost') && u.port && u.port !== '8008') {
        window.NEXUS_API_ROOT = 'http://127.0.0.1:8008';
        return;
    }
    window.NEXUS_API_ROOT = '';
})();

// ===================== LIVE LANDING STATS =====================
// Fetches real data from /api/landing-stats and populates the
// expertise tab mini-cards with live numbers from all 4 integrations.
(function fetchLandingData() {
    // Helper: animate a numeric value into a DOM element
    function animateStat(id, value) {
        const el = document.getElementById(id);
        if (!el) return;
        if (typeof value === 'number' && typeof gsap !== 'undefined') {
            const obj = { v: 0 };
            gsap.to(obj, {
                v: value,
                duration: 1.4,
                ease: 'power2.out',
                onUpdate: () => { el.textContent = Math.floor(obj.v); }
            });
        } else {
            el.textContent = value ?? '—';
        }
    }

    async function load() {
        try {
            const res  = await fetch((window.NEXUS_API_ROOT || '') + '/api/landing-stats');
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();

            // GitHub
            animateStat('stat-gh-prs',   data.github?.open_prs);
            animateStat('stat-gh-ci',    data.github?.failing_ci);
            animateStat('stat-gh-stale', data.github?.stale_reviews);

            // Jira
            animateStat('stat-jira-progress', data.jira?.in_progress);
            animateStat('stat-jira-blocked',  data.jira?.blocked);
            animateStat('stat-jira-done',     data.jira?.done);

            // Calendar
            animateStat('stat-cal-ooo',   data.calendar?.ooo_count);
            animateStat('stat-cal-heavy', data.calendar?.heavy_meeting_days);
            animateStat('stat-cal-focus', data.calendar?.focus_hours != null
                ? `${data.calendar.focus_hours}h` : '—');

            // Slack
            animateStat('stat-slack-unanswered', data.slack?.unanswered_messages);
            animateStat('stat-slack-blocked',    data.slack?.blocked_devs);
            animateStat('stat-slack-channels',   data.slack?.channels_monitored);

        } catch (err) {
            console.warn('[Nexus] Landing stats fetch failed:', err);
            // Leave the — placeholder visible; page still looks fine
        }
    }

    // Wait for DOM then load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', load);
    } else {
        load();
    }
})();

// ===================== NEXUS AI GUIDE (runs FIRST — must not depend on GSAP/Lenis) =====================
(function initNexusGuideChat() {
    const shell = document.getElementById('nexus-guide-chat');
    const openBtn = document.getElementById('nexus-lets-talk-btn');
    const messagesEl = document.getElementById('nexus-guide-messages');
    const form = document.getElementById('nexus-guide-form');
    const input = document.getElementById('nexus-guide-input');
    const sendBtn = document.getElementById('nexus-guide-send');
    const chips = document.querySelectorAll('.nx-chip');
    if (!shell || !openBtn || !messagesEl || !form || !input || !sendBtn) return;

    function openChat() {
        shell.hidden = false;
        shell.classList.add('is-open');
        shell.setAttribute('aria-hidden', 'false');
        if (typeof lenis !== 'undefined' && lenis) lenis.stop();
        requestAnimationFrame(() => input.focus());
    }

    function closeChat() {
        shell.classList.remove('is-open');
        shell.setAttribute('aria-hidden', 'true');
        shell.hidden = true;
        if (typeof lenis !== 'undefined' && lenis) lenis.start();
    }

    function formatTime() {
        return new Date().toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
    }

    function appendBubble(role, text, isError = false) {
        const isAi = role === 'assistant';
        const msgDiv = document.createElement('div');
        msgDiv.className = `nx-msg ${isAi ? 'nx-msg-ai' : 'nx-msg-user'}`;
        
        const avatar = document.createElement('div');
        avatar.className = 'nx-msg-avatar';
        avatar.textContent = isAi ? 'N' : 'U';
        
        const content = document.createElement('div');
        content.className = 'nx-msg-content';
        
        const bubble = document.createElement('div');
        bubble.className = 'nx-msg-bubble';
        if (isError) bubble.style.color = '#ff6b6b';
        bubble.textContent = text;
        
        const time = document.createElement('div');
        time.className = 'nx-msg-time';
        time.textContent = formatTime();
        
        content.appendChild(bubble);
        content.appendChild(time);
        msgDiv.appendChild(avatar);
        msgDiv.appendChild(content);
        
        messagesEl.appendChild(msgDiv);
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function showTyping() {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'nx-msg nx-msg-ai';
        msgDiv.id = 'nx-typing-indicator';
        
        const avatar = document.createElement('div');
        avatar.className = 'nx-msg-avatar';
        avatar.textContent = 'N';
        
        const content = document.createElement('div');
        content.className = 'nx-msg-content';
        
        const bubble = document.createElement('div');
        bubble.className = 'nx-typing';
        
        const dots = document.createElement('div');
        dots.className = 'nx-dots';
        dots.innerHTML = '<span></span><span></span><span></span>';
        
        bubble.appendChild(document.createTextNode('Nexus is thinking '));
        bubble.appendChild(dots);
        
        content.appendChild(bubble);
        msgDiv.appendChild(avatar);
        msgDiv.appendChild(content);
        
        messagesEl.appendChild(msgDiv);
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function removeTyping() {
        const el = document.getElementById('nx-typing-indicator');
        if (el) el.remove();
    }

    async function sendMessage(text) {
        if (!text) return;
        appendBubble('user', text);
        input.value = '';
        input.disabled = true;
        sendBtn.disabled = true;

        showTyping();

        const apiRoot = window.NEXUS_API_ROOT || '';
        const chatUrl = apiRoot + '/api/chat';
        try {
            const res = await fetch(chatUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question: text }),
            });
            const data = await res.json().catch(() => ({}));
            removeTyping();

            if (!res.ok) {
                const d = data.detail;
                const err = Array.isArray(d) ? d.map((x) => x.msg || x).join(' ') : (d || data.message || `Request failed (${res.status})`);
                appendBubble('assistant', String(err), true);
                return;
            }
            appendBubble('assistant', data.answer || '(No answer returned)');
        } catch {
            removeTyping();
            appendBubble('assistant', 'Network error calling ' + chatUrl + '. Start uvicorn on port 8008.', true);
        } finally {
            input.disabled = false;
            sendBtn.disabled = false;
            input.focus();
        }
    }

    openBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        openChat();
    });

    shell.querySelectorAll('[data-guide-close]').forEach((el) => {
        el.addEventListener('click', () => closeChat());
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && shell.classList.contains('is-open')) closeChat();
    });

    form.addEventListener('submit', (e) => {
        e.preventDefault();
        sendMessage(input.value.trim());
    });

    chips.forEach(chip => {
        chip.addEventListener('click', () => {
            const text = chip.textContent;
            sendMessage(text);
        });
    });
})();

console.clear();

if (typeof gsap === 'undefined' || typeof ScrollTrigger === 'undefined') {
    console.error('[Nexus] GSAP failed to load from CDN.');
} else {
    gsap.registerPlugin(ScrollTrigger);
}

/** @type {InstanceType<typeof Lenis> | null} */
let lenis = null;
try {
    if (typeof Lenis !== 'undefined' && gsap && ScrollTrigger) {
        lenis = new Lenis({
            duration: 1.2,
            easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
            smooth: true,
        });
        lenis.on('scroll', ScrollTrigger.update);
        gsap.ticker.add((time) => {
            if (lenis) lenis.raf(time * 1000);
        });
        gsap.ticker.lagSmoothing(0);
    }
} catch (err) {
    console.warn('[Nexus] Lenis init failed:', err);
}

// ===================== PRELOADER =====================
const preloader = document.getElementById('preloader');
if (preloader && typeof gsap !== 'undefined') {
    if (lenis) lenis.stop();

    gsap.to('#wave-path', {
        x: -500,
        duration: 2.2,
        ease: "none",
        repeat: -1
    });

    gsap.fromTo('#wave-path', 
        { y: 0 }, 
        { 
            y: -220, 
            duration: 4.0, 
            ease: "power1.inOut", 
            onComplete: () => {
                gsap.to(preloader, {
                    yPercent: -100,
                    duration: 0.8,
                    ease: "power3.inOut",
                    onComplete: () => {
                        preloader.remove();
                        if (lenis) lenis.start();
                    }
                });
            }
        }
    );

    let counter = { val: 0 };
    gsap.to(counter, {
        val: 100,
        duration: 4.0,
        ease: "power1.inOut",
        onUpdate: () => {
            const percText = document.getElementById('loading-percent');
            if (percText) {
                percText.textContent = `loading... ${Math.floor(counter.val)} %`;
            }
        }
    });
}


const video = document.getElementById("hero-video");

const tl =
    typeof gsap !== "undefined" && video
        ? gsap.timeline({
              scrollTrigger: {
                  trigger: ".hero-pinned-section",
                  start: "top top",
                  end: "+=1500",
                  pin: true,
                  scrub: 1.5,
              },
          })
        : null;

// Create the double-grid effect. Video scales very wide (97vw), while text boundary
// remains tightly wrapped to the logo/header padding (var--content-margin).
if (tl) {
    tl.to(video, {
        width: "97vw",
        height: "60vh",
        marginTop: "12vh",
        borderRadius: "24px",
        ease: "power2.inOut",
    }, 0);

    tl.to([".subtitle", ".text-bottom"], {
        opacity: 1,
        filter: "blur(0px)",
        y: 0,
        stagger: 0.15,
        ease: "power2.out",
        duration: 0.6,
    }, 0.3);
}

// ===================== PARTICLE MORPH (Technology Section) =====================
(function initParticleMorph() {
    const canvas = document.getElementById('dot-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    let cw = 0, ch = 0;
    const MAX_PARTICLES = 3000;
    let particles = [];
    let targets   = [];
    let rawProgress = 0;   // direct from scroll
    let smoothProg  = 0;   // lerped value for smooth animation
    let animId;

    // ---- Resize: use ResizeObserver so we get real dimensions ----
    function resizeCanvas() {
        cw = canvas.offsetWidth;
        ch = canvas.offsetHeight;
        canvas.width  = cw;
        canvas.height = ch;
        if (targets.length) buildParticles();
    }

    const ro = new ResizeObserver(() => resizeCanvas());
    ro.observe(canvas);

    // ---- Sample portrait image for dot target positions ----
    function samplePortrait(callback) {
        const img = new Image();
        img.crossOrigin = 'anonymous';
        img.src = 'dot-head.png';
        img.onload = () => {
            const offW = 500, offH = 500;
            const off  = document.createElement('canvas');
            off.width  = offW;
            off.height = offH;
            const octx = off.getContext('2d');
            octx.drawImage(img, 0, 0, offW, offH);
            const data = octx.getImageData(0, 0, offW, offH).data;
            const pts  = [];
            const step = 3;
            for (let y = 0; y < offH; y += step) {
                for (let x = 0; x < offW; x += step) {
                    const i  = (y * offW + x) * 4;
                    const br = (data[i] + data[i+1] + data[i+2]) / 3;
                    if (br < 248) {   // capture all non-white pixels (including light gray fade)
                        const density = (248 - br) / 248;
                        pts.push({
                            nx: x / offW,
                            ny: y / offH,
                            r:  0.8 + density * 2.4,
                            // Preserve each dot's original brightness for faithful color rendering
                            gray: Math.round(40 + (1 - density) * 160)
                        });
                    }
                }
            }
            // Shuffle so MAX_PARTICLES is drawn from the full portrait, not just the top rows
            for (let i = pts.length - 1; i > 0; i--) {
                const j = Math.floor(Math.random() * (i + 1));
                [pts[i], pts[j]] = [pts[j], pts[i]];
            }
            callback(pts);
        };
        img.onerror = () => callback([]);
    }

    // ---- Build particles: map targets → canvas coords (preserve aspect ratio) ----
    function buildParticles() {
        if (!cw || !ch) return;
        // Use smaller dimension as portrait size to keep it square (not squished)
        const size   = Math.min(cw, ch) * 0.92;
        const xOff   = (cw - size) / 2;   // center horizontally
        const yOff   = (ch - size) * 0.1; // slight top bias (like reference)
        particles = targets.slice(0, MAX_PARTICLES).map(t => ({
            tx: xOff + t.nx * size,
            ty: yOff + t.ny * size,
            // Start: bottom area of canvas
            sx: Math.random() * cw,
            sy: ch * 0.75 + Math.random() * ch * 0.24,
            r:  t.r,
            delay: Math.random() * 0.35
        }));
    }

    // ---- Render frame ----
    function draw() {
        ctx.clearRect(0, 0, cw, ch);
        const p = smoothProg;

        for (let i = 0; i < particles.length; i++) {
            const pt = particles[i];
            const localP = Math.max(0, Math.min(1, (p - pt.delay) / (1 - pt.delay)));
            // easeInOutCubic
            const ep = localP < 0.5
                ? 4 * localP * localP * localP
                : 1 - Math.pow(-2 * localP + 2, 3) / 2;

            const x = pt.sx + (pt.tx - pt.sx) * ep;
            const y = pt.sy + (pt.ty - pt.sy) * ep;

            const g = pt.gray ?? 55;
            ctx.globalAlpha = 0.06 + ep * 0.88;
            ctx.fillStyle   = `rgb(${g},${g},${g})`;
            ctx.beginPath();
            ctx.arc(x, y, pt.r * (0.3 + ep * 0.7), 0, Math.PI * 2);
            ctx.fill();
        }
        ctx.globalAlpha = 1;
    }

    // ---- Animation loop: smooth-lerp towards rawProgress ----
    function loop() {
        smoothProg += (rawProgress - smoothProg) * 0.08;
        draw();
        animId = requestAnimationFrame(loop);
    }

    // ---- Scroll: pin the tech section while portrait assembles ----
    // Mirrors the hero pin: section locks to viewport, user scrolls 1500px through it,
    // rawProgress goes 0→1, then section unpins and scroll resumes normally.
    ScrollTrigger.create({
        trigger: '.tech-section',
        start: 'top top',
        end: () => "+=" + (1500 + window.innerHeight),
        pin: true,
        onUpdate: (self) => {
            const total = 1500 + window.innerHeight;
            const threshold = 1500 / total;
            rawProgress = Math.min(1, self.progress / threshold);
        }
    });

    // ---- Init ----
    samplePortrait(pts => {
        targets = pts;
        // Ensure canvas is sized (ResizeObserver may not have fired yet)
        if (!cw) resizeCanvas();
        buildParticles();
        loop();   // start rAF loop
    });
})();

// ===================== ANIMATION #1: Scrub-triggered staggered card entrance =====================
gsap.set('.product-card', { opacity: 0, y: 100 });

gsap.to('.product-card', {
    opacity: 1,
    y: 0,
    stagger: 0.1,
    ease: 'none',
    scrollTrigger: {
        trigger: '.products-grid',
        start: 'top 85%',
        end: 'center 40%',
        scrub: 1
    }
});

// ===================== ANIMATION #2: Typewriter on widget body =====================
(function initTypewriter() {
    const widgetBody = document.querySelector('.widget-body');
    if (!widgetBody) return;

    const fullText = widgetBody.textContent.replace('|', '').trim();
    widgetBody.textContent = '';

    const cursor = document.createElement('span');
    cursor.className = 'typewriter-cursor';
    cursor.textContent = '|';
    widgetBody.appendChild(cursor);

    function typeOut(el, cursorEl, text, speed) {
        let i = 0;
        const interval = setInterval(() => {
            if (i < text.length) {
                el.insertBefore(document.createTextNode(text[i]), cursorEl);
                i++;
            } else {
                clearInterval(interval);
            }
        }, speed);
    }

    ScrollTrigger.create({
        trigger: '.card-wide', // Trigger based on the wide card visibility
        start: 'center 75%',   // Wait until card is mostly in view to start typing
        once: true,
        onEnter: () => {
            setTimeout(() => typeOut(widgetBody, cursor, fullText, 65), 500); // Give it a slight delay
        }
    });
})();

// ===================== ANIMATION #3: Card Hovers & Image Parallax =====================
document.querySelectorAll('.product-card').forEach(card => {
    const bg = card.querySelector('.card-bg');

    // Hover Scaling (Handled via GSAP to prevent inline transform conflicts with Scrub timeline)
    card.addEventListener('mouseenter', () => {
        gsap.to(card, { scale: 1.02, duration: 0.4, ease: 'power2.out', overwrite: 'auto' });
        if (bg) gsap.to(bg, { scale: 1.05, opacity: 0.8, duration: 0.6, ease: 'power2.out', overwrite: 'auto' });
    });

    card.addEventListener('mouseleave', () => {
        gsap.to(card, { scale: 1, duration: 0.4, ease: 'power2.out', overwrite: 'auto' });
        if (bg) gsap.to(bg, { scale: 1, opacity: 0.65, duration: 0.6, ease: 'power2.out', overwrite: 'auto' });
    });

    // Scrub Image Parallax
    if (bg) {
        // As the card moves through the viewport, move the background slightly
        gsap.to(bg, {
            yPercent: 15,
            ease: 'none',
            scrollTrigger: {
                trigger: card,
                start: 'top bottom', // When top of card hits bottom of viewport
                end: 'bottom top',   // When bottom of card hits top of viewport
                scrub: true
            }
});
    }
});

// ===================== EXPERTISE SECTION ANIMATIONS =====================

// 1. Staggered Scroll-Entrance with Hero Blur Effect
gsap.set('.expertise-header-wrap, .expertise-left, .stacked-card', { opacity: 0, y: 50, filter: 'blur(10px)' });
ScrollTrigger.create({
    trigger: '.expertise-section',
    start: 'top 75%',
    onEnter: () => {
        gsap.to('.expertise-header-wrap', { opacity: 1, y: 0, filter: 'blur(0px)', duration: 0.8, ease: 'power3.out' });
        gsap.to('.expertise-left', { opacity: 1, y: 0, filter: 'blur(0px)', duration: 0.8, delay: 0.2, ease: 'power3.out' });
        // The stacked-card enters with a nice slight elasticity
        gsap.to('.stacked-card', { opacity: 1, y: 0, filter: 'blur(0px)', duration: 0.8, delay: 0.4, ease: 'back.out(1.2)' });
    },
    once: true
});

// 4. Continuous Floating Parallax
// Add a very subtle yoyo floating effect so the interface feels "live"
gsap.to('.stacked-card', {
    y: "-=8",
    duration: 3,
    yoyo: true,
    repeat: -1,
    ease: "sine.inOut",
    delay: 1.2 // start float after entrance animation finishes
});

// 3 & 5. Auto-Cycling Tabs & Refined Transitions
const tabBtns = document.querySelectorAll('.tab-btn');
const tabPanes = document.querySelectorAll('.tab-pane');
let currentTabIdx = 0;
let tabTimer;
const TAB_DURATION = 6000; // 6 seconds

let isAnimating = false;

function goToTab(idx, userInitiated = false) {
    if (idx === currentTabIdx && userInitiated) return;
    if (isAnimating) return;
    isAnimating = true;
    
    // Clear existing timer and animations
    clearTimeout(tabTimer);
    gsap.killTweensOf('.tab-progress');

    // Reset old button progress smoothly
    gsap.to('.tab-progress', { width: "0%", duration: 0.3 });
    tabBtns.forEach(b => b.classList.remove('active'));

    // Animate out old pane
    const oldPane = tabPanes[currentTabIdx];
    gsap.to(oldPane, { 
        opacity: 0, 
        y: -15, 
        duration: 0.3, 
        onComplete: () => {
            gsap.set(oldPane, { display: 'none' });
            
            // Animate in new pane
            currentTabIdx = idx;
            const newPane = tabPanes[currentTabIdx];
            gsap.set(newPane, { display: 'block' });
            
            // Refined blur + alpha in transition
            gsap.fromTo(newPane, 
                { opacity: 0, y: 15, filter: 'blur(8px)' }, 
                { opacity: 1, y: 0, filter: 'blur(0px)', duration: 0.5, ease: 'power2.out', onComplete: () => isAnimating = false }
            );

            // Activate new button and start progress
            tabBtns[currentTabIdx].classList.add('active');
            const newProgress = tabBtns[currentTabIdx].querySelector('.tab-progress');
            
            // Auto progress animation
            gsap.to(newProgress, { 
                width: "100%", 
                duration: TAB_DURATION / 1000, 
                ease: "none" 
            });

            // Schedule next cycle
            tabTimer = setTimeout(() => {
                const nextIdx = (currentTabIdx + 1) % tabBtns.length;
                goToTab(nextIdx);
            }, TAB_DURATION);
        }
    });
}

if (typeof gsap !== 'undefined' && tabBtns.length && tabPanes.length) {
    gsap.set(tabPanes, { display: 'none', opacity: 0 });
    gsap.set(tabPanes[0], { display: 'block', opacity: 1 });

    tabBtns.forEach((btn, idx) => {
        const progressSpan = document.createElement('span');
        progressSpan.className = 'tab-progress';
        btn.appendChild(progressSpan);

        btn.addEventListener('click', () => {
            goToTab(idx, true);
        });
    });

    tabBtns[0].classList.add('active');
    gsap.to(tabBtns[0].querySelector('.tab-progress'), { width: "100%", duration: TAB_DURATION / 1000, ease: "none" });
    tabTimer = setTimeout(() => {
        goToTab(1);
    }, TAB_DURATION);
}

// ===================== SPRINT HEALTH SCROLL REVEAL (CORRECTED) =====================
(function initHealthScroll() {
    const wrapper   = document.querySelector('.health-pin-wrapper');
    const wCards    = document.querySelectorAll('.white-card');
    const dCards    = document.querySelectorAll('.dark-accordion-card');
    const glowBox   = document.querySelector('.health-ambient-glow');
    
    // Classes to toggle
    const wClasses = ['w-risk', 'w-watch', 'w-track'];
    const dClasses = ['d-risk', 'd-watch', 'd-track'];
    const glowClasses = ['glow-risk', 'glow-watch', 'glow-track'];

    if (!wrapper || !wCards.length || !dCards.length) return;

    let currentHealth = -1;

    function activateHealthCard(idx) {
        if (idx === currentHealth) return;
        currentHealth = idx;

        // Sync Ambient Glow
        if (glowBox) {
            glowBox.classList.remove('glow-risk', 'glow-watch', 'glow-track');
            glowBox.classList.add(glowClasses[idx]);
        }

        // Toggle left-side white cards
        wCards.forEach((c, i) => {
            c.classList.toggle('w-active', i === idx);
        });

        // Toggle right-side dark accordion expanding cards
        dCards.forEach((c, i) => {
            // Remove previous active classes and specific colors
            c.classList.remove('d-active', 'd-risk', 'd-watch', 'd-track');
            if (i === idx) {
                c.classList.add('d-active', dClasses[idx]);
            }
        });
    }

    // Init — show first card configuration
    activateHealthCard(0);

    // Click on a dark card to manually jump/activate
    dCards.forEach((card, i) => {
        card.addEventListener('click', () => {
            // When building manual click-to-scroll, we would push the window scroll position.
            // For now, it simply forces active state.
            activateHealthCard(i);
        });
    });

    // Control via ScrollTrigger
    ScrollTrigger.create({
        trigger: '.health-sticky-inner',
        start: 'top top',
        end: '+=2500',
        pin: true,
        snap: {
            snapTo: 1 / 2, // Snap exactly to thresholds (0, 0.5, 1) to feel "clicky" and smooth
            duration: { min: 0.3, max: 0.8 },
            delay: 0.05,
            ease: "power2.inOut"
        },
        onUpdate: (self) => {
            let idx = 0;
            if (self.progress > 0.25) idx = 1;
            if (self.progress > 0.75) idx = 2;
            activateHealthCard(idx);
        }
    });
})();

// ===================== WAVE DOT GRID CANVAS (TRUE 3D) =====================
(function initWaveDotGrid() {
    const canvas = document.getElementById('wave-dot-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    let W, H;
    let t = 0;

    function resize() {
        W = canvas.width = canvas.offsetWidth;
        H = canvas.height = canvas.offsetHeight;
    }

    function draw() {
        ctx.clearRect(0, 0, W, H);

        // --- World space grid config ---
        const COLS       = 38;        // more columns for edge-to-edge coverage
        const ROWS       = 24;
        const GRID_W     = 2800;   // much wider — fills extreme left to right
        const GRID_D     = 1200;   // world units deep (Z axis)
        const WAVE_SPEED = 0.005;  // slightly slower
        const WAVE_AMP   = 120;    // world-unit wave height
        const WAVE_FREQ  = 0.22;   // spatial frequency

        // --- Camera config ---
        const CAM_Y    = 420;      // camera height above grid
        const CAM_Z    = -200;     // camera behind grid origin
        const FOCAL    = 550;      // focal length (perspective strength)
        const HORIZON  = H * 0.08; // screen Y of the horizon (top of canvas area)

        // Collect dots for painter's algorithm (back→front)
        const dots = [];

        for (let row = 0; row < ROWS; row++) {
            for (let col = 0; col < COLS; col++) {
                // World X: centered
                const wx = (col / (COLS - 1) - 0.5) * GRID_W;
                // World Z: 0 = near camera, GRID_D = far (horizon)
                const wz = (row / (ROWS - 1)) * GRID_D;

                // Wave height (Y) — two overlapping sine waves for organic feel
                // Positive t = wave travels from viewer INTO horizon (natural ocean look)
                const wy =
                    WAVE_AMP * 0.65 * Math.sin(col * WAVE_FREQ + t * 1.2) +
                    WAVE_AMP * 0.35 * Math.sin(col * WAVE_FREQ * 0.5 + row * 0.3 + t * 0.7);

                // --- Perspective projection ---
                // Translate to camera space
                const camRelZ = wz - CAM_Z;
                const camRelY = -CAM_Y + wy;      // Y is up in world, down on screen

                if (camRelZ <= 0) continue;       // behind camera, skip

                const scale  = FOCAL / camRelZ;
                const sx     = W / 2 + wx * scale;
                const sy     = HORIZON + (-camRelY) * scale;

                // Clip dots outside visible canvas area
                if (sx < -40 || sx > W + 40 || sy < 0 || sy > H + 20) continue;

                // --- Dot appearance ---
                // Radius: smaller and more subtle
                const radius = Math.max(0.3, scale * 5 + (wy / WAVE_AMP) * 0.6);

                // Alpha: very faint — barely visible like reference
                const alpha = Math.min(0.28, Math.max(0, scale * 1.1 - 0.02));

                // Color: light grey, only slightly affected by wave height
                const brightness = Math.floor(185 + (wy / WAVE_AMP) * 20);  // 165–205 (light grey range)

                dots.push({ sx, sy, radius, alpha, brightness, wz });
            }
        }

        // Painter's algorithm: draw farthest first so near dots overlap correctly
        dots.sort((a, b) => b.wz - a.wz);

        for (const d of dots) {
            ctx.beginPath();
            ctx.arc(d.sx, d.sy, d.radius, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(${d.brightness}, ${d.brightness}, ${d.brightness}, ${d.alpha})`;
            ctx.fill();
        }

        t += WAVE_SPEED;
        requestAnimationFrame(draw);
    }

    resize();
    window.addEventListener('resize', resize);
    draw();
})();

// ===================== FOOTER NEXUS WORDMARK REVEAL =====================
(function initNexusReveal() {
    const letters = document.querySelectorAll('#footer-nexus-wordmark .brand-letter');
    if (!letters.length) return;

    gsap.to(letters, {
        clipPath: 'inset(0% 0 -30px 0)',   // reveal from top, -30px bottom never clips
        duration: 1.1,
        ease: 'power4.out',
        stagger: 0.08,
        scrollTrigger: {
            trigger: '#footer-nexus-wordmark',
            start: 'top 92%',
            toggleActions: 'play none none reverse'
        }
    });
})();

// ===================== SMOOTH SCROLL NAVIGATION =====================
// Nav links with data-scroll use Lenis for buttery smooth scrolling
(function initSmoothNav() {
    document.querySelectorAll('[data-scroll]').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const targetId = link.getAttribute('href');
            const target = document.querySelector(targetId);
            if (!target) return;

            if (lenis) {
                let scrollTarget = target;
                if (target.parentElement && target.parentElement.classList.contains('pin-spacer')) {
                    scrollTarget = target.parentElement;
                }

                lenis.scrollTo(scrollTarget, {
                    offset: -80,
                    duration: 1.4,
                    easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t))
                });
            } else {
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        });
    });

    // Footer nav links also scroll smoothly
    document.querySelectorAll('.footer-nav-col a[href^="#"]').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const target = document.querySelector(link.getAttribute('href'));
            if (!target) return;
            if (lenis) {
                let scrollTarget = target;
                if (target.parentElement && target.parentElement.classList.contains('pin-spacer')) {
                    scrollTarget = target.parentElement;
                }
                lenis.scrollTo(scrollTarget, { offset: -80, duration: 1.4 });
            } else {
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        });
    });
})();

// ===================== DASHBOARD LOADING SCREEN =====================
// Any element with data-dashboard shows a loading overlay then redirects
(function initDashboardLoader() {
    const loader = document.getElementById('dashboard-loader');
    if (!loader) return;

    function showLoaderAndRedirect(e) {
        e.preventDefault();
        e.stopPropagation();

        // Show the loader
        loader.style.display = 'flex';
        // Force reflow so the animation plays
        loader.offsetHeight;
        loader.style.animation = 'loader-fade-in 0.35s ease forwards';

        // Redirect after 1 second
        setTimeout(() => {
            window.location.href = '/dashboard';
        }, 1000);
    }

    // Wire up all dashboard triggers
    document.querySelectorAll('[data-dashboard]').forEach(el => {
        el.addEventListener('click', showLoaderAndRedirect);
    });
})();

// ===================== SECTION SCROLL (KEYBOARD NAV) =====================
// Arrow keys or Page Up/Down to navigate between sections
(function initSectionKeyNav() {
    const sections = [
        '.hero-pinned-section',
        '#technology',
        '#products',
        '#expertise',
        '#key-features',
        '.team-cta-section',
        '.main-footer'
    ].map(sel => document.querySelector(sel)).filter(Boolean);

    if (!sections.length) return;

    // Find current section in viewport
    function getCurrentSectionIndex() {
        const scrollY = window.scrollY + window.innerHeight / 3;
        for (let i = sections.length - 1; i >= 0; i--) {
            if (sections[i].offsetTop <= scrollY) return i;
        }
        return 0;
    }

    document.addEventListener('keydown', (e) => {
        // Only if no input is focused
        if (document.activeElement.tagName === 'INPUT' || document.activeElement.tagName === 'TEXTAREA') return;

        let targetIdx = -1;
        if (e.key === 'PageDown' || (e.key === 'ArrowDown' && e.altKey)) {
            targetIdx = Math.min(getCurrentSectionIndex() + 1, sections.length - 1);
        } else if (e.key === 'PageUp' || (e.key === 'ArrowUp' && e.altKey)) {
            targetIdx = Math.max(getCurrentSectionIndex() - 1, 0);
        }

        if (targetIdx >= 0) {
            e.preventDefault();
            if (lenis) {
                lenis.scrollTo(sections[targetIdx], { offset: 0, duration: 1.2 });
            } else {
                sections[targetIdx].scrollIntoView({ behavior: 'smooth' });
            }
        }
    });
})();
