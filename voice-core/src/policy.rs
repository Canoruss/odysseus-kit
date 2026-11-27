//! Avaliador de intenção e risco do Agente Odysseus (antes AgentPolicy.java + AgentSafety.java).
use jni::objects::{JClass, JString};
use jni::sys::{jboolean, jint, jstring};
use jni::JNIEnv;
use regex::Regex;
use std::sync::OnceLock;
use unicode_normalization::UnicodeNormalization;

#[derive(Default, Clone)]
pub struct Node {
    pub id: i32,
    pub text: String,
    pub desc: String,
    pub view_id: String,
    pub cx: i32,
    pub cy: i32,
    pub editable: bool,
    pub password: bool,
}

#[derive(Default)]
pub struct Input<'a> {
    pub self_pkg: &'a str,
    pub goal: &'a str,
    pub action: &'a str,
    pub fg_pkg: &'a str,
    pub fg_class: &'a str,
    pub target_pkg: &'a str,
    pub node: Option<Node>,
    pub x: i32,
    pub y: i32,
    pub text_or_url: &'a str,
    pub submit: bool,
    pub model_critical: bool,
    pub model_reason: &'a str,
    pub confirm_critical: bool,
    pub confirm_all_steps: bool,
}

#[derive(Debug, PartialEq)]
pub struct Decision {
    pub verdict: &'static str,
    pub category: &'static str,
    pub reason: String,
    pub signature: String,
    pub critical_pkg: String,
}

fn d(verdict: &'static str, category: &'static str, reason: String, signature: &str, pkg: &str) -> Decision {
    Decision { verdict, category, reason, signature: signature.to_string(), critical_pkg: pkg.to_string() }
}

