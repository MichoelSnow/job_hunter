import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  createCompany,
  deleteCompany,
  getCompanies,
  updateCompany,
} from "../services/api";

const EMPTY_COMPANY_FORM = {
  name: "",
  website_url: "",
  ats_type: "",
  ats_id: "",
  workday_board: "",
  workday_instance: "",
  html_selectors_text: "",
};

export default function CompaniesPage() {
  const queryClient = useQueryClient();
  const [newCompany, setNewCompany] = useState(EMPTY_COMPANY_FORM);
  const [editingId, setEditingId] = useState(null);
  const [editData, setEditData] = useState({});
  const [error, setError] = useState(null);

  const { data: companies = [], isLoading } = useQuery({
    queryKey: ["companies"],
    queryFn: getCompanies,
  });

  const createMutation = useMutation({
    mutationFn: createCompany,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["companies"] });
      setNewCompany(EMPTY_COMPANY_FORM);
      setError(null);
    },
    onError: (err) => {
      setError(err.response?.data?.detail ?? "Failed to create company.");
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => updateCompany(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["companies"] });
      setEditingId(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteCompany,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["companies"] });
      setError(null);
      if (editingId !== null) setEditingId(null);
    },
    onError: (err) => {
      setError(err.response?.data?.detail ?? "Failed to delete company.");
    },
  });

  function startEdit(company) {
    setEditingId(company.id);
    setEditData({
      name: company.name,
      website_url: company.website_url ?? "",
      ats_type: company.ats_type ?? "",
      ats_id: company.ats_id ?? "",
      workday_board: company.workday_board ?? "",
      workday_instance: company.workday_instance ?? "",
      html_selectors_text: company.html_selectors
        ? JSON.stringify(company.html_selectors, null, 2)
        : "",
    });
  }

  const newAtsType = (newCompany.ats_type || "").toLowerCase();
  const showNewWorkdayFields = newAtsType === "workday";
  const showNewHtmlSelectors = newAtsType === "custom" || newAtsType === "html";

  function saveEdit() {
    let htmlSelectors = null;
    if (editData.html_selectors_text?.trim()) {
      try {
        htmlSelectors = JSON.parse(editData.html_selectors_text);
      } catch {
        setError("html_selectors must be valid JSON.");
        return;
      }
    }

    updateMutation.mutate({
      id: editingId,
      data: {
        ...editData,
        website_url: editData.website_url || null,
        ats_type: editData.ats_type || null,
        ats_id: editData.ats_id || null,
        workday_board: editData.workday_board || null,
        workday_instance: editData.workday_instance || null,
        html_selectors: htmlSelectors,
      },
    });
  }

  return (
    <div>
      <h1 className="text-lg font-semibold mb-4 text-gray-900">Companies</h1>

      {/* Add form */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (!newCompany.name.trim()) return;
          let htmlSelectors = null;
          if (newCompany.html_selectors_text.trim()) {
            try {
              htmlSelectors = JSON.parse(newCompany.html_selectors_text);
            } catch {
              setError("html_selectors must be valid JSON.");
              return;
            }
          }
          createMutation.mutate({
            name: newCompany.name.trim(),
            website_url: newCompany.website_url.trim() || null,
            ats_type: newCompany.ats_type || null,
            ats_id: newCompany.ats_id.trim() || null,
            workday_board: newCompany.workday_board.trim() || null,
            workday_instance: newCompany.workday_instance.trim() || null,
            html_selectors: htmlSelectors,
          });
        }}
        className="flex flex-wrap gap-2 mb-4 items-end"
      >
        <input
          value={newCompany.name}
          onChange={(e) => setNewCompany((d) => ({ ...d, name: e.target.value }))}
          placeholder="Company name"
          className="border rounded px-3 py-1.5 text-sm flex-1 min-w-56"
        />
        <input
          value={newCompany.website_url}
          onChange={(e) => setNewCompany((d) => ({ ...d, website_url: e.target.value }))}
          placeholder="Website URL"
          className="border rounded px-3 py-1.5 text-sm flex-1 min-w-56"
        />
        <select
          value={newCompany.ats_type}
          onChange={(e) => setNewCompany((d) => ({ ...d, ats_type: e.target.value }))}
          className="border rounded px-3 py-1.5 text-sm min-w-40"
        >
          <option value="">ATS Type</option>
          <option value="greenhouse">greenhouse</option>
          <option value="lever">lever</option>
          <option value="workday">workday</option>
          <option value="ashby">ashby</option>
          <option value="custom">custom</option>
          <option value="html">html</option>
        </select>
        <input
          value={newCompany.ats_id}
          onChange={(e) => setNewCompany((d) => ({ ...d, ats_id: e.target.value }))}
          placeholder="ATS ID"
          className="border rounded px-3 py-1.5 text-sm min-w-40"
        />
        {showNewWorkdayFields ? (
          <>
            <input
              value={newCompany.workday_board}
              onChange={(e) => setNewCompany((d) => ({ ...d, workday_board: e.target.value }))}
              placeholder="Workday board (optional)"
              className="border rounded px-3 py-1.5 text-sm min-w-48"
            />
            <input
              value={newCompany.workday_instance}
              onChange={(e) => setNewCompany((d) => ({ ...d, workday_instance: e.target.value }))}
              placeholder="Workday instance (wd1, wd5...)"
              className="border rounded px-3 py-1.5 text-sm min-w-48"
            />
          </>
        ) : null}
        {showNewHtmlSelectors ? (
          <textarea
            value={newCompany.html_selectors_text}
            onChange={(e) => setNewCompany((d) => ({ ...d, html_selectors_text: e.target.value }))}
            placeholder='html_selectors JSON, e.g. {"job_list":"ul.jobs li","title":"a.title","url":"a.title"}'
            rows={2}
            className="border rounded px-3 py-1.5 text-sm min-w-[24rem] flex-1"
          />
        ) : null}
        <button
          type="submit"
          disabled={createMutation.isPending || !newCompany.name.trim()}
          className="rounded bg-blue-600 text-white px-3 py-1.5 text-sm hover:bg-blue-700 disabled:opacity-50"
        >
          Add
        </button>
      </form>
      {error && (
        <div className="mb-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">
          {error}
        </div>
      )}

      <div className="bg-white rounded border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b text-xs text-gray-500 uppercase tracking-wide">
            <tr>
              <th className="text-left px-4 py-2">Name</th>
              <th className="text-left px-4 py-2">ATS Type</th>
              <th className="text-left px-4 py-2">ATS ID</th>
              <th className="px-4 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-gray-400">Loading...</td>
              </tr>
            ) : companies.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-gray-400">No companies yet.</td>
              </tr>
            ) : (
              companies.map((company) => (
                <tr key={company.id} className="border-b last:border-0 hover:bg-gray-50">
                  <td className="px-4 py-2 font-medium text-gray-900">
                    {editingId === company.id ? (
                      <div className="space-y-1">
                        <input
                          value={editData.name}
                          onChange={(e) => setEditData((d) => ({ ...d, name: e.target.value }))}
                          className="border rounded px-1 py-0.5 text-sm w-56"
                        />
                        <input
                          value={editData.website_url}
                          onChange={(e) => setEditData((d) => ({ ...d, website_url: e.target.value }))}
                          placeholder="https://..."
                          className="border rounded px-1 py-0.5 text-sm w-72"
                        />
                      </div>
                    ) : company.website_url ? (
                      <a
                        href={company.website_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-blue-600 hover:underline"
                      >
                        {company.name}
                      </a>
                    ) : (
                      company.name
                    )}
                  </td>
                  <td className="px-4 py-2 text-gray-600">
                    {editingId === company.id ? (
                      <select
                        value={editData.ats_type}
                        onChange={(e) => setEditData((d) => ({ ...d, ats_type: e.target.value }))}
                        className="border rounded px-1 py-0.5 text-sm"
                      >
                        <option value="">—</option>
                        <option value="greenhouse">greenhouse</option>
                        <option value="lever">lever</option>
                        <option value="workday">workday</option>
                        <option value="ashby">ashby</option>
                        <option value="custom">custom</option>
                        <option value="html">html</option>
                      </select>
                    ) : (
                      company.ats_type ?? "—"
                    )}
                  </td>
                  <td className="px-4 py-2 text-gray-600">
                    {editingId === company.id ? (
                      <div className="space-y-1">
                        <input
                          value={editData.ats_id}
                          onChange={(e) => setEditData((d) => ({ ...d, ats_id: e.target.value }))}
                          className="border rounded px-1 py-0.5 text-sm w-44"
                          placeholder="ATS ID"
                        />
                        {(editData.ats_type || "").toLowerCase() === "workday" ? (
                          <>
                            <input
                              value={editData.workday_board}
                              onChange={(e) => setEditData((d) => ({ ...d, workday_board: e.target.value }))}
                              className="border rounded px-1 py-0.5 text-sm w-44"
                              placeholder="Workday board"
                            />
                            <input
                              value={editData.workday_instance}
                              onChange={(e) => setEditData((d) => ({ ...d, workday_instance: e.target.value }))}
                              className="border rounded px-1 py-0.5 text-sm w-44"
                              placeholder="Workday instance"
                            />
                          </>
                        ) : null}
                        {(editData.ats_type || "").toLowerCase() === "custom" ||
                        (editData.ats_type || "").toLowerCase() === "html" ? (
                          <textarea
                            value={editData.html_selectors_text}
                            onChange={(e) => setEditData((d) => ({ ...d, html_selectors_text: e.target.value }))}
                            rows={2}
                            className="border rounded px-1 py-0.5 text-sm w-64"
                            placeholder='html_selectors JSON'
                          />
                        ) : null}
                      </div>
                    ) : (
                      <div className="space-y-0.5">
                        <div>{company.ats_id ?? "—"}</div>
                        {company.workday_board ? (
                          <div className="text-xs text-gray-500">board: {company.workday_board}</div>
                        ) : null}
                        {company.workday_instance ? (
                          <div className="text-xs text-gray-500">instance: {company.workday_instance}</div>
                        ) : null}
                        {company.html_selectors ? (
                          <div className="text-xs text-gray-500">html selectors configured</div>
                        ) : null}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-2 text-right">
                    {editingId === company.id ? (
                      <div className="flex gap-2 justify-end text-xs">
                        <button onClick={saveEdit} className="text-blue-600 hover:underline">Save</button>
                        <button onClick={() => setEditingId(null)} className="text-gray-400 hover:text-gray-600">Cancel</button>
                      </div>
                    ) : (
                      <div className="flex gap-3 justify-end text-xs">
                        <button
                          onClick={() => startEdit(company)}
                          className="text-gray-500 hover:text-blue-600"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => {
                            const confirmed = window.confirm(
                              `Delete ${company.name}? This removes it from the database.`
                            );
                            if (confirmed) {
                              deleteMutation.mutate(company.id);
                            }
                          }}
                          className="text-red-600 hover:text-red-700"
                        >
                          Delete
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
