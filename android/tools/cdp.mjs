// Tiny CDP helper: node cdp.mjs '<js expression>' [waitMs]  -> logs document network events + eval result
const [,, expr, wait='8000'] = process.argv;
const list = await (await fetch('http://localhost:9222/json')).json();
const ws = new WebSocket(list.find(p => p.type === 'page').webSocketDebuggerUrl);
let id = 0; const pending = {};
const send = (method, params={}) => new Promise(r => { const i=++id; pending[i]=r; ws.send(JSON.stringify({id:i,method,params})); });
ws.onmessage = ev => { const m = JSON.parse(ev.data);
  if (m.id && pending[m.id]) { pending[m.id](m.result); return; }
  if (m.method === 'Network.responseReceived' && ['Document','Fetch','XHR'].includes(m.params.type) ) console.log('RESP', m.params.type, m.params.response.status, m.params.response.url.slice(0,120));
  if (m.method === 'Network.loadingFailed') console.log('FAIL', m.params.type, m.params.errorText, m.params.blockedReason||'');
  if (m.method === 'Runtime.consoleAPICalled') console.log('CONSOLE', m.params.args.map(a=>a.value).join(' ').slice(0,200));
  if (m.method === 'Runtime.exceptionThrown') console.log('EXC', m.params.exceptionDetails.exception?.description?.slice(0,200));
};
await new Promise(r => ws.onopen = r);
await send('Network.enable'); await send('Runtime.enable');
const res = await send('Runtime.evaluate', {expression: expr, awaitPromise: true, returnByValue: true});
console.log('EVAL', JSON.stringify(res?.result?.value ?? res?.result?.description ?? res).slice(0,600));
await new Promise(r => setTimeout(r, +wait));
const loc = await send('Runtime.evaluate', {expression: 'location.href', returnByValue: true});
console.log('NOW', loc?.result?.value); process.exit(0);