const PAYMENT_PACKAGES: &[&str] = &[
    "pt.sibs.android.mbway", "wit.android.bcpbankingapp", "cgd.pt.caixadirecta", "pt.novobanco",
    "pt.santander", "pt.activo", "pt.bancomontepio", "pt.moey.app", "pt.creditoagricola",
    "com.bankinter.launcher", "com.revolut.revolut", "com.wise.android", "de.number26.android",
    "com.paypal.android.p2pmobile", "com.google.android.apps.walletnfcrel",
    "com.google.android.apps.nbu.paisa.user", "com.binance.dev", "com.coinbase.android",
    "com.kraken.trade", "co.mona.android", "com.klarna.android",
];
const PASSWORD_MANAGER_PACKAGES: &[&str] = &[
    "com.x8bit.bitwarden", "com.onepassword.android", "com.agilebits.onepassword",
    "com.kunzisoft.keepass", "keepass2android", "proton.android.pass", "com.dashlane",
    "com.lastpass.lpandroid", "com.nordpass.android.app.password.manager", "io.enpass.app",
    "com.siber.roboform", "com.samsung.android.samsungpass", "com.samsung.android.samsungpassautofill",
    "com.google.android.apps.authenticator2", "com.azure.authenticator", "com.authy.authy",
    "com.twofasapp", "com.beemdevelopment.aegis", "org.shadowice.flocke.andotp",
    "com.yubico.yubioath", "com.android.credentialmanager", "com.google.android.gms.credential",
];
const MESSAGING_AND_SOCIAL_PACKAGES: &[&str] = &[
    "com.whatsapp", "com.whatsapp.w4b", "org.telegram.messenger", "org.thoughtcrime.securesms",
    "com.google.android.apps.messaging", "com.android.mms", "com.samsung.android.messaging",
    "com.google.android.gm", "com.microsoft.office.outlook", "ch.protonmail.android",
    "com.yahoo.mobile.client.android.mail", "com.instagram.android", "com.facebook.katana",
    "com.facebook.orca", "com.facebook.lite", "com.twitter.android", "com.zhiliaoapp.musically",
    "com.linkedin.android", "com.slack", "com.discord", "com.reddit.frontpage",
    "com.snapchat.android", "com.threads.android", "xyz.blueskyweb.app",
];
const SYSTEM_CRITICAL_PACKAGES: &[&str] = &[
    "com.android.settings", "com.android.permissioncontroller", "com.google.android.permissioncontroller",
    "com.android.packageinstaller", "com.google.android.packageinstaller", "com.miui.securitycenter",
];
const PAYMENT_DOMAINS_OR_PATHS: &[&str] = &[
    "mbway.", "caixadirecta.", "millenniumbcp.", "novobanco.", "santander.", "activobank.",
    "bancomontepio.", "paypal.com", "revolut.com", "wise.com", "binance.com", "coinbase.com",
    "checkout.stripe.com", "/checkout", "/payment", "/pagamento",
];
const PASSWORD_MANAGER_KEYWORDS: &[&str] = &[
    "bitwarden", "1password", "keepass", "proton pass", "protonpass", "dashlane",
    "lastpass", "nordpass", "enpass", "roboform", "samsung pass", "authenticator",
    "authy", "aegis", "gestor de palavras-passe", "gestor de senhas", "password manager",
    "vault.bitwarden", "my.1password",
];
const PAYMENT_WORDS: &[&str] = &[
    "pagar", "pagamento", "comprar", "comprar agora", "finalizar compra", "encomendar",
    "transferir", "confirmar transferencia", "confirmar pagamento", "autorizar pagamento",
    "levantar dinheiro", "enviar dinheiro", "mb way",
    "pay", "pay now", "checkout", "buy now", "place order", "send money", "authorize payment",
];
const SEND_PUBLISH_WORDS: &[&str] = &[
    "enviar", "enviar mensagem", "enviar email", "publicar", "partilhar agora",
    "submeter", "fazer chamada", "ligar agora",
    "send", "send message", "publish", "post", "tweet", "submit", "place call",
];
const DELETE_WORDS: &[&str] = &[
    "apagar", "eliminar", "excluir", "mover para o lixo", "esvaziar lixo",
    "desinstalar", "formatar", "repor dados", "limpar dados", "limpar armazenamento", "limpar tudo",
    "delete", "remove", "move to trash", "empty trash", "uninstall", "erase",
    "factory reset", "clear data", "clear storage",
];
const PAYMENT_VIEW_IDS: &[&str] = &["btn_pay", "pay_button", "checkout_button", "buy_button", "place_order", "confirm_payment"];
const SEND_VIEW_IDS: &[&str] = &[
    ":id/send", "send_btn", "btn_send", "send_button", "compose_send",
    "post_button", "tweet_button", "publish_button", "call_button",
];
const DELETE_OR_SYSTEM_VIEW_IDS: &[&str] = &[
    "btn_delete", "delete_button", "action_delete", "menu_delete", "trash_button",
    "uninstall_button", "permission_allow_button", "permission_allow_foreground_only_button",
    "permission_allow_one_time_button",
];
const SEARCH_OR_URL_HINTS: &[&str] = &[
    "url_bar", "location_bar", "omnibox", "mozac_browser_toolbar", "address_bar",
    "search", "pesquisa", "pesquisar", "procurar", "buscar", "query",
    "endereco web", "escreve ou pesquisa", "o que queres ouvir", "what do you want to listen",
];
const MESSAGE_COMPOSER_HINTS: &[&str] = &[
    "escreve uma mensagem", "mensagem", "escrever email", "redigir", "responder",
    "adicionar comentario", "escreve uma resposta", "publicacao", "o que esta a acontecer",
    "write a message", "type a message", "compose", "reply", "add a comment", "what's happening",
];
const ACTION_INTENT_VERBS: &[&str] = &[
    "abre", "abrir", "vai", "ir ", "navega", "procura", "pesquisa", "toca", "poe", "por ",
    "reproduz", "ouvir", "mostra", "ve ", "ver ", "cria", "escreve", "muda", "ativa",
    "open", "go to", "launch", "play", "search", "find", "navigate", "browse", "show", "tap", "type",
];
const WEB_AND_OPEN_INTENT_TOKENS: &[&str] = &[
    "abre", "abrir", "vai", "ir ", "navega", "navegar", "visita", "acede", "entra",
    "site", "pagina", "web", "endereco", "url", "link", "browser", "navegador", "chrome",
    "pesquisa", "procura", "busca", "noticias", "ler ", "mostra",
    "open", "go to", "visit", "browse", "website", "page", "search", "look up",
];

