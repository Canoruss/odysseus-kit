use tauri::{AppHandle, Manager, Url, WebviewUrl, WebviewWindow, WebviewWindowBuilder};
use tauri_plugin_autostart::ManagerExt as AutostartExt;
use tauri_plugin_notification::NotificationExt;

use crate::state::{local_url, St, REPO_URL};

pub const SETTINGS_JS: &str = r#"
(function(){
  if (location.protocol === 'tauri:' || location.hostname === 'tauri.localhost') return;
  if (window.__odyDesktopInjected) return;
  window.__odyDesktopInjected = 1;
  var pt = /^pt/i.test(navigator.language||'');
  var L = pt ? {t:'Odysseus Desktop',u:'Procurar atualizações',a:'Arranque automático',r:'Recarregar',s:'Mudar servidor',g:'GitHub',q:'Sair',d:'Aplicação de computador'}
             : {t:'Odysseus Desktop',u:'Check for updates',a:'Toggle autostart',r:'Reload',s:'Change server',g:'GitHub',q:'Quit',d:'Desktop app'};
  var pending = 0;
  function add(){
    pending = 0;
    var panel = document.querySelector('[data-settings-panel="system"]') || document.querySelector('[data-settings-panel="appearance"]');
    if (!panel || panel.querySelector('[data-ody-desktop]')) return;
    var box = document.createElement('div'); box.setAttribute('data-ody-desktop','1');
    box.style.cssText='margin:14px 0;padding:14px;border:1px solid var(--border,#333);border-radius:10px';
    box.innerHTML='<div style="font-weight:600;margin-bottom:4px">'+L.t+'</div><div style="opacity:.7;font-size:12px;margin-bottom:10px">'+L.d+'</div><div style="display:flex;flex-wrap:wrap;gap:8px"></div>';
    var row = box.lastChild;
    [['update',L.u],['autostart',L.a],['reload',L.r],['server',L.s],['github',L.g],['exit',L.q]].forEach(function(x){
      var b=document.createElement('button'); b.type='button'; b.textContent=x[1];
      b.style.cssText='padding:6px 12px;border-radius:8px;border:1px solid var(--border,#444);background:var(--panel,#222);color:inherit;cursor:pointer';
      b.onclick=function(){ location.href='odysseus-app://'+x[0]; };
      row.appendChild(b);
    });
    panel.insertBefore(box, panel.firstChild);
  }
  function scheduleAdd(){
    if (pending) return;
    pending = setTimeout(add, 250);
  }
  function start(){
    add();
    if (document.body) new MutationObserver(scheduleAdd).observe(document.body, {childList:true, subtree:true});
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once:true});
  else start();
})();
"#;

#[cfg(windows)]
pub fn set_webview_low_memory(w: &WebviewWindow, low: bool) {
    use webview2_com::Microsoft::Web::WebView2::Win32::{
        ICoreWebView2_19, COREWEBVIEW2_MEMORY_USAGE_TARGET_LEVEL_LOW,
        COREWEBVIEW2_MEMORY_USAGE_TARGET_LEVEL_NORMAL,
    };
    use windows_core::Interface;
    let _ = w.with_webview(move |platform| unsafe {
        if let Ok(view) = platform.controller().CoreWebView2() {
            if let Ok(v19) = view.cast::<ICoreWebView2_19>() {
                let level = if low {
                    COREWEBVIEW2_MEMORY_USAGE_TARGET_LEVEL_LOW
                } else {
                    COREWEBVIEW2_MEMORY_USAGE_TARGET_LEVEL_NORMAL
                };
                let _ = v19.SetMemoryUsageTargetLevel(level);
            }
        }
    });
}

#[cfg(not(windows))]
pub fn set_webview_low_memory(_w: &WebviewWindow, _low: bool) {}

pub fn hide_to_tray(w: &WebviewWindow) {
    let _ = w.hide();
    set_webview_low_memory(w, true);
}

pub fn show(app: &AppHandle, toggle: bool) {
    if let Some(w) = app.get_webview_window("main") {
        if toggle && w.is_visible().unwrap_or(false) && !w.is_minimized().unwrap_or(false) {
            hide_to_tray(&w);
        } else {
            set_webview_low_memory(&w, false);
            let _ = w.show();
            let _ = w.unminimize();
            let _ = w.set_focus();
        }
    }
}

