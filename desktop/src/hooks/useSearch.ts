import { useState, useCallback } from "react";
import { invoke } from "@tauri-apps/api/core";

export interface SearchResult {
  id: number;
  chat_id: number;
  date: string;
  text: string;
  link: string;
}

export interface SearchResponse {
  count: number;
  elapsed_ms: number;
  results: SearchResult[];
}

interface UseSearchResult {
  results: SearchResult[];
  count: number;
  elapsedMs: number;
  loading: boolean;
  error: string | null;
  search: (query: string, limit?: number, chatId?: number) => Promise<void>;
  clear: () => void;
}

export function useSearch(): UseSearchResult {
  const [results, setResults] = useState<SearchResult[]>([]);
  const [count, setCount] = useState(0);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const search = useCallback(
    async (query: string, limit?: number, chatId?: number) => {
      if (query.length < 3) {
        setError("검색어는 최소 3글자 이상이어야 합니다.");
        return;
      }

      setLoading(true);
      setError(null);

      try {
        const response = await invoke<SearchResponse>("run_search", {
          query,
          limit: limit || 20,
          chatId: chatId || null,
        });
        setResults(response.results);
        setCount(response.count);
        setElapsedMs(response.elapsed_ms);
      } catch (e) {
        const errorMessage = e instanceof Error ? e.message : String(e);
        setError(errorMessage);
        setResults([]);
        setCount(0);
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const clear = useCallback(() => {
    setResults([]);
    setCount(0);
    setElapsedMs(0);
    setError(null);
  }, []);

  return { results, count, elapsedMs, loading, error, search, clear };
}
