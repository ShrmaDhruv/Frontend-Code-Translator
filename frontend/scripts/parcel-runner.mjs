import { spawn } from "node:child_process";
import { mkdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");
const tempDir = path.join(root, ".parcel-tmp");
const mode = process.argv[2] === "build" ? "build" : "dev";
const parcelBin = path.join(
  root,
  "node_modules",
  ".bin",
  process.platform === "win32" ? "parcel.cmd" : "parcel",
);

mkdirSync(tempDir, { recursive: true });

const args = mode === "build" ? ["build", "index.html"] : ["index.html"];
const child = spawn(parcelBin, args, {
  cwd: root,
  shell: process.platform === "win32",
  env: {
    ...process.env,
    TMP: tempDir,
    TEMP: tempDir,
    TMPDIR: tempDir,
  },
  stdio: "inherit",
});

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 1);
});
