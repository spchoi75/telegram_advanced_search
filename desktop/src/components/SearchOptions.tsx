interface Props {
  limit: number;
  onLimitChange: (limit: number) => void;
}

export function SearchOptions({ limit, onLimitChange }: Props) {
  return (
    <div className="search-options">
      <label>
        결과 수
        <select value={limit} onChange={(e) => onLimitChange(Number(e.target.value))}>
          <option value={10}>10개</option>
          <option value={20}>20개</option>
          <option value={50}>50개</option>
          <option value={100}>100개</option>
        </select>
      </label>
    </div>
  );
}
