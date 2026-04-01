import { Route, Routes } from "react-router-dom";
import ApplicationsPage from "./pages/ApplicationsPage";
import CompaniesPage from "./pages/CompaniesPage";
import JobsPage from "./pages/JobsPage";
import SettingsPage from "./pages/SettingsPage";

export default function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="border-b bg-white px-6 py-3 flex gap-6 text-sm font-medium">
        <a href="/" className="text-gray-900 hover:text-blue-600">
          Jobs
        </a>
        <a href="/applications" className="text-gray-900 hover:text-blue-600">
          Applications
        </a>
        <a href="/companies" className="text-gray-900 hover:text-blue-600">
          Companies
        </a>
        <a href="/settings" className="text-gray-900 hover:text-blue-600">
          Settings
        </a>
      </nav>
      <main className="p-6">
        <Routes>
          <Route path="/" element={<JobsPage />} />
          <Route path="/applications" element={<ApplicationsPage />} />
          <Route path="/companies" element={<CompaniesPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>
    </div>
  );
}
