import axios from "axios";

const api = axios.create({
  baseURL: "/api",
  timeout: 30_000,
});

// Jobs
export const getJobs = (params) => api.get("/jobs", { params }).then((r) => r.data);
export const getJob = (id) => api.get(`/jobs/${id}`).then((r) => r.data);
export const refreshApiJobs = () => api.post("/jobs/refresh/apis").then((r) => r.data);
export const refreshScrapedJobs = () => api.post("/jobs/refresh/scrapers").then((r) => r.data);
export const getRefreshStatus = () => api.get("/jobs/refresh/status").then((r) => r.data);
export const hideJob = (id) => api.put(`/jobs/${id}/hide`).then((r) => r.data);
export const unhideJob = (id) => api.put(`/jobs/${id}/unhide`).then((r) => r.data);
export const getJobLocations = (params) => api.get("/jobs/filters/locations", { params }).then((r) => r.data);

// Applications
export const getApplications = () => api.get("/applications").then((r) => r.data);
export const createApplication = (data) => api.post("/applications", data).then((r) => r.data);
export const updateApplication = (id, data) =>
  api.put(`/applications/${id}`, data).then((r) => r.data);
export const deleteApplication = (id) => api.delete(`/applications/${id}`).then((r) => r.data);
export const getStatusHistory = (id) =>
  api.get(`/applications/${id}/history`).then((r) => r.data);

// Companies
export const getCompanies = (params) => api.get("/companies", { params }).then((r) => r.data);
export const createCompany = (data) => api.post("/companies", data).then((r) => r.data);
export const updateCompany = (id, data) => api.put(`/companies/${id}`, data).then((r) => r.data);
export const deleteCompany = (id) => api.delete(`/companies/${id}`).then((r) => r.data);

// Criteria
export const getCriteria = () => api.get("/criteria").then((r) => r.data);
export const createCriterion = (data) => api.post("/criteria", data).then((r) => r.data);
export const updateCriterion = (id, data) =>
  api.put(`/criteria/${id}`, data).then((r) => r.data);
export const deleteCriterion = (id) => api.delete(`/criteria/${id}`).then((r) => r.data);

// Discovery Settings
export const getDiscoverySettings = () => api.get("/settings/discovery").then((r) => r.data);
export const updateDiscoverySettings = (data) =>
  api.put("/settings/discovery", data).then((r) => r.data);

// Analytics
export const getDashboardStats = () => api.get("/analytics/dashboard").then((r) => r.data);
export const getApiUsage = () => api.get("/analytics/api-usage").then((r) => r.data);
export const getUserProfile = () => api.get("/user/profile").then((r) => r.data);
