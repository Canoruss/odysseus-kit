#![cfg_attr(all(windows, not(debug_assertions)), windows_subsystem = "windows")]
use serde_json::{json, Value};
use std::sync::{
    atomic::{AtomicU64, AtomicU8, Ordering},
    Mutex,
};
use std::time::Duration;
use tauri::{
    menu::MenuBuilder,
    tray::TrayIconBuilder,
    webview::{NewWindowResponse, PermissionKind, PermissionResponse},
    AppHandle, Manager, State, Url, WebviewUrl, WebviewWindow, WebviewWindowBuilder,
};
use tauri_plugin_global_shortcut::{GlobalShortcutExt, ShortcutState};
use tauri_plugin_notification::NotificationExt;
use tauri_plugin_updater::UpdaterExt;
use tauri_plugin_window_state::StateFlags;

fn show(app: &AppHandle, toggle: bool) {
    if let Some(w) = app.get_webview_window("main") {
        if toggle && w.is_visible().unwrap_or(false) && !w.is_minimized().unwrap_or(false) {
            let _ = w.hide();
        } else {
            let _ = w.show();
            let _ = w.unminimize();
            let _ = w.set_focus();
        }
    }
}
fn notice(app: &AppHandle, title: &str, body: &str) {
    let _ = app.notification().builder().title(title).body(body).show();
}
fn background_notice(w: &WebviewWindow, title: &str, body: &str) {
    if !w.is_focused().unwrap_or(false) || !w.is_visible().unwrap_or(false) {
        notice(w.app_handle(), title, body);
    }
}
const UPDATE_URL: &str =
    "https://github.com/Canoruss/odysseus-kit/releases/download/desktop-latest/latest.json";
const REPO_URL: &str = "https://github.com/Canoruss/odysseus-kit";

#[derive(Default)]
struct St {
    server: Mutex<Option<Url>>,
    update: Mutex<Option<tauri_plugin_updater::Update>>,
    got: AtomicU64,
    total: AtomicU64,
    phase: AtomicU8, // 0 parado, 1 a descarregar, 2 a instalar, 3 erro
}
fn cfg_file(app: &AppHandle) -> Option<std::path::PathBuf> {
    app.path().app_config_dir().ok().map(|d| d.join("server.json"))
}
fn valid_server(u: &Url) -> bool {
    matches!(u.scheme(), "http" | "https")
        && u.host_str().is_some()
        && u.username().is_empty()
        && u.password().is_none()
        && u.query().is_none()
        && u.fragment().is_none()
}
fn load_server(app: &AppHandle) -> Option<Url> {
    let v: Value = serde_json::from_slice(&std::fs::read(cfg_file(app)?).ok()?).ok()?;
    let u = Url::parse(v["url"].as_str()?).ok()?;
    valid_server(&u).then_some(u)
}
fn app_origin_ok(app: &AppHandle, url: &Url) -> bool {
    if let Some(s) = app.state::<St>().server.lock().unwrap().as_ref() {
        if url.origin() == s.origin() {
            return true;
        }
    }
    local_page(url)
}
fn local_page(url: &Url) -> bool {
    (url.scheme() == "tauri" && url.host_str() == Some("localhost"))
        || (url.scheme() == "http" && url.host_str() == Some("tauri.localhost"))
}
fn local_url(page: &str) -> Url {
    Url::parse(&format!(
        "{}/{}",
        if cfg!(windows) { "http://tauri.localhost" } else { "tauri://localhost" },
        page
    ))
    .unwrap()
}
fn go_local(app: &AppHandle, page: &str) {
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.navigate(local_url(page));
        show(app, false);
    }
}
fn external(url: &Url) {
    if matches!(url.scheme(), "http" | "https" | "mailto") {
        let _ = open::that_detached(url.as_str());
    }
}
#[cfg(target_os = "linux")]
fn hooks(w: &WebviewWindow, offline: Url) -> tauri::Result<()> {
    use webkit2gtk::{NotificationExt as WebNotificationExt, SettingsExt, WebViewExt};
    let window = w.clone();
    w.with_webview(move |platform| {
        let view = platform.inner();
        if let Some(settings) = view.settings() {
            settings.set_enable_media_stream(true);
        }
        view.connect_load_failed(move |view, _, uri, error| {
            if uri == offline.as_str() || error.matches(webkit2gtk::NetworkError::Cancelled) {
                return false;
            }
            view.load_uri(offline.as_str());
            true
        });
        view.connect_show_notification(move |_, notification| {
            background_notice(
                &window,
                notification.title().as_deref().unwrap_or("Odysseus"),
                notification.body().as_deref().unwrap_or(""),
            );
            true
        });
    })
}
#[cfg(windows)]
fn hooks(w: &WebviewWindow, offline: Url) -> tauri::Result<()> {
    use webview2_com::{
        take_pwstr,
        Microsoft::Web::WebView2::Win32::{
            ICoreWebView2_24, COREWEBVIEW2_WEB_ERROR_STATUS_OPERATION_CANCELED,
        },
        NavigationCompletedEventHandler, NotificationReceivedEventHandler,
    };
    use windows_core::{Interface, BOOL, PWSTR};
    let window = w.clone();
    w.with_webview(move |platform| unsafe {
        let Ok(view) = platform.controller().CoreWebView2() else {
            return;
        };
        let fallback = window.clone();
        let mut token = 0;
        let _ = view.add_NavigationCompleted(
            &NavigationCompletedEventHandler::create(Box::new(move |_, args| {
                if let Some(args) = args {
                    let mut success = BOOL::default();
                    let mut status = Default::default();
                    args.IsSuccess(&mut success)?;
                    args.WebErrorStatus(&mut status)?;
                    if !success.as_bool()
                        && status != COREWEBVIEW2_WEB_ERROR_STATUS_OPERATION_CANCELED
                        && fallback.url().ok().as_ref() != Some(&offline)
                    {
                        let _ = fallback.navigate(offline.clone());
                    }
                }
                Ok(())
            })),
            &mut token,
        );
        if let Ok(v) = view.cast::<ICoreWebView2_24>() {
            let _ = v.add_NotificationReceived(
                &NotificationReceivedEventHandler::create(Box::new(move |_, args| {
                    if let Some(args) = args {
                        args.SetHandled(true)?;
                        let n = args.Notification()?;
                        let mut t = PWSTR::null();
                        n.Title(&mut t)?;
                        let title = take_pwstr(t);
                        let mut b = PWSTR::null();
                        n.Body(&mut b)?;
                        background_notice(&window, &title, &take_pwstr(b));
                    }
                    Ok(())
                })),
                &mut token,
            );
        }
    })
}

