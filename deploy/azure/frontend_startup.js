// App Service startup for the frontend. Builds once per package or backend URL change, then serves.
// Portal startup command: node /home/site/wwwroot/startup.js
const { execFileSync, spawn } = require("node:child_process");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const app = __dirname;
const home = process.env.ATLAS_HOME || "/home/atlas";
const output = path.join(home, "frontend");
const stampFile = path.join(output, ".atlas-stamp");
const backend = process.env.ATLAS_BACKEND_URL;
const log = (message) => console.log(`[agentic-qe] ${message}`);

if (!backend) {
  console.error("[agentic-qe] ATLAS_BACKEND_URL is not set. Add it in Environment variables, then restart.");
  process.exit(1);
}

function digest(dir, hash) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
    if (entry.name === "node_modules" || entry.name.startsWith(".next")) continue;
    const item = path.join(dir, entry.name);
    if (entry.isDirectory()) digest(item, hash);
    else hash.update(entry.name).update(fs.readFileSync(item));
  }
  return hash;
}

function build(wanted) {
  // the build runs on fast local disk; only its output goes to the persistent /home share
  const work = fs.mkdtempSync(path.join(os.tmpdir(), "atlas-build-"));
  log(`Building in ${work}. The first run takes several minutes`);
  fs.cpSync(app, work, { recursive: true, filter: (src) => !src.includes("node_modules") && !src.includes(`${path.sep}.next`) });
  const npm = process.platform === "win32" ? "npm.cmd" : "npm";
  const env = { ...process.env, ATLAS_STANDALONE: "1", NODE_ENV: "development", NEXT_TELEMETRY_DISABLED: "1", NODE_OPTIONS: "--max-old-space-size=1024" };
  execFileSync(npm, ["ci", "--no-audit", "--no-fund"], { cwd: work, env, stdio: "inherit", shell: process.platform === "win32" });
  execFileSync(npm, ["run", "build"], { cwd: work, env: { ...env, NODE_ENV: "production" }, stdio: "inherit", shell: process.platform === "win32" });
  fs.rmSync(output, { recursive: true, force: true });
  fs.cpSync(path.join(work, ".next", "standalone"), output, { recursive: true });
  fs.cpSync(path.join(work, ".next", "static"), path.join(output, ".next", "static"), { recursive: true });
  if (fs.existsSync(path.join(work, "public"))) fs.cpSync(path.join(work, "public"), path.join(output, "public"), { recursive: true });
  fs.writeFileSync(stampFile, wanted);
  fs.rmSync(work, { recursive: true, force: true });
  log("Build finished");
}

const wanted = digest(app, crypto.createHash("sha256").update(backend).update(process.version)).digest("hex");
if (fs.existsSync(stampFile) && fs.readFileSync(stampFile, "utf8") === wanted) log("Build is current; skipping");
else build(wanted);

log(`Starting UI on port ${process.env.PORT || 3000}`);
const server = spawn(process.execPath, [path.join(output, "server.js")], { cwd: output, stdio: "inherit", env: { ...process.env, HOSTNAME: "0.0.0.0", PORT: process.env.PORT || "3000", NODE_ENV: "production" } });
server.on("exit", (code) => process.exit(code ?? 1));
for (const signal of ["SIGTERM", "SIGINT"]) process.on(signal, () => server.kill(signal));
