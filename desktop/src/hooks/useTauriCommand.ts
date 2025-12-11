import { invoke } from "@tauri-apps/api/core";
import { useState, useCallback } from "react";

interface UseCommandResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  execute: (...args: unknown[]) => Promise<T | null>;
}

export function useTauriCommand<T>(commandName: string): UseCommandResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const execute = useCallback(
    async (...args: unknown[]): Promise<T | null> => {
      setLoading(true);
      setError(null);
      try {
        const result = await invoke<T>(commandName, args[0] as Record<string, unknown> || {});
        setData(result);
        return result;
      } catch (e) {
        const errorMessage = e instanceof Error ? e.message : String(e);
        setError(errorMessage);
        return null;
      } finally {
        setLoading(false);
      }
    },
    [commandName]
  );

  return { data, loading, error, execute };
}
