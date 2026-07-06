import type {
  EvaluationRequest,
  PipelineEvent,
  PluginFinding,
  PluginRunRecord,
  PluginSettingState,
  Policy,
  PolicyDecision,
  McpToolCall,
  PluginLogRecord
} from "@openleash/shared";

export type PromptPipelineResult = {
  finalPrompt: string;
  blocked: boolean;
  summary: string;
  model: string;
  compression?: {
    enabled: boolean;
    originalLength: number;
    compressedLength: number;
    ratio: number;
  };
  dlp?: {
    enabled: boolean;
    action: "block" | "mask";
    matched: boolean;
    categories: Array<"pii" | "phi" | "tokens" | "keys" | "credentials">;
    findings: Array<{ category: "pii" | "phi" | "tokens" | "keys" | "credentials"; quote: string; reason: string }>;
    masked: boolean;
  };
  runs: PluginRunRecord[];
};

export type EvaluationPipelineInput = {
  request: EvaluationRequest;
  organizationId?: string;
  conversationEventId?: string;
  userId?: string;
  computerId?: string;
  runtimeId?: string;
  policies: Policy[];
  plugins?: Map<string, PluginSettingState>;
};

export type SkillObservationInput = {
  agentKind: string;
  agentName: string;
  skillName: string;
  skillPath: string;
  content?: string | null;
  contentPreview?: string | null;
  status?: string;
  riskScore?: number;
  reasons: Array<{ reason: string; quote?: string }>;
};

export type SkillObservationResult = {
  status: "observed" | "suspicious";
  riskScore: number;
  reasons: Array<{ reason: string; quote?: string }>;
  findings: PluginFinding[];
  run: PluginRunRecord;
};

export type SiemExportInput = {
  request: EvaluationRequest;
  event: PipelineEvent;
  decision: "allow" | "ask" | "deny";
  summary: string;
  evaluationId?: string;
  conversationEventId: string;
  organization: { id: string; name?: string; slug?: string | null };
  user: { id: string; email?: string; displayName?: string };
  computerId?: string;
  runtimeId?: string;
  policyResults?: PolicyDecision[];
  pluginRuns?: PluginRunRecord[];
  pluginLogs?: PluginLogRecord[];
  config?: Record<string, unknown>;
};

export type SiemLogExportInput = {
  log: PluginLogRecord;
  organization: { id: string; name?: string; slug?: string | null };
  user?: { id?: string; email?: string; displayName?: string };
  request?: EvaluationRequest;
  conversationEventId?: string | null;
  config?: Record<string, unknown>;
};

export function pluginRun({
  pluginId,
  event,
  status,
  summary,
  startedAt,
  findings,
  metadata
}: {
  pluginId: string;
  event: PipelineEvent;
  status: PluginRunRecord["status"];
  summary: string;
  startedAt: number;
  findings?: PluginFinding[];
  metadata?: Record<string, unknown>;
}): PluginRunRecord {
  return {
    pluginId,
    event,
    status,
    summary,
    durationMs: Math.max(0, Date.now() - startedAt),
    findings,
    metadata
  };
}

export function eventForHookEvent(eventName: EvaluationRequest["event"]["eventName"]): PipelineEvent {
  if (eventName === "PreToolUse") return "tool.beforeUse";
  if (eventName === "PostToolUse") return "tool.afterUse";
  if (eventName === "UserPromptSubmit") return "prompt.beforeSubmit";
  if (eventName === "Stop") return "agent.response";
  return "agent.detected";
}

export type { McpToolCall };
