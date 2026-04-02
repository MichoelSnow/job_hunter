import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  createApplication,
  deleteApplication,
  getApplications,
  getStatusHistory,
  updateApplication,
} from "../services/api";

const STATUSES = ["interested", "applied", "phone_screen", "interview", "offer", "rejected", "withdrawn"];

const STATUS_COLORS = {
  interested: "bg-blue-100 text-blue-800",
  applied: "bg-indigo-100 text-indigo-800",
  phone_screen: "bg-yellow-100 text-yellow-800",
  interview: "bg-orange-100 text-orange-800",
  offer: "bg-green-100 text-green-800",
  rejected: "bg-red-100 text-red-800",
  withdrawn: "bg-gray-100 text-gray-600",
};

function StatusBadge({ status }) {
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[status] ?? "bg-gray-100 text-gray-600"}`}>
      {status}
    </span>
  );
}

function HistoryPanel({ appId, onClose }) {
  const { data: history = [], isLoading } = useQuery({
    queryKey: ["history", appId],
    queryFn: () => getStatusHistory(appId),
    enabled: !!appId,
  });

  return (
    <div className="fixed inset-y-0 right-0 w-80 bg-white shadow-xl flex flex-col z-10 border-l">
      <div className="flex items-center justify-between px-4 py-3 border-b">
        <span className="font-semibold text-gray-800 text-sm">Status History</span>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">
          ×
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        {isLoading ? (
          <div className="text-gray-400 text-sm">Loading...</div>
        ) : history.length === 0 ? (
          <div className="text-gray-400 text-sm">No history yet.</div>
        ) : (
          <ol className="relative border-l border-gray-200 space-y-4 ml-2">
            {history.map((h) => (
              <li key={h.id} className="ml-4">
                <div className="absolute -left-1.5 mt-1 w-3 h-3 rounded-full bg-blue-400 border-2 border-white" />
                <div className="text-xs text-gray-400">
                  {new Date(h.changed_at).toLocaleString()}
                </div>
                <div className="text-sm mt-0.5">
                  <StatusBadge status={h.old_status ?? "—"} />
                  {" → "}
                  <StatusBadge status={h.new_status} />
                </div>
                {h.notes && <div className="text-xs text-gray-500 mt-0.5">{h.notes}</div>}
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}

export default function ApplicationsPage() {
  const queryClient = useQueryClient();
  const [historyAppId, setHistoryAppId] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [editStatus, setEditStatus] = useState("");
  const [editNotes, setEditNotes] = useState("");

  const { data: applications = [], isLoading, isError } = useQuery({
    queryKey: ["applications"],
    queryFn: getApplications,
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => updateApplication(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["applications"] });
      queryClient.invalidateQueries({ queryKey: ["history", editingId] });
      setEditingId(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteApplication,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["applications"] }),
  });

  function startEdit(app) {
    setEditingId(app.id);
    setEditStatus(app.status);
    setEditNotes(app.notes ?? "");
  }

  function saveEdit() {
    updateMutation.mutate({ id: editingId, data: { status: editStatus, notes: editNotes } });
  }

  return (
    <div className="relative">
      <div className={historyAppId ? "mr-80" : ""}>
        <h1 className="text-lg font-semibold mb-4 text-gray-900">Applications</h1>

        {isError && (
          <div className="mb-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">
            Failed to load applications.
          </div>
        )}

        <div className="bg-white rounded border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b text-xs text-gray-500 uppercase tracking-wide">
              <tr>
                <th className="text-left px-4 py-2">Job ID</th>
                <th className="text-left px-4 py-2">Status</th>
                <th className="text-left px-4 py-2">Applied</th>
                <th className="text-left px-4 py-2">Notes</th>
                <th className="px-4 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-gray-400">
                    Loading...
                  </td>
                </tr>
              ) : applications.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-gray-400">
                    No applications yet.
                  </td>
                </tr>
              ) : (
                applications.map((app) => (
                  <tr key={app.id} className="border-b last:border-0 hover:bg-gray-50">
                    <td className="px-4 py-2 text-gray-700">#{app.job_id}</td>
                    <td className="px-4 py-2">
                      {editingId === app.id ? (
                        <select
                          value={editStatus}
                          onChange={(e) => setEditStatus(e.target.value)}
                          className="border rounded px-1 py-0.5 text-sm"
                        >
                          {STATUSES.map((s) => (
                            <option key={s} value={s}>{s}</option>
                          ))}
                        </select>
                      ) : (
                        <StatusBadge status={app.status} />
                      )}
                    </td>
                    <td className="px-4 py-2 text-gray-500">{app.applied_date ?? "—"}</td>
                    <td className="px-4 py-2 text-gray-600 max-w-xs truncate">
                      {editingId === app.id ? (
                        <input
                          value={editNotes}
                          onChange={(e) => setEditNotes(e.target.value)}
                          className="border rounded px-1 py-0.5 text-sm w-full"
                        />
                      ) : (
                        app.notes ?? "—"
                      )}
                    </td>
                    <td className="px-4 py-2 text-right">
                      <div className="flex gap-2 justify-end text-xs">
                        {editingId === app.id ? (
                          <>
                            <button
                              onClick={saveEdit}
                              disabled={updateMutation.isPending}
                              className="text-blue-600 hover:underline"
                            >
                              Save
                            </button>
                            <button
                              onClick={() => setEditingId(null)}
                              className="text-gray-400 hover:text-gray-600"
                            >
                              Cancel
                            </button>
                          </>
                        ) : (
                          <>
                            <button
                              onClick={() => startEdit(app)}
                              className="text-gray-500 hover:text-blue-600"
                            >
                              Edit
                            </button>
                            <button
                              onClick={() => setHistoryAppId(app.id === historyAppId ? null : app.id)}
                              className="text-gray-500 hover:text-indigo-600"
                            >
                              History
                            </button>
                            <button
                              onClick={() => deleteMutation.mutate(app.id)}
                              className="text-gray-400 hover:text-red-500"
                            >
                              Delete
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {historyAppId && (
        <HistoryPanel appId={historyAppId} onClose={() => setHistoryAppId(null)} />
      )}
    </div>
  );
}
