/**
 * ApplyTools Extension — Element Picker (picker.js) — v2.7
 *
 * PROBLEM HISTORY:
 *   v2.4: rejected ancestor IDs/classes because it required
 *         `matches[0] === clicked element`. On detail pages the user hovers
 *         over a <p> inside #editor; #editor is the container the user wants
 *         but matches[0] is the <p>'s parent (#editor), not the <p>. So every
 *         ancestor ID/class was rejected and we fell back to nth-of-type.
 *
 *   v2.5: tried to fix by climbing IDs FIRST. WRONG for list pages — listing
 *         cards almost never have IDs, so we'd climb past the card's .job-card
 *         class and pick some unrelated ancestor ID. Class selectors are
 *         semantically better (work for both list & detail pages).
 *
 *   v2.6: PREFER CLASS selectors over IDs. When climbing UP, accept ancestor
 *         class/ID even if clicked element isn't matches[0]. Strategy 1 passes
 *         allowOkayClasses:false so fragile utility classes aren't accepted
 *         on the clicked element itself.
 *
 * v2.7 FIX (this version):
 *   1. Combined-all-classes path: when the clicked element has ONLY utility
 *      classes (e.g., FindAPhD's `<span class="h4 text-dark mx-0 mb-3">` or
 *      `<a class="w-100 card shadow-sm p-4">`), combine ALL classes into a
 *      compound selector like `.h4.text-dark.mx-0.mb-3`. This is the only
 *      way to generate a unique selector for such elements.
 *   2. Order: good classes → ID → combined-all-classes → single utility
 *      classes → nth-of-type. This ensures #apply-now-btn wins over
 *      `button.btn.btn-primary`, while FindAPhD's title still gets
 *      `.h4.text-dark` instead of falling through to nth-of-type.
 *   3. Added shadow|rounded|border|w-|h- to utility class patterns so
 *      `a.shadow-sm`, `a.w-100` etc. get filtered into the "okay" bucket
 *      and trigger the combined-classes path.
 *   4. `tryElement` accepts an `descendantOf` option for ancestor climbing —
 *      verifies the clicked element is INSIDE the ancestor via .contains().
 *
 * Public API unchanged: generateSelector(element, scope), countMatches, ElementPicker.
 */

const UTILITY_CLASS_PATTERNS = [
    /^(col|row|container|offset|mr-|ml-|mx-|mt-|mb-|my-|m-[0-9]|p-[0-9]|pr-|pl-|pt-|pb-|px-|py-|g-[0-9])/,
    /^(d-|flex|justify-|align-|float-|position-|overflow-|w-|h-|vw-|vh-|mw-|mh-)/,
    /^(text-(dark|light|white|primary|secondary|muted|danger|warning|info|success|reset|center|left|right|truncate|nowrap|wrap|lowercase|uppercase|capitalize|monospace))$/,
    /^(bg-(primary|secondary|dark|light|white|transparent|success|danger|warning|info))$/,
    // Bootstrap / Tailwind component classes — both the bare noun (btn, card,
    // nav, alert, badge, dropdown, modal) and prefixed variants (btn-primary,
    // card-body, etc.). Treating bare `btn` as utility ensures we prefer a
    // unique element ID like #apply-now-btn over the generic .btn class.
    /^(btn|card|nav|alert|badge|dropdown|modal|table|form|input|close|fade|show|hide|active|disabled|hover|sr-only|spinner|carousel|accordion|tab|toast|tooltip|popover|breadcrumb|pagination|jumbotron|collapse|shadow|rounded|border|w-|h-)([-_]|$)/,
    /^[mp][tblrxy]?-[0-5]$/,
    /^(clearfix|visible|invisible|hidden|container|wrapper|inner|outer|content|main|header|footer|body|section|item|element|widget|component|block|box|wrap|grid|cell|row|col)$/,
    /^(tw-|flex-|grid-|gap-|space-|items-|justify-|self-|place-|order-|col-span|row-span)/,
    /^(css-|_)[a-z0-9]{5,}/i,
    /^(jsx-|emotion-|sc-|styled-|__)/,
];

function isUtilityClass(cls) {
    return UTILITY_CLASS_PATTERNS.some(pattern => pattern.test(cls));
}

