// Self-contained Unified Semantic DOM, Accessibility & Interaction Engine.
// Runs inside Chrome's ISOLATED world via chrome.scripting.executeScript({ func, args }).
// Zero host-DOM attribute pollution: all element references live in globalThis.__odyRefs.

export async function domEngine(op, arg = {}) {
  if (!['http:', 'https:'].includes(location.protocol)) return { error: 'noPage', ok: false, msg: 'unsupported page' };

  const trim = (s, n = 160) => String(s || '').replace(/\s+/g, ' ').trim().slice(0, n);
  const SENSITIVE_PARAMS = /^(?:token|access_token|id_token|refresh_token|api_?key|key|secret|password|passwd|pwd|code|auth|session|sid|sig|signature|jwt|bearer|credential|otp)$/i;
  const SENSITIVE_FIELD = /passw(?:or)?d|passcode|cvv|cvc|\bcc[-_ ]?(?:num|exp|name|csc)|(?:^|[^a-z])(?:pin|otp|2fa|mfa)(?:[^a-z]|$)|card.?num|credit.?card|one.?time|verif(?:y|ication).?code|auth(?:entication)?.?code|api.?key|secret|token|palavra.?passe|cart[aã]o|c[oó]digo.?de.?verifica/i;

  function publicUrl(raw, keepQuery = false) {
    try {
      const u = new URL(raw, location.href);
      if (!['http:', 'https:'].includes(u.protocol)) return '';
      if (!keepQuery) return (u.origin + u.pathname).slice(0, 2000);
      const clean = new URL(u.origin + u.pathname);
      for (const [k, v] of u.searchParams.entries()) {
        clean.searchParams.append(k, SENSITIVE_PARAMS.test(k) ? '[REDACTED]' : v.slice(0, 120));
      }
      const hash = u.hash && u.hash.length <= 160 && !SENSITIVE_PARAMS.test(u.hash.slice(1)) ? u.hash : '';
      return (clean.origin + clean.pathname + clean.search + hash).slice(0, 2000);
    } catch { return ''; }
  }

  // Banner management (isolated UI overlay, cleaned up reliably)
  if (op === 'banner') {
    let b = document.getElementById('__ody_banner');
    if (!arg.on) {
      if (b) b.remove();
      document.getElementById('__ody_som_layer')?.remove();
      return { ok: true };
    }
    if (b) {
      const txt = b.firstChild;
      if (txt && txt.nodeType === 3 && arg.label) txt.textContent = arg.label;
      return { ok: true };
    }
    b = document.createElement('div');
    b.id = '__ody_banner';
    b.setAttribute('data-ody-ignore', '1');
    b.style.cssText = 'position:fixed;top:8px;left:50%;transform:translateX(-50%);z-index:2147483647;background:#e8590c;color:#fff;font:600 13px system-ui,sans-serif;padding:6px 8px 6px 14px;border-radius:20px;box-shadow:0 2px 10px #0006;display:flex;gap:10px;align-items:center;pointer-events:auto';
    b.append(document.createTextNode(arg.label || 'Working…'));
    const s = document.createElement('button');
    s.textContent = arg.stopLabel || 'Stop';
    s.style.cssText = 'background:#fff;color:#e8590c;border:0;border-radius:12px;padding:3px 10px;font:700 12px system-ui,sans-serif;cursor:pointer';
    s.onclick = () => { try { chrome.runtime.sendMessage({ odyStop: true }); } catch {} b.remove(); };
    b.append(s);
    document.documentElement.append(b);
    return { ok: true };
  }

  // Set-of-Marks (SoM) visual grounding overlay for accurate vision (`look`)
  if (op === 'som') {
    document.getElementById('__ody_som_layer')?.remove();
    if (!arg.on) return { ok: true };
    const refs = globalThis.__odyRefs?.map;
    if (!refs || !refs.size) return { ok: false };
    const layer = document.createElement('div');
    layer.id = '__ody_som_layer';
    layer.setAttribute('data-ody-ignore', '1');
    layer.style.cssText = 'position:fixed;inset:0;pointer-events:none;z-index:2147483646;overflow:hidden';
    let count = 0;
    for (const [id, entry] of refs.entries()) {
      if (count >= 90) break;
      const el = entry.el;
      if (!el?.isConnected) continue;
      const r = el.getBoundingClientRect();
      if (r.width < 4 || r.height < 4 || r.bottom <= 0 || r.right <= 0 || r.top >= innerHeight || r.left >= innerWidth) continue;
      const tag = document.createElement('span');
      const top = Math.max(0, Math.min(innerHeight - 16, Math.round(r.top)));
      const left = Math.max(0, Math.min(innerWidth - 26, Math.round(r.left)));
      tag.textContent = String(id);
      tag.style.cssText = `position:fixed;top:${top}px;left:${left}px;background:#d9480f;color:#fff;font:700 10px/1.2 ui-monospace,monospace;padding:1px 4px;border-radius:4px;border:1px solid #fff;box-shadow:0 1px 3px #0009`;
      const box = document.createElement('div');
      box.style.cssText = `position:fixed;top:${Math.round(r.top)}px;left:${Math.round(r.left)}px;width:${Math.round(r.width)}px;height:${Math.round(r.height)}px;border:1.5px dashed #d9480fcc;border-radius:3px`;
      layer.append(box, tag);
      count++;
    }
    document.documentElement.append(layer);
    await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
    return { ok: true, count };
  }

  // Adaptive MutationObserver + rAF DOM Stability Waiter (Proposal 2)
  if (op === 'settle') {
    const quietMs = arg.quietMs ?? 130;
    const maxMs = arg.maxMs ?? 4200;
    const minMs = arg.minMs ?? 90;
    const started = performance.now();
    await new Promise(resolve => {
      let quietTimer = null, maxTimer = null, lastMut = performance.now();
      const hasBusy = () => !!document.querySelector('[aria-busy="true"],[data-loading="true"],.skeleton,[class*="skeleton" i]');
      const finish = () => {
        observer.disconnect();
        clearTimeout(quietTimer);
        clearTimeout(maxTimer);
        requestAnimationFrame(() => resolve());
      };
      const schedule = () => {
        clearTimeout(quietTimer);
        const elapsed = performance.now() - started;
        const extra = hasBusy() && elapsed < 1800 ? 220 : quietMs;
        quietTimer = setTimeout(() => {
          if (document.readyState === 'loading' && performance.now() - started < maxMs - 200) { schedule(); return; }
          finish();
        }, Math.max(extra, minMs - elapsed));
      };
      const observer = new MutationObserver((muts) => {
        for (const m of muts) {
          if (m.target?.id === '__ody_banner' || m.target?.id === '__ody_som_layer' || m.target?.closest?.('[data-ody-ignore]')) continue;
          lastMut = performance.now();
          schedule();
          break;
        }
      });
      if (document.documentElement) {
        observer.observe(document.documentElement, { childList: true, subtree: true, attributes: true, characterData: true });
      }
      maxTimer = setTimeout(finish, maxMs);
      schedule();
    });
    return { ok: true, waited: Math.round(performance.now() - started), readyState: document.readyState };
  }

  const meta = { url: publicUrl(location.href, false), stateUrl: publicUrl(location.href, true), title: trim(document.title, 200) };
  if (op === 'meta') return { ...meta, currentHref: location.href };

  const privateNodes = 'script,style,noscript,template,object,embed,canvas,svg,[hidden],[inert],[aria-hidden="true"],#__ody_banner,#__ody_som_layer,[data-ody-ignore]';
  const chatSkipNodes = privateNodes + ',iframe,input,textarea,select,option,[contenteditable]:not([contenteditable="false"]),[role="textbox"],[role="searchbox"],[role="combobox"]';

  function isVisible(el) {
    if (!el || !(el instanceof Element)) return false;
    if (el.closest('[hidden],[inert],[aria-hidden="true"],#__ody_banner,#__ody_som_layer,[data-ody-ignore]')) return false;
    if (el.checkVisibility && !el.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })) return false;
    const s = getComputedStyle(el);
    return s.display !== 'none' && s.visibility !== 'hidden' && s.visibility !== 'collapse' && parseFloat(s.opacity || '1') > 0.02;
  }

  // Deep TreeWalker supporting open Shadow Roots and same-origin iframes
  function readStructuredText(limit, range, includeSubtrees = true) {
    const root = document.body;
    if (!root || !isVisible(root)) return { text: '', clipped: false };
    const parts = [];
    let length = 0, inspected = 0, clipped = false, lastBlock = null;
    const skipSelector = range || !includeSubtrees ? chatSkipNodes : privateNodes + ',option';

    function walkRoot(nodeRoot) {
      if (!nodeRoot || clipped || inspected > 55000) return;
      const walker = (nodeRoot.ownerDocument || document).createTreeWalker(
        nodeRoot,
        NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT,
        {
          acceptNode(n) {
            inspected++;
            if (inspected > 55000 || (range && !range.intersectsNode(n))) return NodeFilter.FILTER_REJECT;
            if (n.nodeType === Node.ELEMENT_NODE) {
              if (n.matches?.(skipSelector)) return NodeFilter.FILTER_REJECT;
              const s = getComputedStyle(n);
              if (s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0' || s.contentVisibility === 'hidden') return NodeFilter.FILTER_REJECT;
              return NodeFilter.FILTER_ACCEPT;
            }
            return NodeFilter.FILTER_ACCEPT;
          }
        }
      );
      for (let n = walker.nextNode(); n; n = walker.nextNode()) {
        if (n.nodeType === Node.ELEMENT_NODE) {
          if (includeSubtrees && !range) {
            if (n.shadowRoot) walkRoot(n.shadowRoot);
            if (n.tagName === 'IFRAME') {
              try { if (n.contentDocument?.body) walkRoot(n.contentDocument.body); } catch {}
            }
          }
          continue;
        }
        const parent = n.parentElement;
        if (parent && parent.matches?.('input,textarea,select,[contenteditable]:not([contenteditable="false"])')) continue;
        const start = n === range?.startContainer ? range.startOffset : 0;
        const end = n === range?.endContainer ? range.endOffset : n.length;
        const budget = limit - length;
        const str = n.data.slice(start, Math.min(end, start + budget + 1)).replace(/\s+/g, ' ').trim();
        if (str) {
          const block = parent?.closest?.('p,li,h1,h2,h3,h4,h5,h6,section,article,tr,div,main,header,footer,nav,aside') || parent;
          const isHeading = parent?.closest?.('h1,h2,h3');
          const prefix = isHeading && block !== lastBlock ? '## ' : '';
          const gap = !parts.length ? '' : block === lastBlock ? ' ' : '\n';
          const chunk = prefix + str;
          parts.push(gap, chunk);
          length += gap.length + chunk.length;
          lastBlock = block;
        }
        if (length >= limit || end - start > budget) { clipped = true; break; }
      }
    }
    walkRoot(root);
    return { text: parts.join('').slice(0, limit), clipped: clipped || inspected > 55000 };
  }

  if (op === 'page') return { ...meta, ...readStructuredText(20000, null, false) };
  if (op === 'selection') {
    const selection = window.getSelection();
    if (!selection?.rangeCount || selection.isCollapsed) return { error: 'emptySelection' };
    const result = readStructuredText(20000, selection.getRangeAt(0), false);
    return result.text ? { ...meta, ...result } : { error: 'emptySelection' };
  }

  // Label & Secret Detection
  function computeLabel(el) {
    const ariaLabel = el.getAttribute('aria-label');
    if (ariaLabel?.trim()) return trim(ariaLabel, 160);
    const labelledBy = el.getAttribute('aria-labelledby');
    if (labelledBy) {
      const doc = el.ownerDocument || document;
      const txt = labelledBy.split(/\s+/).map(id => doc.getElementById(id)?.innerText || '').join(' ');
      if (txt.trim()) return trim(txt, 160);
    }
    if (el.labels?.length) {
      const lt = Array.from(el.labels).map(l => l.innerText || '').join(' ');
      if (lt.trim()) return trim(lt, 160);
    }
    const isEditable = el.isContentEditable || el.tagName === 'TEXTAREA' || (el.tagName === 'INPUT' && !['button', 'submit', 'reset', 'checkbox', 'radio', 'image'].includes((el.type || '').toLowerCase()));
    if (!isEditable) {
      const inner = trim(el.innerText || '', 160);
      if (inner) return inner;
      const svgTitle = el.querySelector?.('svg title,[aria-label],[alt]');
      if (svgTitle) {
        const st = svgTitle.getAttribute?.('aria-label') || svgTitle.getAttribute?.('alt') || svgTitle.textContent;
        if (st?.trim()) return trim(st, 120);
      }
    }
    const fallback = el.getAttribute('placeholder') || el.getAttribute('title') || el.getAttribute('alt') || el.getAttribute('name') || '';
    if (fallback.trim()) return trim(fallback, 140);
    if (el.tagName === 'INPUT' && (el.type === 'checkbox' || el.type === 'radio')) {
      const near = el.closest('label')?.innerText || (el.nextSibling?.nodeType === 3 ? el.nextSibling.textContent : '') || el.nextElementSibling?.innerText || '';
      if (near.trim()) return trim(near, 100);
    }
    const tid = el.getAttribute('data-testid') || el.getAttribute('data-test') || el.getAttribute('data-qa');
    if (tid) return '(' + trim(tid.replace(/[-_]+/g, ' '), 80) + ')';
    if (isEditable && el.getAttribute('role')) return '(' + el.getAttribute('role') + ')';
    return '';
  }

  function isSecret(el, computedName = '') {
    const ty = (el.type || '').toLowerCase();
    if (ty === 'password' || ty === 'file') return true;
    if (/(?:^|\s)(?:cc-\S+|one-time-code|current-password|new-password|webauthn)(?:\s|$)/i.test(el.autocomplete || '')) return true;
    return SENSITIVE_FIELD.test([el.id, el.name, el.placeholder, el.getAttribute('aria-label'), computedName].join(' '));
  }

  // Detect active top-layer modal / dialog / popover
  function detectActiveModal() {
    const candidates = [
      ...document.querySelectorAll('dialog[open],[aria-modal="true"],[role="dialog"],[role="alertdialog"]')
    ].filter(d => {
      if (!isVisible(d)) return false;
      const r = d.getBoundingClientRect();
      return r.width >= 140 && r.height >= 80 && r.bottom > 0 && r.top < innerHeight;
    });
    if (!candidates.length) return null;
    candidates.sort((a, b) => (parseInt(getComputedStyle(b).zIndex) || 0) - (parseInt(getComputedStyle(a).zIndex) || 0));
    return candidates[0];
  }

  // Traverse Document + Open Shadow Roots + Same-origin Iframes
  const INTERACTIVE_SEL = [
    'a[href]', 'button', 'input:not([type="hidden" i])', 'select', 'textarea', 'summary',
    '[role="button"]', '[role="link"]', '[role="tab"]', '[role="menuitem"]', '[role="menuitemcheckbox"]', '[role="menuitemradio"]',
    '[role="option"]', '[role="checkbox"]', '[role="radio"]', '[role="switch"]', '[role="combobox"]', '[role="searchbox"]', '[role="textbox"]',
    '[role="row"]', '[role="listitem"]', '[role="gridcell"]', '[role="treeitem"]',
    '[contenteditable="true"]', '[contenteditable=""]',
    '[aria-expanded]', '[aria-haspopup]', '[onclick]', '[tabindex]:not([tabindex="-1"])',
    '[data-testid*="expand" i]', '[data-testid*="toggle" i]', '[data-testid*="dropdown" i]', '[data-testid*="btn" i]', '[data-testid*="button" i]'
  ].join(',');

  function collectCandidates(root, frameOffset = { x: 0, y: 0 }, frameDoc = document, out = []) {
    if (!root || out.length >= 900) return out;
    for (const el of root.querySelectorAll(INTERACTIVE_SEL)) {
      if (out.length >= 900) break;
      if (el.closest('#__ody_banner,#__ody_som_layer,[data-ody-ignore]')) continue;
      out.push({ el, frameOffset, frameDoc });
    }
    // Also inspect shadow roots & same-origin iframes
    const allEls = root.querySelectorAll('*');
    let scanned = 0;
    for (const el of allEls) {
      if (++scanned > 4500 || out.length >= 900) break;
      if (el.id === '__ody_banner' || el.id === '__ody_som_layer') continue;
      if (el.shadowRoot) collectCandidates(el.shadowRoot, frameOffset, frameDoc, out);
      if (el.tagName === 'IFRAME' && isVisible(el)) {
        try {
          const doc = el.contentDocument;
          if (doc?.body) {
            const ir = el.getBoundingClientRect();
            collectCandidates(doc, { x: frameOffset.x + ir.left, y: frameOffset.y + ir.top }, doc, out);
          }
        } catch {}
      }
      // Pointer-cursor custom clickable elements without semantic roles (cap tightly)
      if (!el.matches?.(INTERACTIVE_SEL) && /^(div|span|li|td|tr|label)$/i.test(el.tagName) && el.childElementCount <= 4) {
        const cs = getComputedStyle(el);
        if (cs.cursor === 'pointer' && (!el.parentElement || getComputedStyle(el.parentElement).cursor !== 'pointer')) {
          const r = el.getBoundingClientRect();
          if (r.width >= 14 && r.height >= 14 && r.width <= 500 && r.height <= 140) out.push({ el, frameOffset, frameDoc });
        }
      }
    }
    return out;
  }

  function capabilitiesOf(el, guideSafe = false) {
    const tag = el.tagName.toLowerCase();
    const role = (el.getAttribute('role') || '').toLowerCase();
    const ty = (el.type || '').toLowerCase();
    const isEditable = el.isContentEditable || tag === 'textarea' || (tag === 'input' && !['button', 'submit', 'reset', 'checkbox', 'radio', 'image', 'file', 'hidden', 'range', 'color'].includes(ty)) || ['textbox', 'searchbox'].includes(role);
    if (isEditable) {
      if (guideSafe && el.isContentEditable) return ['type'];
      return ['type', 'click'];
    }
    if (tag === 'select') return el.multiple && guideSafe ? [] : ['select', 'click'];
    if (role === 'combobox' || el.getAttribute('aria-haspopup') === 'listbox') return guideSafe ? ['click'] : ['select', 'click'];
    if (tag === 'a' && el.href) {
      try {
        const u = new URL(el.href, location.href);
        if (['http:', 'https:'].includes(u.protocol) && !u.username && !u.password && (!guideSafe || !el.hasAttribute('download'))) return ['click'];
      } catch {}
      if (!guideSafe && el.getAttribute('href')?.startsWith('#')) return ['click'];
      return guideSafe ? [] : ['click'];
    }
    if (guideSafe && el.form && ['submit', 'reset', 'image'].includes(ty)) return [];
    return ['click'];
  }

  function optionsFor(el) {
    if (el.tagName !== 'SELECT') return [];
    return Array.from(el.options).slice(0, 45).filter(o => !o.disabled && !o.parentElement?.disabled);
  }

  function signatureOf(el, name, actions) {
    const opts = el.tagName === 'SELECT' ? optionsFor(el).map(o => [o.label, o.value]) : null;
    return JSON.stringify([el.tagName, el.type || '', name, el.href || '', el.getAttribute('target'), el.getAttribute('role'), el.name || '', el.formAction || '', actions, opts]);
  }

  // Hit-test occlusion check (detects if element is covered by a modal/cookie banner)
  function isOccludedByModal(el, rect, modal, frameDoc) {
    if (!modal || frameDoc !== document) return false;
    if (modal.contains(el)) return false;
    const cx = rect.left + rect.width / 2, cy = rect.top + rect.height / 2;
    if (cx < 0 || cy < 0 || cx >= innerWidth || cy >= innerHeight) return true;
    const topEl = document.elementFromPoint(cx, cy);
    if (!topEl) return false;
    return modal.contains(topEl) && !el.contains(topEl) && !topEl.contains(el);
  }

  // Scrollable containers summary
  function getScrollSummary() {
    const docEl = document.scrollingElement || document.documentElement;
    const pageScroll = {
      y: Math.round(window.scrollY),
      maxY: Math.max(0, Math.round((docEl?.scrollHeight || innerHeight) - innerHeight)),
      vh: innerHeight
    };
    const regions = [];
    for (const el of document.querySelectorAll('div,ul,ol,main,section,aside,nav,[role="listbox"],[role="grid"],[role="tree"]')) {
      if (regions.length >= 4) break;
      if (el.scrollHeight > el.clientHeight + 50 && el.clientHeight >= 120) {
        const cs = getComputedStyle(el);
        if (/auto|scroll/.test(cs.overflowY) && isVisible(el)) {
          const label = trim(el.getAttribute('aria-label') || el.getAttribute('data-testid') || el.tagName.toLowerCase(), 40);
          regions.push({ label, top: Math.round(el.scrollTop), max: Math.round(el.scrollHeight - el.clientHeight) });
        }
      }
    }
    return { page: pageScroll, regions };
  }

  // Unified Snapshot (serves both Guide mode `snapshot` and Autonomous Agent `agentSnapshot`)
  if (op === 'snapshot' || op === 'agentSnapshot') {
    const guideMode = op === 'snapshot';
    const maxElements = guideMode ? 140 : (arg.maxElements || 160);
    const activeModal = detectActiveModal();
    const rawCandidates = collectCandidates(document);
    const scored = [];
    const seenNodes = new Set();

    for (const { el, frameOffset, frameDoc } of rawCandidates) {
      if (seenNodes.has(el)) continue;
      seenNodes.add(el);
      if (!el.isConnected || el.disabled || el.matches?.(':disabled,[aria-disabled="true"]')) continue;
      if (guideMode && el.matches?.('[readonly]')) continue;
      if (!isVisible(el)) continue;

      const rawRect = el.getBoundingClientRect();
      const r = {
        left: rawRect.left + frameOffset.x,
        top: rawRect.top + frameOffset.y,
        right: rawRect.right + frameOffset.x,
        bottom: rawRect.bottom + frameOffset.y,
        width: rawRect.width,
        height: rawRect.height
      };
      if (r.width < 3 || r.height < 3) continue;
      if (r.bottom < -innerHeight * 0.5 || r.top > innerHeight * 2.8) continue;
      // Skip giant virtualized list wrappers so individual rows are indexed instead
      if (r.height > innerHeight * 1.4 && el.querySelector?.('[role="gridcell"],[role="listitem"],[role="row"],a[href],button')) continue;
      // Skip generic container rows if they merely wrap a single button/link with identical text
      if (/^(div|li|tr|span)$/i.test(el.tagName) && !el.getAttribute('role') && !el.onclick && el.querySelector?.('a[href],button,input,select')) continue;

      const name = computeLabel(el);
      const secret = isSecret(el, name);
      if (guideMode && secret) continue;

      const actions = capabilitiesOf(el, guideMode);
      if (!actions.length) continue;
      if (!name && !['input', 'textarea', 'select'].includes(el.tagName.toLowerCase()) && !el.getAttribute('aria-expanded')) continue;

      const occluded = isOccludedByModal(el, r, activeModal, frameDoc);
      if (guideMode && occluded) continue;

      const inViewport = r.bottom > 0 && r.top < innerHeight && r.right > 0 && r.left < innerWidth;
      const inModal = activeModal ? activeModal.contains(el) : false;
      const priority = (inModal ? 1000 : 0) + (occluded ? -600 : 0) + (inViewport ? 300 : 0) - Math.max(0, Math.round(r.top / 20));
      scored.push({ el, r, name: name || el.tagName.toLowerCase(), secret, actions, inViewport, inModal, occluded, priority });
    }

    // Sort so modal controls & in-viewport controls always survive truncation, then restore top-to-bottom reading order
    scored.sort((a, b) => b.priority - a.priority);
    const selected = scored.slice(0, maxElements).sort((a, b) => (a.r.top - b.r.top) || (a.r.left - b.r.left));

    const token = crypto.randomUUID ? crypto.randomUUID() : Array.from(crypto.getRandomValues(new Uint32Array(4))).join('-');
    const refMap = new Map();
    const elements = [];
    const els = [];

    for (const item of selected) {
      const { el, r, secret, actions, inModal, occluded, inViewport } = item;
      let label = item.name;
      const id = (guideMode ? elements.length : els.length) + 1;
      const tag = el.tagName.toLowerCase();
      const ty = (el.type || '').toLowerCase();
      const role = el.getAttribute('role') || undefined;
      const testid = el.getAttribute('data-testid') || el.getAttribute('data-test') || el.getAttribute('data-qa') || undefined;
      const expanded = el.getAttribute('aria-expanded') ?? (tag === 'summary' && el.parentElement?.tagName === 'DETAILS' ? String(el.parentElement.open) : null);
      const isChk = (tag === 'input' && (ty === 'checkbox' || ty === 'radio')) || role === 'checkbox' || role === 'switch' || role === 'radio';
      const checked = isChk ? (el.checked ?? el.getAttribute('aria-checked') === 'true') : undefined;

      if (!guideMode && tag === 'select') {
        const cur = [...(el.selectedOptions || [])].map(o => trim(o.text, 60)).filter(Boolean).join(', ');
        if (cur) label = `${label} = “${cur}”`.trim();
      }
      let currentVal;
      if (!guideMode && !secret && (tag === 'input' || tag === 'textarea') && !isChk && !['button', 'submit', 'reset'].includes(ty) && el.value) {
        currentVal = trim(el.value, 60);
      }

      if (guideMode) {
        const entry = { id, label, tag, actions: actions.filter(a => ['click', 'type', 'select'].includes(a)) };
        if (tag === 'a' && el.href) entry.link = publicUrl(el.href, false);
        if (entry.actions.includes('select') && tag === 'select') entry.options = optionsFor(el).map(o => trim(o.label, 120));
        if (entry.actions.length) {
          refMap.set(id, { el, signature: signatureOf(el, label, entry.actions) });
          elements.push(entry);
        }
      } else {
        refMap.set(id, { el });
        els.push({
          id,
          tag,
          type: ty || undefined,
          testid,
          role,
          label,
          value: currentVal,
          checked,
          expanded,
          haspopup: el.getAttribute('aria-haspopup') || undefined,
          href: tag === 'a' && el.href ? publicUrl(el.href, true).slice(0, 140) : undefined,
          targetBlank: tag === 'a' && el.getAttribute('target') === '_blank' ? true : undefined,
          secret: secret || undefined,
          inModal: inModal || undefined,
          occluded: occluded || undefined,
          offscreen: !inViewport || undefined,
          options: tag === 'select' ? optionsFor(el).slice(0, 20).map(o => trim(o.label || o.text, 60)) : undefined
        });
      }
    }

    if (guideMode) {
      globalThis.__odysseusReview = { token, location: location.href, refs: refMap };
      return { ...meta, ...readStructuredText(7500, null, true), elements, token };
    }

    globalThis.__odyRefs = { url: location.href, at: Date.now(), map: refMap };
    const textCapture = readStructuredText(6500, null, true);
    const modalTitle = activeModal ? trim(activeModal.getAttribute('aria-label') || activeModal.querySelector('h1,h2,h3,[class*="title" i]')?.innerText || 'Active dialog/modal', 100) : null;
    const alerts = [...document.querySelectorAll('[role="alert"],[aria-live="assertive"],.error-message,[class*="error" i]:not(script):not(style)')]
      .filter(e => isVisible(e) && e.getBoundingClientRect().height < 120)
      .map(e => trim(e.innerText, 140))
      .filter(t => t.length >= 3 && t.length <= 140)
      .slice(0, 3);

    return {
      url: meta.stateUrl || meta.url,
      publicUrl: meta.url,
      title: meta.title,
      text: textCapture.text,
      clipped: textCapture.clipped,
      modal: modalTitle,
      alerts: [...new Set(alerts)],
      scroll: getScrollSummary(),
      els
    };
  }

  // Synthetic realistic pointer & mouse interaction sequence (fixes Radix/MUI/React Aria)
  function dispatchRealisticClick(target, clientX, clientY) {
    const r = target.getBoundingClientRect();
    const x = clientX ?? (r.left + r.width / 2);
    const y = clientY ?? (r.top + r.height / 2);
    const opts = { bubbles: true, cancelable: true, composed: true, view: target.ownerDocument?.defaultView || window, clientX: x, clientY: y, button: 0, buttons: 1 };
    target.dispatchEvent(new PointerEvent('pointerover', { ...opts, buttons: 0 }));
    target.dispatchEvent(new MouseEvent('mouseover', { ...opts, buttons: 0 }));
    target.dispatchEvent(new PointerEvent('pointerdown', opts));
    target.dispatchEvent(new MouseEvent('mousedown', opts));
    if (typeof target.focus === 'function') { try { target.focus({ preventScroll: true }); } catch {} }
    target.dispatchEvent(new PointerEvent('pointerup', { ...opts, buttons: 0 }));
    target.dispatchEvent(new MouseEvent('mouseup', { ...opts, buttons: 0 }));
    target.click();
  }

  // Realistic typing for React controlled inputs AND Lexical/ProseMirror/Slate contenteditable
  function setEditableText(el, text, clearFirst = true) {
    el.focus();
    if (el.isContentEditable || el.getAttribute('contenteditable') === 'true' || el.getAttribute('contenteditable') === '') {
      const doc = el.ownerDocument || document;
      const sel = doc.getSelection();
      if (sel) {
        const range = doc.createRange();
        range.selectNodeContents(el);
        if (!clearFirst) range.collapse(false);
        sel.removeAllRanges();
        sel.addRange(range);
      }
      el.dispatchEvent(new InputEvent('beforeinput', { bubbles: true, cancelable: true, composed: true, inputType: clearFirst ? 'insertReplacementText' : 'insertText', data: text }));
      let inserted = false;
      try { inserted = doc.execCommand('insertText', false, text); } catch {}
      if (!inserted) {
        if (clearFirst) el.textContent = text;
        else el.textContent = (el.textContent || '') + text;
        el.dispatchEvent(new InputEvent('input', { bubbles: true, composed: true, inputType: 'insertText', data: text }));
      }
      el.dispatchEvent(new Event('change', { bubbles: true }));
      return;
    }
    const tag = el.tagName.toLowerCase();
    const proto = tag === 'textarea' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
    const nextVal = clearFirst ? text : (el.value || '') + text;
    if (setter) setter.call(el, nextVal);
    else el.value = nextVal;
    el.dispatchEvent(new InputEvent('input', { bubbles: true, composed: true, inputType: 'insertText', data: text }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }

  // Guide Mode review/apply compatibility
  if (op === 'inspect' || op === 'show' || op === 'apply') {
    if (op === 'apply' && document.visibilityState !== 'visible') return { error: 'guideTab' };
    const state = globalThis.__odysseusReview;
    if (!state || state.token !== arg.token || state.location !== location.href) return { error: 'stale' };
    const a = arg.action, ref = state.refs.get(a.id), el = ref?.el;
    if (['click', 'select', 'type'].includes(a.a)) {
      if (!el?.isConnected || !isVisible(el) || isSecret(el, computeLabel(el))) return { error: 'stale' };
      const acts = capabilitiesOf(el, true).filter(x => ['click', 'type', 'select'].includes(x));
      if (!acts.includes(a.a) || ref.signature !== signatureOf(el, computeLabel(el), acts)) return { error: 'stale' };
    }
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
      case 'click': dispatchRealisticClick(el); break;
      case 'type': {
        if (typeof a.text !== 'string' || a.text.length > 2000) return { error: 'unsupported' };
        setEditableText(el, a.text, true); break;
      }
      case 'select': {
        const choices = optionsFor(el).filter(o => trim(o.label, 120) === a.value);
        if (choices.length !== 1) return { error: 'stale' };
        el.selectedIndex = choices[0].index;
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true })); break;
      }
      default: return { error: 'unsupported' };
    }
    return { ok: true };
  }

  // Coordinate probing & clicking
  if (op === 'probeXY' || op === 'clickXY') {
    const x = (a => a.x / 1000 * innerWidth)(arg), y = (a => a.y / 1000 * innerHeight)(arg);
    const e = document.elementFromPoint(x, y);
    if (!e) return { ok: false, msg: 'nothing at that point' };
    if (e.closest('#__ody_banner,#__ody_som_layer')) return { ok: false, msg: 'cannot click agent banner' };
    if (isSecret(e, computeLabel(e))) return { ok: false, msg: 'refused: secret field' };
    const desc = 'clicked ' + e.tagName.toLowerCase() + ' “' + trim(computeLabel(e) || e.innerText || '', 60) + '”';
    if (op === 'probeXY') return { ok: true, px: x, py: y, data: desc };
    dispatchRealisticClick(e, x, y);
    return { ok: true, data: desc };
  }

  // Autonomous Agent Actions (`act`)
  if (op === 'act') {
    const a = arg;

    if (a.a === 'key') {
      const t = document.activeElement || document.body;
      const rawKey = String(a.key || 'Enter');
      const parts = rawKey.split('+');
      const mainKey = parts.pop();
      const mods = new Set(parts.map(p => p.toLowerCase()));
      const evInit = {
        key: mainKey,
        bubbles: true,
        cancelable: true,
        composed: true,
        ctrlKey: mods.has('control') || mods.has('ctrl'),
        metaKey: mods.has('meta') || mods.has('cmd') || mods.has('command'),
        altKey: mods.has('alt') || mods.has('option'),
        shiftKey: mods.has('shift'),
        keyCode: mainKey === 'Enter' ? 13 : mainKey === 'Escape' ? 27 : mainKey === 'Tab' ? 9 : mainKey === 'Backspace' ? 8 : 0
      };
      t.dispatchEvent(new KeyboardEvent('keydown', evInit));
      t.dispatchEvent(new KeyboardEvent('keyup', evInit));
      if (mainKey === 'Enter' && t.form?.requestSubmit && t.tagName === 'INPUT') {
        try { t.form.requestSubmit(); } catch {}
      }
      return { ok: true };
    }

    if (a.a === 'extract') {
      const full = readStructuredText(15000, null, true);
      return { ok: true, data: full.text };
    }

    if (a.a === 'scroll') {
      const d = a.dir === 'up' ? -1 : 1;
      // If an element id is supplied or a modal/scrollable list container is prominent, scroll it
      const refEl = a.id ? globalThis.__odyRefs?.map?.get(a.id)?.el : null;
      if (refEl) {
        let sc = refEl;
        while (sc && sc !== document.body && !(sc.scrollHeight > sc.clientHeight + 20 && /auto|scroll/.test(getComputedStyle(sc).overflowY))) {
          sc = sc.parentElement;
        }
        if (sc && sc !== document.body) {
          const prev = sc.scrollTop;
          sc.scrollBy({ top: d * sc.clientHeight * 0.8, behavior: 'instant' });
          return { ok: true, msg: 'scrolled target container' + (sc.scrollTop === prev ? ' (at boundary)' : '') };
        }
      }
      const activeModal = detectActiveModal();
      const searchRoot = activeModal || document;
      let box = null, bestScore = 0;
      for (const el of searchRoot.querySelectorAll('div,ul,ol,section,main,aside,[role="listbox"],[role="grid"]')) {
        if (el.scrollHeight > el.clientHeight + 40 && el.clientHeight > 140 && isVisible(el) && /auto|scroll/.test(getComputedStyle(el).overflowY)) {
          const items = el.querySelectorAll('[role="gridcell"],[role="row"],[role="listitem"],[role="option"],li,article,tr').length;
          const score = items * 10 + Math.min(el.clientHeight, 600);
          if (score > bestScore) { bestScore = score; box = el; }
        }
      }
      if (box && bestScore >= 260) {
        const b = box.scrollTop;
        box.scrollBy({ top: d * box.clientHeight * 0.8, behavior: 'instant' });
        if (box.scrollTop !== b) return { ok: true, msg: 'scrolled container' };
      }
      const prevY = window.scrollY;
      scrollBy({ top: d * innerHeight * 0.82, behavior: 'instant' });
      return { ok: true, msg: window.scrollY === prevY ? 'already at scroll boundary' : `scrolled page to y=${Math.round(window.scrollY)}` };
    }

    // Universal semantic & visual region inspector (generalizes rowicons while keeping backward compatibility)
    if (a.a === 'inspect_region' || a.a === 'rowicons') {
      const want = String(a.label || '').trim().toLowerCase();
      const own = (el) => [...el.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join(' ').replace(/\s+/g, ' ').trim().toLowerCase();
      let labels = [...document.querySelectorAll('body *')].filter(el => own(el) === want && isVisible(el));
      if (!labels.length) {
        labels = [...document.querySelectorAll('body *')].filter(el => {
          const o = own(el);
          return o && o.includes(want) && o.length <= want.length + 40 && isVisible(el);
        });
      }
      if (!labels.length) return { ok: false, msg: `no visible region matching "${a.label}" (try scrolling or extract)` };

      const parse = (c) => { const m = (c || '').match(/rgba?\(([\d.]+)[, ]+([\d.]+)[, ]+([\d.]+)(?:[,/ ]+([\d.]+))?/); return m && (m[4] === undefined || +m[4] > 0.15) ? [+m[1], +m[2], +m[3]] : null; };
      const cname = ([r, g, b]) => {
        const mx = Math.max(r, g, b), mn = Math.min(r, g, b), l = (mx + mn) / 510, sat = mx === mn ? 0 : (mx - mn) / (255 - Math.abs(mx + mn - 255));
        if (sat < 0.22 || mx - mn < 30) return l > 0.9 ? 'white' : l < 0.12 ? 'black' : 'grey';
        let h = mx === r ? ((g - b) / (mx - mn)) % 6 : mx === g ? (b - r) / (mx - mn) + 2 : (r - g) / (mx - mn) + 4; h = (h * 60 + 360) % 360;
        return h < 15 || h >= 345 ? 'red' : h < 45 ? 'orange' : h < 70 ? 'yellow' : h < 170 ? 'green' : h < 200 ? 'teal' : h < 260 ? 'blue' : 'purple';
      };
      const score = (c) => { if (!c) return -1; const n = cname(c); return n === 'white' || n === 'black' ? 0 : n === 'grey' ? 1 : 2; };
      const colourOf = (el, stop) => {
        let best = null, bs = -1;
        const consider = (c) => { const sc = score(c); if (sc > bs) { bs = sc; best = c; } };
        const nodes = [el, ...el.querySelectorAll('*')].slice(0, 40);
        let p = el.parentElement;
        for (let i = 0; i < 2 && p && p !== stop && p.getBoundingClientRect().width < 64; i++, p = p.parentElement) nodes.push(p);
        for (const n of nodes) {
          const cs = getComputedStyle(n);
          for (const k of ['fill', 'stroke', 'backgroundColor', 'borderTopColor', 'color']) {
            if ((k === 'fill' || k === 'stroke') && !(n instanceof SVGElement)) continue;
            if (k === 'borderTopColor' && parseFloat(cs.borderTopWidth) < 1) continue;
            if (k === 'color' && !(n instanceof SVGElement) && !n.querySelector('svg')) continue;
            consider(parse(cs[k]));
          }
        }
        return best ? cname(best) + ' rgb(' + best.join(',') + ')' : 'neutral';
      };

      const out = [];
      labels.slice(0, 3).forEach((lab, li) => {
        const lr = lab.getBoundingClientRect(), cy = lr.top + lr.height / 2;
        const grab = (r) => {
          const arr = [...r.querySelectorAll('svg,img,button,[role="status"],[class*="badge" i],[class*="chip" i],[class*="pill" i],[class*="icon" i],[class*="circle" i],[class*="status" i]')].filter(x => isVisible(x) && !x.contains(lab) && x.getBoundingClientRect().width < 120 && !(x.parentElement && x.parentElement.closest('svg')));
          return arr.filter(x => !arr.some(y => y !== x && y.contains(x)));
        };
        const isHead = (x) => { const r = x.getBoundingClientRect(); return Math.abs(r.top + r.height / 2 - cy) < 16 && r.left > lr.left; };
        const isBelow = (x) => { const r = x.getBoundingClientRect(); return r.top >= lr.bottom - 2 && r.top < lr.bottom + 110; };
        let container = lab, head = [], below = [];
        for (let i = 0; i < 8 && container.parentElement; i++) {
          container = container.parentElement;
          if (container.getBoundingClientRect().height > 300) break;
          const all = grab(container);
          if (all.filter(isHead).length > head.length) head = all.filter(isHead);
          const b = all.filter(isBelow);
          if (b.length >= 1) {
            const t0 = Math.min(...b.map(x => x.getBoundingClientRect().top));
            below = b.filter(x => x.getBoundingClientRect().top < t0 + 16);
          }
          if (head.length >= 2 && below.length >= 2) break;
        }
        const byX = (p, q) => p.getBoundingClientRect().left - q.getBoundingClientRect().left;
        head.sort(byX); below.sort(byX);
        const fmt = (arr) => arr.slice(0, 12).map((x, i) => {
          const r = x.getBoundingClientRect();
          const t = trim(x.getAttribute('aria-label') || x.getAttribute('title') || x.querySelector('title')?.textContent || x.getAttribute('alt') || x.innerText || '', 50);
          return `${i + 1}. ${colourOf(x, container)}${t ? ` "${t}"` : ''} at x=${Math.round((r.left + r.width / 2) / innerWidth * 1000)},y=${Math.round((r.top + r.height / 2) / innerHeight * 1000)}`;
        });
        const regionText = trim(container.innerText || '', 300);
        out.push(
          `Region ${li + 1} "${trim(lab.textContent, 60)}":\n` +
          `Text: ${regionText}\n` +
          `Inline/Header controls: ${head.length ? '\n' + fmt(head).join('\n') : 'none'}\n` +
          `Sub-row badges/icons: ${below.length ? '\n' + fmt(below).join('\n') : 'none'}`
        );
      });
      return { ok: true, data: out.join('\n\n') };
    }

    // Element-targeted actions: resolve from isolated WeakMap/Map
    const entry = globalThis.__odyRefs?.map?.get(Number(a.id));
    const e = entry?.el;
    if (!e || !e.isConnected) return { ok: false, msg: 'element not found or detached; page updated' };
    const label = computeLabel(e);
    const secret = isSecret(e, label);

    e.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'instant' });

    if (a.a === 'hover') {
      const r = e.getBoundingClientRect();
      const opts = { bubbles: true, cancelable: true, composed: true, view: window, clientX: r.left + r.width / 2, clientY: r.top + r.height / 2 };
      e.dispatchEvent(new PointerEvent('pointerenter', opts));
      e.dispatchEvent(new MouseEvent('mouseenter', opts));
      e.dispatchEvent(new PointerEvent('pointerover', opts));
      e.dispatchEvent(new MouseEvent('mouseover', opts));
      return { ok: true };
    }

    if (a.a === 'click') {
      const target = e.getAttribute('role') === 'gridcell' && e.firstElementChild
        ? e.firstElementChild
        : !e.onclick && /^(div|li|tr|td|span|section|article|ul)$/i.test(e.tagName)
          ? ([...e.querySelectorAll('a[href],button,[role="button"],[onclick]')].find(isVisible) || e)
          : e;
      dispatchRealisticClick(target);
      return { ok: true };
    }

    if (a.a === 'clear') {
      if (secret) return { ok: false, msg: 'refused: secret field' };
      setEditableText(e, '', true);
      return { ok: true };
    }

    if (a.a === 'type') {
      if (secret) return { ok: false, msg: 'refused: secret field' };
      setEditableText(e, String(a.text ?? ''), a.append !== true);
      if (a.submit) {
        if (e.form?.requestSubmit) { try { e.form.requestSubmit(); } catch { e.form.submit(); } }
        else {
          const kInit = { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true, cancelable: true, composed: true };
          e.dispatchEvent(new KeyboardEvent('keydown', kInit));
          e.dispatchEvent(new KeyboardEvent('keyup', kInit));
        }
      }
      return { ok: true };
    }

    if (a.a === 'select') {
      const want = String(a.value || '').trim().toLowerCase();
      // Native <select>
      if (e.tagName === 'SELECT') {
        const opts = [...(e.options || [])];
        const match = opts.find(x => x.value.toLowerCase() === want || x.text.trim().toLowerCase() === want)
          || opts.find(x => x.text.trim().toLowerCase().includes(want));
        if (!match) return { ok: false, msg: `option "${a.value}" not found in <select>` };
        e.value = match.value;
        e.dispatchEvent(new Event('input', { bubbles: true }));
        e.dispatchEvent(new Event('change', { bubbles: true }));
        return { ok: true };
      }
      // Custom ARIA combobox / listbox trigger (Proposal 4)
      dispatchRealisticClick(e);
      await new Promise(r => setTimeout(r, 180));
      const optionEls = [...document.querySelectorAll('[role="option"],[role="menuitem"],[role="menuitemradio"],li[data-value]')].filter(isVisible);
      const bestOpt = optionEls.find(o => trim(o.innerText || o.getAttribute('aria-label'), 120).toLowerCase() === want)
        || optionEls.find(o => trim(o.innerText || o.getAttribute('aria-label'), 120).toLowerCase().includes(want));
      if (!bestOpt) return { ok: false, msg: `opened dropdown, but option "${a.value}" was not found among visible options` };
      bestOpt.scrollIntoView({ block: 'nearest', behavior: 'instant' });
      dispatchRealisticClick(bestOpt);
      return { ok: true };
    }

    return { ok: false, msg: 'unknown action: ' + a.a };
  }

  return { error: 'unsupported', ok: false, msg: 'unsupported op: ' + op };
}
