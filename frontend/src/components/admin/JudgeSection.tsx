import { useState } from "react";
import type { JudgeResults } from "../../lib/types";
import type { PieSlice } from "../../lib/analytics";
import { BarChart } from "./BarChart";
import { PieChart } from "../sidebar/PieChart";
import { CountUp } from "../CountUp";

interface Props {
  results: JudgeResults | null;
}

const GRADE_COLORS: Record<string, string> = {
  A: "#34d399",
  B: "#2dd4bf",
  C: "#fbbf24",
  D: "#fb923c",
  F: "#f87171",
};

const DIMENSION_LABELS: Record<string, string> = {
  citation_accuracy: "Citation",
  factuality: "Factuality",
  completeness: "Completeness",
  rule_compliance: "Compliance",
};

const DIMENSIONS = ["citation_accuracy", "factuality", "completeness", "rule_compliance"];

function scoreColor(score: number): string {
  if (score >= 0.8) return "text-emerald-400";
  if (score >= 0.6) return "text-amber-400";
  return "text-rose-400";
}

function gradeColor(grade: string): string {
  return GRADE_COLORS[grade] ?? "#888";
}

export function JudgeSection({ results }: Props) {
  const [showQueries, setShowQueries] = useState(false);
  const [expandedQuery, setExpandedQuery] = useState<string | null>(null);

  if (!results || results.total_queries === 0) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex gap-3">
            {["A", "B", "C", "D", "F"].map((g) => (
              <div key={g} className="text-center">
                <div
                  className="w-8 h-16 rounded-md opacity-20"
                  style={{ backgroundColor: GRADE_COLORS[g] }}
                />
                <div className="text-[10px] text-text-muted mt-1">{g}</div>
              </div>
            ))}
          </div>
          <div className="text-right">
            <div className="text-2xl font-semibold text-text-muted">--</div>
            <div className="text-[10px] text-text-muted">Avg Score</div>
          </div>
        </div>
        <div className="bg-dark-elevated rounded-lg p-3 text-center">
          <p className="text-sm text-text-muted mb-1">
            No judge results found
          </p>
          <p className="text-xs text-text-muted">
            Run to generate:{" "}
            <code className="text-text-secondary bg-dark-bg px-1.5 py-0.5 rounded text-[10px]">
              python -m eval.run_eval --full http://localhost:8001 --judge
            </code>
          </p>
        </div>
      </div>
    );
  }

  const grades = results.overall_grade_distribution;
  const gradesBars = ["A", "B", "C", "D", "F"].map((g) => ({
    label: g,
    value: grades[g] ?? 0,
    color: GRADE_COLORS[g],
  }));

  const gradeSlices: PieSlice[] = ["A", "B", "C", "D", "F"]
    .filter((g) => (grades[g] ?? 0) > 0)
    .map((g) => ({
      label: g,
      value: grades[g],
      color: GRADE_COLORS[g],
    }));

  const passRate = results.total_queries > 0
    ? (((grades.A ?? 0) + (grades.B ?? 0)) / results.total_queries) * 100
    : 0;

  return (
    <div className="space-y-4">
      {/* Top row: score + pass rate + queries */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-dark-elevated rounded-lg p-3 text-center">
          <div className={`text-2xl font-semibold ${scoreColor(results.avg_score)}`}>
            <CountUp
              to={results.avg_score * 100}
              format={(n) => `${n.toFixed(0)}%`}
            />
          </div>
          <div className="text-[10px] text-text-muted mt-0.5">Avg Score</div>
        </div>
        <div className="bg-dark-elevated rounded-lg p-3 text-center">
          <div className="text-2xl font-semibold text-emerald-400">
            <CountUp
              to={passRate}
              format={(n) => `${n.toFixed(0)}%`}
            />
          </div>
          <div className="text-[10px] text-text-muted mt-0.5">A+B Rate</div>
        </div>
        <div className="bg-dark-elevated rounded-lg p-3 text-center">
          <div className="text-2xl font-semibold text-text-primary">
            {results.total_queries}
          </div>
          <div className="text-[10px] text-text-muted mt-0.5">
            Judged{results.skipped_queries > 0 && ` (${results.skipped_queries} skipped)`}
          </div>
        </div>
      </div>

      {/* Charts row: bar + pie */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="text-[10px] text-text-muted uppercase tracking-wider mb-2">
            Grade Distribution
          </div>
          <BarChart bars={gradesBars} />
        </div>
        <div className="flex flex-col items-center">
          <div className="text-[10px] text-text-muted uppercase tracking-wider mb-2">
            Grade Breakdown
          </div>
          <PieChart slices={gradeSlices} size={140} />
        </div>
      </div>

      {/* Dimension breakdown: 4 mini bar sections */}
      <div>
        <div className="text-[10px] text-text-muted uppercase tracking-wider mb-2">
          By Dimension
        </div>
        <div className="grid grid-cols-2 gap-3">
          {DIMENSIONS.map((dim) => {
            const summary = results.dimension_summaries[dim];
            if (!summary) return null;
            const dist = summary.grade_distribution;
            const total = Object.values(dist).reduce((a, b) => a + b, 0);
            if (total === 0) return null;

            return (
              <div key={dim} className="bg-dark-elevated rounded-lg p-2.5">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-[10px] text-text-secondary font-medium">
                    {DIMENSION_LABELS[dim] ?? dim}
                  </span>
                  <span className={`text-[10px] font-mono ${
                    summary.avg_numeric >= 3 ? "text-emerald-400" :
                    summary.avg_numeric >= 2 ? "text-amber-400" : "text-rose-400"
                  }`}>
                    {summary.avg_numeric.toFixed(1)}/4
                  </span>
                </div>
                <div className="flex h-3 rounded-sm overflow-hidden gap-px">
                  {["A", "B", "C", "D", "F"].map((g) => {
                    const count = dist[g] ?? 0;
                    if (count === 0) return null;
                    const pct = (count / total) * 100;
                    return (
                      <div
                        key={g}
                        className="h-full transition-all"
                        style={{
                          width: `${pct}%`,
                          backgroundColor: GRADE_COLORS[g],
                          minWidth: count > 0 ? "4px" : undefined,
                        }}
                        title={`${g}: ${count} (${pct.toFixed(0)}%)`}
                      />
                    );
                  })}
                </div>
                <div className="flex gap-2 mt-1">
                  {["A", "B", "C", "D", "F"].map((g) => {
                    const count = dist[g] ?? 0;
                    if (count === 0) return null;
                    return (
                      <span key={g} className="text-[9px] text-text-muted">
                        <span style={{ color: GRADE_COLORS[g] }}>{g}</span>={count}
                      </span>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Per-query detail table (collapsible) */}
      {results.per_query.length > 0 && (
        <div>
          <button
            onClick={() => setShowQueries(!showQueries)}
            className="flex items-center gap-1.5 text-xs text-text-muted hover:text-text-secondary transition-colors"
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
            <table className="w-full text-[11px] mt-2">
              <thead>
                <tr className="text-text-muted uppercase tracking-wider text-[9px]">
                  <th className="text-left py-1.5 font-medium">Query</th>
                  <th className="text-center py-1.5 font-medium w-10">All</th>
                  <th className="text-center py-1.5 font-medium w-10">Cite</th>
                  <th className="text-center py-1.5 font-medium w-10">Fact</th>
                  <th className="text-center py-1.5 font-medium w-10">Comp</th>
                  <th className="text-center py-1.5 font-medium w-10">Rule</th>
                </tr>
              </thead>
              <tbody>
                {results.per_query.map((q) => {
                  const dimGrades: Record<string, string> = {};
                  for (const d of q.dimensions) {
                    dimGrades[d.dimension] = d.grade;
                  }
                  const isExpanded = expandedQuery === q.id;

                  return (
                    <tr
                      key={q.id}
                      className="border-t border-dark-border cursor-pointer hover:bg-dark-elevated/50"
                      onClick={() => setExpandedQuery(isExpanded ? null : q.id)}
                    >
                      <td className="py-1.5" colSpan={isExpanded ? 6 : undefined}>
                        {isExpanded ? (
                          <div className="space-y-2 py-1">
                            <div className="text-text-secondary font-medium">
                              {q.id.replace(/_/g, " ")}
                            </div>
                            <div className="text-text-muted italic text-[10px]">
                              {q.question}
                            </div>
                            {q.overall_reasoning && (
                              <div className="text-text-muted text-[10px]">
                                <span className="text-text-secondary">Overall:</span> {q.overall_reasoning}
                              </div>
                            )}
                            {q.dimensions.map((d) => (
                              <div key={d.dimension} className="text-[10px] text-text-muted flex gap-2">
                                <span
                                  className="inline-block w-4 h-4 rounded text-[9px] font-bold leading-4 text-center shrink-0"
                                  style={{
                                    backgroundColor: gradeColor(d.grade) + "22",
                                    color: gradeColor(d.grade),
                                  }}
                                >
                                  {d.grade}
                                </span>
                                <span>
                                  <span className="text-text-secondary">
                                    {DIMENSION_LABELS[d.dimension] ?? d.dimension}:
                                  </span>{" "}
                                  {d.reasoning}
                                </span>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <span className="text-text-secondary">
                            {q.id.replace(/_/g, " ")}
                          </span>
                        )}
                      </td>
                      {!isExpanded && (
                        <>
                          <td className="py-1.5 text-center">
                            <GradeBadge grade={q.overall_grade} />
                          </td>
                          <td className="py-1.5 text-center">
                            <GradeBadge grade={dimGrades.citation_accuracy} />
                          </td>
                          <td className="py-1.5 text-center">
                            <GradeBadge grade={dimGrades.factuality} />
                          </td>
                          <td className="py-1.5 text-center">
                            <GradeBadge grade={dimGrades.completeness} />
                          </td>
                          <td className="py-1.5 text-center">
                            <GradeBadge grade={dimGrades.rule_compliance} />
                          </td>
                        </>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Footer */}
      <div className="text-[10px] text-text-muted">
        {results.last_run && (
          <>Last run: {new Date(results.last_run).toLocaleDateString()} &middot; </>
        )}
        Update: <code className="text-text-secondary bg-dark-bg px-1 py-0.5 rounded">
          python -m eval.run_eval --full http://localhost:8001 --judge
        </code>
      </div>
    </div>
  );
}

function GradeBadge({ grade }: { grade: string | undefined }) {
  if (!grade) return <span className="text-text-muted">-</span>;
  return (
    <span
      className="inline-block w-5 h-5 rounded text-[10px] font-bold leading-5 text-center"
      style={{
        backgroundColor: gradeColor(grade) + "22",
        color: gradeColor(grade),
      }}
    >
      {grade}
    </span>
  );
}
