// ===================== API CONFIG ===================== //
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
const API_BASE = window.NEXUS_API_ROOT || '';

// ===================== BADGE RENDERER ===================== //
function getBadgeHtml(riskLevel) {
    const r = (riskLevel || '').toLowerCase();
    if (r === 'high') return `<div class="d-badge"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"></circle><path d="M12 8v4M12 16h.01"></path></svg>AT RISK</div>`;
    if (r === 'medium' || r === 'med') return `<div class="d-badge"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>WATCH</div>`;
    if (r === 'low') return `<div class="d-badge"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>ON TRACK</div>`;
    return '';
}

// risk level → CSS class
function riskClass(riskLevel) {
    const r = (riskLevel || '').toLowerCase();
    if (r === 'high')            return 'high';
    if (r === 'medium' || r === 'med') return 'med';
    return 'low';
}

// ===================== TICKET RENDERER ===================== //
function renderTickets(tickets) {
    const container = document.getElementById('tickets-container');
    if (!container) return;

    container.innerHTML = tickets.map(t => {
        const rl = riskClass(t.risk || t.riskLevel);
        const assignee = t.assignee || 'Unknown';
        const isUnassigned = assignee === 'Unassigned';
        const assigneeHtml = isUnassigned
            ? '<span style="color: var(--c-red); font-weight: 600;">Unassigned ⚠</span>'
            : `<span class="d-status-val">${assignee}</span>`;
        return `
            <div class="d-ticket-card risk-${rl}">
                <div class="d-card-header">
                    <span class="d-ticket-id">${t.id}</span>
                    ${getBadgeHtml(rl)}
                </div>

                <h3 class="d-ticket-title">${t.title}</h3>

                <div class="d-status-row">
                    <span>Assignee:</span>
                    ${assigneeHtml}
                </div>
                <div class="d-status-row">
                    <span>Status:</span>
                    <span class="d-status-val">${t.status || '—'}</span>
                </div>
                <div class="d-status-row">
                    <span>Due:</span>
                    <span class="d-status-val">${t.due || '&nbsp;'}</span>
                </div>

                <div class="d-divider"></div>

                <div class="d-insight-label">
                    <div class="d-dot"></div>
                    AI Insight
                </div>
                <p class="d-insight-text">
                    ${t.insight || t.action || 'No insight available.'}
                    <span style="color: #00d2ff; font-weight: 700; margin-left: 2px;">|</span>
                </p>
            </div>
        `;
    }).join('');

    // GSAP animations for tickets wait until loader is hidden.
}

// ===================== METRICS UPDATER ===================== //
function updateMetrics(summary) {
    const vals = document.querySelectorAll('.d-metric-value');
    if (!summary || !vals.length) return;

    const data = [
        summary.points_at_risk ?? 14,
        summary.days_remaining ?? 3,
        (summary.completion_pct ?? 68) + '%'
    ];

    vals.forEach((el, i) => {
        const raw = data[i];
        if (typeof raw === 'number' && typeof gsap !== 'undefined') {
            const obj = { val: 0 };
            gsap.to(obj, {
                val: raw, duration: 1.5, ease: 'power3.out',
                onUpdate: () => { el.innerText = Math.floor(obj.val); }
            });
        } else {
            el.innerText = raw;
        }
    });
}

// ===================== LOADING STATE ===================== //
function setLoading(isLoading) {
    const container = document.getElementById('tickets-container');
    if (!container) return;
    if (isLoading) {
        container.innerHTML = `
            <div style="grid-column:1/-1;display:flex;flex-direction:column;align-items:center;gap:16px;padding:60px 0;color:#a0aec0;">
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#00d8ff" stroke-width="2" stroke-linecap="round" style="animation:spin 1s linear infinite;">
                    <path d="M21.5 2v6h-6M2.13 15.57a9 9 0 1 0 3.14-10.2L2.5 8"/>
                </svg>
                <span style="font-size:14px;letter-spacing:.05em;">Running health check…</span>
            </div>`;
    }
}

