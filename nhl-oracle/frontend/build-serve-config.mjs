import { readFileSync, writeFileSync } from "node:fs";

const [templatePath, outputPath] = process.argv.slice(2);
const apiBase = process.env.VITE_API_URL ?? "";

if (!templatePath || !outputPath) {
  throw new Error("serve config input and output paths are required");
}

let parsed;
try {
  parsed = new URL(apiBase);
} catch {
  throw new Error("VITE_API_URL must be a valid URL");
}
if (parsed.protocol !== "https:" || parsed.origin !== apiBase) {
  throw new Error("VITE_API_URL must be an HTTPS origin without a path or trailing slash");
}

const template = readFileSync(templatePath, "utf8");
const marker = "__VITE_API_URL__";
if (template.split(marker).length !== 2) {
  throw new Error("serve config template must contain exactly one API origin marker");
}
const rendered = template.replace(marker, apiBase);
JSON.parse(rendered);
writeFileSync(outputPath, rendered, { encoding: "utf8", mode: 0o644 });
