import { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

interface IndexingProgress {
  status: string;
  message: string;
  current?: number;
  total?: number;
  percentage?: number;
  elapsed_sec?: number;
  eta_sec?: number;
  rate?: number;
  rolled_back?: number;
}

interface SyncProgress {
  status: string;
  message: string;
  current?: number;
  total?: number;
  percentage?: number;
  elapsed_sec?: number;
  eta_sec?: number;
  rolled_back?: number;
}

interface Props {
  selectedChatId: number | null;
}

function formatTime(seconds: number): string {
  if (seconds < 60) return `${seconds}초`;
  const minutes = Math.floor(seconds / 60);
  const secs = seconds % 60;
  if (minutes < 60) return `${minutes}분 ${secs}초`;
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return `${hours}시간 ${mins}분`;
}

export function IndexingPanel({ selectedChatId }: Props) {
  // Indexing state
  const [isIndexing, setIsIndexing] = useState(false);
  const [indexingProgress, setIndexingProgress] = useState<IndexingProgress | null>(null);
  const [years, setYears] = useState<number>(3);

  // Sync state
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncProgress, setSyncProgress] = useState<SyncProgress | null>(null);

  // Error state
  const [error, setError] = useState<string | null>(null);

  // Listen for indexing progress
  useEffect(() => {
    const unlisten = listen<IndexingProgress>("indexing-progress", (event) => {
      const data = event.payload;
      setIndexingProgress(data);

      if (data.status === "completed" || data.status === "error" || data.status === "cancelled") {
        setIsIndexing(false);
        if (data.status === "error") {
          setError(data.message);
        }
        if (data.status === "cancelled" && data.rolled_back) {
          setError(`취소됨: ${data.rolled_back}개 메시지 롤백됨`);
        }
      }
    });

    return () => {
      unlisten.then((fn) => fn());
    };
  }, []);

  // Listen for sync progress
  useEffect(() => {
    const unlisten = listen<SyncProgress>("sync-progress", (event) => {
      const data = event.payload;
      setSyncProgress(data);

      if (data.status === "completed" || data.status === "error" || data.status === "cancelled") {
        setIsSyncing(false);
        if (data.status === "error") {
          setError(data.message);
        }
        if (data.status === "cancelled" && data.rolled_back) {
          setError(`취소됨: ${data.rolled_back}개 메시지 롤백됨`);
        }
      }
    });

    return () => {
      unlisten.then((fn) => fn());
    };
  }, []);

  const startIndexing = async () => {
    if (!selectedChatId) {
      setError("채팅방을 선택해주세요.");
      return;
    }

    setIsIndexing(true);
    setError(null);
    setIndexingProgress({ status: "start", message: "인덱싱 시작 중..." });

    try {
      await invoke("start_indexing", {
        chatId: selectedChatId,
        years,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setIsIndexing(false);
    }
  };

  const cancelIndexing = async () => {
    try {
      await invoke("cancel_indexing");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const runSync = async () => {
    setIsSyncing(true);
    setError(null);
    setSyncProgress({ status: "start", message: "동기화 시작 중..." });

    try {
      await invoke("run_sync");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setIsSyncing(false);
    }
  };

  const cancelSync = async () => {
    try {
      await invoke("cancel_sync");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const renderProgressBar = (
    progress: IndexingProgress | SyncProgress | null,
    isRunning: boolean,
    onCancel: () => void,
    label: string
  ) => {
    if (!isRunning || !progress) return null;

    const percentage = progress.percentage ?? (progress.current && progress.total
      ? Math.round((progress.current / progress.total) * 100)
      : null);

    return (
      <div className="progress-section">
        <div className="progress-header">
          <span className="progress-label">{label}</span>
          <button onClick={onCancel} className="cancel-btn">
            취소
          </button>
        </div>

        <div className="progress-bar">
          <div
            className="progress-fill"
            style={{ width: percentage !== null ? `${percentage}%` : "100%" }}
          />
        </div>

        <div className="progress-details">
          <span className="progress-message">{progress.message}</span>

          <div className="progress-stats">
            {progress.current !== undefined && (
              <span>
                {progress.current.toLocaleString()}
                {progress.total ? ` / ${progress.total.toLocaleString()}` : ""} 메시지
              </span>
            )}

            {percentage !== null && (
              <span className="progress-percentage">{percentage}%</span>
            )}

            {progress.elapsed_sec !== undefined && (
              <span>경과: {formatTime(progress.elapsed_sec)}</span>
            )}

            {progress.eta_sec !== undefined && progress.eta_sec > 0 && (
              <span>남은 시간: ~{formatTime(progress.eta_sec)}</span>
            )}

            {(progress as IndexingProgress).rate !== undefined && (
              <span>{(progress as IndexingProgress).rate?.toFixed(1)} msg/s</span>
            )}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="indexing-panel">
      <h3>인덱싱</h3>

      <div className="indexing-options">
        <label>
          수집 기간 (년)
          <select
            value={years}
            onChange={(e) => setYears(Number(e.target.value))}
            disabled={isIndexing}
          >
            <option value={1}>1년</option>
            <option value={2}>2년</option>
            <option value={3}>3년</option>
            <option value={5}>5년</option>
          </select>
        </label>
      </div>

      <div className="indexing-buttons">
        <button
          onClick={startIndexing}
          disabled={isIndexing || isSyncing || !selectedChatId}
          className="primary-btn"
        >
          {isIndexing ? "인덱싱 중..." : "인덱싱 시작"}
        </button>
        <button
          onClick={runSync}
          disabled={isIndexing || isSyncing}
          className="secondary-btn"
        >
          {isSyncing ? "동기화 중..." : "Supabase 동기화"}
        </button>
      </div>

      {renderProgressBar(indexingProgress, isIndexing, cancelIndexing, "인덱싱")}
      {renderProgressBar(syncProgress, isSyncing, cancelSync, "동기화")}

      {error && <p className="error-text">{error}</p>}
    </div>
  );
}
