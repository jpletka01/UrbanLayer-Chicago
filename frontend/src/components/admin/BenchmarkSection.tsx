import { useState } from "react";
import type { BenchmarkResults } from "../../lib/types";
import type { PieSlice } from "../../lib/analytics";
import { BarChart } from "./BarChart";
import { PieChart } from "../sidebar/PieChart";
import { CountUp } from "../CountUp";

interface Props {
  benchmark: BenchmarkResults | null;
}

const GRADE_COLORS: Record<string, string> = {
  A: "#34d399",
  B: "#2dd4bf",
  C: "#fbbf24",
  D: "#fb923c",
  F: "#f87171",
};

const GRADE_LABELS: Record<string, string> = {
  A: "Excellent",
  B: "Good",
  C: "Fair",
  D: "Poor",
  F: "Failing",
};

function scoreColor(score: number): string {
  if (score >= 0.8) return "text-emerald-400";
  if (score >= 0.6) return "text-amber-400";
  return "text-rose-400";
}

function gradeColor(grade: string): string {
  return GRADE_COLORS[grade] ?? "#888";
}

export function BenchmarkSection({ benchmark }: Props) {
  const [showQueries, setShowQueries] = useState(false);

  if (!benchmark || benchmark.total_queries === 0) {
    return (
      <div className="space-y-4">
        {/* Empty state with placeholder grade bars */}
        <div className="flex items-center justify-between">
          <div className="flex gap-3">
            {["A", "B", "C", "D", "F"].map((g) => (
              <div key={g} className="text-center">
                <div
                  className="w-8 h-16 rounded-md opacity-20"
                  style={{ backgroundColor: GRADE_COLORS[g] }}
                />
                <div className="text-micro text-text-muted mt-1">{g}</div>
              </div>
            ))}
          </div>
          <div className="text-right">
            <div className="text-section font-semibold text-text-muted">--</div>
            <div className="text-micro text-text-muted">Avg Score</div>
          </div>
        </div>
        <div className="bg-dark-elevated rounded-lg p-3 text-center">
          <p className="text-body text-text-muted mb-1">
            No benchmark results found
          </p>
          <p className="text-caption text-text-muted">
            Run to generate:{" "}
            <code className="text-text-secondary bg-dark-bg px-1.5 py-0.5 rounded text-micro">
              python -m eval.retrieval_benchmark --json-out eval/benchmark_results.json
            </code>
          </p>
        </div>
      </div>
    );
  }

  const grades = benchmark.grade_distribution;
  const gradesBars = ["A", "B", "C", "D", "F"].map((g) => ({
    label: g,
    value: grades[g] ?? 0,
    color: GRADE_COLORS[g],
  }));

  const gradeSlices: PieSlice[] = ["A", "B", "C", "D", "F"]
    .filter((g) => (grades[g] ?? 0) > 0)
    .map((g) => ({
      label: `${g} (${GRADE_LABELS[g]})`,
      value: grades[g],
      color: GRADE_COLORS[g],
    }));

  const passRate = benchmark.total_queries > 0
    ? (((grades.A ?? 0) + (grades.B ?? 0)) / benchmark.total_queries) * 100
    : 0;

  return (
    <div className="space-y-4">
      {/* Top row: score + pass rate + last run */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-dark-elevated rounded-lg p-3 text-center">
          <div className={`text-section font-semibold ${scoreColor(benchmark.avg_score)}`}>
            <CountUp
              to={benchmark.avg_score * 100}
              format={(n) => `${n.toFixed(0)}%`}
            />
          </div>
          <div className="text-micro text-text-muted mt-0.5">Avg Score</div>
        </div>
        <div className="bg-dark-elevated rounded-lg p-3 text-center">
          <div className="text-section font-semibold text-emerald-400">
            <CountUp
              to={passRate}
              format={(n) => `${n.toFixed(0)}%`}
            />
          </div>
          <div className="text-micro text-text-muted mt-0.5">A+B Rate</div>
        </div>
        <div className="bg-dark-elevated rounded-lg p-3 text-center">
          <div className="text-section font-semibold text-text-primary">
            {benchmark.total_queries}
          </div>
          <div className="text-micro text-text-muted mt-0.5">Queries</div>
        </div>
      </div>

      {/* Charts row: bar + pie side by side */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="text-micro text-text-muted uppercase tracking-wider mb-2">
            Grade Distribution
          </div>
          <BarChart bars={gradesBars} />
        </div>
        <div className="flex flex-col items-center">
          <div className="text-micro text-text-muted uppercase tracking-wider mb-2">
            Grade Breakdown
          </div>
          <PieChart slices={gradeSlices} size={140} />
        </div>
      </div>

      {/* Per-query detail table (collapsible) */}
      {benchmark.per_query.length > 0 && (
        <div>
          <button
            onClick={() => setShowQueries(!showQueries)}
            className="flex items-center gap-1.5 text-caption text-text-muted hover:text-text-secondary transition-colors"
          >
            <svg
              className={`w-3 h-3 transition-transform ${showQueries ? "rotate-90" : ""}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
            </svg>
            {showQueries ? "Hide" : "Show"} per-query details
          </button>

          {showQueries && (
            <table className="w-full text-micro mt-2">
              <thead>
                <tr className="text-text-muted uppercase tracking-wider text-micro">
                  <th className="text-left py-1.5 font-medium">Query</th>
                  <th className="text-center py-1.5 font-medium w-12">Grade</th>
                  <th className="text-right py-1.5 font-medium w-14">Score</th>
                  <th className="text-left py-1.5 font-medium">Issues</th>
                </tr>
              </thead>
              <tbody>
                {benchmark.per_query.map((q) => (
                  <tr key={q.id} className="border-t border-dark-border">
                    <td className="py-1.5 text-text-secondary">
                      {q.id.replace(/_/g, " ")}
                    </td>
                    <td className="py-1.5 text-center">
                      <span
                        className="inline-block w-5 h-5 rounded text-micro font-bold leading-5 text-center"
                        style={{
                          backgroundColor: gradeColor(q.grade) + "22",
                          color: gradeColor(q.grade),
                        }}
                      >
                        {q.grade}
                      </span>
                    </td>
                    <td className={`py-1.5 text-right font-mono ${scoreColor(q.score)}`}>
                      {(q.score * 100).toFixed(0)}%
                    </td>
                    <td className="py-1.5 text-text-muted truncate max-w-[180px]">
                      {q.issues.length > 0 ? q.issues.join("; ") : "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Footer */}
      <div className="text-micro text-text-muted">
        {benchmark.last_run && (
          <>Last run: {new Date(benchmark.last_run).toLocaleDateString()} &middot; </>
        )}
        Update: <code className="text-text-secondary bg-dark-bg px-1 py-0.5 rounded">
          python -m eval.retrieval_benchmark --json-out eval/benchmark_results.json
        </code>
      </div>
    </div>
  );
}
