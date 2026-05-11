#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
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
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