// ===================== FETCH LIVE DATA ===================== //
async function fetchHealthData() {
    const btn = document.getElementById('run-health-btn');
    setLoading(true);
    if (btn) btn.classList.add('d-spinning');

    try {
        const res = await fetch(`${API_BASE}/api/sprint-health`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        updateMetrics(data.summary || {});
        renderTickets(data.tickets || []);
    } catch (err) {
        console.warn('Backend unavailable, using fallback data:', err);
        // Fallback to hardcoded mock so the page still looks good
        renderTickets(FALLBACK_TICKETS);
    } finally {
        if (btn) {
            setTimeout(() => btn.classList.remove('d-spinning'), 600);
        }
    }
}

// ===================== INTELLIGENCE RENDERER ===================== //
function renderIntelligenceData(data) {
    if (!data) return;

    // Predictive Planning
    const plan = data.predictive_planning?.prediction || {};
    const planConfidenceEl = document.getElementById('plan-confidence');
    const planCompletionEl = document.getElementById('plan-completion');
    const planCapacityEl = document.getElementById('plan-capacity');
    const planOutcomeEl = document.getElementById('plan-outcome');

    if (planConfidenceEl) planConfidenceEl.textContent = plan.confidence || 'Medium';
    if (planCompletionEl) planCompletionEl.textContent = (plan.predicted_completion_pct || 0) + '%';
    if (planCapacityEl) planCapacityEl.textContent = plan.capacity_score_next_sprint || '7/10';
    if (planOutcomeEl) planOutcomeEl.textContent = plan.sprint_outcome || 'Analyzing...';

    // Smart Rebalancing
    const reb = data.smart_rebalancing?.rebalancing_plan || {};
    const rebImpactEl = document.getElementById('rebalance-impact');
    const rebGainEl = document.getElementById('rebalance-gain');
    const rebMovesEl = document.getElementById('rebalance-moves');

    if (rebImpactEl) rebImpactEl.textContent = `Impact: ${reb.projected_improvement || 'High'}`;
    if (rebGainEl) rebGainEl.textContent = `+${(reb.completion_pct_after_estimate || 0) - (reb.completion_pct_before || 0)}%`;

    if (rebMovesEl) {
        const moves = reb.rebalancing_moves || [];
        if (moves.length === 0) {
            rebMovesEl.innerHTML = '<div class="d-intel-move-placeholder">Workload is already optimal.</div>';
        } else {
            rebMovesEl.innerHTML = moves.map(m => `
                <div class="d-intel-move">
                    <div class="d-intel-move-icon">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M16 3h5v5M4 20L21 3M21 16v5h-5M15 15l6 6M4 4l5 5"></path></svg>
                    </div>
                    <div class="d-intel-move-text">
                        <strong>${m.ticket_id}</strong>: ${m.from_engineer} → <strong>${m.to_engineer}</strong>
                    </div>
                </div>
            `).join('');
        }
    }
}

async function fetchIntelligenceData() {
    try {
        const res = await fetch(`${API_BASE}/api/intelligence/dashboard`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        renderIntelligenceData(data);
    } catch (err) {
        console.warn('Intelligence data unavailable:', err);
    }
}

// ===================== FALLBACK MOCK DATA ===================== //
const FALLBACK_TICKETS = [
    { id: "AUTH-412", risk: "high",   title: "Authentication Issue",     status: "overloaded", due: "", insight: "Priya Sharma is overloaded with 2 open PRs, 4 meetings today, and 2 unanswered slack messages." },
    { id: "API-334",  risk: "medium", title: "API Update",               status: "overloaded", due: "", insight: "Karan Singh is overloaded with 1 open PR, 5 meetings today, and 1 unanswered slack message." },
    { id: "DATA-389", risk: "low",    title: "Data Fix",                 status: "busy",       due: "", insight: "Arjun Mehta is busy with 1 open PR, 3 meetings today, recent commit, no unanswered messages." },
    { id: "SEC-089",  risk: "high",   title: "Security Patch",           status: "overloaded", due: "", insight: "Priya Sharma is overloaded with 2 open PRs, 4 meetings today, and 2 unanswered slack messages." },
    { id: "UI-105",   risk: "low",    title: "UI Update",                status: "busy",       due: "", insight: "Arjun Mehta is busy with 1 open PR, 3 meetings today, recent commit, no unanswered messages." },
    { id: "INFRA-201",risk: "low",    title: "Infrastructure Update",    status: "available",  due: "", insight: "Riya Patel is available with no open PRs, 1 meeting today, and a recent commit." }
];

// ===================== CALENDAR RENDERER ===================== //
function formatEventTime(isoStr) {
    try {
        const d = new Date(isoStr);
        return d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true });
    } catch { return isoStr; }
}

