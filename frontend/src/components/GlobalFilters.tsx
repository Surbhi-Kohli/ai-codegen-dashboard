import { useEffect, useState } from "react";
import type { ApiFilters } from "../api/types";
import { fetchBoards } from "../api/client";

interface Props {
  filters: ApiFilters;
  onChange: (filters: ApiFilters) => void;
}

export default function GlobalFilters({ filters, onChange }: Props) {
  const [start, setStart] = useState(filters.start_date ?? "");
  const [end, setEnd] = useState(filters.end_date ?? "");
  const [boards, setBoards] = useState<{ key: string; issue_count: number }[]>([]);
  const [selectedBoard, setSelectedBoard] = useState(filters.project ?? "");

  useEffect(() => {
    fetchBoards().then(setBoards);
  }, []);

  function handleBoardChange(value: string) {
    setSelectedBoard(value);
    onChange({ ...filters, project: value || undefined });
  }

  const dateError =
    start && end && end < start ? "End date must be after start date" : "";

  function apply() {
    if (dateError) return;
    onChange({
      ...filters,
      start_date: start || undefined,
      end_date: end || undefined,
      project: selectedBoard || undefined,
    });
  }

  return (
    <div className="flex items-center gap-3 text-sm">
      <label className="text-gray-400">Board</label>
      <select
        value={selectedBoard}
        onChange={(e) => handleBoardChange(e.target.value)}
        className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-gray-200"
      >
        <option value="">All Teams</option>
        {boards.map((b) => (
          <option key={b.key} value={b.key}>
            {b.key} ({b.issue_count})
          </option>
        ))}
      </select>

      <span className="mx-1 text-gray-700">|</span>

      <label className="text-gray-400">From</label>
      <input
        type="date"
        value={start}
        max={end || undefined}
        onChange={(e) => setStart(e.target.value)}
        className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-gray-200"
      />
      <label className="text-gray-400">To</label>
      <input
        type="date"
        value={end}
        min={start || undefined}
        onChange={(e) => setEnd(e.target.value)}
        className={`bg-gray-800 border rounded px-2 py-1 text-gray-200 ${dateError ? "border-red-500" : "border-gray-700"
          }`}
      />
      {dateError && (
        <span className="text-red-400 text-xs">{dateError}</span>
      )}
      <button
        onClick={apply}
        disabled={!!dateError}
        className={`px-3 py-1 rounded text-sm text-white ${dateError
            ? "bg-gray-600 cursor-not-allowed"
            : "bg-brand-500 hover:bg-brand-600"
          }`}
      >
        Apply
      </button>
    </div>
  );
}
