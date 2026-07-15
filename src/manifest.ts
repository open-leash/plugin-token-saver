import type { OpenLeashPluginManifest } from "@openleash/shared";

export const promptCompressionManifest: OpenLeashPluginManifest = {
  id: "openleash.prompt-compression",
  name: "token-saver",
  description: "Trim noisy context before every model call.",
  repositoryUrl: "https://github.com/open-leash/plugin-token-saver",
  version: "1.1.1",
  publisher: "openleash",
  runtime: "container",
  execution: {
    type: "container",
    placement: "either",
    protocol: "openleash-container-plugin.v1",
    image: "ghcr.io/open-leash/plugin-token-saver:1.1.1",
      digest: "sha256:4b681430b8455c42e2bdcc66500fc60c5b4bc197eb3db4817fb44cd69d6814c5",
    healthPath: "/healthz",
    transformPath: "/v1/transform",
    toolExecutePath: "/v1/tools/execute",
    edgePort: 9331,
    timeoutMs: 30000,
    failureMode: "open",
    isolation: "shared-trusted",
    resources: { memoryMb: 1024, cpuShares: 1024 },
    storage: { persistent: true, volumeName: "openleash-token-saver-data" }
  },
  entrypoint: "container",
  events: ["provider.request.beforeSend", "plugin.tool.execute", "prompt.beforeSubmit"],
  permissions: ["event:read", "prompt:read", "prompt:write", "provider-request:read", "provider-request:write", "local-model:run", "storage:read", "storage:write", "audit:write", "log:write", "usage:write"],
  effects: ["transform", "observe"],
  ordering: {
    priority: 100,
    before: ["openleash.dlp"]
  },
  configSchema: {
    type: "object",
    additionalProperties: false,
    properties: {
      enabled: { type: "boolean" },
      level: { enum: ["light", "standard", "maximum"] },
      conciseResponse: { type: "boolean" },
      model: { type: "string" },
      minimumChars: { type: "number", minimum: 256 },
      protectRecent: { type: "number", minimum: 0 },
      ccrEnabled: { type: "boolean" },
      ccrTtlSeconds: { type: "number", minimum: 60 }
    }
  },
  defaultConfig: {
    enabled: false,
    level: "standard",
    conciseResponse: false,
    minimumChars: 1200,
    protectRecent: 2,
    ccrEnabled: false,
    ccrTtlSeconds: 3600
  },
  tags: ["tokens", "cost", "prompt"]
};
