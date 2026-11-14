import { CountUp } from "../../components/CountUp";

interface Props {
  label: string;
  value: number;
  format?: (n: number) => string;
  subtitle?: string;
  trend?: number | null;
}

export function StatCard({ label, value, format, subtitle, trend }: Props) {
  return (
    <div className="bg-nx-block border border-nx-ink/10 rounded-xl p-6">
      <div className="text-caption nx-muted uppercase tracking-wider mb-2">
        {label}
      </div>
      <CountUp
        to={value}
        format={format}
        className="text-stat font-semibold text-nx-ink"
      />
      {trend != null && trend !== 0 && (
        <div
          className={`text-caption mt-1 ${
            trend > 0 ? "text-nx-pill-green" : "text-nx-pill-red"
          }`}
        >
          {trend > 0 ? "+" : ""}
          {trend.toFixed(1)}% from prior period
        </div>
      )}
      {subtitle && (
        <div className="text-caption nx-muted mt-1">{subtitle}</div>
      )}
    </div>
  );
}
