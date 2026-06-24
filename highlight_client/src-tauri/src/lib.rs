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
