/**
 * ApplyTools Extension — Overlay Wizard (overlay.js) — v3.2
 *
 * Changes:
 * - Removed chrome.storage.local for picker_state
 * - _saveState() now saves selectors to Django via API immediately
 * - Reset button clears selectors in Django (sends empty strings)
 * - Draggable panel
 * - Clickable step indicators
 * - Step 5 (detail_container_css) uses scope=document, not firstCard
 *   (detail page has no listing-card hierarchy)
 *
 * v3.2 changes (auto-extract disabled by user request):
 * - checkResume() is now a no-op that only clears stale extraction_state.
 *   It NO LONGER auto-starts extraction on page load.
 * - _toggleExtraction() no longer auto-navigates to the next page.
 *   Multi-page extraction requires the user to manually click "Extract" on
 *   each page.
 * - content.js no longer calls overlay.checkResume() — extraction is now
 *   STRICTLY MANUAL via the "🚀 Extract This Page" button.
 */

class Overlay {
    constructor(picker) {
        this.picker = picker;
        this.website = null;
        this.state = {
            listing_css: '',
            title_css: '',
            link_css: '',
            company_css: '',
            detail_container_css: '',
            pagination_url_pattern: '',
        };
        this.step = 0;
        this.collapsed = false;
        this.extractor = null;
        this.isExtracting = false;
        this.cancelled = false;
        this._highlights = [];
        this._create();
    }

    _create() {
        this.host = document.createElement('div');
        this.host.id = 'applytools-overlay-host';
        this.host.style.cssText = 'position:fixed;top:16px;right:16px;z-index:2147483647;font-family:Inter,sans-serif;';
        this.shadow = this.host.attachShadow({ mode: 'open' });
        this.shadow.innerHTML = this._getCSS() + this._getHTML();
        document.body.appendChild(this.host);
        this._wireEvents();
        this._makeDraggable();
    }