/// Remove acentos (bloco U+0300–U+036F), passa a minúsculas e apara.
pub fn norm(s: &str) -> String {
    if s.is_empty() { return String::new(); }
    let stripped: String = s.nfd().filter(|c| !('\u{0300}'..='\u{036F}').contains(c)).collect();
    stripped.to_lowercase().trim().to_string()
}

fn safe_lower(s: &str) -> String { s.trim().to_lowercase() }

/// Corta ao número máximo de unidades UTF-16 (igual a String.length() em Java).
fn truncate(s: &str, max: usize) -> String {
    let mut units = 0;
    for (i, ch) in s.char_indices() {
        if units + ch.len_utf16() > max { return format!("{}…", &s[..i]); }
        units += ch.len_utf16();
    }
    s.to_string()
}

fn contains_any(h: &str, needles: &[&str]) -> bool { needles.iter().any(|n| h.contains(n)) }

fn matches_pkg_list(pkg: &str, list: &[&str]) -> bool {
    if pkg.is_empty() { return false; }
    let p = pkg.to_lowercase();
    list.iter().any(|item| p.contains(item))
}

pub fn is_payment_package(p: &str) -> bool { matches_pkg_list(p, PAYMENT_PACKAGES) }
pub fn is_password_manager_package(p: &str) -> bool { matches_pkg_list(p, PASSWORD_MANAGER_PACKAGES) }
pub fn is_messaging_or_social_package(p: &str) -> bool { matches_pkg_list(p, MESSAGING_AND_SOCIAL_PACKAGES) }
pub fn is_system_critical_package(p: &str) -> bool { matches_pkg_list(p, SYSTEM_CRITICAL_PACKAGES) }

pub fn is_payment_url(s: &str) -> bool {
    if s.is_empty() { return false; }
    let l = s.to_lowercase();
    contains_any(&l, PAYMENT_DOMAINS_OR_PATHS)
}

pub fn contains_password_manager_keyword(s: &str) -> bool {
    if s.is_empty() { return false; }
    contains_any(&norm(s), PASSWORD_MANAGER_KEYWORDS)
}

fn matches_word(h: &str, w: &str) -> bool {
    if w.is_empty() { return false; }
    let mut from = 0;
    while let Some(rel) = h[from..].find(w) {
        let idx = from + rel;
        let left_ok = h[..idx].chars().next_back().map_or(true, |c| !c.is_alphanumeric());
        let end = idx + w.len();
        let right_ok = h[end..].chars().next().map_or(true, |c| !c.is_alphanumeric());
        if left_ok && right_ok { return true; }
        from = idx + h[idx..].chars().next().map_or(1, |c| c.len_utf8());
        if from > h.len() { break; }
    }
    false
}

fn matches_any_word(h: &str, words: &[&str]) -> bool {
    !h.is_empty() && words.iter().any(|w| matches_word(h, w))
}

fn view_id(n: &Node) -> String { n.view_id.to_lowercase() }

fn matches_view_id(n: &Node, ids: &[&str]) -> bool {
    let vid = view_id(n);
    !vid.is_empty() && ids.iter().any(|id| vid.contains(id))
}

fn combined(n: &Node) -> String { norm(&format!("{} {}", n.text, n.desc)) }

pub fn label_of(n: Option<&Node>) -> String {
    match n {
        None => "ecrã".into(),
        Some(n) if !n.text.is_empty() => truncate(&n.text, 40),
        Some(n) if !n.desc.is_empty() => truncate(&n.desc, 40),
        Some(n) if !n.view_id.is_empty() => n.view_id.clone(),
        Some(n) => format!("#{}", n.id),
    }
}

fn is_credential_node(n: &Node) -> bool {
    if n.password { return true; }
    let c = combined(n);
    let vid = view_id(n);
    vid.contains("autofill") || vid.contains("passkey") || contains_password_manager_keyword(&c)
        || matches_any_word(&c, &["passkey", "ver palavra-passe", "copiar palavra-passe", "copy password", "reveal password"])
}

fn is_payment_node(n: &Node) -> bool { matches_view_id(n, PAYMENT_VIEW_IDS) || matches_any_word(&combined(n), PAYMENT_WORDS) }

fn is_send_or_publish_node(n: &Node) -> bool {
    !n.editable && (matches_view_id(n, SEND_VIEW_IDS) || matches_any_word(&combined(n), SEND_PUBLISH_WORDS))
}