function renderCalendarData(data) {
    // Update stat tiles
    const countEl = document.getElementById('cal-meetings-count');
    const hoursEl = document.getElementById('cal-meeting-hours');
    const focusEl = document.getElementById('cal-focus-hours');
    const oooEl   = document.getElementById('cal-ooo-count');

    if (countEl) countEl.textContent = data.meetings_count ?? 0;
    if (hoursEl) hoursEl.textContent = (data.meetings_today ?? 0) + 'h';
    if (focusEl) focusEl.textContent = (data.focus_hours ?? 8) + 'h';
    if (oooEl)   oooEl.textContent   = data.ooo_count ?? 0;

    // Animate stat values with GSAP
    if (typeof gsap !== 'undefined') {
        document.querySelectorAll('.d-cal-stat').forEach((card, i) => {
            gsap.from(card, { y: 30, opacity: 0, duration: 0.8, ease: 'power3.out', delay: 0.1 * i });
        });
    }

    // Render events list
    const listEl = document.getElementById('cal-events-list');
    if (!listEl) return;

    const events = data.events_today || [];
    if (events.length === 0) {
        listEl.innerHTML = `
            <div class="d-cal-empty">
                <div class="d-cal-empty-icon">📅</div>
                No meetings scheduled today — enjoy your focus time!
            </div>`;
        return;
    }

    listEl.innerHTML = `
        <div class="d-cal-section-title">Today's Schedule</div>
        ${events.map(e => {
            const isAllDay = e.all_day;
            const timeStr = isAllDay
                ? 'All Day'
                : `${formatEventTime(e.start)} – ${formatEventTime(e.end)}`;
            const durStr = e.duration_min > 0 ? `${e.duration_min} min` : '';
            return `
                <div class="d-cal-event">
                    <span class="d-cal-event-time">${timeStr}</span>
                    <span class="d-cal-event-dot ${isAllDay ? 'all-day' : ''}"></span>
                    <span class="d-cal-event-title">${e.title}</span>
                    <span class="d-cal-event-dur">${durStr}</span>
                </div>`;
        }).join('')}`;

    // GSAP animations for calendar wait until loader is hidden.
}

