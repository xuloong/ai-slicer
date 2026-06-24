use std::io::{Read, Write};
use std::net::{TcpStream, ToSocketAddrs};
use std::process::Command;
use std::time::Duration;

const SERVER_PORT: u16 = 8765;

fn server_matches_current_version(port: u16) -> bool {
    let Ok(mut addrs) = ("127.0.0.1", port).to_socket_addrs() else {
        return false;
    };
    let Some(addr) = addrs.next() else {
        return false;
    };
    let Ok(mut stream) = TcpStream::connect_timeout(&addr, Duration::from_millis(250)) else {
        return false;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_millis(500)));
    let request = format!(
        "GET /api/config HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n\r\n"
    );
    if stream.write_all(request.as_bytes()).is_err() {
        return false;
    }
    let mut response = String::new();
    if stream.read_to_string(&mut response).is_err() {
        return false;
    }
    let version_marker = format!("\"version\":\"{}\"", env!("CARGO_PKG_VERSION"));
    let spaced_version_marker = format!("\"version\": \"{}\"", env!("CARGO_PKG_VERSION"));
    response.contains(&version_marker) || response.contains(&spaced_version_marker)
}

#[cfg(target_os = "windows")]
fn pids_listening_on_port(port: u16) -> Vec<u32> {
    let Ok(output) = Command::new("cmd")
        .args(["/C", "netstat -ano -p tcp"])
        .output()
    else {
        return Vec::new();
    };
    let text = String::from_utf8_lossy(&output.stdout);
    text.lines()
        .filter(|line| line.contains(&format!(":{}", port)) && line.contains("LISTENING"))
        .filter_map(|line| line.split_whitespace().last()?.parse::<u32>().ok())
        .filter(|pid| *pid != std::process::id())
        .collect()
}

#[cfg(not(target_os = "windows"))]
fn pids_listening_on_port(port: u16) -> Vec<u32> {
    let Ok(output) = Command::new("lsof")
        .args(["-ti", &format!("tcp:{}", port)])
        .output()
    else {
        return Vec::new();
    };
    String::from_utf8_lossy(&output.stdout)
        .lines()
        .filter_map(|line| line.trim().parse::<u32>().ok())
        .filter(|pid| *pid != std::process::id())
        .collect()
}

fn stop_stale_server(port: u16) {
    if server_matches_current_version(port) {
        return;
    }
    let pids = pids_listening_on_port(port);
    for pid in pids {
        #[cfg(target_os = "windows")]
        let _ = Command::new("taskkill")
            .args(["/PID", &pid.to_string(), "/F"])
            .output();

        #[cfg(not(target_os = "windows"))]
        let _ = Command::new("kill").args(["-TERM", &pid.to_string()]).output();
    }
    std::thread::sleep(Duration::from_millis(500));
}

#[tauri::command]
async fn check_for_update(app: tauri::AppHandle) -> Result<Option<String>, String> {
    use tauri_plugin_updater::UpdaterExt;

    let update = app
        .updater()
        .map_err(|error| error.to_string())?
        .check()
        .await
        .map_err(|error| error.to_string())?;
    Ok(update.map(|item| item.version))
}

#[tauri::command]
async fn install_update_if_available(app: tauri::AppHandle) -> Result<String, String> {
    use tauri_plugin_updater::UpdaterExt;

    let Some(update) = app
        .updater()
        .map_err(|error| error.to_string())?
        .check()
        .await
        .map_err(|error| error.to_string())?
    else {
        return Ok("当前已是最新版本".to_string());
    };

    update
        .download_and_install(|_, _| {}, || {})
        .await
        .map_err(|error| error.to_string())?;
    app.restart()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .setup(|app| {
            use tauri_plugin_shell::ShellExt;

            #[cfg(not(debug_assertions))]
            stop_stale_server(SERVER_PORT);

            // In packaged builds this starts the PyInstaller sidecar API server.
            // In development, beforeDevCommand starts `python3 server.py`, so a
            // missing sidecar here is harmless.
            if let Ok(command) = app.shell().sidecar("highlight-server") {
                let _ = command.spawn();
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            check_for_update,
            install_update_if_available
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
