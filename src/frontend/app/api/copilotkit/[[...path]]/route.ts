import { HttpAgent } from "@ag-ui/client";
import { CopilotRuntime, createCopilotRuntimeHandler } from "@copilotkit/runtime/v2";

const backend = process.env.ATLAS_BACKEND_URL || "http://127.0.0.1:8000";
const keys = ["copilot", "business_analyst", "requirements_analyst", "test_architect", "test_designer", "defect_diagnostician", "bug_reviewer", "repo_analyst"];

const runtime = new CopilotRuntime({
  agents: Object.fromEntries(keys.map((key) => [key, new HttpAgent({ url: `${backend}/agui/${key}` })])),
});

const handler = createCopilotRuntimeHandler({ runtime, basePath: "/api/copilotkit" });

export const GET = handler;
export const POST = handler;