function isGeneratedClass(cls) {
    return /^(css-|_)[a-z0-9]{5,}/i.test(cls) || /^(jsx-|emotion-|sc-|styled-|__)/.test(cls);
}

function getGoodClasses(element) {
    if (!element.classList) return [];
    return Array.from(element.classList).filter(c => c && !isUtilityClass(c) && !isGeneratedClass(c) && c.length > 1);
}

function countMatches(selector, scope) {
    try {
        return (scope || document).querySelectorAll(selector).length;
    } catch (e) {
        return 0;
    }
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function safeEscape(str) {
    if (window.CSS && CSS.escape) return CSS.escape(str);
    return str.replace(/([^a-zA-Z0-9_-])/g, '\\$1');
}

// Generic framework IDs we should never use as selectors. Match exact IDs
// (like `app`, `root`) OR IDs whose first separator (- or _) immediately
// follows the prefix (e.g. `app-root`, `react_root`). IDs like `apply-now-btn`
// or `editor` do NOT match.
function isGenericId(id) {
    if (!id || id.length < 2) return true;
    const m = id.match(/^([a-zA-Z]+)([-_]|$)/);
    if (!m) return false;
    const prefix = m[1].toLowerCase();
    return ['react','vue','app','root','main','content','wrapper'].includes(prefix);
}

// ─── Selector generation ───────────────────────────────────────

function generateSelector(element, scope) {
    scope = scope || document;
    if (!element || element === document.body) return 'body';
    if (element === document.documentElement) return 'html';

    const DEBUG = window.__APPLYTOOLS_PICKER_DEBUG__ !== false;
    if (DEBUG) console.log('%c[ApplyTools Debug] Generating selector for:', 'color: #4F46E5; font-weight: bold;', element);

    // ── Strategy 1: Try the clicked element itself.
    // Pass allowOkayClasses:false so we DON'T accept a fragile utility class
    // like `.col-lg-8` on the clicked element itself. We want either a real
    // good class, a unique ID, a combined-all-classes selector, or we fall
    // through to climbing.
    let result = tryElement(element, scope, { allowOkayClasses: false, requireExact: true });
    if (result) {
        if (DEBUG) console.log('%c[ApplyTools Debug] Strategy 1 (Self) succeeded:', 'color: #10B981;', result.selector);
        return result.selector;
    }

    // ── Strategy 2: Climb UP (max 6 levels).
    // PREFER CLASS selectors first (works for both list & detail pages), then
    // fall back to ID. Accept ancestor class/ID even when the clicked element
    // isn't the match — the ancestor IS the container the user wants; we just
    // verify the clicked element is a descendant (via .contains()).
    //
    // Pass 1: good classes only (no utility classes).
    let current = element;
    for (let i = 0; i < 6; i++) {
        current = current.parentElement;
        if (!current || current === document.body || current === scope) break;

        result = tryElement(current, scope, {
            allowOkayClasses: false,
            requireExact: false,        // accept ancestor even if not matches[0]
            descendantOf: element      // clicked element must be inside the match
        });
        if (result) {
            const count = countMatches(result.selector, scope);
            if (count >= 1 && !result.selector.includes('nth-of-type')) {
                if (DEBUG) console.log(`%c[ApplyTools Debug] Strategy 2a (Climb UP good-class ${i+1}) succeeded:`, 'color: #10B981;', result.selector, '(' + count + ' matches)');
                return result.selector;
            }
        }
    }

    // Pass 2: ID (only if no good class was found on any ancestor).
    current = element;
    for (let i = 0; i < 6; i++) {
        current = current.parentElement;
        if (!current || current === document.body || current === scope) break;

        if (!current.id || isGenericId(current.id)) continue;
        const sel = '#' + safeEscape(current.id);
        try {
            const matches = scope.querySelectorAll(sel);
            if (matches.length >= 1 && matches[0].contains(element)) {
                if (DEBUG) console.log(`%c[ApplyTools Debug] Strategy 2b (Climb UP ID ${i+1}) succeeded:`, 'color: #10B981;', sel, '(' + matches.length + ' matches, ancestor ID)');
                return sel;
            }
            if (DEBUG) console.log(`[ApplyTools Debug] Ancestor ID ${sel} skipped. Matches: ${matches.length}`);
        } catch(e) {}
    }

    // Pass 3: okay (utility) classes — last resort before look-DOWN.
    current = element;
    for (let i = 0; i < 6; i++) {
        current = current.parentElement;
        if (!current || current === document.body || current === scope) break;

        result = tryElement(current, scope, {
            allowOkayClasses: true,
            requireExact: false,
            descendantOf: element
        });
        if (result) {
            const count = countMatches(result.selector, scope);
            if (count >= 1 && count <= 30 && !result.selector.includes('nth-of-type')) {
                if (DEBUG) console.log(`%c[ApplyTools Debug] Strategy 2c (Climb UP utility-class ${i+1}) succeeded:`, 'color: #F59E0B;', result.selector, '(' + count + ' matches, fallback)');
                return result.selector;
            }
        }
    }

    // ── Strategy 3: Look DOWN at children (max 3 levels). Used when the user
    // clicks a wrapper that has no good selector but contains a child with one.
    let child = element.querySelector('div, section, article, main, [id], [class]');
    if (child) {
        result = tryElement(child, scope, { allowOkayClasses: false, requireExact: true });
        if (result) {
            const count = countMatches(result.selector, scope);
            if (count >= 1 && !result.selector.includes('nth-of-type')) {
                if (DEBUG) console.log('%c[ApplyTools Debug] Strategy 3 (Look DOWN 1) succeeded:', 'color: #10B981;', result.selector, '(' + count + ' matches)');
                return result.selector;
            }
        }

        let grandChild = child.querySelector('div, section, article, main, [id], [class]');
        if (grandChild) {
            result = tryElement(grandChild, scope, { allowOkayClasses: false, requireExact: true });
            if (result) {
                const count = countMatches(result.selector, scope);
                if (count >= 1 && !result.selector.includes('nth-of-type')) {
                    if (DEBUG) console.log('%c[ApplyTools Debug] Strategy 3 (Look DOWN 2) succeeded:', 'color: #10B981;', result.selector, '(' + count + ' matches)');
                    return result.selector;
                }
            }
        }
    }

    // ── Strategy 4: Fall back to nth-of-type.
    if (DEBUG) console.log('%c[ApplyTools Debug] All strategies failed. Falling back to nth-of-type.', 'color: #F43F5E;');
    return generateFallback(element, scope);
}

/**
 * Test whether `element` can be uniquely identified by a selector.
 *
 * Order of attempts:
 *   1. Good classes (single, then tag.class, then all good classes combined)
 *   2. Unique element ID (#apply-now-btn beats .btn.btn-primary)
 *   3. Combined ALL classes including utility (e.g., .h4.text-dark for FindAPhD)
 *      — ONLY when there is no ID and good classes failed
 *   4. Single utility classes (only when allowOkayClasses is true)
 *
 * @param {Element} element  - The element to find a selector for.
 * @param {Element} scope    - Scope for querySelectorAll.
 * @param {Object}  options
 *   - allowOkayClasses (default true): if false, single utility classes are
 *     not tried (Strategy 1 uses false to avoid fragile utility selectors).
 *     NOTE: the combined-all-classes path ALWAYS runs regardless of this flag,
 *     because a compound selector like `.h4.text-dark` is specific enough.
 *   - requireExact (default true): if true, the selector must match `element`
 *     as matches[0]. If false, accepts ancestor matches (where the clicked
 *     element is a descendant of matches[0]).
 *   - descendantOf (optional): if set, requires the first match to .contain()
 *     this element.
 * @returns {{selector: string}|null}
 */
function tryElement(element, scope, options) {
    scope = scope || document;
    options = options || {};
    const allowOkayClasses = options.allowOkayClasses !== false;
    const requireExact = options.requireExact !== false;
    const descendantOf = options.descendantOf || null;

    // Helper: did the selector "hit" the element?
    function hit(matches) {
        if (matches.length === 0) return false;
        if (requireExact) {
            return matches[0] === element;
        }
        // requireExact:false — accept if element is the first match OR is a
        // descendant of the first match (i.e., we're picking an ancestor).
        if (descendantOf) {
            return matches[0].contains(descendantOf);
        }
        return matches[0] === element || matches[0].contains(element);
    }

    // ── 1. Good classes first.
    if (element.classList) {
        const goodClasses = [];
        const okayClasses = [];
        Array.from(element.classList).forEach(c => {
            if (!c || c.length <= 1) return;
            if (isGeneratedClass(c)) return;
            if (isUtilityClass(c)) {
                okayClasses.push(c);
            } else {
                goodClasses.push(c);
            }
        });

        const testClasses = (classes) => {
            if (classes.length === 0) return null;

            const classCounts = classes.map(c => {
                try { return { name: c, count: scope.querySelectorAll('.' + safeEscape(c)).length }; }
                catch(e) { return { name: c, count: 999 }; }
            }).sort((a, b) => a.count - b.count);

            const tag = element.tagName.toLowerCase();

            // Single class (rarest first). Accept if matches[0] hits the target.
            for (const { name, count } of classCounts) {
                if (count < 1 || count > 50) continue;
                const sel = '.' + safeEscape(name);
                try {
                    const matches = scope.querySelectorAll(sel);
                    if (hit(matches)) return { selector: sel };
                } catch(e) {}
            }

            // tag.class
            for (const { name, count } of classCounts) {
                if (count < 1 || count > 50) continue;
                const sel = tag + '.' + safeEscape(name);
                try {
                    const matches = scope.querySelectorAll(sel);
                    if (hit(matches)) return { selector: sel };
                } catch(e) {}
            }

            // All provided classes combined (most specific).
            let sel = tag + '.' + classes.map(c => safeEscape(c)).join('.');
            try {
                const matches = scope.querySelectorAll(sel);
                if (matches.length >= 1 && hit(matches)) return { selector: sel };
            } catch(e) {}

            sel = '.' + classes.map(c => safeEscape(c)).join('.');
            try {
                const matches = scope.querySelectorAll(sel);
                if (matches.length >= 1 && hit(matches)) return { selector: sel };
            } catch(e) {}

            return null;
        };

        // Good classes are always preferred.
        let selector = testClasses(goodClasses);
        if (selector) return selector;
    }

    // ── 2. ID next (BEFORE the combined-all-classes path). A unique element
    // ID like #apply-now-btn is more specific than `button.btn.btn-primary`,
    // so when the clicked element has both, ID wins. But good classes (above)
    // still win over ID — e.g. .job-description is preferred over #editor.
    if (element.id && !isGenericId(element.id)) {
        const sel = '#' + safeEscape(element.id);
        try {
            const matches = scope.querySelectorAll(sel);
            if (hit(matches)) {
                return { selector: sel };
            }
            if (window.__APPLYTOOLS_PICKER_DEBUG__ !== false) {
                console.log(`[ApplyTools Debug] ID ${sel} rejected. Matches: ${matches.length}, First match is clicked/target: ${matches[0] === element || (descendantOf && matches[0].contains(descendantOf))}`);
            }
        } catch(e) {}
    }

    // ── 3. Combined ALL classes (utility + good together) — CRITICAL for
    // FindAPhD where the title is `<span class="h4 text-dark mx-0 mb-3">` and
    // the link is `<a class="w-100 card shadow-sm p-4 text-decoration-none">`.
    // All classes are utility, so goodClasses=[] and we'd fall through to
    // nth-of-type. By combining ALL classes into one compound selector
    // (`.h4.text-dark.mx-0.mb-3`), we get a unique selector.
    //
    // This runs REGARDLESS of allowOkayClasses because a compound selector
    // is specific enough to be safe.
    if (element.classList && element.classList.length >= 2) {
        const allClasses = Array.from(element.classList).filter(c =>
            c && c.length > 1 && !isGeneratedClass(c)
        );
        if (allClasses.length >= 2) {
            const tag = element.tagName.toLowerCase();
            // tag + all classes combined
            let sel = tag + '.' + allClasses.map(c => safeEscape(c)).join('.');
            try {
                const matches = scope.querySelectorAll(sel);
                if (matches.length >= 1 && hit(matches)) return { selector: sel };
            } catch(e) {}
            // just all classes combined (no tag)
            sel = '.' + allClasses.map(c => safeEscape(c)).join('.');
            try {
                const matches = scope.querySelectorAll(sel);
                if (matches.length >= 1 && hit(matches)) return { selector: sel };
            } catch(e) {}
        }
    }

    // ── 4. Single utility (okay) classes — only when allowOkayClasses is true.
    // This is the weakest selector type and is only tried as a last resort.
    if (allowOkayClasses && element.classList) {
        const okayClasses = [];
        Array.from(element.classList).forEach(c => {
            if (!c || c.length <= 1) return;
            if (isGeneratedClass(c)) return;
            if (isUtilityClass(c)) okayClasses.push(c);
        });

        const testClasses = (classes) => {
            if (classes.length === 0) return null;
            const classCounts = classes.map(c => {
                try { return { name: c, count: scope.querySelectorAll('.' + safeEscape(c)).length }; }
                catch(e) { return { name: c, count: 999 }; }
            }).sort((a, b) => a.count - b.count);
            const tag = element.tagName.toLowerCase();
            for (const { name, count } of classCounts) {
                if (count < 1 || count > 50) continue;
                const sel = '.' + safeEscape(name);
                try {
                    const matches = scope.querySelectorAll(sel);
                    if (hit(matches)) return { selector: sel };
                } catch(e) {}
            }
            for (const { name, count } of classCounts) {
                if (count < 1 || count > 50) continue;
                const sel = tag + '.' + safeEscape(name);
                try {
                    const matches = scope.querySelectorAll(sel);
                    if (hit(matches)) return { selector: sel };
                } catch(e) {}
            }
            let sel = tag + '.' + classes.map(c => safeEscape(c)).join('.');
            try {
                const matches = scope.querySelectorAll(sel);
                if (matches.length >= 1 && hit(matches)) return { selector: sel };
            } catch(e) {}
            sel = '.' + classes.map(c => safeEscape(c)).join('.');
            try {
                const matches = scope.querySelectorAll(sel);
                if (matches.length >= 1 && hit(matches)) return { selector: sel };
            } catch(e) {}
            return null;
        };

        let selector = testClasses(okayClasses);
        if (selector) return selector;
    }

    return null;
}

function generateFallback(element, scope) {
    scope = scope || document;
    const tag = element.tagName.toLowerCase();
    if (scope.querySelectorAll(tag).length <= 5) return tag;

    const parent = element.parentElement;
    if (parent && parent !== document) {
        const siblings = Array.from(parent.children).filter(s => s.tagName === element.tagName);
        const index = siblings.indexOf(element) + 1;
        if (index > 0) return tag + ':nth-of-type(' + index + ')';
    }
    return tag;
}

// ─── ElementPicker class ───────────────────────────────────────

class ElementPicker {
    constructor() {
        this.active = false;
        this.currentTarget = null;
        this.scope = document;
        this.onSelect = null;
        this.onCancel = null;
        this._overlay = null;
        this._tooltip = null;
        this._matches = [];
        this._onMouseMove = this._onMouseMove.bind(this);
        this._onClick = this._onClick.bind(this);
        this._onKeyDown = this._onKeyDown.bind(this);
    }

    enable(options = {}) {
        if (this.active) this.disable();
        this.active = true;
        this.scope = options.scope || document;
        this.onSelect = options.onSelect || null;
        this.onCancel = options.onCancel || null;

        this._overlay = document.createElement('div');
        this._overlay.style.cssText = 'position:fixed;pointer-events:none;z-index:2147483646;border:2px solid #4F46E5;background:rgba(79,70,229,0.08);transition:all 0.05s ease;display:none;border-radius:3px;';
        document.body.appendChild(this._overlay);

        this._tooltip = document.createElement('div');
        this._tooltip.style.cssText = 'position:fixed;z-index:2147483647;pointer-events:none;background:#0F172A;color:white;padding:8px 12px;border-radius:8px;font-size:12px;font-family:monospace;max-width:420px;word-break:break-all;display:none;box-shadow:0 8px 24px rgba(0,0,0,0.3);line-height:1.5;';
        document.body.appendChild(this._tooltip);

        document.addEventListener('mousemove', this._onMouseMove, true);
        document.addEventListener('click', this._onClick, true);
        document.addEventListener('keydown', this._onKeyDown, true);
        document.body.style.cursor = 'crosshair';
    }

    disable() {
        if (!this.active) return;
        this.active = false;
        document.removeEventListener('mousemove', this._onMouseMove, true);
        document.removeEventListener('click', this._onClick, true);
        document.removeEventListener('keydown', this._onKeyDown, true);
        if (this._overlay) { this._overlay.remove(); this._overlay = null; }
        if (this._tooltip) { this._tooltip.remove(); this._tooltip = null; }
        this._clearMatches();
        document.body.style.cursor = '';
    }

    _clearMatches() {
        this._matches.forEach(el => { el.style.outline = el.dataset._applytools_old_outline || ''; delete el.dataset._applytools_old_outline; });
        this._matches = [];
    }

    _highlightMatches(selector) {
        this._clearMatches();
        const matches = this.scope.querySelectorAll(selector);
        matches.forEach(el => { el.dataset._applytools_old_outline = el.style.outline || ''; el.style.outline = '2px solid #10B981'; el.style.outlineOffset = '-2px'; });
        this._matches = Array.from(matches);
    }

    _isOurElement(el) {
        return el === this._overlay || el === this._tooltip || (el.closest && el.closest('#applytools-overlay-host'));
    }

    _onMouseMove(e) {
        if (!this.active) return;
        e.stopPropagation();
        const el = e.target;
        if (this._isOurElement(el)) return;

        this.currentTarget = el;
        const rect = el.getBoundingClientRect();
        this._overlay.style.display = 'block';
        this._overlay.style.top = rect.top + 'px';
        this._overlay.style.left = rect.left + 'px';
        this._overlay.style.width = rect.width + 'px';
        this._overlay.style.height = rect.height + 'px';

        const selector = generateSelector(el, this.scope);
        const count = countMatches(selector, this.scope);

        this._tooltip.style.display = 'block';
        const tipX = e.clientX + 20;
        const tipY = e.clientY + 20;
        this._tooltip.style.left = (tipX + 400 > window.innerWidth ? e.clientX - 420 : tipX) + 'px';
        this._tooltip.style.top = tipY + 'px';

        const tagInfo = el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/).slice(0, 3).join('.') : '');
        const climbedHint = count >= 2 ? '<div style="color:#10B981;margin-top:2px;">✓ Found ' + count + ' matching elements</div>' : count === 1 ? '<div style="color:#10B981;margin-top:2px;">✓ Found 1 match</div>' : '<div style="color:#F59E0B;margin-top:2px;">⚠ Only ' + count + ' matches — try a different element</div>';
        this._tooltip.innerHTML = '<div style="color:#818CF8;margin-bottom:4px;">' + escapeHtml(tagInfo) + '</div><div>Selector: <strong style="color:#10B981;">' + escapeHtml(selector) + '</strong></div>' + climbedHint + '<div style="color:#64748B;margin-top:4px;font-size:11px;">Click to select · Esc to cancel</div>';
    }

    _onClick(e) {
        if (!this.active) return;
        e.stopPropagation();
        e.preventDefault();
        const el = e.target;
        if (this._isOurElement(el)) return;

        const selector = generateSelector(el, this.scope);
        const count = countMatches(selector, this.scope);
        this._highlightMatches(selector);

        if (this.onSelect) {
            this.onSelect(selector, count);
        }
    }

    _onKeyDown(e) {
        if (!this.active) return;
        if (e.key === 'Escape') {
            e.stopPropagation();
            e.preventDefault();
            this.disable();
            if (this.onCancel) this.onCancel();
        }
    }
}

