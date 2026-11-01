import { HttpAgent } from "@ag-ui/client";
import { CopilotRuntime, createCopilotRuntimeHandler } from "@copilotkit/runtime/v2";

const backend = process.env.ATLAS_BACKEND_URL || "http://127.0.0.1:8000";
// the chat agents of src/backend/maf/agents that have chat tools; their keys use hyphens, as in the plugin
const keys = ["project-copilot", "business-analyst", "requirements-analyst", "principal-test-architect", "test-design-architect", "defect-diagnostician", "bug-reviewer", "repo-intelligence-analyst"];

// a runtime per request, because each chat call must carry the caller's session to the backend
function handle(request: Request) {
  const headers = { cookie: request.headers.get("cookie") || "" };
  const runtime = new CopilotRuntime({
    agents: Object.fromEntries(keys.map((key) => [key, new HttpAgent({ url: `${backend}/agui/${key}`, headers })])),
  });
  return createCopilotRuntimeHandler({ runtime, basePath: "/api/copilotkit" })(request);
}

export const GET = handle;
export const POST = handle;
