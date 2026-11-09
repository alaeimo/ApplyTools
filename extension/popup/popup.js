/**
 * ApplyTools Extension — Popup script
 * Handles token configuration and connection testing.
 */

const statusDot = document.getElementById('statusDot');
const messageBox = document.getElementById('messageBox');
const saveBtn = document.getElementById('saveBtn');
const clearBtn = document.getElementById('clearBtn');
const testLink = document.getElementById('testLink');

// ─── Load saved settings on popup open ────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
    const { api_token, api_base } = await chrome.storage.local.get(['api_token', 'api_base']);
    if (api_token) {
        document.getElementById('tokenInput').value = api_token;
        clearBtn.style.display = 'inline-block';
        testConnection();
    }
    if (api_base) {
        document.getElementById('apiBase').value = api_base;
    }
});

// ─── Save & Test ───────────────────────────────────────────────

saveBtn.addEventListener('click', async () => {
    const token = document.getElementById('tokenInput').value.trim();
    const apiBase = document.getElementById('apiBase').value.trim();

    if (!token) {
        showMessage('Please enter your extension token.', 'error');
        return;
    }

    // Save to chrome.storage
    await chrome.storage.local.set({ api_token: token, api_base: apiBase });
    showMessage('Saved. Testing connection...', 'success');

    // Test the connection
    testConnection();
});

// ─── Clear token ──────────────────────────────────────────────

clearBtn.addEventListener('click', async () => {
    if (!confirm('Clear the saved token?')) return;
    await chrome.storage.local.remove(['api_token']);
    document.getElementById('tokenInput').value = '';
    clearBtn.style.display = 'none';
    setStatus(false);
    showMessage('Token cleared.', 'error');
});

// ─── Test connection ──────────────────────────────────────────

testLink.addEventListener('click', (e) => {
    e.preventDefault();
    testConnection();
});

async function testConnection() {
    try {
        const response = await chrome.runtime.sendMessage({ action: 'check_auth' });
        if (response.ok) {
            setStatus(true);
            showMessage(`✅ Connected as ${response.data.user}`, 'success');
        } else {
            setStatus(false);
            showMessage(`❌ ${response.error}`, 'error');
        }
    } catch (err) {
        setStatus(false);
        showMessage(`❌ ${err.message}`, 'error');
    }
}

// ─── UI helpers ───────────────────────────────────────────────

function setStatus(connected) {
    statusDot.className = 'status-dot ' + (connected ? 'connected' : 'disconnected');
    statusDot.title = connected ? 'Connected' : 'Disconnected';
    clearBtn.style.display = connected ? 'inline-block' : 'none';
}

function showMessage(text, type) {
    messageBox.textContent = text;
    messageBox.className = 'message ' + type;
    setTimeout(() => { messageBox.className = 'message'; }, 5000);
}
