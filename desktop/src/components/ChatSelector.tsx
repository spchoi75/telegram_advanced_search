import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

interface Chat {
  id: number;
  name: string;
  type: string;
}

interface ChatListResponse {
  chats: Chat[];
}

interface Props {
  value: number | null;
  onChange: (chatId: number | null) => void;
}

export function ChatSelector({ value, onChange }: Props) {
  const [chats, setChats] = useState<Chat[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadChats();
  }, []);

  const loadChats = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await invoke<ChatListResponse>("get_chat_list");
      setChats(response.chats);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const getTypeLabel = (type: string) => {
    switch (type) {
      case "user":
        return "개인";
      case "group":
        return "그룹";
      case "supergroup":
        return "슈퍼그룹";
      case "channel":
        return "채널";
      default:
        return type;
    }
  };

  return (
    <div className="chat-selector">
      <label>채팅방</label>
      <select
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}
        disabled={loading}
      >
        <option value="">전체</option>
        {chats.map((chat) => (
          <option key={chat.id} value={chat.id}>
            [{getTypeLabel(chat.type)}] {chat.name}
          </option>
        ))}
      </select>
      {loading && <span className="loading-indicator">로딩 중...</span>}
      {error && <span className="error-text">{error}</span>}
      <button onClick={loadChats} disabled={loading} className="refresh-btn">
        새로고침
      </button>
    </div>
  );
}
