import { openUrl } from "@tauri-apps/plugin-opener";

interface SearchResult {
  id: number;
  chat_id: number;
  date: string;
  text: string;
  link: string;
}

interface Props {
  results: SearchResult[];
  count: number;
  elapsedMs: number;
  error: string | null;
}

export function ResultList({ results, count, elapsedMs, error }: Props) {
  const handleResultClick = async (link: string) => {
    try {
      await openUrl(link);
    } catch (e) {
      console.error("Failed to open link:", e);
    }
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleString("ko-KR", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const highlightText = (text: string, maxLength: number = 200) => {
    if (text.length > maxLength) {
      return text.substring(0, maxLength) + "...";
    }
    return text;
  };

  if (error) {
    return <div className="result-error">{error}</div>;
  }

  if (results.length === 0) {
    return null;
  }

  return (
    <div className="result-list">
      <div className="result-summary">
        {count}개 결과 ({elapsedMs.toFixed(1)}ms)
      </div>

      <div className="results">
        {results.map((result, index) => (
          <div
            key={result.id}
            className="result-item"
            onClick={() => handleResultClick(result.link)}
          >
            <div className="result-header">
              <span className="result-index">[{index + 1}]</span>
              <span className="result-date">{formatDate(result.date)}</span>
            </div>
            <div className="result-text">{highlightText(result.text)}</div>
            <div className="result-link">{result.link}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
