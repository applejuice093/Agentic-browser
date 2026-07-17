"""In-page JavaScript that extracts a semantic DOM candidate list."""

from __future__ import annotations

# Runs in the browser. Returns a flat list of candidate nodes with:
# type, role, text, name, attributes, value, checked, visible, enabled,
# bounding_box, dom_path, parent_path, description, depth
SEMANTIC_EXTRACT_JS = r"""
() => {
  const SKIP_TAGS = new Set([
    'SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE', 'SVG', 'PATH', 'META',
    'LINK', 'HEAD', 'BR', 'WBR', 'SOURCE', 'TRACK', 'COL', 'COLGROUP',
  ]);
  const LANDMARK_TAGS = new Set([
    'MAIN', 'NAV', 'HEADER', 'FOOTER', 'ASIDE', 'FORM', 'SECTION', 'ARTICLE',
    'TABLE', 'UL', 'OL', 'DL', 'FIELDSET', 'DIALOG',
  ]);
  const HEADING_TAGS = new Set(['H1', 'H2', 'H3', 'H4', 'H5', 'H6']);
  const INTERACTIVE_TAGS = new Set([
    'A', 'BUTTON', 'INPUT', 'SELECT', 'TEXTAREA', 'SUMMARY', 'OPTION', 'LABEL',
  ]);
  const PRESENTATION_ROLES = new Set(['presentation', 'none']);

  function isVisible(el) {
    const style = window.getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
      return false;
    }
    const rect = el.getBoundingClientRect();
    // allow zero-size for some inputs still in a11y tree conceptually, but mark not visible
    return rect.width > 0 && rect.height > 0;
  }

  function directText(el) {
    let t = '';
    for (const node of el.childNodes) {
      if (node.nodeType === Node.TEXT_NODE) {
        t += node.textContent || '';
      }
    }
    return t.replace(/\s+/g, ' ').trim();
  }

  function accessibleNameHint(el) {
    return (
      el.getAttribute('aria-label') ||
      el.getAttribute('aria-labelledby') ||
      el.getAttribute('alt') ||
      el.getAttribute('title') ||
      el.getAttribute('placeholder') ||
      el.getAttribute('name') ||
      null
    );
  }

  function implicitRole(el) {
    const tag = el.tagName;
    const type = (el.getAttribute('type') || '').toLowerCase();
    if (el.getAttribute('role')) return el.getAttribute('role');
    if (tag === 'A' && el.hasAttribute('href')) return 'link';
    if (tag === 'BUTTON') return 'button';
    if (tag === 'INPUT') {
      if (type === 'submit' || type === 'button' || type === 'reset' || type === 'image') return 'button';
      if (type === 'checkbox') return 'checkbox';
      if (type === 'radio') return 'radio';
      if (type === 'range') return 'slider';
      if (type === 'hidden') return null;
      return 'textbox';
    }
    if (tag === 'TEXTAREA') return 'textbox';
    if (tag === 'SELECT') return 'combobox';
    if (tag === 'IMG') return 'img';
    if (HEADING_TAGS.has(tag)) return 'heading';
    if (tag === 'NAV') return 'navigation';
    if (tag === 'MAIN') return 'main';
    if (tag === 'HEADER') return 'banner';
    if (tag === 'FOOTER') return 'contentinfo';
    if (tag === 'ASIDE') return 'complementary';
    if (tag === 'FORM') return 'form';
    if (tag === 'TABLE') return 'table';
    if (tag === 'UL' || tag === 'OL') return 'list';
    if (tag === 'LI') return 'listitem';
    if (tag === 'DIALOG') return 'dialog';
    if (tag === 'LABEL') return 'label';
    if (el.isContentEditable) return 'textbox';
    return tag.toLowerCase();
  }

  function isSemantic(el) {
    if (SKIP_TAGS.has(el.tagName)) return false;
    if (el.closest('[aria-hidden="true"]')) return false;

    const roleAttr = (el.getAttribute('role') || '').toLowerCase();
    if (PRESENTATION_ROLES.has(roleAttr)) return false;

    if (INTERACTIVE_TAGS.has(el.tagName)) {
      if (el.tagName === 'INPUT' && (el.getAttribute('type') || '').toLowerCase() === 'hidden') {
        return false;
      }
      if (el.tagName === 'A' && !el.hasAttribute('href')) return false;
      return true;
    }
    if (HEADING_TAGS.has(el.tagName)) return true;
    if (LANDMARK_TAGS.has(el.tagName)) return true;
    if (roleAttr) return true;
    if (el.tagName === 'IMG' && (el.getAttribute('alt') || '').trim() !== '') return true;
    if (el.hasAttribute('onclick') || el.hasAttribute('tabindex')) return true;
    if (el.isContentEditable) return true;

    // Leaf-ish text containers with own text
    const own = directText(el);
    if (own.length >= 1 && ['P', 'SPAN', 'DIV', 'LI', 'TD', 'TH', 'DT', 'DD', 'FIGCAPTION', 'CAPTION'].includes(el.tagName)) {
      // Skip pure layout wrappers with only whitespace children handled elsewhere
      if (own.length >= 2 || el.tagName === 'P' || el.tagName === 'LI') return true;
    }
    return false;
  }

  function pathFor(el) {
    const parts = [];
    let cur = el;
    while (cur && cur.nodeType === 1 && cur !== document.documentElement) {
      const parent = cur.parentElement;
      let idx = 0;
      if (parent) {
        const siblings = Array.from(parent.children).filter(c => c.tagName === cur.tagName);
        idx = siblings.indexOf(cur);
      }
      parts.unshift(cur.tagName.toLowerCase() + '[' + idx + ']');
      cur = parent;
    }
    return parts.join('/');
  }

  const all = Array.from(document.body ? document.body.querySelectorAll('*') : []);
  const candidates = [];
  for (const el of all) {
    if (!isSemantic(el)) continue;
    candidates.push(el);
  }

  // parent_path: nearest ancestor that is also a candidate
  const candSet = new Set(candidates);
  const out = [];

  for (const el of candidates) {
    const rect = el.getBoundingClientRect();
    const visible = isVisible(el);
    const attrs = {};
    for (const a of el.attributes) {
      if (a.name === 'data-agent-id') continue;
      attrs[a.name] = a.value;
    }

    let text = '';
    if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
      text = (el.getAttribute('placeholder') || el.value || '').toString();
    } else if (el.tagName === 'IMG') {
      text = (el.getAttribute('alt') || '').toString();
    } else {
      // Prefer direct text; fall back to truncated innerText for leaves
      text = directText(el);
      if (!text) {
        text = (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();
      }
    }
    text = text.slice(0, 200);

    let parentEl = el.parentElement;
    let parent_path = null;
    while (parentEl) {
      if (candSet.has(parentEl)) {
        parent_path = pathFor(parentEl);
        break;
      }
      parentEl = parentEl.parentElement;
    }

    const role = implicitRole(el);
    const nameHint = accessibleNameHint(el);
    let name = el.getAttribute('aria-label') || null;
    if (!name && el.tagName === 'INPUT') {
      // associated label
      if (el.id) {
        const lab = document.querySelector('label[for="' + CSS.escape(el.id) + '"]');
        if (lab) name = (lab.innerText || lab.textContent || '').trim() || null;
      }
      if (!name && el.closest('label')) {
        const lab = el.closest('label');
        name = (lab.innerText || lab.textContent || '').trim() || null;
      }
    }
    if (!name) name = nameHint;

    out.push({
      type: el.tagName.toLowerCase(),
      role: role,
      text: text,
      name: name,
      description: el.getAttribute('aria-description') || el.getAttribute('aria-describedby') || null,
      attributes: attrs,
      value: ('value' in el && el.value !== undefined && el.tagName !== 'LI') ? String(el.value) : null,
      checked: ('checked' in el && (el.type === 'checkbox' || el.type === 'radio' || el.getAttribute('role') === 'checkbox'))
        ? Boolean(el.checked) : null,
      visible: visible,
      enabled: !Boolean(el.disabled),
      bounding_box: {
        x: rect.x,
        y: rect.y,
        width: rect.width,
        height: rect.height,
      },
      dom_path: pathFor(el),
      parent_path: parent_path,
      depth: pathFor(el).split('/').length,
    });
  }
  return out;
}
"""

STAMP_IDS_JS = r"""
(map) => {
  // map: [{path, id}, ...]
  const byPath = {};
  for (const item of map) {
    byPath[item.path] = item.id;
  }
  // Clear previous stamps
  for (const el of document.querySelectorAll('[data-agent-id]')) {
    el.removeAttribute('data-agent-id');
  }
  const all = document.body ? document.body.querySelectorAll('*') : [];
  function pathFor(el) {
    const parts = [];
    let cur = el;
    while (cur && cur.nodeType === 1 && cur !== document.documentElement) {
      const parent = cur.parentElement;
      let idx = 0;
      if (parent) {
        const siblings = Array.from(parent.children).filter(c => c.tagName === cur.tagName);
        idx = siblings.indexOf(cur);
      }
      parts.unshift(cur.tagName.toLowerCase() + '[' + idx + ']');
      cur = parent;
    }
    return parts.join('/');
  }
  let stamped = 0;
  for (const el of all) {
    const p = pathFor(el);
    if (p in byPath) {
      el.setAttribute('data-agent-id', String(byPath[p]));
      stamped++;
    }
  }
  return stamped;
}
"""
