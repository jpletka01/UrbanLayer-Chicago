import { CountUp } from "../CountUp";

interface Props {
  label: string;
  value: number;
  format?: (n: number) => string;
  subtitle?: string;
  trend?: number | null;
}

export function StatCard({ label, value, format, subtitle, trend }: Props) {
  return (
    <div className="bg-dark-surface border border-dark-border rounded-xl p-6">
      <div className="text-xs text-text-muted uppercase tracking-wider mb-2">
        {label}
      </div>
      <CountUp
        to={value}
        format={format}
        className="text-3xl font-semibold text-text-primary"
      />
      {trend != null && trend !== 0 && (
        <div
          className={`text-xs mt-1 ${
            trend > 0 ? "text-emerald-400" : "text-rose-400"
          }`}
        >
          {trend > 0 ? "+" : ""}
          {trend.toFixed(1)}% from prior period
        </div>
      )}
      {subtitle && (
        <div className="text-xs text-text-muted mt-1">{subtitle}</div>
      )}
    </div>
  );
}
