import { 
  Project, 
  TestCase, 
  TestRun, 
  Schedule, 
  OverviewStats, 
  TestDefinition,
  TestCaseGenerateResponse,
  DiscoveryReport,
  StepAction,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  const response = await fetch(url, {
    ...options,
    headers,
    cache: "no-store",
  });

  if (!response.ok) {
    let errorDetail = `Request failed: ${response.status} ${response.statusText}`;
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || JSON.stringify(errJson);
    } catch {
      // ignore
    }
    throw new Error(errorDetail);
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}

export const api = {
  // Stats
  getOverviewStats: () => request<OverviewStats>("/api/v1/stats/overview"),

  // Projects
  getProjects: (q?: string) => request<Project[]>(`/api/v1/projects${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  getProject: (id: string) => request<Project>(`/api/v1/projects/${id}`),
  createProject: (data: { name: string; base_url: string; description?: string }) => 
    request<Project>("/api/v1/projects", { method: "POST", body: JSON.stringify(data) }),
  updateProject: (id: string, data: Partial<Project>) => 
    request<Project>(`/api/v1/projects/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteProject: (id: string) => 
    request<void>(`/api/v1/projects/${id}`, { method: "DELETE" }),
  discoverProject: (projectId: string, maxPages: number = 15) => 
    request<DiscoveryReport>(`/api/v1/projects/${projectId}/discover?max_pages=${maxPages}`, {
      method: "POST",
    }),
  getLatestDiscovery: (projectId: string) => 
    request<DiscoveryReport | null>(`/api/v1/projects/${projectId}/discover/latest`),
  saveDiscoveredTest: (projectId: string, data: { name: string; description?: string; steps: StepAction[] }) => 
    request<TestCase>(`/api/v1/projects/${projectId}/discover/save-test`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // Test Cases
  getTestCases: (projectId?: string) => 
    request<TestCase[]>(`/api/v1/test-cases${projectId ? `?project_id=${projectId}` : ""}`),
  getTestCase: (id: string) => request<TestCase>(`/api/v1/test-cases/${id}`),
  createTestCase: (data: { project_id: string; name: string; description?: string; enabled?: boolean; definition_json: TestDefinition }) => 
    request<TestCase>("/api/v1/test-cases", { method: "POST", body: JSON.stringify(data) }),
  updateTestCase: (id: string, data: Partial<{ name: string; description?: string; enabled?: boolean; definition_json: TestDefinition }>) => 
    request<TestCase>(`/api/v1/test-cases/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteTestCase: (id: string) => 
    request<void>(`/api/v1/test-cases/${id}`, { method: "DELETE" }),
  validateTestDefinition: (definition_json: any) => 
    request<{ valid: boolean; step_count: number; errors: string[] }>("/api/v1/test-cases/validate", {
      method: "POST",
      body: JSON.stringify({ definition_json }),
    }),
  generateTestCase: (data: { project_id: string; prompt: string; page_path?: string }) => 
    request<TestCaseGenerateResponse>("/api/v1/test-cases/generate", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // Test Runs
  triggerRun: (testCaseId: string) => 
    request<TestRun>("/api/v1/test-runs", {
      method: "POST",
      body: JSON.stringify({ test_case_id: testCaseId, trigger_type: "manual" }),
    }),
  getRuns: (params?: { project_id?: string; test_case_id?: string; status?: string; page?: number; page_size?: number }) => {
    const searchParams = new URLSearchParams();
    if (params?.project_id) searchParams.set("project_id", params.project_id);
    if (params?.test_case_id) searchParams.set("test_case_id", params.test_case_id);
    if (params?.status) searchParams.set("status", params.status);
    if (params?.page) searchParams.set("page", params.page.toString());
    if (params?.page_size) searchParams.set("page_size", params.page_size.toString());
    const query = searchParams.toString();
    return request<{ items: TestRun[]; total: number; page: number; page_size: number }>(`/api/v1/test-runs${query ? `?${query}` : ""}`);
  },
  getRun: (id: string) => request<TestRun>(`/api/v1/test-runs/${id}`),
  cancelRun: (id: string) => request<TestRun>(`/api/v1/test-runs/${id}/cancel`, { method: "POST" }),

  // Artifacts
  getArtifactUrl: (path: string) => `${API_BASE}/api/v1/artifacts/${path}`,

  // Schedules
  getSchedules: (testCaseId?: string) => 
    request<Schedule[]>(`/api/v1/schedules${testCaseId ? `?test_case_id=${testCaseId}` : ""}`),
  createSchedule: (data: { test_case_id: string; interval_seconds?: number; cron_expression?: string; enabled?: boolean }) => 
    request<Schedule>("/api/v1/schedules", { method: "POST", body: JSON.stringify(data) }),
  toggleSchedule: (id: string) => 
    request<Schedule>(`/api/v1/schedules/${id}/toggle`, { method: "POST" }),
  deleteSchedule: (id: string) => 
    request<void>(`/api/v1/schedules/${id}`, { method: "DELETE" }),
};
