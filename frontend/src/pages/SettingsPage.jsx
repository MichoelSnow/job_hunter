import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { getApiUsage, getDiscoverySettings, updateDiscoverySettings } from "../services/api";
import axios from "axios";

function DiscoverySettingsSection() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    search_queries_text: "",
    filter_location_query: "",
    filter_title_query: "",
    filter_exclude_remote: true,
    filter_target_salary_text: "",
    filter_include_missing_salary: true,
    matching_skills_text: "",
    matching_experience_years_text: "",
    matching_current_title: "",
  });
  const [apiError, setApiError] = useState(null);
  const [filtersError, setFiltersError] = useState(null);
  const [profileError, setProfileError] = useState(null);
  const [apiSaved, setApiSaved] = useState(false);
  const [filtersSaved, setFiltersSaved] = useState(false);
  const [profileSaved, setProfileSaved] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["discovery-settings"],
    queryFn: getDiscoverySettings,
  });

  const saveMutation = useMutation({
    mutationFn: updateDiscoverySettings,
    onSuccess: (updated) => {
      queryClient.setQueryData(["discovery-settings"], updated);
      setApiError(null);
      setFiltersError(null);
      setProfileError(null);
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
    onError: (err) => {
      const message = err.response?.data?.detail ?? "Failed to save settings.";
      setApiError(message);
      setFiltersError(message);
      setProfileError(message);
    },
  });

  useEffect(() => {
    if (!data) return;
    setForm({
      search_queries_text: (data.search_queries || []).join("\n"),
      filter_location_query: data.filter_location_query || "",
      filter_title_query: data.filter_title_query || "",
      filter_exclude_remote: !!data.filter_exclude_remote,
      filter_target_salary_text: data.filter_target_salary == null ? "" : String(data.filter_target_salary),
      filter_include_missing_salary: !!data.filter_include_missing_salary,
      matching_skills_text: (data.matching_skills || []).join("\n"),
      matching_experience_years_text:
        data.matching_experience_years == null ? "" : String(data.matching_experience_years),
      matching_current_title: data.matching_current_title || "",
    });
  }, [data]);

  function parsedQueries() {
    return form.search_queries_text
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
  }

  function parsedTargetSalary() {
    const raw = form.filter_target_salary_text.trim();
    if (!raw) return null;
    const value = Number(raw);
    if (!Number.isFinite(value)) return null;
    return Math.round(value);
  }

  function parsedMatchingExperience() {
    const raw = form.matching_experience_years_text.trim();
    if (!raw) return null;
    const value = Number(raw);
    if (!Number.isFinite(value)) return null;
    return Math.round(value);
  }

  function parsedMatchingSkills() {
    return form.matching_skills_text
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
  }

  function payload() {
    return {
      search_queries: parsedQueries(),
      filter_location_query: form.filter_location_query,
      filter_title_query: form.filter_title_query,
      filter_exclude_remote: form.filter_exclude_remote,
      filter_target_salary: parsedTargetSalary(),
      filter_include_missing_salary: form.filter_include_missing_salary,
      matching_skills: parsedMatchingSkills(),
      matching_experience_years: parsedMatchingExperience(),
      matching_current_title: form.matching_current_title,
    };
  }

  return (
    <div className="space-y-4">
      <div className="bg-white rounded border p-4">
        <h2 className="font-semibold text-gray-800 mb-1 text-sm">API Search Inputs</h2>
        <div className="text-xs text-gray-500 mb-3">
          These settings affect only paid API searches (JSearch/Serply).
        </div>
        {isLoading ? (
          <div className="text-gray-400 text-sm">Loading...</div>
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              saveMutation.mutate(payload());
              setApiSaved(true);
              setTimeout(() => setApiSaved(false), 1500);
            }}
            className="space-y-3"
          >
            <div>
              <label className="block text-xs text-gray-500 mb-1">Search queries (one per line)</label>
              <textarea
                rows={4}
                value={form.search_queries_text}
                onChange={(e) => setForm((d) => ({ ...d, search_queries_text: e.target.value }))}
                className="border rounded px-2 py-1 text-sm w-full"
              />
            </div>
            {apiError ? (
              <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">
                {apiError}
              </div>
            ) : null}
            <div className="flex items-center gap-3">
              <button
                type="submit"
                disabled={saveMutation.isPending}
                className="rounded bg-blue-600 text-white px-3 py-1.5 text-sm hover:bg-blue-700 disabled:opacity-50"
              >
                Save API Search Inputs
              </button>
              {apiSaved ? <span className="text-xs text-green-700">Saved</span> : null}
            </div>
          </form>
        )}
      </div>

      <div className="bg-white rounded border p-4">
        <h2 className="font-semibold text-gray-800 mb-1 text-sm">Job Filters</h2>
        <div className="text-xs text-gray-500 mb-3">
          These rules affect visibility after jobs are collected from APIs and scrapers.
        </div>
        {isLoading ? (
          <div className="text-gray-400 text-sm">Loading...</div>
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              saveMutation.mutate(payload());
              setFiltersSaved(true);
              setTimeout(() => setFiltersSaved(false), 1500);
            }}
            className="space-y-3"
          >
            <div>
              <label className="block text-xs text-gray-500 mb-1">Allowed locations query (Boolean)</label>
              <textarea
                rows={3}
                value={form.filter_location_query}
                onChange={(e) => setForm((d) => ({ ...d, filter_location_query: e.target.value }))}
                className="border rounded px-2 py-1 text-sm w-full"
                placeholder='e.g. ("new york" OR brooklyn OR manhattan) AND NOT "san francisco"'
              />
              <div className="text-xs text-gray-400 mt-1">
                Supports AND, OR, NOT, parentheses, and quoted phrases.
              </div>
            </div>
            <div className="flex flex-wrap gap-4">
              <label className="inline-flex items-center gap-2 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={form.filter_exclude_remote}
                  onChange={(e) => setForm((d) => ({ ...d, filter_exclude_remote: e.target.checked }))}
                />
                Exclude fully remote jobs
              </label>
              <label className="inline-flex items-center gap-2 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={form.filter_include_missing_salary}
                  onChange={(e) =>
                    setForm((d) => ({ ...d, filter_include_missing_salary: e.target.checked }))
                  }
                />
                Include jobs with missing salary range
              </label>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">
                Minimum salary (jobs that can meet/exceed this value)
              </label>
              <input
                type="number"
                min={0}
                value={form.filter_target_salary_text}
                onChange={(e) => setForm((d) => ({ ...d, filter_target_salary_text: e.target.value }))}
                className="border rounded px-2 py-1 text-sm w-48"
                placeholder="e.g. 190000"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Job title query (Boolean)</label>
              <textarea
                rows={4}
                value={form.filter_title_query}
                onChange={(e) => setForm((d) => ({ ...d, filter_title_query: e.target.value }))}
                className="border rounded px-2 py-1 text-sm w-full"
                placeholder='e.g. (director OR vp OR "head of") AND (data OR analytics)'
              />
            </div>
            {filtersError ? (
              <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">
                {filtersError}
              </div>
            ) : null}
            <div className="flex items-center gap-3">
              <button
                type="submit"
                disabled={saveMutation.isPending}
                className="rounded bg-blue-600 text-white px-3 py-1.5 text-sm hover:bg-blue-700 disabled:opacity-50"
              >
                Save Job Filters
              </button>
              {filtersSaved ? <span className="text-xs text-green-700">Saved</span> : null}
            </div>
          </form>
        )}
      </div>

      <div className="bg-white rounded border p-4">
        <h2 className="font-semibold text-gray-800 mb-1 text-sm">Matching Profile</h2>
        <div className="text-xs text-gray-500 mb-3">
          Score is based on this profile versus each job description and requirements.
        </div>
        {isLoading ? (
          <div className="text-gray-400 text-sm">Loading...</div>
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              saveMutation.mutate(payload());
              setProfileSaved(true);
              setTimeout(() => setProfileSaved(false), 1500);
            }}
            className="space-y-3"
          >
            <div>
              <label className="block text-xs text-gray-500 mb-1">Skills used for matching (one per line)</label>
              <textarea
                rows={6}
                value={form.matching_skills_text}
                onChange={(e) => setForm((d) => ({ ...d, matching_skills_text: e.target.value }))}
                className="border rounded px-2 py-1 text-sm w-full"
                placeholder="python\nsql\nmachine learning"
              />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Years of experience</label>
                <input
                  type="number"
                  min={0}
                  value={form.matching_experience_years_text}
                  onChange={(e) => setForm((d) => ({ ...d, matching_experience_years_text: e.target.value }))}
                  className="border rounded px-2 py-1 text-sm w-full"
                  placeholder="e.g. 10"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Current title</label>
                <input
                  value={form.matching_current_title}
                  onChange={(e) => setForm((d) => ({ ...d, matching_current_title: e.target.value }))}
                  className="border rounded px-2 py-1 text-sm w-full"
                  placeholder="e.g. Director of Data"
                />
              </div>
            </div>
            {profileError ? (
              <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">
                {profileError}
              </div>
            ) : null}
            <div className="flex items-center gap-3">
              <button
                type="submit"
                disabled={saveMutation.isPending}
                className="rounded bg-blue-600 text-white px-3 py-1.5 text-sm hover:bg-blue-700 disabled:opacity-50"
              >
                Save Matching Profile
              </button>
              {profileSaved ? <span className="text-xs text-green-700">Saved</span> : null}
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

