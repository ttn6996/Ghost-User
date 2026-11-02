export type RunStatus = 'queued' | 'running' | 'passed' | 'failed' | 'error' | 'cancelled';
export type StepStatus = 'passed' | 'failed' | 'error' | 'skipped';
export type TriggerType = 'manual' | 'schedule' | 'api';

export type ActionType = 
  | 'goto'
  | 'click'
  | 'fill'
  | 'select_option'
  | 'check'
  | 'uncheck'
  | 'wait_for_visible'
  | 'assert_visible'
  | 'assert_text'
  | 'assert_url'
  | 'screenshot';

export interface StepAction {
  action: ActionType;
  url?: string;
  selector?: string;
  value?: string;
  expected_text?: string;
  exact?: boolean;
  expected_url?: string;
  name?: string;
  timeout_ms?: number;
}

export interface TestDefinition {
  name: string;
  description?: string;
  steps: StepAction[];
}

export interface Project {
  id: string;
  name: string;
  base_url: string;
  description?: string;
  source_code_path?: string;
  allow_local_loopback?: boolean;
  execution_mode?: string;
  auth_profile_json?: any;
  secrets_json?: any;
  created_at: string;
  updated_at: string;
}

export interface TestCase {
  id: string;
  project_id: string;
  name: string;
  description?: string;
  enabled: boolean;
  definition_json: TestDefinition;
  created_at: string;
  updated_at: string;
}

export interface TestStepResult {
  id: string;
  test_run_id: string;
  step_index: number;
  action: string;
  status: StepStatus;
  started_at?: string;
  finished_at?: string;
  duration_ms?: number;
  error_message?: string;
  screenshot_path?: string;
}

export interface ConsoleLog {
  type: string;
  text: string;
  location?: Record<string, any>;
  timestamp: string;
}

export interface TestRun {
  id: string;
  test_case_id: string;
  status: RunStatus;
  started_at?: string;
  finished_at?: string;
  duration_ms?: number;
  error_summary?: string;
  trigger_type: TriggerType;
  console_logs_json?: ConsoleLog[];
  page_errors_json?: string[];
  trace_path?: string;
  created_at: string;
  step_results?: TestStepResult[];
}

export interface Schedule {
  id: string;
  test_case_id: string;
  cron_expression?: string;
  interval_seconds?: number;
  enabled: boolean;
  next_run_at?: string;
  last_run_at?: string;
  created_at: string;
  updated_at: string;
}

export interface TestCaseGenerateResponse {
  suggested_name: string;
  suggested_description: string;
  steps: StepAction[];
  model_used: string;
  explanation: string;
}

export interface DiscoveryPage {
  url: string;
  path: string;
  title: string;
  status_code: number;
  forms_count: number;
  links_found: number;
  is_broken: boolean;
}

export interface DiscoveredForm {
  page_path: string;
  page_url: string;
  form_type: string;
  inputs: { name: string; id: string; type: string; placeholder: string }[];
  buttons: { type: string; text: string }[];
}

export interface DiscoveryReport {
  id: string;
  project_id: string;
  status: string;
  base_url: string;
  pages_count: number;
  broken_links_count: number;
  forms_count: number;
  pages_json?: DiscoveryPage[];
  suggested_tests_json?: {
    name: string;
    description?: string;
    steps: StepAction[];
  }[];
  error_message?: string;
  created_at: string;
  finished_at?: string;
}

export interface OverviewStats {
  total_projects: number;
  total_test_cases: number;
  total_runs: number;
  passed_runs: number;
  failed_runs: number;
  error_runs: number;
  running_runs: number;
  queued_runs: number;
  pass_rate_percentage: number;
  recent_runs: {
    id: string;
    test_case_id: string;
    status: RunStatus;
    duration_ms?: number;
    trigger_type: TriggerType;
    created_at: string;
  }[];
  recent_failures: {
    id: string;
    test_case_id: string;
    status: RunStatus;
    error_summary?: string;
    created_at: string;
  }[];
}


export interface DevServerInfo {
  project_id: string;
  local_path: string;
  command: string;
  pid?: number;
  target_url?: string;
  port?: number;
  is_running: boolean;
  start_time?: number;
  last_log?: string;
}

export interface DiscoveredRoute {
  path: string;
  file_path: string;
  type: string;
}

export interface SourceScanResult {
  project_id: string;
  source_path: string;
  detected_frameworks: string[];
  routes: DiscoveredRoute[];
  forms: DiscoveredForm[];
  start_command?: string;
  package_manager?: string;
}

export interface AutonomousAuditResponse {
  project_id: string;
  base_url: string;
  status: string;
  frameworks: string[];
  source_code_path?: string;
  dev_server_running: boolean;
  dev_server_url?: string;
  static_routes_count: number;
  pages_audited_count: number;
  broken_links_count: number;
  forms_detected_count: number;
  console_errors_count: number;
  tests_executed_count: number;
  tests_passed_count: number;
  tests_failed_count: number;
  test_runs: {
    id: string;
    test_case_id: string;
    name: string;
    status: RunStatus;
    duration_ms?: number;
    error_summary?: string;
  }[];
  discovery_report_id?: string;
  audit_summary: string;
  visual_qa_report?: {
    page_url: string;
    visual_score_out_of_100: number;
    has_visual_bugs: boolean;
    issues: { severity: string; category: string; description: string; suggested_fix: string }[];
    ux_recommendations: string[];
  };
}


export interface AISetting {
  id: string;
  provider: string; // 'gemini' | 'openai' | 'anthropic' | 'custom_openai'
  base_url?: string;
  api_key_masked?: string;
  model: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface AITestConnectionResult {
  success: boolean;
  provider: string;
  base_url: string;
  model: string;
  latency_ms: number;
  reply?: string;
  error?: string;
}
