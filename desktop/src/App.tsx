import { useState } from "react";
import { ChatSelector } from "./components/ChatSelector";
import { IndexingPanel } from "./components/IndexingPanel";
import { SearchBar } from "./components/SearchBar";
import { SearchOptions } from "./components/SearchOptions";
import { ResultList } from "./components/ResultList";
import { useSearch } from "./hooks/useSearch";
import "./App.css";

function App() {
  const [selectedChatId, setSelectedChatId] = useState<number | null>(null);
  const [limit, setLimit] = useState(20);
  const { results, count, elapsedMs, loading, error, search } = useSearch();

  const handleSearch = (query: string) => {
    search(query, limit, selectedChatId ?? undefined);
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <h1>TeleSearch-KR</h1>
        <p className="subtitle">Telegram 한국어 메시지 검색</p>
      </header>

      <main className="app-main">
        <section className="settings-section">
          <ChatSelector value={selectedChatId} onChange={setSelectedChatId} />
          <IndexingPanel selectedChatId={selectedChatId} />
        </section>

        <hr className="divider" />

        <section className="search-section">
          <SearchBar onSearch={handleSearch} loading={loading} />
          <SearchOptions limit={limit} onLimitChange={setLimit} />
        </section>

        <section className="results-section">
          <ResultList
            results={results}
            count={count}
            elapsedMs={elapsedMs}
            error={error}
          />
        </section>
      </main>
    </div>
  );
}

export default App;