fn is_delete_or_system_node(n: &Node) -> bool {
    !n.editable && (matches_view_id(n, DELETE_OR_SYSTEM_VIEW_IDS) || matches_any_word(&combined(n), DELETE_WORDS))
}

fn is_search_or_address_node(n: Option<&Node>) -> bool {
    let Some(n) = n else { return false };
    let vid = view_id(n);
    let c = combined(n);
    SEARCH_OR_URL_HINTS.iter().any(|h| vid.contains(h) || c.contains(h))
}

fn is_message_composer_node(n: Option<&Node>) -> bool {
    let Some(node) = n else { return false };
    if is_search_or_address_node(n) { return false; }
    let vid = view_id(node);
    if ["compose", "comment", "reply_input", "chat_input"].iter().any(|k| vid.contains(k)) { return true; }
    contains_any(&combined(node), MESSAGE_COMPOSER_HINTS)
}

/// Host de um URL absoluto (como android.net.Uri.getHost()).
fn uri_host(url: &str) -> Option<String> {
    let rest = &url[url.find("://")? + 3..];
    let authority = rest.split(['/', '?', '#']).next().unwrap_or("");
    let host_port = authority.rsplit('@').next().unwrap_or("");
    let host = if let Some(stripped) = host_port.strip_prefix('[') {
        stripped.split(']').next().unwrap_or("")
    } else {
        host_port.split(':').next().unwrap_or("")
    };
    if host.is_empty() { None } else { Some(host.to_string()) }
}

pub fn looks_like_url_or_domain(s: &str) -> bool {
    let t = s.trim().to_lowercase();
    if t.is_empty() || t.contains(' ') { return false; }
    if t.starts_with("http://") || t.starts_with("https://") || t.starts_with("www.") { return true; }
    let host = t.split('/').next().unwrap_or("");
    let Some(dot) = host.rfind('.') else { return false };
    if dot == 0 || dot + 2 >= host.len() { return false; }
    let tld = &host[dot + 1..];
    (2..=12).contains(&tld.len()) && tld.bytes().all(|b| b.is_ascii_lowercase())
}

pub fn normalize_http_url(raw: &str) -> Option<String> {
    let s = raw.trim();
    if s.is_empty() || s.contains(' ') { return None; }
    let lower = s.to_lowercase();
    if lower.starts_with("https://") || lower.starts_with("http://") {
        return uri_host(s).map(|_| s.to_string());
    }
    if s.contains(':') { return None; }
    if looks_like_url_or_domain(s) {
        let with = format!("https://{s}");
        return match uri_host(&with) { Some(h) if h.contains('.') => Some(with), _ => None };
    }
    None
}

fn looks_like_url_containing_text(g: &str) -> bool {
    static RE: OnceLock<Regex> = OnceLock::new();
    if g.contains("http://") || g.contains("https://") || g.contains("www.") { return true; }
    // Em Java, String.matches(".*…​.*") falha se houver quebras de linha.
    if g.contains(['\n', '\r', '\u{85}', '\u{2028}', '\u{2029}']) { return false; }
    RE.get_or_init(|| Regex::new(r"\b[a-z0-9-]+\.(pt|com|org|net|io|eu|gov|edu)\b").unwrap()).is_match(g)
}

fn extract_scheme(raw: &str) -> String {
    match raw.find(':') { Some(i) if i > 0 => raw[..i].trim().to_lowercase(), _ => String::new() }
}

pub fn has_clear_actionable_intent(goal: &str, act: &str, text_or_url: &str) -> bool {
    if goal.trim().is_empty() { return false; }
    let g = norm(goal);
    let passive = g.ends_with('?')
        && ["o que esta ", "o que diz ", "le o ecra", "descreve o ecra", "what is on ", "what does this say"]
            .iter().any(|p| g.starts_with(p))
        && !contains_any(&g, ACTION_INTENT_VERBS);
    if passive { return false; }
    if act == "open_url" {
        if contains_any(&g, WEB_AND_OPEN_INTENT_TOKENS) || looks_like_url_containing_text(&g) { return true; }
        let host = normalize_http_url(text_or_url).and_then(|u| uri_host(&u)).unwrap_or_default().to_lowercase();
        if !host.is_empty() {
            let bare = host.strip_prefix("www.").unwrap_or(&host);
            let brand = match bare.find('.') { Some(dot) if dot > 2 => &bare[..dot], _ => bare };
            if g.contains(&norm(brand)) { return true; }
        }
        return false;
    }
    true
}