// ---------- comandos chamados pelas páginas locais (assistente, atualização, ecrã offline) ----------
#[tauri::command]
fn app_info(app: AppHandle, st: State<'_, St>) -> Value {
    json!({
        "version": app.package_info().version.to_string(),
        "server": st.server.lock().unwrap().as_ref().map(|u| u.to_string()),
        "windows": cfg!(windows),
        "repo": REPO_URL,
    })
}
#[tauri::command]
async fn check_server(input: String) -> Result<Value, String> {
    let raw = input.trim().trim_end_matches('/').to_string();
    if raw.is_empty() || raw.len() > 300 || raw.contains(char::is_whitespace) {
        return Err("invalid".into());
    }
    let cands: Vec<String> = if raw.contains("://") {
        vec![raw.clone()]
    } else {
        let host = raw.split(['/', ':']).next().unwrap_or("");
        let local = host == "localhost"
            || host.ends_with(".local")
            || host.parse::<std::net::Ipv4Addr>().is_ok();
        if local {
            vec![format!("http://{raw}"), format!("https://{raw}")]
        } else {
            vec![format!("https://{raw}"), format!("http://{raw}")]
        }
    };
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(8))
        .redirect(reqwest::redirect::Policy::limited(5))
        .user_agent("OdysseusDesktop")
        .build()
        .map_err(|e| e.to_string())?;
    let mut why = "unreachable";
    for c in cands {
        let Ok(url) = Url::parse(&c) else { why = "invalid"; continue };
        if !valid_server(&url) || url.path() != "/" && !url.path().is_empty() {
            why = "invalid";
            continue;
        }
        let Ok(root) = client.get(url.clone()).send().await else { continue };
        let final_url = root.url().clone();
        let body = root.text().await.unwrap_or_default().to_lowercase();
        let health = match client.get(url.join("/api/health").unwrap()).send().await {
            Ok(r) if r.status().is_success() => r.text().await.unwrap_or_default().contains("healthy"),
            _ => false,
        };
        if health || body.contains("odysseus") {
            let mut base = url.clone();
            if final_url.origin() == url.origin() || final_url.origin().is_tuple() {
                // segue redirecionamentos de http -> https
                base = Url::parse(&final_url.origin().ascii_serialization()).unwrap_or(url);
            }
            let secure = base.scheme() == "https" || matches!(base.host_str(), Some("localhost") | Some("127.0.0.1"));
            return Ok(json!({"url": base.as_str().trim_end_matches('/'), "secure": secure}));
        }
        why = "not_odysseus";
    }
    Err(why.into())
}
#[tauri::command]
fn save_server(app: AppHandle, st: State<'_, St>, url: String) -> Result<(), String> {
    let u = Url::parse(url.trim()).map_err(|_| "invalid".to_string())?;
    if !valid_server(&u) {
        return Err("invalid".into());
    }
    let file = cfg_file(&app).ok_or("config")?;
    std::fs::create_dir_all(file.parent().unwrap()).map_err(|e| e.to_string())?;
    std::fs::write(&file, json!({"url": u.as_str().trim_end_matches('/')}).to_string())
        .map_err(|e| e.to_string())?;
    *st.server.lock().unwrap() = Some(u.clone());
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.navigate(u);
    }
    Ok(())
}
#[tauri::command]
fn forget_server(app: AppHandle, st: State<'_, St>) {
    if let Some(f) = cfg_file(&app) {
        let _ = std::fs::remove_file(f);
    }
    *st.server.lock().unwrap() = None;
    go_local(&app, "index.html");
}
#[tauri::command]
fn retry_server(app: AppHandle, st: State<'_, St>) {
    let s = st.server.lock().unwrap().clone();
    match s {
        Some(u) => {
            if let Some(w) = app.get_webview_window("main") {
                let _ = w.navigate(u);
            }
        }
        None => go_local(&app, "index.html"),
    }
}
#[tauri::command]
fn open_update(app: AppHandle) {
    open_update_window(&app);
}
#[tauri::command]
fn close_win(app: AppHandle, label: String) {
    if let Some(w) = app.get_webview_window(&label) {
        let _ = w.close();
    }
}
#[tauri::command]
fn open_link(url: String) {
    if let Ok(u) = Url::parse(&url) {
        external(&u);
    }
}
#[tauri::command]
async fn test_key(kind: String, value: String) -> Result<bool, String> {
    let value = value.trim().to_string();
    if value.is_empty() || value.len() > 300 {
        return Ok(false);
    }
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(10))
        .user_agent("OdysseusDesktop")
        .build()
        .map_err(|e| e.to_string())?;
    let req = match kind.as_str() {
        "groq" => client.get("https://api.groq.com/openai/v1/models").bearer_auth(&value),
        "openrouter" => client.get("https://openrouter.ai/api/v1/auth/key").bearer_auth(&value),
        "openai" => client.get("https://api.openai.com/v1/models").bearer_auth(&value),
        "gemini" => client
            .get("https://generativelanguage.googleapis.com/v1beta/models")
            .header("x-goog-api-key", &value),
        "deepl" => {
            let host = if value.ends_with(":fx") { "api-free.deepl.com" } else { "api.deepl.com" };
            client
                .get(format!("https://{host}/v2/usage"))
                .header("Authorization", format!("DeepL-Auth-Key {value}"))
        }
        _ => return Err("kind".into()),
    };
    Ok(req.send().await.map(|r| r.status().is_success()).unwrap_or(false))
}
#[tauri::command]
async fn check_update(app: AppHandle, st: State<'_, St>) -> Result<Value, String> {
    let updater = app
        .updater_builder()
        .endpoints(vec![Url::parse(UPDATE_URL).unwrap()])
        .map_err(|e| e.to_string())?
        .build()
        .map_err(|e| e.to_string())?;
    match updater.check().await.map_err(|e| e.to_string())? {
        Some(u) => {
            let v = json!({"available": true, "version": u.version, "notes": u.body});
            *st.update.lock().unwrap() = Some(u);
            Ok(v)
        }
        None => Ok(json!({"available": false})),
    }
}
#[tauri::command]
async fn install_update(app: AppHandle, st: State<'_, St>) -> Result<(), String> {
    let Some(u) = st.update.lock().unwrap().take() else { return Err("none".into()) };
    st.got.store(0, Ordering::Relaxed);
    st.total.store(0, Ordering::Relaxed);
    st.phase.store(1, Ordering::Relaxed);
    let a = app.clone();
    let b = app.clone();
    let res = u
        .download_and_install(
            move |chunk, total| {
                let s = a.state::<St>();
                s.got.fetch_add(chunk as u64, Ordering::Relaxed);
                s.total.store(total.unwrap_or(0), Ordering::Relaxed);
            },
            move || b.state::<St>().phase.store(2, Ordering::Relaxed),
        )
        .await;
    match res {
        Ok(()) => {
            app.restart();
        }
        Err(e) => {
            st.phase.store(3, Ordering::Relaxed);
            Err(e.to_string())
        }
    }
}
#[tauri::command]
fn update_progress(st: State<'_, St>) -> Value {
    json!({"phase": st.phase.load(Ordering::Relaxed), "got": st.got.load(Ordering::Relaxed), "total": st.total.load(Ordering::Relaxed)})
}
fn open_update_window(app: &AppHandle) {
    if let Some(w) = app.get_webview_window("update") {
        let _ = w.show();
        let _ = w.set_focus();
        return;
    }
    let _ = WebviewWindowBuilder::new(app, "update", WebviewUrl::App("update.html".into()))
        .title("Odysseus")
        .inner_size(460., 320.)
        .resizable(false)
        .center()
        .build();
}
const SETTINGS_JS: &str = r#"
(function(){
  if (location.protocol === 'tauri:' || location.hostname === 'tauri.localhost') return;
  var pt = /^pt/i.test(navigator.language||'');
  var L = pt ? {t:'Odysseus Desktop',u:'Procurar atualizações',r:'Recarregar',s:'Mudar servidor',g:'GitHub',q:'Sair',d:'Aplicação de computador'}
             : {t:'Odysseus Desktop',u:'Check for updates',r:'Reload',s:'Change server',g:'GitHub',q:'Quit',d:'Desktop app'};
  function add(){
    var panel = document.querySelector('[data-settings-panel="system"]') || document.querySelector('[data-settings-panel="appearance"]');
    if (!panel) return;
    if (panel.querySelector('[data-ody-desktop]')) return;
    var box = document.createElement('div'); box.setAttribute('data-ody-desktop','1');
    box.style.cssText='margin:14px 0;padding:14px;border:1px solid var(--border,#333);border-radius:10px';
    box.innerHTML='<div style="font-weight:600;margin-bottom:4px">'+L.t+'</div><div style="opacity:.7;font-size:12px;margin-bottom:10px">'+L.d+'</div><div style="display:flex;flex-wrap:wrap;gap:8px"></div>';
    var row = box.lastChild;
    [['update',L.u],['reload',L.r],['server',L.s],['github',L.g],['exit',L.q]].forEach(function(x){
      var b=document.createElement('button'); b.type='button'; b.textContent=x[1];
      b.style.cssText='padding:6px 12px;border-radius:8px;border:1px solid var(--border,#444);background:var(--panel,#222);color:inherit;cursor:pointer';
      b.onclick=function(){ location.href='odysseus-app://'+x[0]; };
      row.appendChild(b);
    });
    panel.insertBefore(box, panel.firstChild);
  }
  function start(){
    add();
    if (document.documentElement) new MutationObserver(add).observe(document.documentElement,{childList:true,subtree:true});
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once:true});
  else start();
})();
"#;
fn act(app: &AppHandle, id: &str) {
    match id {
        "open" => show(app, false),
        "hide" => {
            if let Some(w) = app.get_webview_window("main") {
                let _ = w.hide();
            }
        }
        "update" => open_update_window(app),
        "server" => go_local(app, "index.html"),
        "reload" => retry_server_app(app),
        "github" => {
            if let Ok(u) = Url::parse(REPO_URL) {
                external(&u)
            }
        }
        "exit" => app.exit(0),
        _ => {}
    }
}
fn retry_server_app(app: &AppHandle) {
    let s = app.state::<St>().server.lock().unwrap().clone();
    if let (Some(u), Some(w)) = (s, app.get_webview_window("main")) {
        let _ = w.navigate(u);
    }
}
fn main() {
    tauri::Builder::default()
        .manage(St::default())
        .plugin(tauri_plugin_single_instance::init(|app, _, _| {
            show(app, false)
        }))
        .plugin(
            tauri_plugin_window_state::Builder::default()
                .with_state_flags(StateFlags::SIZE | StateFlags::POSITION | StateFlags::MAXIMIZED)
                .build(),
        )
        .plugin(
            tauri_plugin_global_shortcut::Builder::new()
                .with_handler(|app, _, event| {
                    if event.state == ShortcutState::Pressed {
                        show(app, true)
                    }
                })
                .build(),
        )
        .plugin(tauri_plugin_notification::init())
        .plugin(
            tauri_plugin_updater::Builder::new()
                .pubkey(include_str!("../update.pub").trim())
                .build(),
        )
        .invoke_handler(tauri::generate_handler![
            app_info,
            check_server,
            save_server,
            forget_server,
            retry_server,
            open_link,
            close_win,
            open_update,
            test_key,
            check_update,
            install_update,
            update_progress
        ])
        .setup(|app| {
            #[cfg(windows)]
            {
                // Sem AppUserModelID registado o Windows descarta as notificações toast.
                use std::os::windows::process::CommandExt;
                let _ = std::process::Command::new("reg")
                    .args([
                        "add",
                        r"HKCU\Software\Classes\AppUserModelId\chat.odysseus.desktop",
                        "/v",
                        "DisplayName",
                        "/d",
                        "Odysseus",
                        "/f",
                    ])
                    .creation_flags(0x0800_0000)
                    .status();
            }
            let handle = app.handle().clone();
            *app.state::<St>().server.lock().unwrap() = load_server(&handle);
            let offline = local_url("offline.html");
            let popup_app = handle.clone();
            let nav_app = handle.clone();
            let perm_app = handle.clone();
            let dl_app = handle.clone();
            let window =
                WebviewWindowBuilder::new(app, "main", WebviewUrl::App("index.html".into()))
                    .title("Odysseus")
                    .inner_size(1100., 750.)
                    .visible(!std::env::args().any(|arg| arg == "--minimized"))
                    .disable_drag_drop_handler()
                    .on_permission_request(move |view, kind| {
                        if view.url().ok().is_some_and(|u| app_origin_ok(&perm_app, &u))
                            && matches!(
                                kind,
                                PermissionKind::Microphone | PermissionKind::Notifications
                            )
                        {
                            PermissionResponse::Allow
                        } else {
                            PermissionResponse::Deny
                        }
                    })
                    .initialization_script(SETTINGS_JS)
                    .on_navigation(move |url| {
                        if url.scheme() == "odysseus-app" {
                            act(&nav_app, url.host_str().unwrap_or(""));
                            return false;
                        }
                        if app_origin_ok(&nav_app, url) {
                            return true;
                        }
                        external(url);
                        false
                    })
                    .on_new_window(move |url, _| {
                        // Ligações que abrem num separador novo (ficheiros, páginas): vão para o navegador do sistema.
                        let _ = &popup_app;
                        external(&url);
                        NewWindowResponse::Deny
                    })
                    .on_download(move |_, event| {
                        if let tauri::webview::DownloadEvent::Requested { destination, .. } = event
                        {
                            let p = dl_app.path();
                            if let (Ok(dir), Some(name)) = (
                                p.download_dir()
                                    .or_else(|_| p.home_dir().map(|h| h.join("Downloads"))),
                                destination.file_name(),
                            ) {
                                if std::fs::create_dir_all(&dir).is_err() {
                                    return false;
                                }
                                let path = dir.join(name);
                                if path.exists() {
                                    return false;
                                }
                                *destination = path;
                            }
                        }
                        true
                    })
                    .build()?;
            hooks(&window, offline)?;
            if let Some(s) = app.state::<St>().server.lock().unwrap().clone() {
                window.navigate(s)?;
            }
            let menu = MenuBuilder::new(app)
                .text("open", "Abrir / Open")
                .text("hide", "Esconder / Hide")
                .text("update", "Procurar atualizações / Check for updates")
                .text("reload", "Recarregar / Reload")
                .text("server", "Mudar servidor / Change server")
                .text("github", "GitHub")
                .separator()
                .text("exit", "Sair / Quit")
                .build()?;
            app.on_menu_event(|app, event| act(app, event.id.as_ref()));
            TrayIconBuilder::new()
                .icon(app.default_window_icon().ok_or("Ícone em falta")?.clone())
                .tooltip("Odysseus")
                .menu(&menu)
                .on_menu_event(|app, event| act(app, event.id.as_ref()))
                .build(app)?;
            if app.global_shortcut().register("Ctrl+Alt+O").is_err() {
                eprintln!("Atalho indisponível / Shortcut unavailable");
            }
            // Verificação silenciosa no arranque: só abre a janela se houver versão nova.
            let upd = handle.clone();
            tauri::async_runtime::spawn(async move {
                tokio_sleep().await;
                let st = upd.state::<St>();
                if let Ok(v) = check_update(upd.clone(), st).await {
                    if v["available"] == true {
                        open_update_window(&upd);
                    }
                }
            });
            let hiding = window.clone();
            window.on_window_event(move |event| {
                if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                    api.prevent_close();
                    let _ = hiding.hide();
                }
            });
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("Falha ao iniciar Odysseus");
}
async fn tokio_sleep() {
    let _ = tauri::async_runtime::spawn_blocking(|| std::thread::sleep(Duration::from_secs(8))).await;
}
