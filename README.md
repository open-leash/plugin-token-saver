# plugin-token-saver

First-party OpenLeash plugin that reduces prompt token usage before model calls.

This is a first-party OpenLeash plugin repository. The plugin owns its domain logic, prompts, schemas, parsing, and local fallbacks. OpenLeash provides only primitive runtime capabilities such as evaluator LLM calls, plugin-scoped storage, signals, logs, usage records, notifications, and selected host context.

## Source

- `src/manifest.ts` declares events, permissions, settings, ordering, and metadata.
- `src/index.ts` implements the plugin.
- `src/openleash-plugin-runtime.ts` contains tiny local helper types used by this standalone repo.

## Development

```bash
npm install
npm run typecheck
```

## Runtime

OpenLeash loads reviewed plugins by manifest metadata and executes their handlers inside the managed plugin runtime.
