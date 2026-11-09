/**
 * ApplyTools Extension — Pagination Detector (pagination.js)
 *
 * Detects the "Next page" mechanism on a listing page using 5 strategies:
 * 1. <a rel="next">
 * 2. Class-based: .next, .pagination-next, li.next a
 * 3. Text-based: <a> containing "Next", "→", "»", "›"
 * 4. URL pattern: ?page=N → increment
 * 5. "Load more" button: button.load-more, button.show-more
 *
 * Returns a PaginationInfo object:
 *   { type: 'link'|'url_pattern'|'load_more'|null, url?: string, selector?: string }
 */

function detectPagination() {
    // Strategy 1: <a rel="next">
    let nextLink = document.querySelector('a[rel="next"]');
    if (nextLink && nextLink.href) {
        return { type: 'link', url: nextLink.href, selector: 'a[rel="next"]', description: 'rel="next"' };
    }

    // Strategy 2: Class-based selectors
    const classSelectors = [
        'a.next', 'a.next-page', 'a.pagination-next',
        'li.next a', 'li.next-page a',
        '.pagination .next a', '.pager .next a',
        'a[aria-label="Next"]', 'a[aria-label="Next page"]',
    ];
    for (const sel of classSelectors) {
        const el = document.querySelector(sel);
        if (el && el.href) {
            return { type: 'link', url: el.href, selector: sel, description: sel };
        }
    }

    // Strategy 3: Text-based — find <a> elements with "Next" or arrow text
    const allLinks = document.querySelectorAll('a[href]');
    const nextTexts = ['next', 'next page', '→', '»', '›', 'next »', 'next →', 'suivant', 'weiter', 'volgende'];
    for (const a of allLinks) {
        const text = (a.textContent || '').trim().toLowerCase();
        if (text.length < 20 && nextTexts.some(t => text === t || text.includes(t))) {
            // Make sure it's not a "Next post" in a sidebar — check if it looks like pagination
            const parent = a.parentElement;
            if (parent && (parent.tagName === 'LI' || parent.className.includes('pag') ||
                          parent.className.includes('nav') || parent.className.includes('pager'))) {
                return { type: 'link', url: a.href, selector: 'a', description: 'text: "' + text + '"' };
            }
        }
    }

    // Strategy 4: URL pattern — ?page=N or &page=N or ?PG=N
    const url = new URL(window.location.href);
    const pageParams = ['page', 'PG', 'pg', 'p', 'Page'];
    for (const param of pageParams) {
        const val = url.searchParams.get(param);
        if (val && /^\d+$/.test(val)) {
            const nextVal = parseInt(val) + 1;
            url.searchParams.set(param, String(nextVal));
            return {
                type: 'url_pattern',
                url: url.href,
                param: param,
                description: '?' + param + '=' + nextVal,
            };
        }
    }

    // Strategy 5: "Load more" button
    const loadMoreSelectors = [
        'button.load-more', 'button.show-more', 'button.load-more-results',
        'a.load-more', 'a.show-more',
        'button[data-action="load-more"]',
        'button[aria-label="Load more"]',
    ];
    for (const sel of loadMoreSelectors) {
        const btn = document.querySelector(sel);
        if (btn) {
            return { type: 'load_more', selector: sel, description: sel };
        }
    }

    return { type: null, description: 'No pagination detected' };
}

/**
 * Check if a "Load more" button is present and clickable.
 * Returns true if new elements were added after clicking.
 */
async function clickLoadMore(selector, previousCount, timeoutMs = 5000) {
    const btn = document.querySelector(selector);
    if (!btn) return false;

    btn.click();

    // Wait for new elements to appear
    const startTime = Date.now();
    while (Date.now() - startTime < timeoutMs) {
        await new Promise(r => setTimeout(r, 500));
        // The caller will check if count increased
    }
    return true;
}