async function fetchCalendarData() {
    try {
        const res = await fetch(`${API_BASE}/api/calendar-stats`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        renderCalendarData(data);
    } catch (err) {
        console.warn('Calendar data unavailable:', err);
        renderCalendarData({
            meetings_count: 0, meetings_today: 0,
            focus_hours: 8, ooo_count: 0, events_today: []
        });
    }
}

// ===================== NEXUS AI GUIDE (live /api/chat) ===================== //
function initDashboardGuideChat() {
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
        requestAnimationFrame(() => input.focus());
    }

    function closeChat() {
        shell.classList.remove('is-open');
        shell.setAttribute('aria-hidden', 'true');
        shell.hidden = true;
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

        try {
            const chatUrl = `${API_BASE}/api/chat`;
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
            appendBubble('assistant', 'Network error. URL: ' + API_BASE + '/api/chat — start uvicorn on 8008.', true);
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

    const closeBtn = document.getElementById('nexus-guide-close');
    if (closeBtn) closeBtn.addEventListener('click', closeChat);

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
}

// ===================== DOM READY ===================== //
document.addEventListener('DOMContentLoaded', () => {
    initDashboardGuideChat();

    // Wire up the Run Health Check button
    const btn = document.getElementById('run-health-btn');
    if (btn) {
        btn.addEventListener('click', () => {
            fetchHealthData();
            fetchIntelligenceData();
        });
    }

    // Initialize the antigravity background
    initAntigravityField();

    // Initialize Splash Loader overlay and await backend data
    (function initSplashLoader() {
        const loader = document.getElementById('app-loader');
        const msgEl = document.getElementById('fake-loader-msg');
        
        if (!loader || !msgEl) {
            // Fallback if missing elements
            fetchHealthData();
            fetchCalendarData();
            initDashboardAnimations();
            return;
        }

        const messages = [
            "Connecting to GitHub...",
            "Reading Jira sprint...",
            "Scanning Slack channels...",
            "Checking team calendar...",
            "Running AI analysis...",
            "Sprint health ready."
        ];

        // 1. Fetch live data IMMEDIATELY in the background
        const dataPromise = Promise.all([
            fetchHealthData(),
            fetchCalendarData(),
            fetchIntelligenceData()
        ]);

        // 2. Cycle messages while we fetch
        let idx = 0;
        const msgInterval = setInterval(async () => {
            idx++;
            if (idx >= messages.length - 1) {
                // Reached the final active checking state
                clearInterval(msgInterval);
                
                // Wait to make sure the API calls actually finished before saying 'ready'
                await dataPromise;
                
                // Show final ready message
                msgEl.style.opacity = 0;
                setTimeout(() => {
                    msgEl.textContent = messages[messages.length - 1];
                    msgEl.style.opacity = 1;

                    // 3. Fade out loader & refresh GSAP animations
                    setTimeout(() => {
                        loader.classList.add('hidden');
                        initDashboardAnimations();
                        
                        // Force GSAP to recalculate bounds after population
                        if (typeof ScrollTrigger !== 'undefined') {
                            setTimeout(() => {
                                ScrollTrigger.refresh();
                                animateLoadedData();
                            }, 100);
                        }
                    }, 600);

                    // 4. Remove loader from DOM entirely after transition ends
                    setTimeout(() => loader.remove(), 1600);
                }, 200);

            } else {
                msgEl.style.opacity = 0;
                setTimeout(() => {
                    msgEl.textContent = messages[idx];
                    msgEl.style.opacity = 1;
                }, 200);
            }
        }, 500);
    })();
});

// ===================== GSAP ANIMATIONS ===================== //
function initDashboardAnimations() {
    if (typeof gsap === 'undefined') return;
    
    // Header & Meta Elements Cascade
    gsap.from('.header, .d-subtitle, .d-title, .d-controls', {
        y: 40,
        opacity: 0,
        duration: 1.2,
        stagger: 0.1,
        ease: 'power3.out',
        delay: 0.2
    });

    // Macro Metrics Counters & Entry
    const metricCards = document.querySelectorAll('.d-metric-card');
    if (metricCards.length) {
        gsap.from(metricCards, {
            y: 50,
            opacity: 0,
            duration: 1.2,
            stagger: 0.15,
            ease: 'power4.out',
            delay: 0.4
        });
    }

    // Ticking Odometer Effect
    document.querySelectorAll('.d-metric-value').forEach((el) => {
        const rawVal = el.innerText;
        const numMatch = rawVal.match(/[\d,]+/);
        if (!numMatch) return;
        const targetNum = parseInt(numMatch[0].replace(/,/g, ''));
        const suffix = rawVal.replace(/[\d,]+/g, '');
        
        const obj = { val: 0 };
        gsap.to(obj, {
            val: targetNum,
            duration: 2,
            ease: 'power3.out',
            delay: 0.6,
            onUpdate: () => {
                el.innerText = Math.floor(obj.val) + suffix;
            }
        });
    });
}

function animateLoadedData() {
    if (typeof gsap === 'undefined') return;

    // Interactive ScrollTrigger for Ticket Cards
    if (typeof ScrollTrigger !== 'undefined') {
        gsap.registerPlugin(ScrollTrigger);
        gsap.utils.toArray('.d-ticket-card').forEach((card, i) => {
            gsap.from(card, {
                scrollTrigger: {
                    trigger: card,
                    start: 'top 95%',
                    toggleActions: 'play none none reverse'
                },
                y: 60,
                opacity: 0,
                duration: 0.8,
                ease: 'power3.out',
                delay: (i % 3) * 0.1 
            });
        });
    }

    // AI Intelligence
    gsap.from('.d-intel-card', {
        y: 40, opacity: 0, duration: 1, stagger: 0.2, ease: 'power3.out', delay: 0.2
    });
    gsap.from('.d-intel-move', {
        x: -20, opacity: 0, duration: 0.5, stagger: 0.1, ease: 'power2.out', delay: 0.6
    });

    // Calendar
    gsap.from('.d-cal-event', {
        x: -30, opacity: 0, duration: 0.5, stagger: 0.06, ease: 'power2.out', delay: 0.3
    });
}

// ===================== ANTIGRAVITY EFFECT ===================== //
function initAntigravityField() {
    const canvas = document.getElementById('antigravity-canvas');
    if (!canvas) return;
    const parent = canvas.parentElement;
    if (!parent) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // NeoLeaf Nexus Cosmic Palette
    const PALETTE = ['#00d8ff', '#2f3ce0', '#3b82f6', '#a855f7', '#ffffff'];
    const COUNT = 1200;
    const SPHERE_R = 0.55;
    const FOCAL = 900;
    const ROT_X = 0.0002;
    const ROT_Y = 0.0005;
    const MOUSE_R = 180;
    const DRAG_F = 0.08;
    const DAMPING = 0.88;

    function randSphere() {
      const u = Math.random();
      const v = Math.random();
      const theta = 2 * Math.PI * u;
      const phi = Math.acos(2 * v - 1);
      return {
        sx: Math.sin(phi) * Math.cos(theta),
        sy: Math.sin(phi) * Math.sin(theta),
        sz: Math.cos(phi),
        ox: 0,
        oy: 0,
        vx: 0,
        vy: 0,
        color: PALETTE[Math.floor(Math.random() * PALETTE.length)],
        baseLen: 4 + Math.random() * 7,
        thick: 0.8 + Math.random() * 1.2
      };
    }

    function rotateX(x, y, z, a) {
      const cos = Math.cos(a);
      const sin = Math.sin(a);
      return { x, y: y * cos - z * sin, z: y * sin + z * cos };
    }

    function rotateY(x, y, z, a) {
      const cos = Math.cos(a);
      const sin = Math.sin(a);
      return { x: x * cos + z * sin, y, z: -x * sin + z * cos };
    }

    let W = 0;
    let H = 0;
    let dpr = 1;
    let cx = 0;
    let cy = 0;
    let sphereR = 0;
    let rotX = 0;
    let rotY = 0;
    let scx = 0;
    let scy = 0;
    let svx = 0.4;
    let svy = 0.2;
    let particles = [];
    let raf = 0;

    const mouse = { x: -9999, y: -9999 };
    let prevMX = -9999;
    let prevMY = -9999;

    function build() {
      particles = [];
      for (let i = 0; i < COUNT; i++) particles.push(randSphere());
    }

    function resize() {
      const rect = parent.getBoundingClientRect();
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      W = Math.max(1, Math.floor(rect.width));
      H = Math.max(1, Math.floor(rect.height));
      canvas.width = Math.floor(W * dpr);
      canvas.height = Math.floor(H * dpr);
      canvas.style.width = `${W}px`;
      canvas.style.height = `${H}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      cx = W / 2;
      cy = H / 2;
      scx = cx;
      scy = cy;
      sphereR = Math.min(W, H) * SPHERE_R;
      build();
    }

    const loop = () => {
      ctx.clearRect(0, 0, W, H);

      rotX += ROT_X;
      rotY += ROT_Y;

      let mouseDX = 0;
      let mouseDY = 0;
      if (prevMX > -9000 && mouse.x > -9000) {
        mouseDX = mouse.x - prevMX;
        mouseDY = mouse.y - prevMY;
      }

      if (mouse.x > -9000) {
        const moved = mouse.x !== prevMX || mouse.y !== prevMY;
        if (moved) {
          svx += (mouse.x - scx) * 0.0008;
          svy += (mouse.y - scy) * 0.0008;
        }
      }
      prevMX = mouse.x;
      prevMY = mouse.y;

      const t = Date.now() * 0.0003;
      svx += Math.sin(t * 1.3) * 0.0012;
      svy += Math.cos(t * 0.9) * 0.0012;
      svx *= 0.982;
      svy *= 0.982;
      scx += svx;
      scy += svy;

      for (const p of particles) {
        let r1 = rotateY(p.sx, p.sy, p.sz, rotY);
        const r2 = rotateX(r1.x, r1.y, r1.z, rotX);
        let x = r2.x;
        let y = r2.y;
        let z = r2.z;

        const scale = FOCAL / (FOCAL + z * sphereR);
        const px = scx + x * sphereR * scale;
        const py = scy + y * sphereR * scale;
        const depth = (z + 1) / 2;

        if (depth < 0.05) {
          p.ox *= DAMPING;
          p.oy *= DAMPING;
          continue;
        }

        const sx = px + p.ox;
        const sy = py + p.oy;

        const mdx = mouse.x - sx;
        const mdy = mouse.y - sy;
        const dist = Math.sqrt(mdx * mdx + mdy * mdy);

        if (dist < MOUSE_R && mouse.x > -9000) {
          const f = 1 - dist / MOUSE_R;
          p.vx += mouseDX * DRAG_F * f;
          p.vy += mouseDY * DRAG_F * f;
        }

        p.ox += p.vx;
        p.oy += p.vy;
        p.vx *= DAMPING;
        p.vy *= DAMPING;
        p.ox *= 0.97;
        p.oy *= 0.97;

        const rx = px + p.ox;
        const ry = py + p.oy;

        const rimFactor = 1 - Math.abs(z);
        // Smoother, less aggressive falloff for a balanced look
        const opacity = 0.12 + Math.pow(rimFactor, 1.5) * 0.78; 
        // Moderate size difference: inner is 0.5x, outer is 1.4x base thickness
        const thick = p.thick * (0.5 + Math.pow(rimFactor, 1.2) * 0.9);

        ctx.globalAlpha = opacity;
        ctx.fillStyle = p.color;
        ctx.beginPath();
        ctx.arc(rx, ry, thick * 1.5, 0, Math.PI * 2);
        ctx.fill();
      }

      ctx.globalAlpha = 1;
      raf = requestAnimationFrame(loop);
    };

    const onPointerMove = (e) => {
      const pr = parent.getBoundingClientRect();
      if (
        e.clientX < pr.left ||
        e.clientX > pr.right ||
        e.clientY < pr.top ||
        e.clientY > pr.bottom
      ) {
        mouse.x = -9999;
        mouse.y = -9999;
        return;
      }
      const c = canvas.getBoundingClientRect();
      mouse.x = (e.clientX - c.left) * (W / c.width);
      mouse.y = (e.clientY - c.top) * (H / c.height);
    };

    let resizeTimer;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(resize, 100);
    });
    
    window.addEventListener('pointermove', onPointerMove, { passive: true });

    resize();
    raf = requestAnimationFrame(loop);
}
