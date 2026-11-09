/**
 * ApplyTools Extension — Background Service Worker (Phase 3+)
 *
 * Phase 0: Token management, API client
 * Phase 1: Website lookup by URL
 * Phase 2: Notifications
 * Phase 3: No changes (pagination handled in content script)
 * Phase 4: MV3 keep-alive alarms
 * Phase 5: Position match trigger
 * Phase 6: External messaging (dashboard → extension)
 */

const DEFAULT_API_BASE = 'http://localhost:8000';

// ─── State management ──────────────────────────────────────────

async function getApiBase() {
    const { api_base } = await chrome.storage.local.get('api_base');
    return api_base || DEFAULT_API_BASE;
}

async function getToken() {
    const { api_token } = await chrome.storage.local.get('api_token');
    return api_token || null;
}

// ─── Django API client ─────────────────────────────────────────

async function apiFetch(path, options = {}) {
    const base = await getApiBase();
    const token = await getToken();
    if (!token) throw new Error('No API token set.');

    const headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Token ' + token,
        ...(options.headers || {}),
    };

    const res = await fetch(base + path, { ...options, headers });

    if (res.status === 401 || res.status === 403) {
        throw new Error('Authentication failed. Check your extension token.');
    }
    if (!res.ok) {
        const text = await res.text();
        throw new Error('API error ' + res.status + ': ' + text);
    }
    return res.json();
}

// ─── Message routing ──────────────────────────────────────────

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {

    if (message.action === 'check_auth') {
        apiFetch('/api/v1/ext/auth/check/')
            .then(data => sendResponse({ ok: true, data }))
            .catch(err => sendResponse({ ok: false, error: err.message }));
        return true;
    }

    if (message.action === 'get_website_for_url') {
        const url = encodeURIComponent(message.url);
        apiFetch('/api/v1/ext/websites/by-url/?url=' + url)
            .then(data => sendResponse({ ok: true, data }))
            .catch(err => sendResponse({ ok: false, error: err.message }));
        return true;
    }

    if (message.action === 'save_selectors') {
        apiFetch('/api/v1/ext/websites/' + message.website_id + '/selectors/', {
            method: 'POST',
            body: JSON.stringify(message.selectors),
        })
            .then(data => sendResponse({ ok: true, data }))
            .catch(err => sendResponse({ ok: false, error: err.message }));
        return true;
    }

    if (message.action === 'upload_positions') {
        apiFetch('/api/v1/ext/websites/' + message.website_id + '/positions/bulk/', {
            method: 'POST',
            body: JSON.stringify({ positions: message.positions }),
        })
            .then(data => sendResponse({ ok: true, data }))
            .catch(err => sendResponse({ ok: false, error: err.message }));
        return true;
    }

    if (message.action === 'lookup_position') {
        const url = encodeURIComponent(message.url);
        apiFetch('/api/v1/ext/positions/by-url/?url=' + url)
            .then(data => sendResponse({ ok: true, data }))
            .catch(err => sendResponse({ ok: false, error: err.message }));
        return true;
    }

    // Bulk lookup positions (for listing page badges)
    if (message.action === 'bulk_lookup_positions') {
        apiFetch('/api/v1/ext/positions/bulk-lookup/', {
            method: 'POST',
            body: JSON.stringify({ urls: message.urls }),
        })
            .then(data => sendResponse({ ok: true, data }))
            .catch(err => sendResponse({ ok: false, error: err.message }));
        return true;
    }
    // Phase 5: Trigger match for a position
    if (message.action === 'match_position') {
        apiFetch('/api/v1/ext/positions/' + message.position_id + '/match/', {
            method: 'POST',
        })
            .then(data => sendResponse({ ok: true, data }))
            .catch(err => sendResponse({ ok: false, error: err.message }));
        return true;
    }

    // Phase 2: Desktop notification
    if (message.action === 'notify') {
        chrome.notifications.create({
            type: 'basic',
            iconUrl: 'icons/icon48.png',
            title: message.title || 'ApplyTools',
            message: message.message || '',
            priority: 2,
        });
        return false;
    }

    // Phase 6: Open tab (from external message)
    if (message.action === 'open_tab') {
        chrome.tabs.create({ url: message.url }, (tab) => {
            sendResponse({ ok: true, tabId: tab.id });
        });
        return true;
    }

    return false;
});

// ─── Phase 6: Externally-connectable (dashboard → extension) ───

chrome.runtime.onMessageExternal.addListener((message, sender, sendResponse) => {
    const allowedOrigins = ['http://localhost:8000', 'http://127.0.0.1:8000'];
    if (!allowedOrigins.includes(sender.origin)) return false;

    if (message.action === 'ping') {
        getToken().then(token => {
            sendResponse({ ok: true, hasToken: !!token });
        });
        return true;
    }

    if (message.action === 'open_and_extract') {
        chrome.tabs.create({ url: message.url }, (tab) => {
            // Send a message to the content script in the new tab after it loads
            chrome.tabs.onUpdated.addListener(function listener(tabId, info) {
                if (tabId === tab.id && info.status === 'complete') {
                    chrome.tabs.onUpdated.removeListener(listener);
                    setTimeout(() => {
                        chrome.tabs.sendMessage(tab.id, { action: 'start_extraction' });
                    }, 2000);
                    sendResponse({ ok: true, tabId: tab.id });
                }
            });
        });
        return true;
    }

    return false;
});

// ─── Phase 4: MV3 keep-alive ──────────────────────────────────

// Alarm to keep service worker alive during long extractions
chrome.alarms.create('applytools-keepalive', { periodInMinutes: 0.4 }); // 24s

chrome.alarms.onAlarm.addListener((alarm) => {
    if (alarm.name === 'applytools-keepalive') {
        // Just waking up the service worker is enough to reset the 30s timer
        // Check if there's an active extraction
        chrome.storage.local.get('extraction_state', (data) => {
            if (data.extraction_state && data.extraction_state.status === 'in_progress') {
                console.log('[ApplyTools] Keep-alive tick — extraction in progress');
            }
        });
    }
});

chrome.runtime.onInstalled.addListener(() => {
    console.log('[ApplyTools] Extension installed (Phase 3+).');
});
