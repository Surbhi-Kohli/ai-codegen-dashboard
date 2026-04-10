import { useState } from "react";

interface Props {
  label: string;
  value: string;
  subtitle?: string;
  tooltip?: string;
}

export default function KpiCard({ label, value, subtitle, tooltip }: Props) {
  const [showTooltip, setShowTooltip] = useState(false);

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-5 relative">
      <div className="flex items-center gap-1.5 mb-1">
        <p className="text-xs text-gray-400 uppercase tracking-wider">{label}</p>
        {tooltip && (
          <button
            className="text-gray-500 hover:text-gray-300 transition-colors"
            onMouseEnter={() => setShowTooltip(true)}
            onMouseLeave={() => setShowTooltip(false)}
            onClick={() => setShowTooltip((v) => !v)}
            aria-label={`How ${label} is calculated`}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 20 20"
              fill="currentColor"
              className="w-3.5 h-3.5"
            >
              <path
                fillRule="evenodd"
                d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a.75.75 0 000 1.5h.253a.25.25 0 01.244.304l-.459 2.066A1.75 1.75 0 0010.747 15H11a.75.75 0 000-1.5h-.253a.25.25 0 01-.244-.304l.459-2.066A1.75 1.75 0 009.253 9H9z"
                clipRule="evenodd"
              />
            </svg>
          </button>
        )}
      </div>
      <p className="text-2xl font-bold text-white">{value}</p>
      {subtitle && <p className="text-xs text-gray-500 mt-1">{subtitle}</p>}

      {tooltip && showTooltip && (
        <div className="absolute z-10 left-0 right-0 top-full mt-1 bg-gray-800 border border-gray-700 rounded-lg p-3 shadow-xl text-xs text-gray-300 leading-relaxed whitespace-pre-line">
          {tooltip}
        </div>
      )}
    </div>
  );
}
