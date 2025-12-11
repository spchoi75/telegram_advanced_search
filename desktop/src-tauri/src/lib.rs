mod commands;

use commands::{
    get_chat_list,
    run_search,
    start_indexing,
    is_indexing,
    cancel_indexing,
    run_sync,
    is_syncing,
    cancel_sync,
};

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![
            get_chat_list,
            run_search,
            start_indexing,
            is_indexing,
            cancel_indexing,
            run_sync,
            is_syncing,
            cancel_sync,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