fn is_type(act: &str) -> bool { matches!(act, "type" | "type_text" | "input_text") }

pub fn signature(act: &str, fg: &str, tgt: &str, node: Option<&Node>, x: i32, y: i32, text: &str) -> String {
    if act == "open_app" || act == "launch" {
        return format!("open_app|{}", if !tgt.is_empty() { tgt.to_string() } else { norm(text) });
    }
    if act == "open_url" {
        return format!("open_url|{}", safe_lower(&normalize_http_url(text).unwrap_or_else(|| text.to_string())));
    }
    let node_key = match node {
        Some(n) => format!("{}|{}|{},{}", safe_lower(&n.view_id), norm(&label_of(Some(n))), n.cx / 48, n.cy / 48),
        None if x > 0 && y > 0 => format!("coord|{},{}", x / 48, y / 48),
        None => "global".into(),
    };
    let txt = if is_type(act) { format!("|{}", truncate(&norm(text), 32)) } else { String::new() };
    format!("{act}|{fg}|{node_key}{txt}")
}

pub fn evaluate(i: &Input) -> Decision {
    if i.action.trim().is_empty() { return d("ALLOW", "ROUTINE", String::new(), "noop", ""); }
    let act = i.action.to_lowercase().trim().to_string();
    let act = act.as_str();
    let fg = safe_lower(i.fg_pkg);
    let tgt = safe_lower(i.target_pkg);
    let node = i.node.as_ref();
    let text = i.text_or_url;
    let sig = signature(act, &fg, &tgt, node, i.x, i.y, text);

    // 1. Bloqueios absolutos de integridade
    let self_pkg = i.self_pkg.to_lowercase();
    if self_pkg == fg && i.fg_class.contains("SettingsActivity") && act != "back" && act != "home" {
        return d("BLOCK", "SELF_PROTECTION", "Proteção ativa: o agente não pode alterar as Definições do Odysseus.".into(), &sig, &self_pkg);
    }
    if (act == "open_app" || act == "launch") && self_pkg == tgt && norm(text).contains("definicoes") {
        return d("BLOCK", "SELF_PROTECTION", "Proteção ativa: o agente não pode abrir/alterar as Definições do Odysseus.".into(), &sig, &self_pkg);
    }
    if node.is_some_and(|n| n.password) && is_type(act) {
        return d("BLOCK", "PASSWORD_AUTOFILL", "Proteção ativa: preenchimento automático de palavras-passe/PIN bloqueado.".into(), &sig, &fg);
    }
    if act == "open_url" {
        let raw = text.trim();
        if normalize_http_url(raw).is_none() {
            let scheme = extract_scheme(raw);
            if matches!(scheme.as_str(), "mailto" | "sms" | "smsto" | "tel") {
                return d("CONFIRM", "MESSAGE_SEND", format!("🔴 Iniciar comunicação externa ({})", truncate(raw, 50)), &sig, "");
            }
            return d("BLOCK", "SELF_PROTECTION", format!("Esquema de endereço não permitido pelo agente: {}", truncate(raw, 45)), &sig, "");
        }
    }

    let touch_or_type = matches!(act, "tap" | "click" | "long_press" | "double_tap") || is_type(act);
    let opens = act == "open_app" || act == "launch";
    if !(touch_or_type || opens || act == "open_url") { return d("ALLOW", "ROUTINE", String::new(), &sig, ""); }

    let coord = if i.x > 0 && i.y > 0 { format!("coordenadas ({}, {})", i.x, i.y) } else { "ecrã".into() };
    let label = match node {
        Some(_) => label_of(node),
        None if !tgt.is_empty() => tgt.clone(),
        None if !text.is_empty() => truncate(text, 45),
        None => coord,
    };
    let pick = |pred: fn(&str) -> bool| if pred(&tgt) { tgt.clone() } else { fg.clone() };

    // 2a) Gestores de palavras-passe e autenticadores
    if is_password_manager_package(&tgt) || is_password_manager_package(&fg)
        || (opens && contains_password_manager_keyword(text))
        || (act == "open_url" && contains_password_manager_keyword(text))
    {
        let c = pick(is_password_manager_package);
        let shown = if c.is_empty() { label.clone() } else { c.clone() };
        return d("CONFIRM", "PASSWORD_MANAGER", format!("🔴 Acesso a gestor de palavras-passe / autenticador ({shown})."), &sig, &c);
    }
    if node.is_some_and(is_credential_node) {
        return d("CONFIRM", "PASSWORD_MANAGER", format!("🔴 Elemento de credenciais / palavras-passe detetado ({label})."), &sig, &fg);
    }
    // 2b) Pagamentos
    if is_payment_package(&tgt) || is_payment_package(&fg) || (act == "open_url" && is_payment_url(text)) {
        let c = pick(is_payment_package);
        let shown = if c.is_empty() { label.clone() } else { c.clone() };
        return d("CONFIRM", "PAYMENT", format!("🔴 Aplicação ou endereço financeiro/pagamentos ({shown}) — alvo: {label}"), &sig, &c);
    }
    if touch_or_type && node.is_some_and(is_payment_node) {
        return d("CONFIRM", "PAYMENT", format!("🔴 Ação de pagamento ou compra detetada: \"{label}\""), &sig, &fg);
    }
    if is_type(act) && i.submit && is_payment_url(text) {
        return d("CONFIRM", "PAYMENT", format!("🔴 Navegação para página financeira/pagamento: \"{}\"", truncate(text, 50)), &sig, &fg);
    }
    // 2c) Sistema e eliminação
    if is_system_critical_package(&tgt) || is_system_critical_package(&fg) {
        let c = pick(is_system_critical_package);
        return d("CONFIRM", "SYSTEM_SENSITIVE", format!("🔴 Definições/permissões críticas do sistema ({c}) — alvo: {label}"), &sig, &c);
    }
    if touch_or_type && node.is_some_and(is_delete_or_system_node) {
        return d("CONFIRM", "DATA_DELETE", format!("🔴 Eliminação de dados ou permissão sensível detetada: \"{label}\""), &sig, &fg);
    }
    // 2d) Envio ou publicação
    if touch_or_type && node.is_some_and(is_send_or_publish_node) {
        return d("CONFIRM", "MESSAGE_SEND", format!("🔴 Envio ou publicação detetada: \"{label}\""), &sig, &fg);
    }
    if is_type(act) && i.submit && !text.trim().is_empty() {
        let social = is_messaging_or_social_package(&fg);
        let search_or_url = is_search_or_address_node(node) || looks_like_url_or_domain(text);
        if (social && !search_or_url) || is_message_composer_node(node) {
            return d("CONFIRM", "MESSAGE_SEND", format!("🔴 Submeter/enviar mensagem ou publicação: \"{}\"", truncate(text, 50)), &sig, &fg);
        }
        if contains_password_manager_keyword(text) {
            return d("CONFIRM", "PASSWORD_MANAGER", format!("🔴 Navegação para cofre de palavras-passe: \"{}\"", truncate(text, 50)), &sig, &fg);
        }
    }
    if touch_or_type && node.is_none() {
        return d("BLOCK", "SELF_PROTECTION", "Não foi possível identificar o elemento. Tenta novamente após ler o ecrã.".into(), &sig, &fg);
    }
    if is_type(act) && i.submit && !is_search_or_address_node(node) {
        return d("CONFIRM", "MESSAGE_SEND", format!("Confirmas submeter o texto no elemento {label}?"), &sig, &fg);
    }
    // 2e) Risco assinalado pelo modelo
    if i.model_critical && i.confirm_critical {
        let msg = if !i.model_reason.trim().is_empty() {
            format!("🔴 Crítico: {}", i.model_reason.trim())
        } else {
            format!("🔴 O agente assinalou este passo como sensível ({label}).")
        };
        return d("CONFIRM", "MODEL_CRITICAL", msg, &sig, "");
    }
    // 3. Depuração passo-a-passo
    if i.confirm_all_steps {
        if is_type(act) {
            return d("CONFIRM", "STEP_DEBUG", format!("Confirmar escrita em {label}: \"{}\"", truncate(text, 45)), &sig, "");
        }
        return d("CONFIRM", "STEP_DEBUG", format!("Confirmar {act} em {label}."), &sig, "");
    }
    // 4. Clareza de intenção
    if !has_clear_actionable_intent(i.goal, act, text) {
        return d("CONFIRM", "UNCLEAR_INTENT", format!("⚠️ Intenção ambígua para '{act}' ({label}). Confirmas executar?"), &sig, "");
    }
    d("ALLOW", "ROUTINE", String::new(), &sig, "")
}

