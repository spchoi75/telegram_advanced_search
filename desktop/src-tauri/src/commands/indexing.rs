use serde::{Deserialize, Serialize};
use std::sync::atomic::{AtomicBool, AtomicU32, Ordering};
use std::sync::Arc;
use tauri::{AppHandle, Emitter};
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::{Child, Command as AsyncCommand};
use tokio::sync::Mutex;

use super::chat_list::get_project_root;

// Global state for process management
static INDEXING_IN_PROGRESS: AtomicBool = AtomicBool::new(false);
static SYNC_IN_PROGRESS: AtomicBool = AtomicBool::new(false);
static CURRENT_INDEXING_PID: AtomicU32 = AtomicU32::new(0);
static CURRENT_SYNC_PID: AtomicU32 = AtomicU32::new(0);

lazy_static::lazy_static! {
    static ref INDEXING_CHILD: Arc<Mutex<Option<Child>>> = Arc::new(Mutex::new(None));
    static ref SYNC_CHILD: Arc<Mutex<Option<Child>>> = Arc::new(Mutex::new(None));
}

// ============================================================
// Progress Structures
// ============================================================

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IndexingProgress {
    pub status: String,           // "progress" | "completed" | "error" | "cancelled" | "info"
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub current: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub total: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub percentage: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub elapsed_sec: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub eta_sec: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rate: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rolled_back: Option<i64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SyncProgress {
    pub status: String,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub current: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub total: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub percentage: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub elapsed_sec: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub eta_sec: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rolled_back: Option<i64>,
}

// Python JSON output structure
#[derive(Debug, Deserialize)]
struct PythonProgress {
    #[serde(rename = "type")]
    progress_type: String,
    message: Option<String>,
    current: Option<i64>,
    total: Option<i64>,
    percentage: Option<i32>,
    elapsed_sec: Option<i64>,
    eta_sec: Option<i64>,
    rate: Option<f64>,
    rolled_back: Option<i64>,
    #[serde(rename = "collected")]
    _collected: Option<i64>,
}

// ============================================================
// Indexing Commands
// ============================================================

#[tauri::command]
pub async fn start_indexing(
    app: AppHandle,
    chat_id: i64,
    years: Option<i32>,
) -> Result<String, String> {
    if INDEXING_IN_PROGRESS.load(Ordering::SeqCst) {
        return Err("인덱싱이 이미 진행 중입니다.".to_string());
    }

    INDEXING_IN_PROGRESS.store(true, Ordering::SeqCst);

    let project_root = get_project_root().map_err(|e| {
        INDEXING_IN_PROGRESS.store(false, Ordering::SeqCst);
        e
    })?;

    let years_arg = years.unwrap_or(3);

    let mut child = AsyncCommand::new("python3")
        .arg("indexer.py")
        .arg("--chat-id")
        .arg(chat_id.to_string())
        .arg("--years")
        .arg(years_arg.to_string())
        .arg("--json-progress")
        .current_dir(&project_root)
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()
        .map_err(|e| {
            INDEXING_IN_PROGRESS.store(false, Ordering::SeqCst);
            format!("Failed to start indexer.py: {}", e)
        })?;

    // Store PID for cancellation
    if let Some(pid) = child.id() {
        CURRENT_INDEXING_PID.store(pid, Ordering::SeqCst);
    }

    let stdout = child.stdout.take().ok_or("Failed to capture stdout")?;
    let stderr = child.stderr.take().ok_or("Failed to capture stderr")?;

    // Store child for cancellation
    {
        let mut guard = INDEXING_CHILD.lock().await;
        *guard = Some(child);
    }

    let mut stdout_reader = BufReader::new(stdout).lines();
    let mut stderr_reader = BufReader::new(stderr).lines();

    let app_clone = app.clone();
    let app_for_stderr = app.clone();

    // stderr handler
    let error_messages = Arc::new(Mutex::new(Vec::<String>::new()));
    let error_messages_clone = error_messages.clone();

    tokio::spawn(async move {
        while let Ok(Some(line)) = stderr_reader.next_line().await {
            error_messages_clone.lock().await.push(line.clone());
            let progress = IndexingProgress {
                status: "progress".to_string(),
                message: format!("[stderr] {}", line),
                current: None,
                total: None,
                percentage: None,
                elapsed_sec: None,
                eta_sec: None,
                rate: None,
                rolled_back: None,
            };
            let _ = app_for_stderr.emit("indexing-progress", progress);
        }
    });

    // stdout handler - parse JSON progress
    tokio::spawn(async move {
        while let Ok(Some(line)) = stdout_reader.next_line().await {
            let progress = parse_indexing_progress(&line);
            let _ = app_clone.emit("indexing-progress", progress);
        }

        // Wait for child to complete
        tokio::time::sleep(std::time::Duration::from_millis(100)).await;

        let mut guard = INDEXING_CHILD.lock().await;
        if let Some(mut child) = guard.take() {
            let status = child.wait().await;
            let errors = error_messages.lock().await;

            let final_status = match status {
                Ok(s) if s.success() => IndexingProgress {
                    status: "completed".to_string(),
                    message: "인덱싱이 완료되었습니다.".to_string(),
                    current: None,
                    total: None,
                    percentage: Some(100),
                    elapsed_sec: None,
                    eta_sec: None,
                    rate: None,
                    rolled_back: None,
                },
                Ok(s) if s.code() == Some(130) => IndexingProgress {
                    status: "cancelled".to_string(),
                    message: "인덱싱이 취소되었습니다.".to_string(),
                    current: None,
                    total: None,
                    percentage: None,
                    elapsed_sec: None,
                    eta_sec: None,
                    rate: None,
                    rolled_back: None,
                },
                Ok(s) => {
                    let error_detail = if errors.is_empty() {
                        format!("종료 코드: {:?}", s.code())
                    } else {
                        errors.join("\n")
                    };
                    IndexingProgress {
                        status: "error".to_string(),
                        message: format!("인덱싱 실패: {}", error_detail),
                        current: None,
                        total: None,
                        percentage: None,
                        elapsed_sec: None,
                        eta_sec: None,
                        rate: None,
                        rolled_back: None,
                    }
                }
                Err(e) => IndexingProgress {
                    status: "error".to_string(),
                    message: format!("프로세스 오류: {}", e),
                    current: None,
                    total: None,
                    percentage: None,
                    elapsed_sec: None,
                    eta_sec: None,
                    rate: None,
                    rolled_back: None,
                },
            };
            let _ = app_clone.emit("indexing-progress", final_status);
        }

        INDEXING_IN_PROGRESS.store(false, Ordering::SeqCst);
        CURRENT_INDEXING_PID.store(0, Ordering::SeqCst);
    });

    Ok("인덱싱을 시작했습니다.".to_string())
}

fn parse_indexing_progress(line: &str) -> IndexingProgress {
    // Try to parse as JSON first
    if let Ok(python_progress) = serde_json::from_str::<PythonProgress>(line) {
        let status = match python_progress.progress_type.as_str() {
            "complete" => "completed",
            "cancelled" => "cancelled",
            "error" => "error",
            "rolling_back" => "rolling_back",
            "cancelling" => "cancelling",
            _ => "progress",
        };

        return IndexingProgress {
            status: status.to_string(),
            message: python_progress.message.unwrap_or_default(),
            current: python_progress.current,
            total: python_progress.total,
            percentage: python_progress.percentage,
            elapsed_sec: python_progress.elapsed_sec,
            eta_sec: python_progress.eta_sec,
            rate: python_progress.rate,
            rolled_back: python_progress.rolled_back,
        };
    }

    // Fallback: parse as plain text (legacy compatibility)
    let collected = if line.contains("Collected") {
        line.split_whitespace()
            .find(|s| s.parse::<i64>().is_ok())
            .and_then(|s| s.parse().ok())
    } else {
        None
    };

    IndexingProgress {
        status: "progress".to_string(),
        message: line.to_string(),
        current: collected,
        total: None,
        percentage: None,
        elapsed_sec: None,
        eta_sec: None,
        rate: None,
        rolled_back: None,
    }
}

#[tauri::command]
pub fn is_indexing() -> bool {
    INDEXING_IN_PROGRESS.load(Ordering::SeqCst)
}

#[tauri::command]
pub async fn cancel_indexing() -> Result<String, String> {
    if !INDEXING_IN_PROGRESS.load(Ordering::SeqCst) {
        return Err("진행 중인 인덱싱이 없습니다.".to_string());
    }

    let mut guard = INDEXING_CHILD.lock().await;
    if let Some(ref mut child) = *guard {
        // Send SIGTERM to allow graceful shutdown
        child.kill().await.map_err(|e| format!("Failed to cancel: {}", e))?;
    }

    Ok("인덱싱 취소 요청을 보냈습니다.".to_string())
}

// ============================================================
// Sync Commands
// ============================================================

#[tauri::command]
pub async fn run_sync(app: AppHandle) -> Result<String, String> {
    if SYNC_IN_PROGRESS.load(Ordering::SeqCst) {
        return Err("동기화가 이미 진행 중입니다.".to_string());
    }

    SYNC_IN_PROGRESS.store(true, Ordering::SeqCst);

    let project_root = get_project_root().map_err(|e| {
        SYNC_IN_PROGRESS.store(false, Ordering::SeqCst);
        e
    })?;

    let mut child = AsyncCommand::new("python3")
        .arg("sync.py")
        .arg("--json-progress")
        .current_dir(&project_root)
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()
        .map_err(|e| {
            SYNC_IN_PROGRESS.store(false, Ordering::SeqCst);
            format!("Failed to start sync.py: {}", e)
        })?;

    // Store PID for cancellation
    if let Some(pid) = child.id() {
        CURRENT_SYNC_PID.store(pid, Ordering::SeqCst);
    }

    let stdout = child.stdout.take().ok_or("Failed to capture stdout")?;
    let stderr = child.stderr.take().ok_or("Failed to capture stderr")?;

    // Store child for cancellation
    {
        let mut guard = SYNC_CHILD.lock().await;
        *guard = Some(child);
    }

    let mut stdout_reader = BufReader::new(stdout).lines();
    let mut stderr_reader = BufReader::new(stderr).lines();

    let app_clone = app.clone();

    // stderr handler
    let error_messages = Arc::new(Mutex::new(Vec::<String>::new()));
    let error_messages_clone = error_messages.clone();

    tokio::spawn(async move {
        while let Ok(Some(line)) = stderr_reader.next_line().await {
            error_messages_clone.lock().await.push(line.clone());
        }
    });

    // stdout handler - parse JSON progress
    tokio::spawn(async move {
        while let Ok(Some(line)) = stdout_reader.next_line().await {
            let progress = parse_sync_progress(&line);
            let _ = app_clone.emit("sync-progress", progress);
        }

        // Wait for child to complete
        tokio::time::sleep(std::time::Duration::from_millis(100)).await;

        let mut guard = SYNC_CHILD.lock().await;
        if let Some(mut child) = guard.take() {
            let status = child.wait().await;
            let errors = error_messages.lock().await;

            let final_status = match status {
                Ok(s) if s.success() => SyncProgress {
                    status: "completed".to_string(),
                    message: "동기화가 완료되었습니다.".to_string(),
                    current: None,
                    total: None,
                    percentage: Some(100),
                    elapsed_sec: None,
                    eta_sec: None,
                    rolled_back: None,
                },
                Ok(s) if s.code() == Some(130) => SyncProgress {
                    status: "cancelled".to_string(),
                    message: "동기화가 취소되었습니다.".to_string(),
                    current: None,
                    total: None,
                    percentage: None,
                    elapsed_sec: None,
                    eta_sec: None,
                    rolled_back: None,
                },
                Ok(s) => {
                    let error_detail = if errors.is_empty() {
                        format!("종료 코드: {:?}", s.code())
                    } else {
                        errors.join("\n")
                    };
                    SyncProgress {
                        status: "error".to_string(),
                        message: format!("동기화 실패: {}", error_detail),
                        current: None,
                        total: None,
                        percentage: None,
                        elapsed_sec: None,
                        eta_sec: None,
                        rolled_back: None,
                    }
                }
                Err(e) => SyncProgress {
                    status: "error".to_string(),
                    message: format!("프로세스 오류: {}", e),
                    current: None,
                    total: None,
                    percentage: None,
                    elapsed_sec: None,
                    eta_sec: None,
                    rolled_back: None,
                },
            };
            let _ = app_clone.emit("sync-progress", final_status);
        }

        SYNC_IN_PROGRESS.store(false, Ordering::SeqCst);
        CURRENT_SYNC_PID.store(0, Ordering::SeqCst);
    });

    Ok("동기화를 시작했습니다.".to_string())
}

fn parse_sync_progress(line: &str) -> SyncProgress {
    // Try to parse as JSON
    if let Ok(python_progress) = serde_json::from_str::<PythonProgress>(line) {
        let status = match python_progress.progress_type.as_str() {
            "complete" => "completed",
            "cancelled" => "cancelled",
            "error" => "error",
            "rolling_back" => "rolling_back",
            "start" => "start",
            "info" => "info",
            _ => "progress",
        };

        return SyncProgress {
            status: status.to_string(),
            message: python_progress.message.unwrap_or_default(),
            current: python_progress.current,
            total: python_progress.total,
            percentage: python_progress.percentage,
            elapsed_sec: python_progress.elapsed_sec,
            eta_sec: python_progress.eta_sec,
            rolled_back: python_progress.rolled_back,
        };
    }

    // Fallback: plain text
    SyncProgress {
        status: "progress".to_string(),
        message: line.to_string(),
        current: None,
        total: None,
        percentage: None,
        elapsed_sec: None,
        eta_sec: None,
        rolled_back: None,
    }
}

#[tauri::command]
pub fn is_syncing() -> bool {
    SYNC_IN_PROGRESS.load(Ordering::SeqCst)
}

#[tauri::command]
pub async fn cancel_sync() -> Result<String, String> {
    if !SYNC_IN_PROGRESS.load(Ordering::SeqCst) {
        return Err("진행 중인 동기화가 없습니다.".to_string());
    }

    let mut guard = SYNC_CHILD.lock().await;
    if let Some(ref mut child) = *guard {
        child.kill().await.map_err(|e| format!("Failed to cancel: {}", e))?;
    }

    Ok("동기화 취소 요청을 보냈습니다.".to_string())
}
