const inv=(c,a)=>window.__TAURI_INTERNALS__?window.__TAURI_INTERNALS__.invoke(c,a||{}):Promise.reject('no-tauri');
let LANG=localStorage.getItem('lang')||((navigator.language||'en').toLowerCase().startsWith('pt')?'pt':'en');
const T={};const tr=k=>(T[LANG]&&T[LANG][k])||(T.en&&T.en[k])||k;
function setLang(l){LANG=l;localStorage.setItem('lang',l);document.documentElement.lang=l;if(window.render)render()}
function langBar(){return `<div class="lang"><button class="${LANG=='pt'?'on':''}" onclick="setLang('pt')">PT</button><button class="${LANG=='en'?'on':''}" onclick="setLang('en')">EN</button></div>`}
function esc(s){return String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
document.addEventListener('click',e=>{const a=e.target.closest('[data-href]');if(a){e.preventDefault();inv('open_link',{url:a.dataset.href})}});
