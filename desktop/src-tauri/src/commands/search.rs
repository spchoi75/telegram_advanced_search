use serde::{Deserialize, Serialize};
use std::process::Command;

use super::chat_list::get_project_root;

#[derive(Debug, Serialize, Deserialize)]
pub struct SearchResult {
    pub id: i64,
    pub chat_id: i64,
    pub date: String,
    pub text: String,
    pub link: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct SearchResponse {
    pub count: i32,
    pub elapsed_ms: f64,
    pub results: Vec<SearchResult>,
}

#[tauri::command]
pub async fn run_search(
    query: String,
    limit: Option<i32>,
    chat_id: Option<i64>,
) -> Result<SearchResponse, String> {
    if query.chars().count() < 3 {
        return Err("검색어는 최소 3글자 이상이어야 합니다.".to_string());
    }

    let project_root = get_project_root()?;

    let mut cmd = Command::new("python3");
    cmd.arg("searcher.py")
        .arg("--json")
        .arg(&query)
        .current_dir(&project_root);

    if let Some(l) = limit {
        cmd.arg("--limit").arg(l.to_string());
    }

    if let Some(cid) = chat_id {
        cmd.arg("--chat-id").arg(cid.to_string());
    }

    let output = cmd
        .output()
        .map_err(|e| format!("Failed to execute searcher.py: {}", e))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("searcher.py failed: {}", stderr));
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    let response: SearchResponse = serde_json::from_str(&stdout)
        .map_err(|e| format!("Failed to parse JSON: {} - Output: {}", e, stdout))?;

    Ok(response)
}
