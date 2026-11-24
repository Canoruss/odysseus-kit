const MIN_CAPTURE = 6500;
const PASSAGE_SIZE = 750;
const EXCERPT_BUDGET = 5200;
const GAP = '\n\n[…]\n\n';
const stopWords = new Set(`
about above after also and any answer are attached before being both can could compare comparison describe details differ
does each explain find from give have here how into like list main more most much only page pages
please provide report same show some source sources summarize summary tabs tell text than that their them then there
these they this through title together under using want was supplied finding findings agree clear points content few for
get had has its preface the too use were what when where which while who why with would you
your cite links capture captures question abaixo acima agora ainda algumas alguns ambos antes aqui assim compara comparar compare
comparam como com conclusao conclusoes contra cada das aos dos dela dele deles delas depois desta deste diferente diferem
entre esses esta este estes estas explicar explica fornece geral geralmente indica ja mais mas mesmo menos mensagem mostra
muitas muitos nome nosso nossa onde pelo pela pelos pelas pode posso porque quais qual quando quanto quero resumo
resume resumir separador separadores sobre sua suas seu seus sao tambem tem texto titulo titulos todas todo todos uma
umas uns voce fonte fontes pagina paginas anexado anexada anexados anexadas concordam pontos claros
`.trim().split(/\s+/));
const broad = /\b(?:entire|whole|comprehensive|overview|everything|every section|full (?:page|text|capture|document)|main ideas|key points|all (?:pages|sections|points|topics)|(?:toda a|todas as|todo o|todos os) (?:pagina|paginas|seccoes|secoes|texto|documento|pontos|topicos)|visao geral|resumo geral|principais (?:pontos|ideias))\b/;
const plain = text => text.normalize('NFKD').replace(/\p{M}/gu, '').toLowerCase();
const words = text => text.match(/[\p{L}\p{N}]+/gu) || [];

export function canFocus({ kind, text }) {
  return (kind === 'page' || kind === 'compare') && text?.length >= MIN_CAPTURE;
}

export function focusTerms(question) {
  const normalized = plain(question);
  if (broad.test(normalized)) return [];
  return [...new Set(words(normalized).filter(word => word.length >= 3 && word.length <= 56 && !stopWords.has(word)))].slice(0, 24);
}

function splitPassages(text) {
  const blocks = [];
  for (let start = 0; start < text.length;) {
    let end = Math.min(text.length, start + PASSAGE_SIZE);
    if (end < text.length) {
      const line = text.lastIndexOf('\n', end - 1) + 1;
      const space = text.lastIndexOf(' ', end - 1) + 1;
      if (line > start + PASSAGE_SIZE / 2) end = line;
      else if (space > start + PASSAGE_SIZE / 2) end = space;
      else if (/[\uD800-\uDBFF]/.test(text[end - 1])) end--;
    }
    blocks.push({ start, end }); start = end;
  }
  return blocks;
}

// Extract verbatim passages in page order, with an explicit gap between non-adjacent passages.
export function relevantPassages(text, terms) {
  if (!terms.length || text.length < MIN_CAPTURE) return text;
  const query = new Set(terms), frequency = new Map();
  const blocks = splitPassages(text);
  for (const block of blocks) {
    const matches = words(plain(text.slice(block.start, block.end))).filter(word => query.has(word));
    block.matches = [...new Set(matches)];
    for (const term of block.matches) frequency.set(term, (frequency.get(term) || 0) + 1);
  }
  if (frequency.size < Math.min(2, query.size)) return text;
  const hits = blocks.map((block, index) => ({ index, score: block.matches.reduce((score, term) => score + 1 + 1 / frequency.get(term), 0) }))
    .filter(hit => hit.score > 0).sort((a, b) => b.score - a.score || a.index - b.index);
  // Widespread matches suggest the entire capture is relevant.
  if (hits.length > blocks.length / 2) return text;

  const chosen = new Set(), covered = new Set(); let used = 0;
  function include(index) {
    const block = blocks[index];
    if (!block || chosen.has(index)) return;
    const cost = block.end - block.start + GAP.length;
    if (used + cost + GAP.length > EXCERPT_BUDGET) return;
    used += cost; chosen.add(index);
    for (const term of block.matches) covered.add(term);
  }
  for (const { index } of hits) include(index);
  if (covered.size !== frequency.size) return text;
  include(0);
  for (const { index } of hits) { include(index - 1); include(index + 1); }
  const ordered = [...chosen].sort((a, b) => a - b);
  let excerpt = '', previous = -1;
  for (const index of ordered) {
    const block = blocks[index];
    if (index !== previous + 1) excerpt += GAP;
    excerpt += text.slice(block.start, block.end);
    previous = index;
  }
  if (previous !== blocks.length - 1) excerpt += GAP;
  return excerpt.trim();
}
