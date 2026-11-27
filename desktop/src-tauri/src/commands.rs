use serde_json::{json, Value};
use std::sync::atomic::Ordering;
use std::time::Duration;
use tauri::{AppHandle, Manager, State, Url};
use tauri_plugin_autostart::ManagerExt as AutostartExt;
use tauri_plugin_updater::UpdaterExt;

use crate::state::{can_self_update, cfg_file, valid_server, St, REPO_URL, UPDATE_URL};
use crate::webview_hooks::{external, go_local, open_update_window};

#[tauri::command]
pub fn app_info(app: AppHandle, st: State<'_, St>) -> Value {
    let autostart = app
        .autolaunch()
        .is_enabled()
        .unwrap_or(false);
    json!({
        "version": app.package_info().version.to_string(),
        "server": st.get_server().map(|u| u.to_string()),
        "windows": cfg!(windows),
        "can_self_update": can_self_update(),
        "autostart": autostart,
        "repo": REPO_URL,
    })
}

#[tauri::command]
pub fn set_autostart(app: AppHandle, enabled: bool) -> Result<bool, String> {
    let mgr = app.autolaunch();
    if enabled {
        mgr.enable().map_err(|e| e.to_string())?;
    } else {
        mgr.disable().map_err(|e| e.to_string())?;
    }
    mgr.is_enabled().map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn check_server(st: State<'_, St>, input: String) -> Result<Value, String> {
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

    let mut why = "unreachable";
    for c in cands {
        let Ok(url) = Url::parse(&c) else {
            why = "invalid";
            continue;
        };
        if !valid_server(&url) || (url.path() != "/" && !url.path().is_empty()) {
            why = "invalid";
            continue;
        }
        let Ok(root) = st
            .http
            .get(url.clone())
            .timeout(Duration::from_secs(8))
            .send()
            .await
        else {
            continue;
        };
        let final_url = root.url().clone();
        let body = root.text().await.unwrap_or_default().to_lowercase();
        let health = match url.join("/api/health") {
            Ok(health_url) => match st
                .http
                .get(health_url)
                .timeout(Duration::from_secs(8))
                .send()
                .await
            {
                Ok(r) if r.status().is_success() => {
                    r.text().await.unwrap_or_default().contains("healthy")
                }
                _ => false,
            },
            Err(_) => false,
        };
        if health || body.contains("odysseus") {
            let mut base = url.clone();
            if final_url.origin() == url.origin() || final_url.origin().is_tuple() {
                base = Url::parse(&final_url.origin().ascii_serialization()).unwrap_or(url);
            }
            let secure = base.scheme() == "https"
                || matches!(base.host_str(), Some("localhost") | Some("127.0.0.1"));
            return Ok(json!({"url": base.as_str().trim_end_matches('/'), "secure": secure}));
        }
        why = "not_odysseus";
    }
    Err(why.into())
}

#[tauri::command]
pub fn save_server(app: AppHandle, st: State<'_, St>, url: String) -> Result<(), String> {
    let u = Url::parse(url.trim()).map_err(|_| "invalid".to_string())?;
    if !valid_server(&u) {
        return Err("invalid".into());
    }
    let file = cfg_file(&app).ok_or_else(|| "config".to_string())?;
    if let Some(parent) = file.parent() {
        std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    std::fs::write(
        &file,
        json!({"url": u.as_str().trim_end_matches('/')}).to_string(),
    )
    .map_err(|e| e.to_string())?;
    st.set_server(Some(u.clone()));
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.navigate(u);
    }
    Ok(())
}

#[tauri::command]
pub fn forget_server(app: AppHandle, st: State<'_, St>) {
    if let Some(f) = cfg_file(&app) {
        let _ = std::fs::remove_file(f);
    }
    st.set_server(None);
    go_local(&app, "index.html");
}

#[tauri::command]
pub fn retry_server(app: AppHandle, st: State<'_, St>) {
    match st.get_server() {
        Some(u) => {
            if let Some(w) = app.get_webview_window("main") {
                let _ = w.navigate(u);
            }
        }
        None => go_local(&app, "index.html"),
    }
}

#[tauri::command]
pub fn open_update(app: AppHandle) {
    open_update_window(&app);
}

#[tauri::command]
pub fn close_win(app: AppHandle, label: String) {
    if let Some(w) = app.get_webview_window(&label) {
        let _ = w.close();
    }
}

#[tauri::command]
pub fn open_link(url: String) {
    if let Ok(u) = Url::parse(&url) {
        external(&u);
    }
}

#[tauri::command]
pub async fn test_key(st: State<'_, St>, kind: String, value: String) -> Result<bool, String> {
    let value = value.trim().to_string();
    if value.is_empty() || value.len() > 300 {
        return Ok(false);
    }
    let req = match kind.as_str() {
        "groq" => st
            .http
            .get("https://api.groq.com/openai/v1/models")
            .bearer_auth(&value),
        "openrouter" => st
            .http
            .get("https://openrouter.ai/api/v1/auth/key")
            .bearer_auth(&value),
        "openai" => st
            .http
            .get("https://api.openai.com/v1/models")
            .bearer_auth(&value),
        "gemini" => st
            .http
            .get("https://generativelanguage.googleapis.com/v1beta/models")
            .header("x-goog-api-key", &value),
        "deepl" => {
            let host = if value.ends_with(":fx") {
                "api-free.deepl.com"
            } else {
                "api.deepl.com"
            };
            st.http
                .get(format!("https://{host}/v2/usage"))
                .header("Authorization", format!("DeepL-Auth-Key {value}"))
        }
        _ => return Err("kind".into()),
    };
    Ok(req
        .timeout(Duration::from_secs(10))
        .send()
        .await
        .map(|r| r.status().is_success())
        .unwrap_or(false))
}

#[tauri::command]
pub async fn check_update(app: AppHandle, st: State<'_, St>) -> Result<Value, String> {
    if !can_self_update() {
        return Ok(json!({"available": false, "managed_by_pkg": true}));
    }
    let endpoint = Url::parse(UPDATE_URL).map_err(|e| e.to_string())?;
    let updater = app
        .updater_builder()
        .endpoints(vec![endpoint])
        .map_err(|e| e.to_string())?
        .build()
        .map_err(|e| e.to_string())?;
    match updater.check().await.map_err(|e| e.to_string())? {
        Some(u) => {
            let v = json!({"available": true, "version": u.version, "notes": u.body});
            st.set_update(Some(u));
            Ok(v)
        }
        None => Ok(json!({"available": false})),
    }
}

#[tauri::command]
pub async fn install_update(app: AppHandle, st: State<'_, St>) -> Result<(), String> {
    let Some(u) = st.take_update() else {
        return Err("none".into());
    };
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
            move || {
                let s = b.state::<St>();
                s.phase.store(2, Ordering::Relaxed);
                s.quitting.store(true, Ordering::SeqCst);
            },
        )
        .await;
    match res {
        Ok(()) => {
            app.restart();
        }
        Err(e) => {
            st.quitting.store(false, Ordering::SeqCst);
            st.phase.store(3, Ordering::Relaxed);
            Err(e.to_string())
        }
    }
}

#[tauri::command]
pub fn update_progress(st: State<'_, St>) -> Value {
    json!({
        "phase": st.phase.load(Ordering::Relaxed),
        "got": st.got.load(Ordering::Relaxed),
        "total": st.total.load(Ordering::Relaxed)
    })
}
