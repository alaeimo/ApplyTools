/**
 * ApplyTools Extension — Badge Injector (badge.js) — v3.0
 *
 * New Features:
 * 1. Scans listing pages for known positions and injects small badges next to links.
 * 2. Shows a rich side-panel on detail pages.
 */

class BadgeInjector {
    constructor() {
        this.panel = null;
    }

    async check(overlay) {
        if (location.hostname === 'localhost' || location.hostname === '127.0.0.1') { if (location.port === '8000') return; }
        if (location.protocol === 'chrome:' || location.protocol === 'chrome-extension:') return;

        try {
            const { api_token } = await chrome.storage.local.get('api_token');
            if (!api_token) return;

            const { picker_state } = await chrome.storage.local.get('picker_state');
            
            // If we have listing selectors, scan the listing page
            if (overlay && picker_state && picker_state.listing_css && picker_state.link_css) {
                await this._scanListingPage(picker_state);
            }
            
            // Always check if the current page is a detail page
            await this._checkDetailPage();

        } catch (err) {
            console.debug('[ApplyTools] Badge check failed:', err);
        }
    }

    async _scanListingPage(state) {
        const cards = document.querySelectorAll(state.listing_css);
        if (cards.length === 0) return;

        const urlsToCheck = [];
        const linkElements = {};

        cards.forEach(card => {
            const linkEl = card.querySelector(state.link_css);
            if (linkEl) {
                let url = linkEl.href || linkEl.getAttribute('href');
                if (url) {
                    try {
                        url = new URL(url, window.location.origin).href;
                        if (!urlsToCheck.includes(url)) {
                            urlsToCheck.push(url);
                            linkElements[url] = linkEl;
                        }
                    } catch (e) {}
                }
            }
        });

        if (urlsToCheck.length === 0) return;

        // Ask background to do bulk lookup
        const response = await chrome.runtime.sendMessage({
            action: 'bulk_lookup_positions',
            urls: urlsToCheck
        });

        if (response.ok && response.data.results) {
            response.data.results.forEach(item => {
                if (item.found && linkElements[item.url]) {
                    this._injectListingBadge(linkElements[item.url], item);
                }
            });
        }
    }

