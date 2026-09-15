export function formatLocation(location) {
  return location || "Location unavailable";
}

export function formatSalary(job) {
  if (!job.salary_min && !job.salary_max) return "—";
  const min = job.salary_min ? `$${job.salary_min.toLocaleString()}` : "";
  const max = job.salary_max ? `$${job.salary_max.toLocaleString()}` : "";
  if (min && max) return `${min} - ${max}`;
  return min || max;
}