    _getCSS() {
        return `<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
:host { all: initial; }
.panel { width: 360px; background: #fff; border: 1px solid #E2E8F0; border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.12); overflow: hidden; }
.header { display: flex; align-items: center; gap: 8px; padding: 12px 16px; background: linear-gradient(135deg, #4F46E5, #7C3AED); color: #fff; cursor: move; }
.header .icon { font-size: 1.1rem; } .header .title { font-weight: 700; font-size: 0.9rem; flex: 1; }
.header button { background: rgba(255,255,255,0.15); border: none; color: #fff; width: 24px; height: 24px; border-radius: 6px; cursor: pointer; font-size: 0.8rem; display: flex; align-items: center; justify-content: center; }
.body { padding: 16px; max-height: 600px; overflow-y: auto; }
.website-info { font-size: 0.78rem; padding: 10px 12px; background: #F1F5F9; border-radius: 8px; margin-bottom: 16px; }
.website-info .name { font-weight: 700; color: #0F172A; font-size: 0.9rem; }
.website-info .url { color: #64748B; word-break: break-all; margin-top: 2px; }
.step-indicator { display: flex; gap: 4px; margin-bottom: 16px; }
.step-dot { flex: 1; height: 4px; border-radius: 2px; background: #E2E8F0; transition: all 0.2s; cursor: pointer; }
.step-dot:hover { background: #94A3B8; }
.step-dot.active { background: #4F46E5; cursor: default; } .step-dot.done { background: #10B981; cursor: pointer; }
.step-title { font-size: 1rem; font-weight: 700; color: #0F172A; margin-bottom: 6px; }
.step-desc { font-size: 0.8rem; color: #64748B; margin-bottom: 16px; line-height: 1.5; }
.selector-box { font-family: monospace; font-size: 0.78rem; padding: 10px 12px; background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; margin-bottom: 12px; word-break: break-all; min-height: 42px; display: flex; align-items: center; }
.selector-box.empty { color: #94A3B8; font-style: italic; }
.selector-box.filled { border-color: #10B981; background: rgba(16,185,129,0.05); }
.selector-box .count { margin-left: auto; color: #10B981; font-weight: 600; }
.btn { padding: 8px 16px; border: none; border-radius: 8px; cursor: pointer; font-size: 0.82rem; font-weight: 600; transition: all 0.15s; display: inline-flex; align-items: center; gap: 6px; }
.btn-primary { background: #4F46E5; color: #fff; } .btn-primary:hover { background: #4338CA; }
.btn-success { background: #10B981; color: #fff; } .btn-success:hover { background: #059669; }
.btn-secondary { background: #F1F5F9; color: #334155; } .btn-secondary:hover { background: #E2E8F0; }
.btn-pick { background: #F59E0B; color: #fff; } .btn-pick:hover { background: #D97706; }
.btn-danger { background: #F43F5E; color: #fff; }
.btn:disabled { opacity: 0.4; cursor: not-allowed; }
.nav-btns { display: flex; gap: 8px; margin-top: 16px; }
.nav-btns .btn { flex: 1; justify-content: center; }
.progress-wrap { margin-top: 12px; display: none; }
.progress-wrap.active { display: block; }
.progress-label { font-size: 0.72rem; color: #64748B; margin-bottom: 4px; }
.progress-track { height: 6px; background: #E2E8F0; border-radius: 999px; overflow: hidden; }
.progress-fill { height: 100%; background: linear-gradient(90deg, #4F46E5, #7C3AED); border-radius: 999px; transition: width 0.3s; width: 0%; }
.progress-fill.success { background: linear-gradient(90deg, #10B981, #059669); }
.config-row { display: flex; align-items: center; gap: 8px; margin: 8px 0; font-size: 0.78rem; color: #64748B; }
.config-row input[type="number"] { width: 60px; padding: 4px 8px; border: 1px solid #cbd5e1; border-radius: 4px; font-size: 0.78rem; }
.config-row input[type="checkbox"] { width: 16px; height: 16px; }
.preview-list { margin-top: 10px; max-height: 180px; overflow-y: auto; display: none; }
.preview-list.active { display: block; }
.preview-item { font-size: 0.75rem; padding: 8px 10px; background: #F8FAFC; border-radius: 6px; margin-bottom: 4px; border: 1px solid #E2E8F0; }
.preview-item .title { font-weight: 600; color: #0F172A; }
.preview-item .company { color: #64748B; }
.status-msg { font-size: 0.75rem; padding: 8px 12px; border-radius: 6px; margin-top: 10px; display: none; }
.status-msg.success { display: block; background: #D1FAE5; color: #065F46; }
.status-msg.error { display: block; background: #FFE4E6; color: #9F1239; }
.status-msg.info { display: block; background: #EEF2FF; color: #3730A3; }
.collapsed-btn { width: 48px; height: 48px; border-radius: 50%; cursor: pointer; background: linear-gradient(135deg, #4F46E5, #7C3AED); display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 12px rgba(79,70,229,0.4); font-size: 1.2rem; color: #fff; position: fixed; top: 16px; right: 16px; }
</style>`;
    }

    _getHTML() {
        return `
<div class="panel" id="panel">
    <div class="header" id="dragHandle">
        <span class="icon">🧩</span>
        <span class="title">ApplyTools</span>
        <button id="btnCollapse">—</button>
        <button id="btnClose">×</button>
    </div>
    <div class="body" id="body"></div>
</div>
<div class="collapsed-btn" id="collapsedBtn" style="display:none;">🧩</div>`;
    }

    _wireEvents() {
        const $ = (id) => this.shadow.getElementById(id);
        $('btnCollapse').addEventListener('click', () => this._toggleCollapse());
        $('btnClose').addEventListener('click', () => this.hide());
        $('collapsedBtn').addEventListener('click', () => this._toggleCollapse());
    }

