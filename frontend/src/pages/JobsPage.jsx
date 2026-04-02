import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { getJob, getJobs, getRefreshStatus, hideJob, refreshJobs } from "../services/api";

const ARRANGEMENTS = ["", "in_office", "hybrid", "remote"];

function ScoreBadge({ score }) {
  if (score == null) return <span className="text-gray-400">—</span>;
  const color =
    score >= 70 ? "bg-green-100 text-green-800" : score >= 45 ? "bg-yellow-100 text-yellow-800" : "bg-red-100 text-red-800";
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-xs font-semibold ${color}`}>
      {score.toFixed(1)}
    </span>
  );
}

function JobDetailPanel({ jobId, onClose, onHide }) {
  const { data: job, isLoading } = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => getJob(jobId),
    enabled: !!jobId,
  });

  if (!jobId) return null;

  return (
    <div className="fixed inset-y-0 right-0 w-[480px] bg-white shadow-xl flex flex-col z-10 border-l">
      <div className="flex items-center justify-between px-5 py-3 border-b">
        <span className="font-semibold text-gray-800 truncate">{job?.title ?? "Loading..."}</span>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">
          ×
        </button>
      </div>
      {isLoading ? (
        <div className="p-5 text-gray-400">Loading...</div>
      ) : job ? (
        <div className="flex-1 overflow-y-auto p-5 space-y-4 text-sm">
          <div className="grid grid-cols-2 gap-3 text-gray-700">
            <div>
              <div className="text-xs text-gray-400 uppercase tracking-wide mb-0.5">Location</div>
              <div>{job.location ?? "—"}</div>
            </div>
            <div>
              <div className="text-xs text-gray-400 uppercase tracking-wide mb-0.5">Arrangement</div>
              <div>{job.work_arrangement ?? "—"}</div>
            </div>
            <div>
              <div className="text-xs text-gray-400 uppercase tracking-wide mb-0.5">Salary</div>
              <div>
                {job.salary_min || job.salary_max
                  ? `${job.salary_min ? "$" + job.salary_min.toLocaleString() : ""}${
                      job.salary_max ? " – $" + job.salary_max.toLocaleString() : ""
                    }`
                  : "—"}
              </div>
            </div>
            <div>
              <div className="text-xs text-gray-400 uppercase tracking-wide mb-0.5">Match Score</div>
              <div>
                <ScoreBadge score={job.overall_match_score} />
              </div>
            </div>
            <div>
              <div className="text-xs text-gray-400 uppercase tracking-wide mb-0.5">Source</div>
              <div>{job.source}</div>
            </div>
            <div>
              <div className="text-xs text-gray-400 uppercase tracking-wide mb-0.5">Discovered</div>
              <div>{job.discovered_date}</div>
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-400 uppercase tracking-wide mb-1">Description</div>
            <p className="text-gray-700 whitespace-pre-wrap leading-relaxed">{job.description}</p>
          </div>
          <div className="flex gap-2 pt-2">
            <a
              href={job.application_url}
              target="_blank"
              rel="noreferrer"
              className="flex-1 text-center rounded bg-blue-600 text-white py-1.5 text-sm font-medium hover:bg-blue-700"
            >
              Apply
            </a>
            <button
              onClick={() => onHide(job.id)}
              className="flex-1 rounded border border-gray-300 text-gray-600 py-1.5 text-sm hover:bg-gray-50"
            >
              Hide
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default function JobsPage() {
  const queryClient = useQueryClient();
  const [filters, setFilters] = useState({ min_score: "", location: "", days: "", work_arrangement: "" });
  const [sort, setSort] = useState("score");
  const [selectedId, setSelectedId] = useState(null);

  const queryParams = {
    ...(filters.min_score !== "" && { min_score: Number(filters.min_score) }),
    ...(filters.location !== "" && { location: filters.location }),
    ...(filters.days !== "" && { days: Number(filters.days) }),
  };

  const { data, isLoading, isError } = useQuery({
    queryKey: ["jobs", queryParams],
    queryFn: () => getJobs(queryParams),
  });

  const refreshMutation = useMutation({
    mutationFn: refreshJobs,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["refreshStatus"] }),
  });

  const { data: refreshStatusData } = useQuery({
    queryKey: ["refreshStatus"],
    queryFn: getRefreshStatus,
    // Poll every 2s while running, otherwise every 30s
    refetchInterval: (query) =>
      query.state.data?.status === "running" ? 10000 : 30000,
    onSuccess: (data) => {
      if (data?.status === "complete") {
        queryClient.invalidateQueries({ queryKey: ["jobs"] });
      }
    },
  });

  const isRunning = refreshStatusData?.status === "running";

  const hideMutation = useMutation({
    mutationFn: hideJob,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      setSelectedId(null);
    },
  });

  const jobs = data?.items ?? [];

  const filtered =
    filters.work_arrangement === ""
      ? jobs
      : jobs.filter((j) => j.work_arrangement === filters.work_arrangement);

  const sorted = [...filtered].sort((a, b) => {
    if (sort === "score") return (b.overall_match_score ?? -1) - (a.overall_match_score ?? -1);
    if (sort === "date") return (b.discovered_date ?? "").localeCompare(a.discovered_date ?? "");
    if (sort === "title") return (a.title ?? "").localeCompare(b.title ?? "");
    return 0;
  });

  function setFilter(key, val) {
    setFilters((prev) => ({ ...prev, [key]: val }));
  }

  return (
    <div className="flex gap-0 relative">
      <div className={`flex-1 min-w-0 transition-all ${selectedId ? "mr-[480px]" : ""}`}>
        {/* Toolbar */}
        <div className="flex flex-wrap items-end gap-3 mb-4">
          <div>
            <label className="block text-xs text-gray-500 mb-0.5">Min score</label>
            <input
              type="number"
              min={0}
              max={100}
              value={filters.min_score}
              onChange={(e) => setFilter("min_score", e.target.value)}
              placeholder="0"
              className="w-20 border rounded px-2 py-1 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-0.5">Location</label>
            <input
              value={filters.location}
              onChange={(e) => setFilter("location", e.target.value)}
              placeholder="Manhattan"
              className="w-32 border rounded px-2 py-1 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-0.5">Days old</label>
            <input
              type="number"
              min={1}
              value={filters.days}
              onChange={(e) => setFilter("days", e.target.value)}
              placeholder="any"
              className="w-20 border rounded px-2 py-1 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-0.5">Arrangement</label>
            <select
              value={filters.work_arrangement}
              onChange={(e) => setFilter("work_arrangement", e.target.value)}
              className="border rounded px-2 py-1 text-sm"
            >
              {ARRANGEMENTS.map((a) => (
                <option key={a} value={a}>
                  {a === "" ? "All" : a}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-0.5">Sort</label>
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value)}
              className="border rounded px-2 py-1 text-sm"
            >
              <option value="score">Score</option>
              <option value="date">Date</option>
              <option value="title">Title</option>
            </select>
          </div>
          <button
            onClick={() => refreshMutation.mutate()}
            disabled={refreshMutation.isPending || isRunning}
            className="ml-auto rounded bg-blue-600 text-white px-3 py-1.5 text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {isRunning ? "Running..." : "Refresh Jobs"}
          </button>
        </div>

        {/* Refresh progress banner */}
        {isRunning && (
          <div className="mb-3 rounded border border-blue-200 bg-blue-50 px-3 py-2">
            <div className="flex items-center gap-2 text-sm text-blue-800 font-medium mb-1">
              <span className="inline-block w-3 h-3 rounded-full bg-blue-400 animate-pulse" />
              Job discovery running
            </div>
            {refreshStatusData?.step && (
              <div className="text-xs text-blue-600">{refreshStatusData.step}</div>
            )}
          </div>
        )}
        {refreshStatusData?.status === "complete" && refreshStatusData?.inserted != null && (
          <div className="mb-3 text-sm text-green-700 bg-green-50 border border-green-200 rounded px-3 py-2">
            Discovery complete — {refreshStatusData.inserted} new,{" "}
            {refreshStatusData.updated} updated,{" "}
            {refreshStatusData.filtered_out} filtered out.
          </div>
        )}
        {refreshStatusData?.status === "error" && (
          <div className="mb-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">
            Discovery failed: {refreshStatusData.error ?? "unknown error"}
          </div>
        )}
        {isError && (
          <div className="mb-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">
            Failed to load jobs.
          </div>
        )}

        {/* Table */}
        <div className="bg-white rounded border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b text-xs text-gray-500 uppercase tracking-wide">
              <tr>
                <th className="text-left px-4 py-2">Title</th>
                <th className="text-left px-4 py-2">Location</th>
                <th className="text-left px-4 py-2">Arrangement</th>
                <th className="text-left px-4 py-2">Discovered</th>
                <th className="text-right px-4 py-2">Score</th>
                <th className="px-4 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-gray-400">
                    Loading...
                  </td>
                </tr>
              ) : sorted.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-gray-400">
                    No jobs found.
                  </td>
                </tr>
              ) : (
                sorted.map((job) => (
                  <tr
                    key={job.id}
                    className={`border-b last:border-0 hover:bg-gray-50 cursor-pointer ${
                      selectedId === job.id ? "bg-blue-50" : ""
                    }`}
                    onClick={() => setSelectedId(job.id === selectedId ? null : job.id)}
                  >
                    <td className="px-4 py-2 font-medium text-gray-900 max-w-xs truncate">
                      {job.title}
                    </td>
                    <td className="px-4 py-2 text-gray-600">{job.location ?? "—"}</td>
                    <td className="px-4 py-2 text-gray-600">{job.work_arrangement ?? "—"}</td>
                    <td className="px-4 py-2 text-gray-500">{job.discovered_date}</td>
                    <td className="px-4 py-2 text-right">
                      <ScoreBadge score={job.overall_match_score} />
                    </td>
                    <td className="px-4 py-2 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          hideMutation.mutate(job.id);
                        }}
                        className="text-xs text-gray-400 hover:text-red-500"
                      >
                        Hide
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        {data && (
          <div className="mt-2 text-xs text-gray-400">
            {sorted.length} of {data.total} jobs
          </div>
        )}
      </div>

      <JobDetailPanel
        jobId={selectedId}
        onClose={() => setSelectedId(null)}
        onHide={(id) => hideMutation.mutate(id)}
      />
    </div>
  );
}
