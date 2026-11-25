use std::path::PathBuf;
use std::sync::{
    atomic::{AtomicBool, AtomicU64, AtomicU8},
    Mutex,
};
use std::time::Duration;
use tauri::{AppHandle, Manager, Url};

pub const UPDATE_URL: &str =
    "https://github.com/Canoruss/odysseus-kit/releases/download/desktop-latest/latest.json";
pub const REPO_URL: &str = "https://github.com/Canoruss/odysseus-kit";

pub struct St {
    pub server: Mutex<Option<Url>>,
    pub update: Mutex<Option<tauri_plugin_updater::Update>>,
    pub http: reqwest::Client,
    pub got: AtomicU64,
    pub total: AtomicU64,
    pub phase: AtomicU8, // 0 parado, 1 a descarregar, 2 a instalar, 3 erro
    pub quitting: AtomicBool,
}

impl Default for St {
    fn default() -> Self {
        let http = reqwest::Client::builder()
            .timeout(Duration::from_secs(10))
            .pool_max_idle_per_host(4)
            .pool_idle_timeout(Duration::from_secs(30))
            .tcp_nodelay(true)
            .redirect(reqwest::redirect::Policy::limited(5))
            .user_agent("OdysseusDesktop")
            .build()
            .unwrap_or_else(|_| reqwest::Client::new());

        Self {
            server: Mutex::new(None),
            update: Mutex::new(None),
            http,
            got: AtomicU64::new(0),
            total: AtomicU64::new(0),
            phase: AtomicU8::new(0),
            quitting: AtomicBool::new(false),
        }
    }
}

impl St {
    pub fn get_server(&self) -> Option<Url> {
        self.server
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .clone()
    }

    pub fn set_server(&self, url: Option<Url>) {
        *self.server.lock().unwrap_or_else(|e| e.into_inner()) = url;
    }

    pub fn set_update(&self, upd: Option<tauri_plugin_updater::Update>) {
        *self.update.lock().unwrap_or_else(|e| e.into_inner()) = upd;
    }

    pub fn take_update(&self) -> Option<tauri_plugin_updater::Update> {
        self.update
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .take()
    }
}

pub fn cfg_file(app: &AppHandle) -> Option<PathBuf> {
    app.path()
        .app_config_dir()
        .ok()
        .map(|d| d.join("server.json"))
}

pub fn valid_server(u: &Url) -> bool {
    matches!(u.scheme(), "http" | "https")
        && u.host_str().is_some()
        && u.username().is_empty()
        && u.password().is_none()
        && u.query().is_none()
        && u.fragment().is_none()
}

pub fn load_server(app: &AppHandle) -> Option<Url> {
    let bytes = std::fs::read(cfg_file(app)?).ok()?;
    let v: serde_json::Value = serde_json::from_slice(&bytes).ok()?;
    let u = Url::parse(v["url"].as_str()?).ok()?;
    valid_server(&u).then_some(u)
}

pub fn local_page(url: &Url) -> bool {
    (url.scheme() == "tauri" && url.host_str() == Some("localhost"))
        || (url.scheme() == "http" && url.host_str() == Some("tauri.localhost"))
}

pub fn local_url(page: &str) -> Option<Url> {
    let page = page.trim_start_matches('/');
    Url::parse(&format!(
        "{}/{}",
        if cfg!(windows) {
            "http://tauri.localhost"
        } else {
            "tauri://localhost"
        },
        page
    ))
    .ok()
}

pub fn app_origin_ok(app: &AppHandle, url: &Url) -> bool {
    if let Some(s) = app.state::<St>().get_server() {
        if url.origin() == s.origin() {
            return true;
        }
    }
    local_page(url)
}

pub fn unique_download_path(dir: &std::path::Path, file_name: &std::ffi::OsStr) -> PathBuf {
    let candidate = dir.join(file_name);
    if !candidate.exists() {
        return candidate;
    }
    let stem = candidate
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("download");
    let ext = candidate.extension().and_then(|e| e.to_str());
    for i in 1..10_000 {
        let next_name = match ext {
            Some(e) if !e.is_empty() => format!("{stem} ({i}).{e}"),
            _ => format!("{stem} ({i})"),
        };
        let next_path = dir.join(next_name);
        if !next_path.exists() {
            return next_path;
        }
    }
    candidate
}

/// Self-updater is supported on Windows (NSIS) and Linux AppImage ($APPIMAGE set),
/// whereas Linux .deb packages are updated via apt/dpkg.
pub fn can_self_update() -> bool {
    cfg!(windows) || std::env::var_os("APPIMAGE").is_some()
}
