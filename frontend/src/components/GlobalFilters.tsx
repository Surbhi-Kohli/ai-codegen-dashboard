import { useState } from "react";
import type { ApiFilters } from "../api/types";

interface Props {
  filters: ApiFilters;
  onChange: (filters: ApiFilters) => void;
}

export default function GlobalFilters({ filters, onChange }: Props) {
  const [start, setStart] = useState(filters.start_date ?? "");
  const [end, setEnd] = useState(filters.end_date ?? "");

  function apply() {
    onChange({
      ...filters,
      start_date: start || undefined,
      end_date: end || undefined,
    });
  }

  return (
    <div className="flex items-center gap-3 text-sm">
      <label className="text-gray-400">From</label>
      <input
        type="date"
        value={start}
        onChange={(e) => setStart(e.target.value)}
        className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-gray-200"
      />
      <label className="text-gray-400">To</label>
      <input
        type="date"
        value={end}
        onChange={(e) => setEnd(e.target.value)}
        className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-gray-200"
      />
      <button
        onClick={apply}
        className="bg-brand-500 hover:bg-brand-600 text-white px-3 py-1 rounded text-sm"
      >
        Apply
      </button>
    </div>
  );
}
