import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import {
  getJob,
  getJobLocations,
  getJobs,
  getRefreshStatus,
  hideJob,
  refreshApiJobs,
  refreshScrapedJobs,
  unhideJob,
} from "../services/api";
import { formatLocation, formatSalary } from "../utils/formatters";

const PAGE_SIZE = 50;
const COLUMN_PREFS_KEY = "jobs.visibleColumns";
const STATUS_OPTIONS = [
  { value: "active", label: "Active" },
  { value: "hidden", label: "Hidden" },
  { value: "all", label: "All" },
];

const COLUMN_DEFS = [
  { key: "title", label: "Title", sortable: true },
  { key: "company_name", label: "Company", sortable: true },
  { key: "location", label: "Location", sortable: true },
  { key: "work_arrangement", label: "Arrangement", sortable: true },
  { key: "salary", label: "Salary", sortable: true },
  { key: "source", label: "Source", sortable: true },
  { key: "posted_date", label: "Posted", sortable: true },
  { key: "closed_date", label: "Closed", sortable: true },
  { key: "discovered_date", label: "Discovered", sortable: true },
  { key: "overall_match_score", label: "Score", sortable: true, align: "right" },
];

const DEFAULT_VISIBLE_COLUMNS = Object.fromEntries(COLUMN_DEFS.map((col) => [col.key, true]));

function loadVisibleColumns() {
  const defaults = { ...DEFAULT_VISIBLE_COLUMNS };
  if (typeof window === "undefined") return defaults;

  try {
    const raw = window.localStorage.getItem(COLUMN_PREFS_KEY);
    if (!raw) return defaults;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return defaults;
    return { ...defaults, ...parsed };
  } catch {
    return defaults;
  }
}

