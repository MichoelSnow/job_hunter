import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { createCompany, getCompanies, updateCompany } from "../services/api";

export default function CompaniesPage() {
  const queryClient = useQueryClient();
  const [newName, setNewName] = useState("");
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
      setNewName("");
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

  function startEdit(company) {
    setEditingId(company.id);
    setEditData({
      name: company.name,
      website: company.website ?? "",
      ats_type: company.ats_type ?? "",
      ats_id: company.ats_id ?? "",
    });
  }

  function saveEdit() {
    updateMutation.mutate({
      id: editingId,
      data: {
        ...editData,
        website: editData.website || null,
        ats_type: editData.ats_type || null,
        ats_id: editData.ats_id || null,
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
          if (newName.trim()) createMutation.mutate({ name: newName.trim() });
        }}
        className="flex gap-2 mb-4"
      >
        <input
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          placeholder="Company name"
          className="border rounded px-3 py-1.5 text-sm flex-1 max-w-xs"
        />
        <button
          type="submit"
          disabled={createMutation.isPending || !newName.trim()}
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
              <th className="text-left px-4 py-2">Website</th>
              <th className="text-left px-4 py-2">ATS Type</th>
              <th className="text-left px-4 py-2">ATS ID</th>
              <th className="px-4 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-gray-400">Loading...</td>
              </tr>
            ) : companies.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-gray-400">No companies yet.</td>
              </tr>
            ) : (
              companies.map((company) => (
                <tr key={company.id} className="border-b last:border-0 hover:bg-gray-50">
                  <td className="px-4 py-2 font-medium text-gray-900">
                    {editingId === company.id ? (
                      <input
                        value={editData.name}
                        onChange={(e) => setEditData((d) => ({ ...d, name: e.target.value }))}
                        className="border rounded px-1 py-0.5 text-sm w-36"
                      />
                    ) : (
                      company.name
                    )}
                  </td>
                  <td className="px-4 py-2 text-gray-600">
                    {editingId === company.id ? (
                      <input
                        value={editData.website}
                        onChange={(e) => setEditData((d) => ({ ...d, website: e.target.value }))}
                        placeholder="https://..."
                        className="border rounded px-1 py-0.5 text-sm w-40"
                      />
                    ) : company.website ? (
                      <a href={company.website} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline">
                        {company.website}
                      </a>
                    ) : (
                      "—"
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
                        <option value="html">html</option>
                      </select>
                    ) : (
                      company.ats_type ?? "—"
                    )}
                  </td>
                  <td className="px-4 py-2 text-gray-600">
                    {editingId === company.id ? (
                      <input
                        value={editData.ats_id}
                        onChange={(e) => setEditData((d) => ({ ...d, ats_id: e.target.value }))}
                        className="border rounded px-1 py-0.5 text-sm w-28"
                      />
                    ) : (
                      company.ats_id ?? "—"
                    )}
                  </td>
                  <td className="px-4 py-2 text-right">
                    {editingId === company.id ? (
                      <div className="flex gap-2 justify-end text-xs">
                        <button onClick={saveEdit} className="text-blue-600 hover:underline">Save</button>
                        <button onClick={() => setEditingId(null)} className="text-gray-400 hover:text-gray-600">Cancel</button>
                      </div>
                    ) : (
                      <button onClick={() => startEdit(company)} className="text-xs text-gray-500 hover:text-blue-600">
                        Edit
                      </button>
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