// ---------------------------------------------------------------- JNI

const SEP: char = '\u{1f}';

fn s(env: &mut JNIEnv, v: &JString) -> String {
    if v.is_null() { return String::new(); }
    env.get_string(v).map(String::from).unwrap_or_default()
}

fn out(env: &mut JNIEnv, value: Option<String>) -> jstring {
    match value {
        None => std::ptr::null_mut(),
        Some(v) => env.new_string(v).map(|j| j.into_raw()).unwrap_or(std::ptr::null_mut()),
    }
}

#[no_mangle]
#[allow(clippy::too_many_arguments)]
pub extern "system" fn Java_com_canorus_odysseus_AgentPolicy_nativeEvaluate<'l>(
    mut env: JNIEnv<'l>, _: JClass<'l>,
    self_pkg: JString<'l>, goal: JString<'l>, action: JString<'l>, fg_pkg: JString<'l>,
    fg_class: JString<'l>, target_pkg: JString<'l>,
    has_node: jboolean, node_id: jint, node_text: JString<'l>, node_desc: JString<'l>,
    node_view_id: JString<'l>, node_cx: jint, node_cy: jint, node_editable: jboolean, node_password: jboolean,
    x: jint, y: jint, text_or_url: JString<'l>, submit: jboolean, model_critical: jboolean,
    model_reason: JString<'l>, confirm_critical: jboolean, confirm_all_steps: jboolean,
) -> jstring {
    let (sp, g, a, fp, fc, tp) = (s(&mut env, &self_pkg), s(&mut env, &goal), s(&mut env, &action),
        s(&mut env, &fg_pkg), s(&mut env, &fg_class), s(&mut env, &target_pkg));
    let node = (has_node != 0).then(|| Node {
        id: node_id, text: s(&mut env, &node_text), desc: s(&mut env, &node_desc),
        view_id: s(&mut env, &node_view_id), cx: node_cx, cy: node_cy,
        editable: node_editable != 0, password: node_password != 0,
    });
    let (t, mr) = (s(&mut env, &text_or_url), s(&mut env, &model_reason));
    let dec = evaluate(&Input {
        self_pkg: &sp, goal: &g, action: &a, fg_pkg: &fp, fg_class: &fc, target_pkg: &tp, node,
        x, y, text_or_url: &t, submit: submit != 0, model_critical: model_critical != 0,
        model_reason: &mr, confirm_critical: confirm_critical != 0, confirm_all_steps: confirm_all_steps != 0,
    });
    let joined = [dec.verdict, dec.category, &dec.signature, &dec.critical_pkg, &dec.reason].join(&SEP.to_string());
    out(&mut env, Some(joined))
}