function ScoreBadge({ score }) {
  if (score == null) return <span className="text-gray-400">—</span>;
  const color =
    score >= 70
      ? "bg-green-100 text-green-800"
      : score >= 45
        ? "bg-yellow-100 text-yellow-800"
        : "bg-red-100 text-red-800";
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-xs font-semibold ${color}`}>
      {score.toFixed(1)}
    </span>
  );
}

function JobDetailPanel({ jobId, onClose, onHideToggle }) {
  const { data: job, isLoading } = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => getJob(jobId),
    enabled: !!jobId,
  });

  if (!jobId) return null;

  return (
    <div className="fixed inset-y-0 right-0 w-[520px] bg-white shadow-xl flex flex-col z-10 border-l">
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
              <div className="text-xs text-gray-400 uppercase tracking-wide mb-0.5">Company</div>
              <div>{job.company_name ?? "—"}</div>
            </div>
            <div>
              <div className="text-xs text-gray-400 uppercase tracking-wide mb-0.5">Location</div>
              <div>{formatLocation(job.location)}</div>
            </div>
            <div>
              <div className="text-xs text-gray-400 uppercase tracking-wide mb-0.5">Arrangement</div>
              <div>{job.work_arrangement ?? "—"}</div>
            </div>
            <div>
              <div className="text-xs text-gray-400 uppercase tracking-wide mb-0.5">Salary</div>
              <div>{formatSalary(job)}</div>
            </div>
            <div>
              <div className="text-xs text-gray-400 uppercase tracking-wide mb-0.5">Source</div>
              <div>{job.source ?? "—"}</div>
            </div>
            <div>
              <div className="text-xs text-gray-400 uppercase tracking-wide mb-0.5">Posted</div>
              <div>{job.posted_date ?? "—"}</div>
            </div>
            <div>
              <div className="text-xs text-gray-400 uppercase tracking-wide mb-0.5">Discovered</div>
              <div>{job.discovered_date ?? "—"}</div>
            </div>
            <div>
              <div className="text-xs text-gray-400 uppercase tracking-wide mb-0.5">Closed</div>
              <div>{job.closed_date ?? "—"}</div>
            </div>
            <div>
              <div className="text-xs text-gray-400 uppercase tracking-wide mb-0.5">Match Score</div>
              <div>
                <ScoreBadge score={job.overall_match_score} />
              </div>
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-400 uppercase tracking-wide mb-1">Score Breakdown</div>
            <div className="grid grid-cols-2 gap-2 text-gray-700">
              <div>Skills: {job.score_breakdown?.skills ?? "—"}</div>
              <div>Experience: {job.score_breakdown?.experience ?? "—"}</div>
              <div>Title: {job.score_breakdown?.title ?? "—"}</div>
              <div>Overall: {job.score_breakdown?.overall ?? job.overall_match_score ?? "—"}</div>
            </div>
          </div>
          <div className="grid grid-cols-1 gap-2 text-sm">
            <div>
              <div className="text-xs text-gray-400 uppercase tracking-wide mb-1">Matched Skills</div>
              <div className="text-gray-700">
                {job.matched_skills?.length ? job.matched_skills.join(", ") : "—"}
              </div>
            </div>
            <div>
              <div className="text-xs text-gray-400 uppercase tracking-wide mb-1">Missing Skills</div>
              <div className="text-gray-700">
                {job.missing_skills?.length ? job.missing_skills.join(", ") : "—"}
              </div>
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-400 uppercase tracking-wide mb-1">Description</div>
            {job.description_html ? (
              <div
                className="text-gray-700 leading-relaxed whitespace-normal [&_p]:mb-3 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5 [&_li]:mb-1 [&_strong]:font-semibold [&_em]:italic"
                dangerouslySetInnerHTML={{ __html: job.description_html }}
              />
            ) : (
              <p className="text-gray-700 whitespace-pre-wrap leading-relaxed">{job.description || "—"}</p>
            )}
          </div>
          <div className="flex gap-2 pt-2">
            <a
              href={job.source_url || job.application_url}
              target="_blank"
              rel="noreferrer"
              className="flex-1 text-center rounded bg-blue-600 text-white py-1.5 text-sm font-medium hover:bg-blue-700"
            >
              Apply
            </a>
            <button
              onClick={() => onHideToggle(job)}
              className="flex-1 rounded border border-gray-300 text-gray-600 py-1.5 text-sm hover:bg-gray-50"
            >
              {job.is_active ? "Hide" : "Unhide"}
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function SortableHeader({ column, sortState, onToggleSort }) {
  const isSorted = sortState.key === column.key;
  const sortMarker = !isSorted ? "" : sortState.direction === "asc" ? " ▲" : " ▼";

  return (
    <th
      className={`px-4 py-2 ${column.align === "right" ? "text-right" : "text-left"} ${
        column.sortable ? "cursor-pointer select-none hover:text-gray-700" : ""
      }`}
      onClick={() => column.sortable && onToggleSort(column.key)}
    >
      {column.label}
      {sortMarker}
    </th>
  );
}

export default function JobsPage() {
  const queryClient = useQueryClient();
  const [filters, setFilters] = useState({
    min_score: "",
    location: "",
    days: "",
    work_arrangement: "",
  });
  const [statusFilter, setStatusFilter] = useState("active");
  const [sortState, setSortState] = useState({ key: "discovered_date", direction: "desc" });
  const [selectedId, setSelectedId] = useState(null);
  const [visibleColumns, setVisibleColumns] = useState(loadVisibleColumns);
  const [page, setPage] = useState(1);

  const isActiveParam =
    statusFilter === "active" ? true : statusFilter === "hidden" ? false : undefined;
  const locationStatusParam = isActiveParam === undefined ? {} : { is_active: isActiveParam };
  const skip = (page - 1) * PAGE_SIZE;
  const queryParams = {
    skip,
    limit: PAGE_SIZE,
    ...(filters.min_score !== "" && { min_score: Number(filters.min_score) }),
    ...(filters.location !== "" && { location_group: filters.location }),
    ...(filters.days !== "" && { days: Number(filters.days) }),
    ...(isActiveParam !== undefined && { is_active: isActiveParam }),
    ...(sortState.key && { sort_by: sortState.key, sort_direction: sortState.direction }),
  };

  const { data, isLoading, isError } = useQuery({
    queryKey: ["jobs", queryParams],
    queryFn: () => getJobs(queryParams),
  });

  const refreshApiMutation = useMutation({
    mutationFn: refreshApiJobs,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["refreshStatus"] }),
  });

  const refreshScraperMutation = useMutation({
    mutationFn: refreshScrapedJobs,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["refreshStatus"] }),
  });

  const { data: refreshStatusData } = useQuery({
    queryKey: ["refreshStatus"],
    queryFn: getRefreshStatus,
    refetchInterval: (query) => (query.state.data?.status === "running" ? 10000 : 30000),
  });

  const { data: locationOptions = [] } = useQuery({
    queryKey: ["jobLocationGroups", locationStatusParam.is_active],
    queryFn: () => getJobLocations(locationStatusParam),
  });

  useEffect(() => {
    if (refreshStatusData?.status === "complete") {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    }
  }, [queryClient, refreshStatusData?.status]);

  useEffect(() => {
    setPage(1);
  }, [
    filters.min_score,
    filters.location,
    filters.days,
    filters.work_arrangement,
    statusFilter,
    sortState.key,
    sortState.direction,
  ]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(COLUMN_PREFS_KEY, JSON.stringify(visibleColumns));
  }, [visibleColumns]);

  const toggleVisibility = (key) => {
    setVisibleColumns((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleToggleSort = (key) => {
    setSortState((prev) => {
      if (prev.key !== key) return { key, direction: "asc" };
      if (prev.direction === "asc") return { key, direction: "desc" };
      return { key: null, direction: null };
    });
  };

  const toggleHideMutation = useMutation({
    mutationFn: (job) => (job.is_active ? hideJob(job.id) : unhideJob(job.id)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      if (selectedId) queryClient.invalidateQueries({ queryKey: ["job", selectedId] });
    },
  });

  const isRunning = refreshStatusData?.status === "running";
  const isRefreshing = refreshApiMutation.isPending || refreshScraperMutation.isPending || isRunning;
  const jobs = data?.items ?? [];
  const arrangementOptions = useMemo(() => {
    const options = new Set(
      jobs.map((job) => job.work_arrangement).filter((value) => value && value !== "unknown"),
    );
    return Array.from(options).sort();
  }, [jobs]);

  const filtered = filters.work_arrangement
    ? jobs.filter((job) => job.work_arrangement === filters.work_arrangement)
    : jobs;

  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const pageStart = total === 0 ? 0 : skip + 1;
  const pageEnd = Math.min(skip + jobs.length, total);
  const visibleColumnDefs = COLUMN_DEFS.filter((column) => visibleColumns[column.key]);

  function setFilter(key, value) {
    setFilters((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <div className="flex gap-0 relative">
      <div className={`flex-1 min-w-0 transition-all ${selectedId ? "mr-[520px]" : ""}`}>
        <div className="flex flex-wrap items-end gap-3 mb-4">
          <div>
            <label className="block text-xs text-gray-500 mb-0.5">Status</label>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="border rounded px-2 py-1 text-sm"
            >
              {STATUS_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
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
            <select
              value={filters.location}
              onChange={(e) => setFilter("location", e.target.value)}
              className="w-52 border rounded px-2 py-1 text-sm"
            >
              <option value="">All</option>
              {locationOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
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
              <option value="">All</option>
              {arrangementOptions.map((arrangement) => (
                <option key={arrangement} value={arrangement}>
                  {arrangement}
                </option>
              ))}
            </select>
          </div>
          <div className="relative">
            <label className="block text-xs text-gray-500 mb-0.5">Columns</label>
            <details className="relative">
              <summary className="list-none border rounded px-3 py-1 text-sm cursor-pointer select-none">
                Select columns
              </summary>
              <div className="absolute z-20 mt-1 w-48 rounded border bg-white shadow p-2 space-y-1">
                {COLUMN_DEFS.map((column) => (
                  <label key={column.key} className="flex items-center gap-2 text-sm text-gray-700">
                    <input
                      type="checkbox"
                      checked={visibleColumns[column.key]}
                      onChange={() => toggleVisibility(column.key)}
                    />
                    {column.label}
                  </label>
                ))}
              </div>
            </details>
          </div>
          <div className="ml-auto flex gap-2">
            <button
              onClick={() => refreshApiMutation.mutate()}
              disabled={isRefreshing}
              className="rounded bg-blue-600 text-white px-3 py-1.5 text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
            >
              {isRunning && refreshStatusData?.mode === "api" ? "Running..." : "Refresh API Jobs"}
            </button>
            <button
              onClick={() => refreshScraperMutation.mutate()}
              disabled={isRefreshing}
              className="rounded bg-slate-700 text-white px-3 py-1.5 text-sm font-medium hover:bg-slate-800 disabled:opacity-50"
            >
              {isRunning && refreshStatusData?.mode === "scrapers"
                ? "Running..."
                : "Refresh Scraped Jobs"}
            </button>
          </div>
        </div>

        {isRunning && (
          <div className="mb-3 rounded border border-blue-200 bg-blue-50 px-3 py-2">
            <div className="flex items-center gap-2 text-sm text-blue-800 font-medium mb-1">
              <span className="inline-block w-3 h-3 rounded-full bg-blue-400 animate-pulse" />
              Job discovery running
              {refreshStatusData?.mode ? ` (${refreshStatusData.mode})` : ""}
            </div>
            {refreshStatusData?.step && <div className="text-xs text-blue-600">{refreshStatusData.step}</div>}
          </div>
        )}
        {refreshStatusData?.status === "complete" && refreshStatusData?.inserted != null && (
          <div className="mb-3 text-sm text-green-700 bg-green-50 border border-green-200 rounded px-3 py-2">
            Discovery complete — {refreshStatusData.inserted} new, {refreshStatusData.updated} updated,{" "}
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

        <div className="bg-white rounded border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b text-xs text-gray-500 uppercase tracking-wide">
              <tr>
                {visibleColumnDefs.map((column) => (
                  <SortableHeader
                    key={column.key}
                    column={column}
                    sortState={sortState}
                    onToggleSort={handleToggleSort}
                  />
                ))}
                <th className="px-4 py-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={visibleColumnDefs.length + 1} className="px-4 py-8 text-center text-gray-400">
                    Loading...
                  </td>
                </tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={visibleColumnDefs.length + 1} className="px-4 py-8 text-center text-gray-400">
                    No jobs found.
                  </td>
                </tr>
              ) : (
                filtered.map((job) => (
                  <tr
                    key={job.id}
                    className={`border-b last:border-0 hover:bg-gray-50 cursor-pointer ${
                      selectedId === job.id ? "bg-blue-50" : ""
                    }`}
                    onClick={() => setSelectedId(job.id === selectedId ? null : job.id)}
                  >
                    {visibleColumns.title && (
                      <td className="px-4 py-2 font-medium text-gray-900 max-w-xs truncate">{job.title}</td>
                    )}
                    {visibleColumns.company_name && (
                      <td className="px-4 py-2 text-gray-700">{job.company_name ?? "—"}</td>
                    )}
                    {visibleColumns.location && (
                      <td className="px-4 py-2 text-gray-600">{formatLocation(job.location)}</td>
                    )}
                    {visibleColumns.work_arrangement && (
                      <td className="px-4 py-2 text-gray-600">{job.work_arrangement ?? "—"}</td>
                    )}
                    {visibleColumns.salary && (
                      <td className="px-4 py-2 text-gray-600">{formatSalary(job)}</td>
                    )}
                    {visibleColumns.source && <td className="px-4 py-2 text-gray-600">{job.source ?? "—"}</td>}
                    {visibleColumns.posted_date && (
                      <td className="px-4 py-2 text-gray-500">{job.posted_date ?? "—"}</td>
                    )}
                    {visibleColumns.closed_date && (
                      <td className="px-4 py-2 text-gray-500">{job.closed_date ?? "—"}</td>
                    )}
                    {visibleColumns.discovered_date && (
                      <td className="px-4 py-2 text-gray-500">{job.discovered_date ?? "—"}</td>
                    )}
                    {visibleColumns.overall_match_score && (
                      <td className="px-4 py-2 text-right">
                        <ScoreBadge score={job.overall_match_score} />
                      </td>
                    )}
                    <td className="px-4 py-2 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleHideMutation.mutate(job);
                        }}
                        className="text-xs text-gray-400 hover:text-red-500"
                      >
                        {job.is_active ? "Hide" : "Unhide"}
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="mt-2 flex items-center justify-between text-xs text-gray-500">
          <div>
            Showing {pageStart}-{pageEnd} of {total}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="border rounded px-2 py-1 disabled:opacity-50"
            >
              Prev
            </button>
            <span>
              Page {page} of {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="border rounded px-2 py-1 disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </div>
      </div>

      <JobDetailPanel
        jobId={selectedId}
        onClose={() => setSelectedId(null)}
        onHideToggle={(job) => toggleHideMutation.mutate(job)}
      />
    </div>
  );
}
