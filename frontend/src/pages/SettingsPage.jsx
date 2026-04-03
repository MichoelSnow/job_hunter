import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import {
  createCriterion,
  deleteCriterion,
  getApiUsage,
  getCriteria,
  getDiscoverySettings,
  getUserProfile,
  updateDiscoverySettings,
  updateCriterion,
} from "../services/api";
import axios from "axios";

const CRITERION_TYPES = ["industry", "location", "min_salary", "role_level", "company_size", "other"];

function DiscoverySettingsSection() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    search_queries_text: "",
    filter_location_query: "",
    filter_title_query: "",
    filter_exclude_remote: true,
    filter_target_salary_text: "",
    filter_include_missing_salary: true,
  });
  const [apiError, setApiError] = useState(null);
  const [filtersError, setFiltersError] = useState(null);
  const [apiSaved, setApiSaved] = useState(false);
  const [filtersSaved, setFiltersSaved] = useState(false);

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
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
    onError: (err) => {
      const message = err.response?.data?.detail ?? "Failed to save settings.";
      setApiError(message);
      setFiltersError(message);
    },
  });

  useEffect(() => {
    if (!data) return;
    setForm({
      search_queries_text: (data.search_queries || []).join("\n"),
      filter_location_query: data.filter_location_query || "",
      filter_title_query: data.filter_title_query || "",
      filter_exclude_remote: !!data.filter_exclude_remote,
      filter_target_salary_text:
        data.filter_target_salary == null ? "" : String(data.filter_target_salary),
      filter_include_missing_salary: !!data.filter_include_missing_salary,
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
              saveMutation.mutate({
                search_queries: parsedQueries(),
                filter_location_query: form.filter_location_query,
                filter_title_query: form.filter_title_query,
                filter_exclude_remote: form.filter_exclude_remote,
                filter_target_salary: parsedTargetSalary(),
                filter_include_missing_salary: form.filter_include_missing_salary,
              });
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
              saveMutation.mutate({
                search_queries: parsedQueries(),
                filter_location_query: form.filter_location_query,
                filter_title_query: form.filter_title_query,
                filter_exclude_remote: form.filter_exclude_remote,
                filter_target_salary: parsedTargetSalary(),
                filter_include_missing_salary: form.filter_include_missing_salary,
              });
              setFiltersSaved(true);
              setTimeout(() => setFiltersSaved(false), 1500);
            }}
            className="space-y-3"
          >
            <div>
              <label className="block text-xs text-gray-500 mb-1">
                Allowed locations query (Boolean)
              </label>
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
              <label className="block text-xs text-gray-500 mb-1">
                Job title query (Boolean)
              </label>
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
    </div>
  );
}

function ProfileSection() {
  const { data: profile, isLoading } = useQuery({
    queryKey: ["user-profile"],
    queryFn: getUserProfile,
  });

  const user = profile?.user ?? {};
  const parsedResume = profile?.parsed_resume ?? {};

  return (
    <div className="bg-white rounded border p-4">
      <h2 className="font-semibold text-gray-800 mb-3 text-sm">Profile</h2>
      {isLoading ? (
        <div className="text-gray-400 text-sm">Loading...</div>
      ) : (
        <div className="grid grid-cols-2 gap-3 text-sm text-gray-700">
          <div>
            <div className="text-xs text-gray-400 uppercase tracking-wide mb-0.5">Name</div>
            <div>{user.name ?? "—"}</div>
          </div>
          <div>
            <div className="text-xs text-gray-400 uppercase tracking-wide mb-0.5">Current title</div>
            <div>{profile?.current_title ?? "—"}</div>
          </div>
          <div>
            <div className="text-xs text-gray-400 uppercase tracking-wide mb-0.5">Resume path</div>
            <div>{user.resume_file_path ?? "—"}</div>
          </div>
          <div>
            <div className="text-xs text-gray-400 uppercase tracking-wide mb-0.5">Parsed skills</div>
            <div>{(parsedResume.skills || []).length}</div>
          </div>
        </div>
      )}
    </div>
  );
}