    _makeDraggable() {
        const handle = this.shadow.getElementById('dragHandle');
        const panel = this.shadow.getElementById('panel');
        let isDragging = false;
        let startX, startY, initialX, initialY;

        handle.addEventListener('mousedown', (e) => {
            if (e.target.tagName === 'BUTTON') return;
            isDragging = true;
            startX = e.clientX;
            startY = e.clientY;
            const rect = panel.getBoundingClientRect();
            initialX = rect.left;
            initialY = rect.top;
            panel.style.transition = 'none';
        });

        document.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            e.preventDefault();
            const dx = e.clientX - startX;
            const dy = e.clientY - startY;
            panel.style.position = 'fixed';
            panel.style.left = (initialX + dx) + 'px';
            panel.style.top = (initialY + dy) + 'px';
            panel.style.right = 'auto';
            panel.style.bottom = 'auto';
        });

        document.addEventListener('mouseup', () => {
            if (isDragging) {
                isDragging = false;
                panel.style.transition = '';
            }
        });
    }

    setWebsite(website) { this.website = website; this._renderStep(); }
    setState(state) { this.state = { ...this.state, ...state }; this._renderStep(); }

    _renderStep() {
        const body = this.shadow.getElementById('body');
        const hasSelectors = Object.values(this.state).some(v => v);
        if (!hasSelectors && this.step === 0) {
            body.innerHTML = this._welcomeHTML();
            this.shadow.getElementById('btnStart')?.addEventListener('click', () => { this.step = 1; this._renderStep(); });
            this.shadow.getElementById('btnReset')?.addEventListener('click', async () => {
                if (!confirm('Clear all saved selectors? You will need to re-pick them.')) return;
                this.state = { listing_css:'', title_css:'', link_css:'', company_css:'', detail_container_css:'', pagination_url_pattern:'' };
                await this._saveState();
                this._renderStep();
            });
            return;
        }
        if (this.step === 0) this.step = 8;

        if (this.step >= 1 && this.step <= 5) {
            body.innerHTML = this._pickerStepHTML(this.step);
            this._wirePickerStep();
        } else if (this.step === 6) {
            body.innerHTML = this._paginationStepHTML();
            this._wirePaginationStep();
        } else if (this.step === 7) {
            body.innerHTML = this._testStepHTML();
            this._wireTestStep();
        } else if (this.step === 8) {
            body.innerHTML = this._settingsStepHTML();
            this._wireSettingsStep();
        }
    }

    _welcomeHTML() {
        const w = this.website || {};
        const hasOldState = Object.values(this.state).some(v => v);
        return `
        <div class="website-info">
            <div class="name">${escapeHtml(w.name || 'Unknown Website')}</div>
            <div class="url">${escapeHtml(w.base_url || '')}</div>
        </div>
        <div class="step-desc" style="margin-bottom: 20px;">Welcome! This wizard will help you configure selectors.<br><br>You'll pick 5 CSS selectors step by step:<br>1. Listing cards container<br>2. Position title<br>3. Position link<br>4. University/institution name<br>5. Detail page content<br>6. Pagination detection</div>
        <button class="btn btn-primary" id="btnStart" style="width:100%;margin-bottom:8px;">🚀 Start Setup</button>
        ${hasOldState ? '<button class="btn btn-danger" id="btnReset" style="width:100%;">🗑️ Reset All Selectors</button>' : ''}`;
    }

    _pickerStepHTML(step) {
        const configs = {
            1: { key: 'listing_css', title: 'Listing Container', desc: 'Click on the OUTER card that wraps each position.', placeholder: 'Click "Pick" then click a position card' },
            2: { key: 'title_css', title: 'Position Title', desc: 'Click on the title text.', placeholder: 'Click "Pick" then click a title' },
            3: { key: 'link_css', title: 'Position Link', desc: 'Click on the link or button that opens the position details.', placeholder: 'Click "Pick" then click the link/button' },
            4: { key: 'company_css', title: 'University / Institution', desc: 'Click on the element showing the university name.', placeholder: 'Click "Pick" then click the institution name' },
            5: { key: 'detail_container_css', title: 'Detail Content', desc: 'Navigate to a detail page, then click on the main description area.', placeholder: 'Open a detail page, then click "Pick"' },
        };
        const cfg = configs[step];
        const value = this.state[cfg.key];
        const count = value ? countMatches(value, document) : 0;

        let dots = '';
        for (let i = 1; i <= 6; i++) {
            const cls = i === step ? 'active' : (i < step || (this.state[configs[i]?.key])) ? 'done' : '';
            dots += `<span class="step-dot ${cls}" data-step="${i}"></span>`;
        }

        return `
        <div class="website-info"><div class="name">${escapeHtml(this.website?.name || '')}</div><div class="url" style="font-size:0.7rem;">${escapeHtml(this.website?.base_url || '')}</div></div>
        <div class="step-indicator" id="stepIndicator">${dots}</div>
        <div class="step-title">Step ${step}/6: ${cfg.title}</div>
        <div class="step-desc">${cfg.desc}</div>
        <div class="selector-box ${value ? 'filled' : 'empty'}">${value ? escapeHtml(value) + '<span class="count">(' + count + ' match' + (count !== 1 ? 'es' : '') + ')</span>' : cfg.placeholder}</div>
        <div class="nav-btns">${step > 1 ? '<button class="btn btn-secondary" id="btnPrev">← Back</button>' : ''}<button class="btn btn-pick" id="btnPick">${value ? '🔄 Re-pick' : '📋 Pick'}</button>${value ? '<button class="btn btn-success" id="btnNext">Next →</button>' : ''}</div>
        <div class="status-msg" id="statusMsg"></div>`;
    }

    _wirePickerStep() {
        const $ = (id) => this.shadow.getElementById(id);
        const step = this.step;
        const configs = {1:'listing_css',2:'title_css',3:'link_css',4:'company_css',5:'detail_container_css'};
        const key = configs[step];

        $('btnPrev')?.addEventListener('click', () => { this._clearHighlights(); this.step--; this._renderStep(); });
        $('btnNext')?.addEventListener('click', () => { this._clearHighlights(); this.step++; this._renderStep(); });

        const pickBtn = $('btnPick');
        pickBtn.addEventListener('click', () => {
            // Steps 2-4 are sub-selectors INSIDE one listing card on a list page,
            // so they get scoped to firstCard. Step 1 (listing_css) and Step 5
            // (detail_container_css) are page-level selectors on the FULL page,
            // so they MUST use document — otherwise ancestor IDs like #editor on a
            // detail page fall outside the picker scope and get rejected.
            let scope = document;
            if ((step === 2 || step === 3 || step === 4) && this.state.listing_css) {
                const firstCard = document.querySelector(this.state.listing_css);
                if (firstCard) scope = firstCard;
            }
            pickBtn.classList.add('btn-secondary'); pickBtn.textContent = '⏳ Picking...';
            this.picker.enable({ scope, onSelect: (selector, count) => { this.picker.disable(); pickBtn.classList.remove('btn-secondary'); this.state[key] = selector; this._saveState(); this._highlightElements(selector); this._renderStep(); console.log('[ApplyTools] Step ' + step + ' selector:', selector, '(' + count + ' matches)'); }, onCancel: () => { pickBtn.classList.remove('btn-secondary'); pickBtn.textContent = this.state[key] ? '🔄 Re-pick' : '📋 Pick'; } });
        });

        if (this.state[key]) { this._highlightElements(this.state[key]); }

        const indicator = $('stepIndicator');
        if (indicator) {
            indicator.querySelectorAll('.step-dot').forEach(dot => {
                dot.addEventListener('click', (e) => {
                    const targetStep = parseInt(e.target.dataset.step);
                    if (targetStep < step || this.state[configs[targetStep]]) {
                        this._clearHighlights();
                        this.step = targetStep;
                        this._renderStep();
                    }
                });
            });
        }
    }

    _paginationStepHTML() {
        const pagination = detectPagination();
        let paginationInfo = '';
        if (pagination && pagination.type) { paginationInfo = '<div class="selector-box filled" style="margin-bottom:10px;"><strong style="color:#10B981;">' + escapeHtml(pagination.description) + '</strong>' + (pagination.url ? '<div style="font-size:0.7rem;color:var(--info);margin-top:6px;word-break:break-all;">🔗 ' + escapeHtml(pagination.url) + '</div>' : '') + '</div>'; }
        return `<div class="website-info"><div class="name">${escapeHtml(this.website?.name || '')}</div></div><div class="step-indicator"><div class="step-dot done"></div><div class="step-dot done"></div><div class="step-dot done"></div><div class="step-dot done"></div><div class="step-dot done"></div><div class="step-dot active"></div></div><div class="step-title">Step 6/6: Pagination</div><div class="step-desc">Pagination auto-detected. If wrong, navigate to next page and come back.</div>${paginationInfo}<div class="status-msg info" style="display:block;">Current URL: ${escapeHtml(window.location.href.substring(0, 100))}...</div><div class="nav-btns"><button class="btn btn-secondary" id="btnPrev">← Back</button><button class="btn btn-secondary" id="btnSkip">Skip</button><button class="btn btn-success" id="btnNext">Done →</button></div>`;
    }

    _wirePaginationStep() {
        const $ = (id) => this.shadow.getElementById(id);
        $('btnPrev').addEventListener('click', () => { this.step--; this._renderStep(); });
        $('btnSkip').addEventListener('click', () => { this.step = 7; this._renderStep(); });
        $('btnNext').addEventListener('click', () => { const pagination = detectPagination(); if (pagination && pagination.type) { this.state.pagination_url_pattern = pagination.url || ''; this._showStatus('Pagination: ' + pagination.description, 'success'); console.log('[ApplyTools] Pagination:', pagination); } this._saveState(); this.step = 7; this._renderStep(); });
    }

    _testStepHTML() {
        return `<div class="website-info"><div class="name">${escapeHtml(this.website?.name || '')}</div></div><div class="step-title">🧪 Test Extraction</div><div class="step-desc">Let's test the selectors by extracting positions from this page.</div><button class="btn btn-primary" id="btnTest" style="width:100%;margin-bottom:10px;">🔍 Test Extract</button><div class="preview-list" id="previewList"></div><div class="progress-wrap" id="progressWrap"><div class="progress-label" id="progressLabel">Testing...</div><div class="progress-track"><div class="progress-fill" id="progressFill"></div></div></div><div class="status-msg" id="statusMsg"></div><div class="nav-btns"><button class="btn btn-secondary" id="btnEditSelectors">← Edit Selectors</button><button class="btn btn-success" id="btnGoSettings">Continue →</button></div>`;
    }

    _wireTestStep() {
        const $ = (id) => this.shadow.getElementById(id);
        $('btnEditSelectors').addEventListener('click', () => { this.step = 1; this._renderStep(); });
        $('btnGoSettings').addEventListener('click', () => { this.step = 8; this._renderStep(); });
        $('btnTest').addEventListener('click', async () => { $('btnTest').disabled = true; $('btnTest').textContent = '⏳ Extracting...'; $('progressWrap').classList.add('active'); $('progressFill').style.width = '20%'; const ext = new Extractor({ listing_css: this.state.listing_css, title_css: this.state.title_css, link_css: this.state.link_css, company_css: this.state.company_css, detail_container_css: '', base_url: this.website?.base_url || window.location.origin }); const positions = ext.extractListing(); $('progressFill').style.width = '100%'; if (positions.length === 0) { this._showStatus('❌ No positions found!', 'error'); } else { this._showStatus('✅ Found ' + positions.length + ' positions!', 'success'); const list = $('previewList'); list.innerHTML = '<div class="step-desc">Preview (' + positions.length + ' found):</div>'; positions.slice(0, 5).forEach(p => { const item = document.createElement('div'); item.className = 'preview-item'; item.innerHTML = '<div class="title">' + escapeHtml(p.title.substring(0, 70)) + '</div><div class="company">' + escapeHtml(p.company || '') + '</div>'; list.appendChild(item); }); list.classList.add('active'); this._highlightCards(); console.log('[ApplyTools] Test extraction:', positions.length, 'positions'); positions.forEach((p, i) => console.log('  ' + (i+1) + '.', p.title, '|', p.company, '|', p.url)); } $('btnTest').disabled = false; $('btnTest').textContent = '🔍 Test Extract'; });
    }

    _settingsStepHTML() {
        const hasListing = !!this.state.listing_css;
        return `<div class="website-info"><div class="name">${escapeHtml(this.website?.name || '')}</div><div class="url" style="font-size:0.7rem;">${escapeHtml(this.website?.base_url || '')}</div></div><div class="step-title">⚙️ Settings</div><div class="config-row"><input type="checkbox" id="multiPage" checked><label for="multiPage">Multi-page (auto-navigate)</label></div><div class="config-row">Max pages: <input type="number" id="maxPages" value="10" min="1" max="100"></div><div class="config-row">Delay between details: <input type="number" id="detailDelay" value="1.5" min="0.5" step="0.5"> sec</div><button class="btn btn-success" id="btnExtract" style="width:100%;margin-top:10px;" ${hasListing ? '' : 'disabled'}>🚀 Extract This Page</button><button class="btn btn-secondary" id="btnEditSelectors" style="width:100%;margin-top:6px;">✏️ Edit Selectors</button><button class="btn btn-danger" id="btnResetSelectors" style="width:100%;margin-top:6px;">🗑️ Reset All Selectors</button><div class="progress-wrap" id="progressWrap"><div class="progress-label" id="progressLabel">Starting...</div><div class="progress-track"><div class="progress-fill" id="progressFill"></div></div></div><div class="status-msg" id="statusMsg"></div>`;
    }

    _wireSettingsStep() {
        const $ = (id) => this.shadow.getElementById(id);
        $('btnEditSelectors').addEventListener('click', () => { this.step = 1; this._renderStep(); });
        $('btnExtract').addEventListener('click', () => this._toggleExtraction());
        
        // FIX: Reset button now saves empty selectors to Django
        $('btnResetSelectors')?.addEventListener('click', async () => {
            if (!confirm('Clear all saved selectors?')) return;
            this.state = { listing_css:'', title_css:'', link_css:'', company_css:'', detail_container_css:'', pagination_url_pattern:'' };
            await this._saveState(); // Saves empty strings to Django
            this.step = 0;
            this._renderStep();
        });
    }

    async _toggleExtraction() {
        if (this.isExtracting) { this.cancelled = true; if (this.extractor) this.extractor.cancel(); this.isExtracting = false; return; }
        this.isExtracting = true; this.cancelled = false;
        const delaySec = parseFloat(this.shadow.getElementById('detailDelay')?.value || 1.5);
        this.extractor = new Extractor({ ...this.state, base_url: this.website?.base_url || window.location.origin, detail_delay: delaySec * 1000 });

        const positions = this.extractor.extractListing();
        if (!positions.length) { this._showStatus('❌ No positions found.', 'error'); this.isExtracting = false; return; }

        // ALWAYS fetch details if a detail selector is set
        if (this.state.detail_container_css) {
            this._showProgress('Fetching details: 0/' + positions.length, 0);
            await this.extractor.fetchDetails(positions, (i, total) => {
                this._showProgress('Details: ' + i + '/' + total, Math.round(i/total*100));
            });
        }

        this._showProgress('Uploading...', 90);
        const batchSize = 10; let saved = 0, skipped = 0;
        for (let i = 0; i < positions.length; i += batchSize) {
            if (this.cancelled) break;
            const batch = positions.slice(i, i + batchSize);
            try { const res = await chrome.runtime.sendMessage({ action: 'upload_positions', website_id: this.website.id, positions: batch }); if (res.ok) { saved += res.data.saved || 0; skipped += res.data.skipped || 0; } } catch (e) {}
        }

                const multiPage = this.shadow.getElementById('multiPage')?.checked;
        const maxPages = parseInt(this.shadow.getElementById('maxPages')?.value || 10);

        // Multi-page auto-navigate: RE-ENABLED in v3.3.
        // Saves state to `sessionStorage` (per-tab, cleared on tab close)
        // instead of `chrome.storage.local` (persists forever).
        if (multiPage && !this.cancelled) {
            const pagination = detectPagination();
            if (pagination && (pagination.type === 'link' || pagination.type === 'url_pattern')) {
                const sessionState = {
                    status: 'in_progress',
                    page: 1,
                    saved: saved,
                    skipped: skipped,
                    url: pagination.url,
                    selectors: this.state,
                    website_id: this.website.id,
                    detail_delay: delaySec,
                    max_pages: maxPages,
                };
                try {
                    sessionStorage.setItem('applytools_extraction', JSON.stringify(sessionState));
                    console.log('[ApplyTools] Navigating to next page:', pagination.url);
                    window.location.href = pagination.url;
                    return; // Page will reload
                } catch (e) {
                    console.warn('[ApplyTools] Failed to save session state:', e);
                }
            }
        }

        this.isExtracting = false;
        this._showProgress('Complete!', 100);
        this._showStatus('✅ ' + saved + ' saved, ' + skipped + ' duplicates', 'success');
        try { chrome.runtime.sendMessage({ action: 'notify', title: 'ApplyTools', message: saved + ' positions saved — ' + this.website.name }); } catch(e) {}
        // Clear any leftover session state (only reached when no pagination
        // was found or extraction was cancelled).
        try { sessionStorage.removeItem('applytools_extraction'); } catch (e) { /* ignore */ }
        setTimeout(() => this._hideProgress(), 4000);
    }

    async checkResume() {
        // v3.3: `checkResume` is now a thin wrapper around
        // `continueSessionExtraction`. Kept as an alias for backwards compat.
        return this.continueSessionExtraction();
    }

    /**
     * Continue a multi-page extraction that was started by a manual click on
     * "🚀 Extract This Page". Reads state from `sessionStorage` (per-tab,
     * cleared on tab close) — so this ONLY runs when the user has manually
     * triggered extraction in this same tab and the page auto-navigated.
     *
     * sessionStorage being empty means: fresh tab open, no extraction in
     * progress, do nothing (no auto-extract).
     */
    async continueSessionExtraction() {
        let sessionState = null;
        try {
            const raw = sessionStorage.getItem('applytools_extraction');
            if (raw) sessionState = JSON.parse(raw);
        } catch (e) { /* ignore */ }

        if (!sessionState || sessionState.status !== 'in_progress') return;
        if (sessionState.website_id !== this.website?.id) {
            try { sessionStorage.removeItem('applytools_extraction'); } catch (e) {}
            return;
        }

        // Don't continue if we are not on a listing page.
        if (sessionState.selectors?.listing_css) {
            const cards = document.querySelectorAll(sessionState.selectors.listing_css);
            if (cards.length === 0) {
                console.log('[ApplyTools] On detail page (or no cards found), pausing session extraction.');
                this.step = 8;
                this._renderStep();
                this._showStatus('⏸️ Extraction paused. Navigate to a listing page, then click "Extract" to continue.', 'info');
                return;
            }
        }

        // Load selectors from the session state.
        this.state = sessionState.selectors;
        this.step = 8;
        this._renderStep();

        this.isExtracting = true; this.cancelled = false;
        const delaySec = sessionState.detail_delay || 1.5;
        const maxPages = sessionState.max_pages || 10;
        this.extractor = new Extractor({
            ...this.state,
            base_url: this.website?.base_url || window.location.origin,
            detail_delay: delaySec * 1000,
        });

        console.log('[ApplyTools] Continuing session extraction on page', (sessionState.page || 1) + 1);

        const positions = this.extractor.extractListing();
        if (!positions.length) {
            this._showStatus('No positions found on this page.', 'info');
            this.isExtracting = false;
            try { sessionStorage.removeItem('applytools_extraction'); } catch (e) {}
            return;
        }

        // Fetch details if a detail selector is set.
        if (this.state.detail_container_css) {
            this._showProgress('Fetching details: 0/' + positions.length, 0);
            await this.extractor.fetchDetails(positions, (i, total) => {
                this._showProgress('Details: ' + i + '/' + total, Math.round(i/total*100));
            });
        }

        this._showProgress('Uploading...', 90);
        const batchSize = 10;
        let saved = sessionState.saved || 0, skipped = sessionState.skipped || 0;
        for (let i = 0; i < positions.length; i += batchSize) {
            if (this.cancelled) break;
            const batch = positions.slice(i, i + batchSize);
            try {
                const res = await chrome.runtime.sendMessage({ action: 'upload_positions', website_id: this.website.id, positions: batch });
                if (res.ok) { saved += res.data.saved || 0; skipped += res.data.skipped || 0; }
            } catch (e) {}
        }

        const currentPage = (sessionState.page || 1) + 1;

        if (!this.cancelled && currentPage < maxPages) {
            const pagination = detectPagination();
            if (pagination && (pagination.type === 'link' || pagination.type === 'url_pattern')) {
                const newState = {
                    ...sessionState,
                    page: currentPage,
                    saved: saved,
                    skipped: skipped,
                    url: pagination.url,
                };
                try {
                    sessionStorage.setItem('applytools_extraction', JSON.stringify(newState));
                    console.log('[ApplyTools] Navigating to page ' + (currentPage + 1) + ':', pagination.url);
                    window.location.href = pagination.url;
                    return;
                } catch (e) {
                    console.warn('[ApplyTools] Failed to save session state:', e);
                }
            }
        }

        // Either cancelled, max pages reached, or no more pagination.
        this.isExtracting = false;
        this._showProgress('Complete!', 100);
        this._showStatus('✅ Total: ' + saved + ' saved, ' + skipped + ' duplicates', 'success');
        try { chrome.runtime.sendMessage({ action: 'notify', title: 'ApplyTools Extraction Complete', message: saved + ' positions saved — ' + this.website.name }); } catch(e) {}
        try { sessionStorage.removeItem('applytools_extraction'); } catch (e) {}
        setTimeout(() => this._hideProgress(), 4000);
    }

    _highlightElements(selector) { this._clearHighlights(); if (!selector) return; const els = document.querySelectorAll(selector); els.forEach(el => { const old = el.style.outline; el.dataset._at_old_outline = old || ''; el.style.outline = '2px solid #3B82F6'; el.style.outlineOffset = '-2px'; this._highlights.push(el); }); console.log('[ApplyTools] Highlighted ' + els.length + ' elements for selector: ' + selector); }
    _highlightCards() { if (!this.state.listing_css) return; const cards = document.querySelectorAll(this.state.listing_css); cards.forEach((card, i) => { const old = card.style.boxShadow; card.dataset._at_old_shadow = old || ''; card.style.boxShadow = '0 0 0 3px #10B981'; card.style.transition = 'box-shadow 0.2s'; const badge = document.createElement('div'); badge.style.cssText = 'position:absolute;top:4px;right:4px;background:#10B981;color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;font-family:sans-serif;z-index:9999;'; badge.textContent = '✓ #' + (i+1); badge.dataset._at_badge = 'true'; if (getComputedStyle(card).position === 'static') card.style.position = 'relative'; card.appendChild(badge); this._highlights.push(card); this._highlights.push(badge); }); }
    _clearHighlights() { this._highlights.forEach(el => { if (el.dataset._at_old_outline !== undefined) { el.style.outline = el.dataset._at_old_outline; delete el.dataset._at_old_outline; } if (el.dataset._at_old_shadow !== undefined) { el.style.boxShadow = el.dataset._at_old_shadow; delete el.dataset._at_old_shadow; } if (el.dataset._at_badge) el.remove(); }); this._highlights = []; }
    _showProgress(label, pct) { const w = this.shadow.getElementById('progressWrap'); const l = this.shadow.getElementById('progressLabel'); const f = this.shadow.getElementById('progressFill'); if (w) w.classList.add('active'); if (l) l.textContent = label; if (f) f.style.width = pct + '%'; }
    _hideProgress() { const w = this.shadow.getElementById('progressWrap'); const f = this.shadow.getElementById('progressFill'); if (w) w.classList.remove('active'); if (f) { f.style.width = '0%'; f.classList.remove('success'); } }
    _showStatus(text, type) { const msg = this.shadow.getElementById('statusMsg'); if (!msg) return; msg.textContent = text; msg.className = 'status-msg ' + type; if (type === 'success') setTimeout(() => { msg.className = 'status-msg'; }, 5000); }
    
    // FIX: Save state to Django instead of chrome.storage.local
    async _saveState() {
        if (!this.website) return;
        try {
            await chrome.runtime.sendMessage({
                action: 'save_selectors',
                website_id: this.website.id,
                selectors: {
                    listing_css: this.state.listing_css,
                    link_css: this.state.link_css,
                    title_css: this.state.title_css,
                    company_css: this.state.company_css,
                    detail_container_css: this.state.detail_container_css,
                },
            });
            console.log('[ApplyTools] Selectors saved to Django');
        } catch (err) {
            console.error('[ApplyTools] Failed to save selectors:', err);
        }
    }

    _toggleCollapse() { this.collapsed = !this.collapsed; const panel = this.shadow.getElementById('panel'); const btn = this.shadow.getElementById('collapsedBtn'); if (this.collapsed) { panel.style.display = 'none'; btn.style.display = 'flex'; } else { panel.style.display = 'block'; btn.style.display = 'none'; } }
    show() { this.host.style.display = 'block'; }
    hide() { this.host.style.display = 'none'; }
}