#[no_mangle]
pub extern "system" fn Java_com_canorus_odysseus_AgentPolicy_norm<'l>(mut env: JNIEnv<'l>, _: JClass<'l>, v: JString<'l>) -> jstring {
    let r = norm(&s(&mut env, &v));
    out(&mut env, Some(r))
}

#[no_mangle]
pub extern "system" fn Java_com_canorus_odysseus_AgentPolicy_normalizeHttpUrl<'l>(mut env: JNIEnv<'l>, _: JClass<'l>, v: JString<'l>) -> jstring {
    let r = normalize_http_url(&s(&mut env, &v));
    out(&mut env, r)
}

#[no_mangle]
pub extern "system" fn Java_com_canorus_odysseus_AgentSafety_nativeLabel<'l>(
    mut env: JNIEnv<'l>, _: JClass<'l>, id: jint, text: JString<'l>, desc: JString<'l>, view_id: JString<'l>,
) -> jstring {
    let n = Node { id, text: s(&mut env, &text), desc: s(&mut env, &desc), view_id: s(&mut env, &view_id), ..Default::default() };
    let r = label_of(Some(&n));
    out(&mut env, Some(r))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn node(text: &str, view_id: &str) -> Option<Node> {
        Some(Node { id: 7, text: text.into(), view_id: view_id.into(), cx: 100, cy: 200, ..Default::default() })
    }
    fn base<'a>(action: &'a str, goal: &'a str) -> Input<'a> {
        Input { self_pkg: "com.canorus.odysseus", action, goal, confirm_critical: true, ..Default::default() }
    }

    #[test]
    fn normalization_and_urls() {
        assert_eq!(norm("  Definições ÁGUA "), "definicoes agua");
        assert_eq!(normalize_http_url("publico.pt").as_deref(), Some("https://publico.pt"));
        assert_eq!(normalize_http_url("HTTPS://Example.com/x").as_deref(), Some("HTTPS://Example.com/x"));
        assert_eq!(normalize_http_url("javascript:alert(1)"), None);
        assert_eq!(normalize_http_url("olá mundo"), None);
        assert!(looks_like_url_or_domain("www.x"));
        assert!(!looks_like_url_or_domain("ficheiro.c"));
        assert_eq!(truncate("abcdef", 3), "abc…");
    }

    #[test]
    fn blocks_and_confirms() {
        let mut i = base("tap", "abre definições");
        i.fg_pkg = "com.canorus.odysseus";
        i.fg_class = "com.canorus.odysseus.SettingsActivity";
        i.node = node("Ligar", "");
        assert_eq!(evaluate(&i).verdict, "BLOCK");

        let mut i = base("open_url", "abre");
        i.text_or_url = "intent://x";
        assert_eq!(evaluate(&i).category, "SELF_PROTECTION");
        i.text_or_url = "tel:912345678";
        assert_eq!(evaluate(&i).category, "MESSAGE_SEND");

        let mut i = base("open_app", "abre o mb way");
        i.target_pkg = "pt.sibs.android.mbway";
        assert_eq!(evaluate(&i).category, "PAYMENT");

        let mut i = base("tap", "envia");
        i.fg_pkg = "com.whatsapp";
        i.node = node("Enviar", "com.whatsapp:id/send");
        let dec = evaluate(&i);
        assert_eq!((dec.verdict, dec.category), ("CONFIRM", "MESSAGE_SEND"));
        assert_eq!(dec.signature, "tap|com.whatsapp|com.whatsapp:id/send|enviar|2,4");

        let mut i = base("tap", "carrega");
        i.node = node("Apagar tudo", "");
        assert_eq!(evaluate(&i).category, "DATA_DELETE");
        i.node = node("Apagarás", "");
        assert_eq!(evaluate(&i).verdict, "ALLOW");

        let mut i = base("tap", "x");
        assert_eq!(evaluate(&i).verdict, "BLOCK");
        i.node = Some(Node { password: true, ..Default::default() });
        i.action = "type";
        assert_eq!(evaluate(&i).category, "PASSWORD_AUTOFILL");
    }

    #[test]
    fn intent_and_routine() {
        let mut i = base("open_app", "abre o spotify");
        i.target_pkg = "com.spotify.music";
        assert_eq!(evaluate(&i), d("ALLOW", "ROUTINE", String::new(), "open_app|com.spotify.music", ""));
        assert!(!has_clear_actionable_intent("O que está no ecrã?", "tap", ""));
        assert!(has_clear_actionable_intent("quero o publico", "open_url", "https://www.publico.pt"));
        assert!(!has_clear_actionable_intent("quanto é 2+2", "open_url", "https://www.publico.pt"));
        let mut i = base("open_url", "quanto é 2+2");
        i.text_or_url = "https://www.publico.pt";
        assert_eq!(evaluate(&i).category, "UNCLEAR_INTENT");
        i.confirm_all_steps = true;
        assert_eq!(evaluate(&i).category, "STEP_DEBUG");
        let mut i = base("scroll", "");
        i.model_critical = true;
        assert_eq!(evaluate(&i).verdict, "ALLOW");
        let mut i = base("tap", "carrega");
        i.node = node("OK", "");
        i.model_critical = true;
        i.model_reason = "apaga conta";
        assert_eq!(evaluate(&i).reason, "🔴 Crítico: apaga conta");
    }
}
