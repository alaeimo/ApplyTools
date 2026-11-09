/**
 * ApplyTools Extension — Extractor (extractor.js) — v2.3
 *
 * Fix: Handles elements with .href correctly (both <a> tags and others)
 * Fix: Falls back to getAttribute('href') if .href is undefined
 * Fix: If link_css points to a non-<a> element (e.g., <h3> wrapped by <a>),
 *      walks up via .closest('a') to find the actual link element. This handles
 *      the common pattern where the title is inside an <a> tag and the user
 *      picks the title element as the link selector.
 * Fix v2.3: When title_css matches multiple elements inside a card (e.g., DAAD
 *      where `.result__headline-content` matches both the institution and the
 *      title spans), picks the most "title-looking" one via _titleScore()
 *      (longer text + larger font size class + heading tag).
 */

class Extractor {
    constructor(config) {
        this.listingCss = config.listing_css || '';
        this.titleCss = config.title_css || '';
        this.linkCss = config.link_css || '';
        this.companyCss = config.company_css || '';
        this.detailContainerCss = config.detail_container_css || '';
        this.baseUrl = config.base_url || '';
        this.detailDelay = config.detail_delay || 1500;
        this.cancelled = false;
    }

    cancel() {
        this.cancelled = true;
    }

    /**
     * Extract positions from the current page's listing cards.
     */
    extractListing() {
        if (!this.listingCss) {
            return [];
        }

        const cards = document.querySelectorAll(this.listingCss);
        const positions = [];

        cards.forEach(card => {
            let title = '';
            let url = '';
            let company = '';

            // Title — pick the most "title-looking" element if the selector
            // matches multiple elements within the card (e.g., DAAD where
            // `.result__headline-content` matches both the institution and the
            // title spans). We score by text length & font size hints.
            if (this.titleCss) {
                const titleEls = card.querySelectorAll(this.titleCss);
                if (titleEls.length === 1) {
                    title = (titleEls[0].textContent || '').trim();
                } else if (titleEls.length > 1) {
                    // Multiple matches — pick the longest text. DAAD's title
                    // span has more text than the institution span, and is
                    // usually the larger font size class (u-size-24 vs u-size-18).
                    let best = titleEls[0];
                    let bestScore = this._titleScore(best);
                    for (let i = 1; i < titleEls.length; i++) {
                        const score = this._titleScore(titleEls[i]);
                        if (score > bestScore) { best = titleEls[i]; bestScore = score; }
                    }
                    title = (best.textContent || '').trim();
                }
            }

            // Link — FIX: handle .href properly
            if (this.linkCss) {
                let linkEl = card.querySelector(this.linkCss);
                if (linkEl) {
                    // If the selected element doesn't have href, check if it's inside an <a>.
                    // This handles the case where the user picks a non-<a> element (e.g.,
                    // the <h3 class="job-title"> that is wrapped by an <a>) as the link selector.
                    if (!linkEl.href && !linkEl.getAttribute('href')) {
                        const parentA = linkEl.closest('a');
                        if (parentA) {
                            linkEl = parentA; // Use the parent <a> tag instead
                        }
                    }

                    // Now extract the URL
                    if (linkEl.href) {
                        url = linkEl.href;
                    } else {
                        // Fallback to getAttribute('href')
                        url = linkEl.getAttribute('href') || '';
                    }

                    // If title was empty, use link text as fallback
                    if (!title) {
                        title = (linkEl.textContent || '').trim();
                    }
                }
            }

            // Company
            if (this.companyCss) {
                const companyEl = card.querySelector(this.companyCss);
                if (companyEl) {
                    company = (companyEl.textContent || '').trim();
                }
            }

            // Resolve relative URL
            if (url && !url.startsWith('http')) {
                try {
                    url = new URL(url, this.baseUrl || window.location.origin).href;
                } catch (e) {
                    // URL constructor failed, try manual join
                    url = (this.baseUrl || window.location.origin).replace(/\/$/, '') + '/' + url.replace(/^\//, '');
                }
            }

            if (url) {
                positions.push({
                    url: url,
                    title: title || 'Untitled Position',
                    company: company,
                    cleaned_text: '',
                });
            }
        });

        return positions;
    }

    /**
     * Fetch detail pages and extract description text.
     */
    async fetchDetails(positions, onProgress) {
        if (!this.detailContainerCss) {
            return positions;
        }

        const total = positions.length;
        for (let i = 0; i < total; i++) {
            if (this.cancelled) break;

            const pos = positions[i];

            if (pos.cleaned_text) {
                if (onProgress) onProgress(i + 1, total, pos, null);
                continue;
            }

            try {
                const text = await this._fetchDetail(pos.url);
                pos.cleaned_text = text;
                if (onProgress) onProgress(i + 1, total, pos, null);
            } catch (err) {
                console.warn('[ApplyTools] Detail fetch failed for', pos.url, err);
                pos.cleaned_text = '';
                if (onProgress) onProgress(i + 1, total, pos, err.message);
            }

            if (i < total - 1 && !this.cancelled) {
                await this._sleep(this.detailDelay);
            }
        }

        return positions;
    }

    async _fetchDetail(url) {
        const res = await fetch(url, {
            credentials: 'include',
            headers: {
                'Accept': 'text/html,application/xhtml+xml',
            },
        });

        if (!res.ok) {
            throw new Error('HTTP ' + res.status);
        }

        const html = await res.text();

        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');

        const container = doc.querySelector(this.detailContainerCss);
        if (!container) {
            throw new Error('Detail container not found');
        }

        container.querySelectorAll('script, style, noscript').forEach(el => el.remove());

        return (container.textContent || '').trim();
    }

    _sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    /**
     * Score a candidate title element. Higher score = more likely to be the
     * actual title (not the institution name or other metadata).
     *
     * Heuristics:
     * - Longer text content is preferred (DAAD title spans have ~50 chars,
     *   institution spans ~30 chars)
     * - Larger font size class (u-size-24, u-size-32) scores higher than
     *   small font (u-size-18)
     * - <h1>/<h2>/<h3> tags score higher than <span>/<div>
     */
    _titleScore(el) {
        if (!el) return 0;
        let score = 0;
        const text = (el.textContent || '').trim();
        score += text.length;
        const tag = el.tagName.toLowerCase();
        if (['h1', 'h2', 'h3'].includes(tag)) score += 100;
        // DAAD-style size hints: u-size-24, u-size-32@lg, etc.
        if (el.className && typeof el.className === 'string') {
            const sizeMatch = el.className.match(/u-size-(\d+)/);
            if (sizeMatch) score += parseInt(sizeMatch[1]);
            // Title usually has "mb-24" or larger margin-bottom
            const mbMatch = el.className.match(/mb-(\d+)/);
            if (mbMatch) score += parseInt(mbMatch[1]) * 2;
        }
        return score;
    }
}