// ─── Auto-suggest sub-selectors ────────────────────────────────

function autoSuggestSubSelectors(listingSelector) {
    const cards = document.querySelectorAll(listingSelector);
    if (cards.length === 0) return null;
    const card = cards[0];

    const titleEl = card.querySelector('h1, h2, h3, h4, h5, h6, .title, [itemprop="title"], [class*="title"]');
    const titleSelector = titleEl ? generateSelector(titleEl, card) : '';

    const allLinks = card.querySelectorAll('a[href]');
    let linkEl = null;
    for (const a of allLinks) {
        const href = a.getAttribute('href') || '';
        if (href.includes('/job') || href.includes('/ad') || href.includes('/position') || href.includes('/project') || href.includes('/phd') || href.startsWith('/')) { linkEl = a; break; }
    }
    if (!linkEl && allLinks.length > 0) linkEl = allLinks[0];
    const linkSelector = linkEl ? generateSelector(linkEl, card) : '';

    const companyEl = card.querySelector('[class*="institution"], [class*="company"], [class*="employer"], [class*="organisation"], [class*="organization"], [class*="university"], [itemprop="hiringOrganization"]');
    const companySelector = companyEl ? generateSelector(companyEl, card) : '';

    return { title: titleSelector, link: linkSelector, company: companySelector };
}