// This single self-contained function runs in Chrome's isolated world in the top document.
export function pageCommand(op, arg = {}) {
  if (!['http:', 'https:'].includes(location.protocol)) return { error: 'noPage' };
  const trim = (s, n) => String(s || '').replace(/\s+/g, ' ').trim().slice(0, n);
  function publicUrl(raw) {
    try {
      const u = new URL(raw);
      if (!['http:', 'https:'].includes(u.protocol)) return '';
      return (u.origin + u.pathname).slice(0, 2000);
    } catch { return ''; }
  }
  const meta = { url: publicUrl(location.href), title: trim(document.title, 200) };
  if (op === 'meta') return { ...meta, currentHref: location.href };
  const privateNodes = 'script,style,noscript,template,iframe,object,embed,canvas,svg,input,textarea,select,option,[contenteditable]:not([contenteditable="false"]),[role="textbox"],[role="searchbox"],[role="combobox"],[hidden],[inert],[aria-hidden="true"]';
  function visible(el) {
    if (el.closest('[hidden],[inert],[aria-hidden="true"]')) return false;
    if (el.checkVisibility && !el.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })) return false;
    const s = getComputedStyle(el);
    return s.display !== 'none' && s.visibility === 'visible' && s.opacity !== '0';
  }
  function readText(limit, range) {
    const root = document.body;
    if (!root || root.matches(privateNodes) || !visible(root)) return { text: '', clipped: false };
    const parts = []; let length = 0, inspected = 0, clipped = false, lastBlock;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
      acceptNode(n) {
        inspected++;
        if (inspected > 50000 || (range && !range.intersectsNode(n))) return NodeFilter.FILTER_REJECT;
        if (n.nodeType === Node.ELEMENT_NODE) {
          if (n.matches(privateNodes)) return NodeFilter.FILTER_REJECT;
          const s = getComputedStyle(n);
          if (s.display === 'none' || s.visibility !== 'visible' || s.opacity === '0' || s.contentVisibility === 'hidden') return NodeFilter.FILTER_REJECT;
          return NodeFilter.FILTER_SKIP;
        }
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      const start = n === range?.startContainer ? range.startOffset : 0;
      const end = n === range?.endContainer ? range.endOffset : n.length;
      const budget = limit - length;
      const str = n.data.slice(start, Math.min(end, start + budget + 1)).replace(/\s+/g, ' ').trim();
      if (str) {
        const block = n.parentElement.closest('p,li,h1,h2,h3,h4,h5,h6,section,article,tr,div,main');
        const gap = !parts.length ? '' : block === lastBlock ? ' ' : '\n';
        parts.push(gap, str); length += gap.length + str.length; lastBlock = block;
      }
      if (length >= limit || end - start > budget) { clipped = true; break; }
    }
    return { text: parts.join('').slice(0, limit), clipped: clipped || inspected > 50000 };
  }
  if (op === 'page') return { ...meta, ...readText(20000) };
  if (op === 'selection') {
    const selection = window.getSelection();
    if (!selection?.rangeCount || selection.isCollapsed) return { error: 'emptySelection' };
    const result = readText(20000, selection.getRangeAt(0));
    return result.text ? { ...meta, ...result } : { error: 'emptySelection' };
  }

  const selector = 'a[href],button,input,select,textarea,[role="button"],[role="tab"],[role="menuitem"],[role="checkbox"],[role="link"],[role="option"],[role="row"],[onclick],[tabindex]:not([tabindex="-1"]),li,div,tr,span,label';
  const pointerClick = el => el.matches('li,div,tr,span,label,[onclick],[tabindex],[role="option"],[role="row"]') && !el.closest('a[href],button,[role="button"],[role="link"]') && getComputedStyle(el).cursor === 'pointer' && !(el.parentElement && getComputedStyle(el.parentElement).cursor === 'pointer' && !el.matches('[onclick],[role="option"],[role="row"]'));
  const sensitive = /passw(?:or)?d|passcode|cvv|cvc|\bcc[-_ ]?(?:num|exp|name|csc)|(?:^|[^a-z])(?:pin|otp|2fa|mfa)(?:[^a-z]|$)|card.?num|credit.?card|one.?time|verif(?:y|ication).?code|auth(?:entication)?.?code|api.?key|secret|token|palavra.?passe|cart[aã]o|c[oó]digo.?de.?verifica/i;
  function label(el) {
    const labelled = el.labels?.[0];
    const fromText = node => {
      if (!node || node.matches(privateNodes) || node.querySelector('input,textarea,select,[contenteditable],[role="textbox"]')) return '';
      return node.innerText || '';
    };
    return trim(el.getAttribute('aria-label') || fromText(labelled) || fromText(el) || el.placeholder || el.title || el.getAttribute('alt') || el.name, 160);
  }
  function secret(el) {
    return el.type === 'password' || el.type === 'file' || /(?:^|\s)(?:cc-\S+|one-time-code|current-password|new-password|webauthn)(?:\s|$)/i.test(el.autocomplete || '') || sensitive.test([el.id, el.name, el.placeholder, el.getAttribute('aria-label'), label(el)].join(' '));
  }
  function eligible(el) {
    if (!el?.isConnected || el.matches(':disabled,[readonly],[aria-disabled="true"]') || el.closest('[contenteditable]:not([contenteditable="false"]),[role="textbox"]') || secret(el)) return false;
    const r = el.getBoundingClientRect();
    return r.width >= 2 && r.height >= 2 && visible(el);
  }
  function capabilities(el) {
    if (el.matches('textarea,input[type="text" i],input:not([type]),input[type="search" i],input[type="email" i],input[type="url" i]')) return ['type'];
    if (el.matches('select') && !el.multiple) return ['select'];
    if (el.matches('a[href]')) {
      try { const u = new URL(el.href); if (publicUrl(u.href) && !u.username && !u.password && !el.hasAttribute('download')) return ['click']; } catch {}
      return [];
    }
    if (el.form && ['submit', 'reset', 'image'].includes(el.type)) return [];
    if (el.matches('button,input[type="button" i],input[type="checkbox" i],input[type="radio" i],[role="button"],[role="link"],[role="tab"],[role="menuitem"],[role="checkbox"]')) return ['click'];
    if (pointerClick(el)) return ['click'];
    return [];
  }
  function optionsFor(el) {
    return Array.from(el.options).slice(0, 40).filter(o => !o.disabled && !o.parentElement?.disabled);
  }
  function signature(el) {
    // Option values and complete link destinations stay inside this document.
    const options = el.localName === 'select' ? optionsFor(el).map(o => [o.label, o.value]) : null;
    return JSON.stringify([el.tagName, el.type, label(el), el.href || '', el.getAttribute('target'), el.getAttribute('role'), el.name, el.formAction || '', capabilities(el), options]);
  }
  if (op === 'snapshot') {
    const token = crypto.randomUUID ? crypto.randomUUID() : Array.from(crypto.getRandomValues(new Uint32Array(4))).join('-');
    const refs = new Map(), elements = []; let examined = 0;
    for (const el of document.querySelectorAll(selector)) {
      if (++examined > 5000 || elements.length >= 120) break;
      const r = el.getBoundingClientRect(); if (r.bottom < 0 || r.top > innerHeight * 2 || !eligible(el)) continue;
      const actions = capabilities(el), name = label(el); if (!actions.length || !name) continue;
      const id = elements.length + 1;
      const entry = { id, label: name, tag: el.localName, actions };
      if (el.matches('a[href]')) entry.link = publicUrl(el.href);
      if (actions.includes('select')) entry.options = optionsFor(el).map(o => trim(o.label, 120));
      refs.set(id, { el, signature: signature(el) }); elements.push(entry);
    }
    globalThis.__odysseusReview = { token, location: location.href, refs };
    return { ...meta, ...readText(7000), elements, token };
  }
  if (op === 'apply' && document.visibilityState !== 'visible') return { error: 'guideTab' };
  const state = globalThis.__odysseusReview;
  if (!state || state.token !== arg.token || state.location !== location.href) return { error: 'stale' };
  const a = arg.action, ref = state.refs.get(a.id), el = ref?.el;
  if (['click', 'select', 'type'].includes(a.a) && (!eligible(el) || ref.signature !== signature(el) || !capabilities(el).includes(a.a))) return { error: 'stale' };
  if (op === 'inspect') return { destination: el?.href || '' };
  if (op === 'show' && el) {
    el.scrollIntoView({ block: 'center', behavior: 'instant' });
    el.animate([{ outline: '3px solid #147c6e' }, { outline: '3px solid #147c6e' }], { duration: 1800 });
    return { ok: true };
  }
  if (op !== 'apply') return { error: 'unsupported' };
  delete globalThis.__odysseusReview;
  switch (a.a) {
    case 'scroll': scrollBy({ top: (a.dir === 'up' ? -1 : 1) * innerHeight * 0.8, behavior: 'instant' }); break;
    case 'goto': {
      let dest; try { dest = new URL(a.url); } catch { return { error: 'unsupported' }; }
      if (!['http:', 'https:'].includes(dest.protocol) || dest.username || dest.password) return { error: 'unsupported' };
      location.assign(dest.href); break;
    }
    case 'click': el.click(); break;
    case 'type': {
      if (typeof a.text !== 'string' || a.text.length > 2000) return { error: 'unsupported' };
      const proto = el.localName === 'textarea' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
      Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, a.text);
      el.dispatchEvent(new Event('input', { bubbles: true })); break;
    }
    case 'select': {
      const choices = optionsFor(el).filter(o => trim(o.label, 120) === a.value);
      if (choices.length !== 1) return { error: 'stale' };
      el.selectedIndex = choices[0].index; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); break;
    }
    default: return { error: 'unsupported' };
  }
  return { ok: true };
}
