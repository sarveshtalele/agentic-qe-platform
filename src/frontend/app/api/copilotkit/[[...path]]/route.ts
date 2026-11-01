import { HttpAgent } from "@ag-ui/client";
import { CopilotRuntime, createCopilotRuntimeHandler } from "@copilotkit/runtime/v2";

const backend = process.env.ATLAS_BACKEND_URL || "http://127.0.0.1:8000";
const keys = ["copilot", "business_analyst", "requirements_analyst", "test_architect", "test_designer", "defect_diagnostician", "bug_reviewer", "repo_analyst"];

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
