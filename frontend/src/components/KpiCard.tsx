interface Props {
  label: string;
  value: string;
  subtitle?: string;
}

export default function KpiCard({ label, value, subtitle }: Props) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
      <p className="text-xs text-gray-400 uppercase tracking-wider mb-1">{label}</p>
      <p className="text-2xl font-bold text-white">{value}</p>
      {subtitle && <p className="text-xs text-gray-500 mt-1">{subtitle}</p>}
    </div>
  );
}
