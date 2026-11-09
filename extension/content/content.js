/**
 * ApplyTools Extension — Content Script (v2.2)
 *
 * FIX: Loads selectors directly from Django API response (no local storage).
 * FIX: Passes picker_state to BadgeInjector for listing page scans.
 * FIX v2.2: Removed `overlay.checkResume()` call — extraction is now
 *      STRICTLY MANUAL. The user must click "🚀 Extract This Page" on the
 *      settings step. No automatic extraction happens on page load anymore.
 *
 *      Side effect: multi-page auto-navigate is also disabled (it relied on
 *      checkResume to continue extraction on the next page). To extract
 *      multiple pages, click "Extract This Page" on each page manually.
 */
(function() {
    'use strict';
    if (window.__applytoolsInjected) return;
    window.__applytoolsInjected = true;

    if (location.protocol === 'chrome:' || location.protocol === 'chrome-extension:' ||
        location.protocol === 'about:' || location.protocol === 'edge:') return;

    // Don't run on ApplyTools itself
    if ((location.hostname === 'localhost' || location.hostname === '127.0.0.1') && location.port === '8000') return;

    let overlay = null, picker = null, badgeInjector = null;

    async function init() {
        const { api_token } = await chrome.storage.local.get('api_token');
        if (!api_token) return;

        // Check if domain matches a configured website
        try {
            const response = await chrome.runtime.sendMessage({
                action: 'get_website_for_url', url: location.href,
            });

            if (!response.ok || !response.data?.found) {
                console.log('[ApplyTools] No website configured for this domain');
                return;
            }

            console.log('[ApplyTools] Website found:', response.data);

            // Initialize Badge Injector with website data
            badgeInjector = new BadgeInjector();
            // Pass response.data which now contains selectors from Django
            setTimeout(() => badgeInjector.check(response.data), 1500);

            // Create picker and overlay
            picker = new ElementPicker();
            overlay = new Overlay(picker);
            overlay.setWebsite(response.data);

            // FIX: Load selectors directly from Django API response
            if (response.data.has_selectors) {
                overlay.setState({
                    listing_css: response.data.listing_css || '',
                    title_css: response.data.title_css || '',
                    link_css: response.data.link_css || '',
                    company_css: response.data.company_css || '',
                    detail_container_css: response.data.detail_container_css || '',
                    pagination_url_pattern: response.data.pagination_url_pattern || '',
                });
            }

            // FIX v2.2: Do NOT call overlay.checkResume() here.
            // The user explicitly requested no automatic extraction. Extraction
            // only happens when the user manually clicks "🚀 Extract This Page"
            // in the wizard's settings step.
            //
            // (Old code that caused auto-extraction:)
            //   overlay.checkResume();
            //
            // We also proactively clear any stale extraction_state that might
            // have been left over from a previous version.
            try {
                await chrome.storage.local.remove('extraction_state');
                console.log('[ApplyTools] Cleared stale extraction_state (no auto-extract).');
            } catch (e) { /* ignore */ }

                        overlay.show();
            console.log('[ApplyTools] Overlay wizard injected');

            // v2.3: Check if we're in the middle of a multi-page extraction
            // session. Only continues if sessionStorage has an active session
            // (set by a manual click on "🚀 Extract This Page" earlier in this
            // same tab). Fresh tab opens will have empty sessionStorage.
            try {
                const raw = sessionStorage.getItem('applytools_extraction');
                if (raw) {
                    const sessionState = JSON.parse(raw);
                    if (sessionState && sessionState.status === 'in_progress' &&
                        sessionState.website_id === response.data.id) {
                        console.log('[ApplyTools] Active extraction session detected — continuing...');
                        // Delay to let the page finish rendering before extracting.
                        setTimeout(() => overlay.continueSessionExtraction(), 2000);
                    } else if (sessionState && sessionState.website_id !== response.data.id) {
                        // Stale session from a different website — clear it.
                        sessionStorage.removeItem('applytools_extraction');
                    }
                }
            } catch (e) {
                console.warn('[ApplyTools] Failed to check session state:', e);
            }
        } catch (err) {
            console.error('[ApplyTools] Init failed:', err);
        }
    }

    setTimeout(init, 1000);

    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
        if (message.action === 'ping') {
            sendResponse({ ok: true, url: location.href, title: document.title });
            return true;
        }
        if (message.action === 'start_extraction' && overlay) {
            overlay.step = 8; // Go to settings
            overlay._renderStep();
            sendResponse({ ok: true });
            return true;
        }
        return false;
    });
})();