    _injectListingBadge(linkEl, data) {
        // Avoid duplicating badges
        if (linkEl.dataset.atBadged) return;
        linkEl.dataset.atBadged = 'true';

        // Make sure parent is positioned
        const parent = linkEl.parentElement;
        if (getComputedStyle(parent).position === 'static') {
            parent.style.position = 'relative';
        }

        const score = data.match_score || 0;
        const color = score >= 80 ? '#10B981' : score >= 60 ? '#4F46E5' : score >= 40 ? '#F59E0B' : '#F43F5E';
        
        const badge = document.createElement('div');
        badge.style.cssText = `
            position: absolute; top: -8px; right: -8px; z-index: 9999;
            background: ${color}; color: white; width: 24px; height: 24px;
            border-radius: 50%; display: flex; align-items: center; justify-content: center;
            font-size: 11px; font-weight: bold; font-family: sans-serif;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2); cursor: pointer;
            border: 2px solid white;
        `;
        badge.textContent = score ? Math.round(score) : '✓';
        badge.title = `ApplyTools: ${data.match_category || 'Saved'} (Click for details)`;
        
        badge.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            window.open('http://127.0.0.1:8000/api/v1/positions/' + data.id + '/view/', '_blank');
        });

        parent.appendChild(badge);
    }

    async _checkDetailPage() {
        try {
            const response = await chrome.runtime.sendMessage({ action: 'lookup_position', url: location.href });
            if (response.ok && response.data && response.data.found) {
                this._showPanel(response.data);
            }
        } catch (err) {}
    }

    _showPanel(data) {
        if (this.panel) this.panel.remove();

        const host = document.createElement('div');
        host.id = 'applytools-detail-panel';
        host.style.cssText = 'position:fixed;bottom:20px;right:20px;z-index:2147483647;font-family:Inter,sans-serif;';
        const shadow = host.attachShadow({ mode: 'open' });
        shadow.innerHTML = this._getPanelHTML(data);
        document.body.appendChild(host);
        this.panel = host;

        shadow.getElementById('btnClose')?.addEventListener('click', () => { host.remove(); this.panel = null; });
        shadow.getElementById('btnDetails')?.addEventListener('click', () => {
            window.open('http://127.0.0.1:8000/api/v1/positions/' + data.id + '/view/', '_blank');
        });

        const rematchBtn = shadow.getElementById('btnRematch');
        if (rematchBtn) {
            rematchBtn.addEventListener('click', async () => {
                rematchBtn.textContent = '⏳ Matching...';
                rematchBtn.disabled = true;
                try {
                    const res = await chrome.runtime.sendMessage({ action: 'match_position', position_id: data.id });
                    if (res.ok) {
                        // Update panel UI
                        const scoreCircle = shadow.querySelector('.score-circle');
                        if (scoreCircle && res.data.match_score !== undefined) {
                            scoreCircle.textContent = Math.round(res.data.match_score);
                            const color = res.data.match_score >= 80 ? '#10B981' : res.data.match_score >= 60 ? '#4F46E5' : res.data.match_score >= 40 ? '#F59E0B' : '#F43F5E';
                            scoreCircle.style.background = color;
                        }
                        rematchBtn.textContent = '✅ Done';
                    } else { rematchBtn.textContent = '❌ Failed'; }
                } catch (e) { rematchBtn.textContent = '❌ Error'; }
                setTimeout(() => { rematchBtn.textContent = '🔄 Re-match'; rematchBtn.disabled = false; }, 3000);
            });
        }
    }

    _getPanelHTML(data) {
        const score = data.match_score;
        const scoreColor = score >= 80 ? '#10B981' : score >= 60 ? '#4F46E5' : score >= 40 ? '#F59E0B' : '#F43F5E';
        const statusColors = { 'PENDING_REVIEW':'#64748B', 'SHORTLISTED':'#F59E0B', 'APPLIED':'#0EA5E9', 'ACCEPTED':'#10B981', 'REJECTED':'#F43F5E', 'NOT_INTERESTED':'#94A3B8' };
        const statusColor = statusColors[data.application_status] || '#64748B';

        return `
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
.panel { background: white; border: 1px solid #E2E8F0; border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,0.12); overflow: hidden; width: 320px; animation: slideIn 0.3s ease; }
@keyframes slideIn { from { opacity: 0; transform: translateX(20px); } to { opacity: 1; transform: translateX(0); } }
.header { display: flex; align-items: center; gap: 8px; padding: 10px 14px; background: linear-gradient(135deg, #4F46E5, #7C3AED); color: white; }
.header .icon { font-size: 1rem; } .header .title { font-weight: 700; font-size: 0.82rem; flex: 1; }
.header button { background: rgba(255,255,255,0.15); border: none; color: white; width: 20px; height: 20px; border-radius: 4px; cursor: pointer; font-size: 0.75rem; display: flex; align-items: center; justify-content: center; }
.body { padding: 14px; }
.position-title { font-size: 0.85rem; font-weight: 600; color: #0F172A; margin-bottom: 4px; line-height: 1.3; }
.position-company { font-size: 0.78rem; color: #64748B; margin-bottom: 12px; }
.status-badge { display: inline-block; font-size: 0.65rem; font-weight: 600; padding: 3px 8px; border-radius: 999px; background: ${statusColor}20; color: ${statusColor}; text-transform: uppercase; margin-bottom: 12px; }
.match-section { display: flex; align-items: center; gap: 12px; padding: 12px; background: #F8FAFC; border-radius: 8px; margin-bottom: 12px; }
.score-circle { width: 48px; height: 48px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 1.1rem; font-weight: 700; color: white; background: ${scoreColor}; box-shadow: 0 2px 8px ${scoreColor}40; }
.match-info { flex: 1; }
.match-category { font-size: 0.78rem; font-weight: 600; color: #0F172A; text-transform: capitalize; }
.match-label { font-size: 0.7rem; color: #64748B; }
.actions { display: flex; gap: 8px; }
.btn { flex: 1; padding: 8px 12px; border: none; border-radius: 6px; font-size: 0.75rem; font-weight: 500; cursor: pointer; transition: all 0.15s; }
.btn-primary { background: #4F46E5; color: white; } .btn-primary:hover { background: #4338CA; }
.btn-secondary { background: #F1F5F9; color: #334155; } .btn-secondary:hover { background: #E2E8F0; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
<div class="panel">
    <div class="header">
        <span class="icon">🎓</span>
        <span class="title">ApplyTools</span>
        <button id="btnClose" title="Close">×</button>
    </div>
    <div class="body">
        <div class="position-title">${escapeHtml(data.title || 'Unknown')}</div>
        <div class="position-company">${escapeHtml(data.company || '')}</div>
        <span class="status-badge">${escapeHtml(data.application_status || 'PENDING')}</span>
        
        ${data.has_match ? `
        <div class="match-section">
            <div class="score-circle">${Math.round(score || 0)}</div>
            <div class="match-info">
                <div class="match-category">${escapeHtml(data.match_category || 'N/A').replace(/_/g, ' ')}</div>
                <div class="match-label">Match Score</div>
            </div>
        </div>
        ` : '<div class="match-label" style="margin-bottom:12px;">Not matched yet</div>'}

        <div class="actions">
            <button class="btn btn-primary" id="btnDetails">📊 Full Details</button>
            <button class="btn btn-secondary" id="btnRematch">🔄 Re-match</button>
        </div>
    </div>
</div>`;
    }
}