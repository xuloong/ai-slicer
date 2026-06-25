fn main() {
    tauri_build::try_build(
        tauri_build::Attributes::new().app_manifest(
            tauri_build::AppManifest::new()
                .commands(&["check_for_update", "install_update_if_available"]),
        ),
    )
    .expect("failed to run tauri build script")
}
