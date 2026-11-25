#![cfg_attr(all(windows, not(debug_assertions)), windows_subsystem = "windows")]

mod commands;
mod state;
mod webview_hooks;

use std::time::Duration;
use tauri::{
    menu::{CheckMenuItemBuilder, MenuBuilder},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    webview::{NewWindowResponse, PermissionKind, PermissionResponse},
    Manager, WebviewUrl, WebviewWindowBuilder,
};
use tauri_plugin_global_shortcut::{GlobalShortcutExt, ShortcutState};
use tauri_plugin_window_state::StateFlags;

use commands::{
    app_info, check_server, check_update, close_win, forget_server, install_update, open_link,
    open_update, retry_server, save_server, set_autostart, test_key, update_progress,
};
use state::{app_origin_ok, can_self_update, load_server, local_url, unique_download_path, St};
use tauri_plugin_autostart::{MacosLauncher, ManagerExt as AutostartExt};
use webview_hooks::{act, external, handle_cli_args, hide_to_tray, hooks, open_update_window, set_webview_low_memory, show, SETTINGS_JS};

fn main() {
    tauri::Builder::default()
        .manage(St::default())
        .plugin(tauri_plugin_single_instance::init(|app, argv, _| {
            handle_cli_args(app, &argv);
        }))
        .plugin(tauri_plugin_autostart::init(
            MacosLauncher::LaunchAgent,
            Some(vec!["--minimized"]),
        ))
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
            set_autostart,
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
            app.state::<St>().set_server(load_server(&handle));
            let offline = local_url("offline.html")
                .ok_or_else(|| std::io::Error::other("URL offline inválida"))?;
            let nav_app = handle.clone();
            let perm_app = handle.clone();
            let dl_app = handle.clone();
            let start_minimized = std::env::args().any(|arg| arg == "--minimized");
            let window =
                WebviewWindowBuilder::new(app, "main", WebviewUrl::App("index.html".into()))
                    .title("Odysseus")
                    .inner_size(1100., 750.)
                    .visible(!start_minimized)
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
                                destination.file_name().map(|n| n.to_os_string()),
                            ) {
                                if std::fs::create_dir_all(&dir).is_err() {
                                    return false;
                                }
                                *destination = unique_download_path(&dir, &name);
                            }
                        }
                        true
                    })
                    .build()?;
            hooks(&window, offline)?;
            if start_minimized {
                set_webview_low_memory(&window, true);
            }
            if let Some(s) = app.state::<St>().get_server() {
                window.navigate(s)?;
            }
            let auto_item = CheckMenuItemBuilder::with_id(
                "autostart",
                "Iniciar no arranque / Start at login",
            )
            .checked(app.autolaunch().is_enabled().unwrap_or(false))
            .build(app)?;
            let mut menu_builder = MenuBuilder::new(app)
                .text("open", "Abrir / Open")
                .text("new-chat", "Novo chat / New chat")
                .text("hide", "Esconder / Hide")
                .separator()
                .item(&auto_item);
            if can_self_update() {
                menu_builder =
                    menu_builder.text("update", "Procurar atualizações / Check for updates");
            }
            let menu = menu_builder
                .text("reload", "Recarregar / Reload")
                .text("server", "Mudar servidor / Change server")
                .text("github", "GitHub")
                .separator()
                .text("exit", "Sair / Quit")
                .build()?;
            TrayIconBuilder::new()
                .icon(app.default_window_icon().ok_or("Ícone em falta")?.clone())
                .tooltip("Odysseus")
                .menu(&menu)
                .show_menu_on_left_click(false)
                .on_menu_event(move |app, event| {
                    let id = event.id.as_ref();
                    act(app, id);
                    if id == "autostart" {
                        let _ = auto_item.set_checked(app.autolaunch().is_enabled().unwrap_or(false));
                    }
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event
                    {
                        show(tray.app_handle(), true);
                    }
                })
                .build(app)?;
            if app.global_shortcut().register("Ctrl+Alt+O").is_err() {
                eprintln!("Atalho indisponível / Shortcut unavailable");
            }
            // Verificação silenciosa no arranque apenas em instalações auto-atualizáveis (Windows / AppImage).
            if can_self_update() {
                let upd = handle.clone();
                tauri::async_runtime::spawn(async move {
                    tokio::time::sleep(Duration::from_secs(8)).await;
                    let st = upd.state::<St>();
                    if let Ok(v) = check_update(upd.clone(), st).await {
                        if v["available"] == true {
                            open_update_window(&upd);
                        }
                    }
                });
            }
            let hiding = window.clone();
            window.on_window_event(move |event| {
                if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                    if !hiding
                        .app_handle()
                        .state::<St>()
                        .quitting
                        .load(std::sync::atomic::Ordering::SeqCst)
                    {
                        api.prevent_close();
                        hide_to_tray(&hiding);
                    }
                }
            });
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("Falha ao iniciar Odysseus");
}
