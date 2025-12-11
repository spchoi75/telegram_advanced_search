use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use std::process::Command;

#[derive(Debug, Serialize, Deserialize)]
pub struct Chat {
    pub id: i64,
    pub name: String,
    #[serde(rename = "type")]
    pub chat_type: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ChatListResponse {
    pub chats: Vec<Chat>,
}

pub fn get_project_root() -> Result<PathBuf, String> {
    // 환경 변수 TELESEARCH_ROOT가 있으면 우선 사용
    if let Ok(root) = std::env::var("TELESEARCH_ROOT") {
        return Ok(PathBuf::from(root));
    }

    // 개발 모드: CARGO_MANIFEST_DIR 환경 변수 사용 (src-tauri 폴더)
    if let Ok(manifest_dir) = std::env::var("CARGO_MANIFEST_DIR") {
        let path = PathBuf::from(manifest_dir);
        // src-tauri -> desktop -> project_root
        if let Some(desktop) = path.parent() {
            if let Some(project_root) = desktop.parent() {
                if project_root.join("chat_list.py").exists() {
                    return Ok(project_root.to_path_buf());
                }
            }
        }
    }

    // 프로덕션 모드: 실행 파일 위치 기준으로 탐색
    if let Ok(exe_path) = std::env::current_exe() {
        let mut current = exe_path.clone();
        for _ in 0..6 {
            if let Some(parent) = current.parent() {
                current = parent.to_path_buf();
                if current.join("chat_list.py").exists() {
                    return Ok(current);
                }
            } else {
                break;
            }
        }
    }

    Err("Cannot find project root. Set TELESEARCH_ROOT environment variable.".to_string())
}

#[tauri::command]
pub async fn get_chat_list() -> Result<ChatListResponse, String> {
    let project_root = get_project_root()?;

    let output = Command::new("python3")
        .arg("chat_list.py")
        .arg("--format")
        .arg("json")
        .current_dir(&project_root)
        .output()
        .map_err(|e| format!("Failed to execute chat_list.py: {}", e))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("chat_list.py failed: {}", stderr));
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    let response: ChatListResponse = serde_json::from_str(&stdout)
        .map_err(|e| format!("Failed to parse JSON: {} - Output: {}", e, stdout))?;

    Ok(response)
}
