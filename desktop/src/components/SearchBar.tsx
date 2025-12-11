import { useState, useEffect, useRef, KeyboardEvent } from "react";

interface Props {
  onSearch: (query: string) => void;
  loading: boolean;
}

export function SearchBar({ onSearch, loading }: Props) {
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const handleKeyDown = (e: globalThis.KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const handleSubmit = () => {
    if (query.trim().length >= 3) {
      onSearch(query.trim());
    }
  };

  const handleKeyPress = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      handleSubmit();
    }
  };

  return (
    <div className="search-bar">
      <div className="search-input-wrapper">
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyPress}
          placeholder="검색어 입력 (최소 3글자)... Cmd+K"
          disabled={loading}
        />
        <button onClick={handleSubmit} disabled={loading || query.length < 3}>
          {loading ? "검색 중..." : "검색"}
        </button>
      </div>
      {query.length > 0 && query.length < 3 && (
        <p className="hint-text">검색어는 최소 3글자 이상이어야 합니다.</p>
      )}
    </div>
  );
}