function ResumeUploadSection() {
  const queryClient = useQueryClient();
  const fileRef = useRef(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [uploading, setUploading] = useState(false);

  async function handleUpload(e) {
    const file = e.target.files[0];
    if (!file) return;
    setUploading(true);
    setResult(null);
    setError(null);
    const form = new FormData();
    form.append("file", file);
    try {
      const resp = await axios.post("/api/user/resume", form);
      setResult(resp.data);
      queryClient.invalidateQueries({ queryKey: ["discovery-settings"] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    } catch (err) {
      setError(err.response?.data?.detail ?? "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="bg-white rounded border p-4">
      <h2 className="font-semibold text-gray-800 mb-3 text-sm">Resume</h2>
      <div className="flex items-center gap-3">
        <input
          ref={fileRef}
          type="file"
          accept=".md,.txt,.pdf,.docx"
          onChange={handleUpload}
          className="hidden"
        />
        <button
          onClick={() => fileRef.current?.click()}
          disabled={uploading}
          className="rounded bg-blue-600 text-white px-3 py-1.5 text-sm hover:bg-blue-700 disabled:opacity-50"
        >
          {uploading ? "Uploading..." : "Upload Resume"}
        </button>
        <span className="text-xs text-gray-400">.md, .txt, .pdf, .docx</span>
      </div>
      {error && (
        <div className="mt-2 text-sm text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">
          {error}
        </div>
      )}
      {result && (
        <div className="mt-3 text-sm text-gray-700 space-y-1">
          <div>
            <span className="font-medium">Current title: </span>
            {result.current_title ?? "—"}
          </div>
          <div>
            <span className="font-medium">Skills: </span>
            {result.skills?.join(", ") || "none detected"}
          </div>
          <div>
            <span className="font-medium">Experience: </span>
            {result.experience_years != null ? `${result.experience_years} years` : "—"}
          </div>
          {result.titles?.length > 0 && (
            <div>
              <span className="font-medium">Titles: </span>
              {result.titles.join(", ")}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ApiUsageSection() {
  const { data: usage = [], isLoading } = useQuery({
    queryKey: ["api-usage"],
    queryFn: getApiUsage,
  });

  return (
    <div className="bg-white rounded border p-4">
      <h2 className="font-semibold text-gray-800 mb-3 text-sm">API Usage</h2>
      {isLoading ? (
        <div className="text-gray-400 text-sm">Loading...</div>
      ) : usage.length === 0 ? (
        <div className="text-gray-400 text-sm">No usage recorded yet.</div>
      ) : (
        <table className="w-full text-sm">
          <thead className="text-xs text-gray-500 uppercase tracking-wide">
            <tr>
              <th className="text-left py-1">Source</th>
              <th className="text-right py-1">Requests</th>
              <th className="text-right py-1">Cost</th>
            </tr>
          </thead>
          <tbody>
            {usage.map((row, i) => (
              <tr key={i} className="border-t">
                <td className="py-1 text-gray-700">{row.api_name}</td>
                <td className="py-1 text-right text-gray-700">{row.total_requests}</td>
                <td className="py-1 text-right text-gray-700">${(row.total_cost ?? 0).toFixed(4)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default function SettingsPage() {
  return (
    <div className="space-y-6 max-w-3xl">
      <h1 className="text-lg font-semibold text-gray-900">Filters</h1>
      <DiscoverySettingsSection />
      <ResumeUploadSection />
      <ApiUsageSection />
    </div>
  );
}