function ResumeUploadSection() {
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
  const queryClient = useQueryClient();
  const [newCriterion, setNewCriterion] = useState({
    criterion_type: "industry",
    criterion_value: "",
    is_hard_requirement: false,
    weight: 1.0,
  });
  const [editingId, setEditingId] = useState(null);
  const [editData, setEditData] = useState({});
  const [addError, setAddError] = useState(null);

  const { data: criteria = [], isLoading } = useQuery({
    queryKey: ["criteria"],
    queryFn: getCriteria,
  });

  const createMutation = useMutation({
    mutationFn: createCriterion,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["criteria"] });
      setNewCriterion({ criterion_type: "industry", criterion_value: "", is_hard_requirement: false, weight: 1.0 });
      setAddError(null);
    },
    onError: (err) => setAddError(err.response?.data?.detail ?? "Failed to add criterion."),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => updateCriterion(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["criteria"] });
      setEditingId(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteCriterion,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["criteria"] }),
  });

  function startEdit(c) {
    setEditingId(c.id);
    setEditData({ criterion_type: c.criterion_type, criterion_value: c.criterion_value, is_hard_requirement: c.is_hard_requirement, weight: c.weight });
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <h1 className="text-lg font-semibold text-gray-900">Filters</h1>
      <DiscoverySettingsSection />

      {/* Criteria */}
      <div className="bg-white rounded border p-4">
        <h2 className="font-semibold text-gray-800 mb-3 text-sm">Job Filters: Match Criteria</h2>
        <div className="mb-3 text-xs text-gray-500">
          Criteria are applied after jobs are collected and influence match scoring.
        </div>

        {/* Add form */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (newCriterion.criterion_value.trim()) {
              createMutation.mutate({ ...newCriterion, criterion_value: newCriterion.criterion_value.trim() });
            }
          }}
          className="grid grid-cols-[1fr_1fr_auto_auto_auto] gap-2 items-end mb-3"
        >
          <div>
            <label className="block text-xs text-gray-500 mb-0.5">Type</label>
            <select
              value={newCriterion.criterion_type}
              onChange={(e) => setNewCriterion((d) => ({ ...d, criterion_type: e.target.value }))}
              className="border rounded px-2 py-1 text-sm w-full"
            >
              {CRITERION_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-0.5">Value</label>
            <input
              value={newCriterion.criterion_value}
              onChange={(e) => setNewCriterion((d) => ({ ...d, criterion_value: e.target.value }))}
              placeholder="e.g. healthcare"
              className="border rounded px-2 py-1 text-sm w-full"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-0.5">Weight</label>
            <input
              type="number"
              step={0.5}
              min={0}
              max={5}
              value={newCriterion.weight}
              onChange={(e) => setNewCriterion((d) => ({ ...d, weight: Number(e.target.value) }))}
              className="border rounded px-2 py-1 text-sm w-16"
            />
          </div>
          <div className="flex items-center gap-1 pb-0.5">
            <input
              type="checkbox"
              id="hard-req"
              checked={newCriterion.is_hard_requirement}
              onChange={(e) => setNewCriterion((d) => ({ ...d, is_hard_requirement: e.target.checked }))}
            />
            <label htmlFor="hard-req" className="text-xs text-gray-600 whitespace-nowrap">Hard req</label>
          </div>
          <button
            type="submit"
            disabled={createMutation.isPending}
            className="rounded bg-blue-600 text-white px-3 py-1.5 text-sm hover:bg-blue-700 disabled:opacity-50"
          >
            Add
          </button>
        </form>

        {addError && (
          <div className="mb-2 text-sm text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">
            {addError}
          </div>
        )}

        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b text-xs text-gray-500 uppercase tracking-wide">
            <tr>
              <th className="text-left px-3 py-2">Type</th>
              <th className="text-left px-3 py-2">Value</th>
              <th className="text-center px-3 py-2">Weight</th>
              <th className="text-center px-3 py-2">Hard req</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr><td colSpan={5} className="px-3 py-6 text-center text-gray-400">Loading...</td></tr>
            ) : criteria.length === 0 ? (
              <tr><td colSpan={5} className="px-3 py-6 text-center text-gray-400">No criteria defined.</td></tr>
            ) : (
              criteria.map((c) => (
                <tr key={c.id} className="border-b last:border-0 hover:bg-gray-50">
                  <td className="px-3 py-2 text-gray-700">
                    {editingId === c.id ? (
                      <select value={editData.criterion_type} onChange={(e) => setEditData((d) => ({ ...d, criterion_type: e.target.value }))} className="border rounded px-1 py-0.5 text-sm">
                        {CRITERION_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                      </select>
                    ) : c.criterion_type}
                  </td>
                  <td className="px-3 py-2 text-gray-700">
                    {editingId === c.id ? (
                      <input value={editData.criterion_value} onChange={(e) => setEditData((d) => ({ ...d, criterion_value: e.target.value }))} className="border rounded px-1 py-0.5 text-sm w-32" />
                    ) : c.criterion_value}
                  </td>
                  <td className="px-3 py-2 text-center text-gray-700">
                    {editingId === c.id ? (
                      <input type="number" step={0.5} min={0} max={5} value={editData.weight} onChange={(e) => setEditData((d) => ({ ...d, weight: Number(e.target.value) }))} className="border rounded px-1 py-0.5 text-sm w-14 text-center" />
                    ) : c.weight}
                  </td>
                  <td className="px-3 py-2 text-center">
                    {editingId === c.id ? (
                      <input type="checkbox" checked={editData.is_hard_requirement} onChange={(e) => setEditData((d) => ({ ...d, is_hard_requirement: e.target.checked }))} />
                    ) : c.is_hard_requirement ? "Yes" : "No"}
                  </td>
                  <td className="px-3 py-2 text-right">
                    {editingId === c.id ? (
                      <div className="flex gap-2 justify-end text-xs">
                        <button onClick={() => updateMutation.mutate({ id: c.id, data: editData })} className="text-blue-600 hover:underline">Save</button>
                        <button onClick={() => setEditingId(null)} className="text-gray-400 hover:text-gray-600">Cancel</button>
                      </div>
                    ) : (
                      <div className="flex gap-2 justify-end text-xs">
                        <button onClick={() => startEdit(c)} className="text-gray-500 hover:text-blue-600">Edit</button>
                        <button onClick={() => deleteMutation.mutate(c.id)} className="text-gray-400 hover:text-red-500">Delete</button>
                      </div>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <ProfileSection />
      <ResumeUploadSection />
      <ApiUsageSection />
    </div>
  );
}