pub fn notice(app: &AppHandle, title: &str, body: &str) {
    let _ = app.notification().builder().title(title).body(body).show();
}

pub fn background_notice(w: &WebviewWindow, title: &str, body: &str) {
    if !w.is_focused().unwrap_or(false) || !w.is_visible().unwrap_or(false) {
        notice(w.app_handle(), title, body);
    }
}

pub fn go_local(app: &AppHandle, page: &str) {
    if let (Some(w), Some(u)) = (app.get_webview_window("main"), local_url(page)) {
        let _ = w.navigate(u);
        show(app, false);
    }
}

pub fn external(url: &Url) {
    if matches!(url.scheme(), "http" | "https" | "mailto") {
        let _ = open::that_detached(url.as_str());
    }
}

pub fn retry_server_app(app: &AppHandle) {
    let s = app.state::<St>().get_server();
    if let (Some(u), Some(w)) = (s, app.get_webview_window("main")) {
        let _ = w.navigate(u);
    }
}

pub fn open_update_window(app: &AppHandle) {
    let app = app.clone();
    // WebView2 bloqueia se outra janela for criada dentro de um evento síncrono.
    std::thread::spawn(move || {
        if let Some(w) = app.get_webview_window("update") {
            let _ = w.show();
            let _ = w.set_focus();
            return;
        }
        if let Err(error) =
            WebviewWindowBuilder::new(&app, "update", WebviewUrl::App("update.html".into()))
                .title("Odysseus")
                .inner_size(460., 320.)
                .resizable(false)
                .center()
                .build()
        {
            eprintln!("Falha ao abrir atualizações / Failed to open updates: {error}");
        }
    });
}

pub fn act(app: &AppHandle, id: &str) {
    match id {
        "open" => show(app, false),
        "hide" => {
            if let Some(w) = app.get_webview_window("main") {
                hide_to_tray(&w);
            }
        }
        "update" => {
            if crate::state::can_self_update() {
                open_update_window(app);
            } else if let Ok(u) = Url::parse(&format!("{REPO_URL}/releases/latest")) {
                external(&u);
            }
        }
        "autostart" => {
            let mgr = app.autolaunch();
            let next = !mgr.is_enabled().unwrap_or(false);
            let ok = if next { mgr.enable() } else { mgr.disable() }.is_ok();
            if ok {
                notice(
                    app,
                    "Odysseus",
                    if next {
                        "Arranque automático ativado / Autostart enabled"
                    } else {
                        "Arranque automático desativado / Autostart disabled"
                    },
                );
            }
        }
        "new-chat" => trigger_new_chat(app),
        "server" => go_local(app, "index.html"),
        "reload" => retry_server_app(app),
        "github" => {
            if let Ok(u) = Url::parse(REPO_URL) {
                external(&u);
            }
        }
        "exit" => {
            app.state::<St>()
                .quitting
                .store(true, std::sync::atomic::Ordering::SeqCst);
            app.exit(0);
        }
        _ => {}
    }
}

#[cfg(target_os = "linux")]
pub fn hooks(w: &WebviewWindow, offline: Url) -> tauri::Result<()> {
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
pub fn hooks(w: &WebviewWindow, offline: Url) -> tauri::Result<()> {
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

#[cfg(not(any(target_os = "linux", windows)))]
pub fn hooks(_w: &WebviewWindow, _offline: Url) -> tauri::Result<()> {
    Ok(())
}

pub fn trigger_new_chat(app: &AppHandle) {
    show(app, false);
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.eval(
            "(function(){var b=document.getElementById('sidebar-new-chat-btn')||document.getElementById('rail-new-session');if(b)b.click();var m=document.getElementById('message');if(m)try{m.focus();}catch(e){}})();",
        );
    }
}

pub fn handle_cli_args(app: &AppHandle, argv: &[String]) {
    if argv.iter().any(|a| a == "--new-chat" || a.starts_with("odysseus://new-chat")) {
        trigger_new_chat(app);
    } else if argv.iter().any(|a| a == "--update" || a.starts_with("odysseus://update")) {
        act(app, "update");
    } else {
        show(app, false);
    }
}
