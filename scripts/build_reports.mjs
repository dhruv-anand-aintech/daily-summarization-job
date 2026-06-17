import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import path from "node:path";

const repoRoot = path.resolve(import.meta.dirname, "..");
const outDir = path.join(repoRoot, "out");
const targetDir = path.join(repoRoot, "src", "generated");
const targetFile = path.join(targetDir, "reports.json");

function excerpt(markdown) {
  const summary = markdown.match(/## Summary\s+([\s\S]*?)(?=\n## |\n# |$)/i);
  const source = summary?.[1] ?? markdown;
  return source.split("\n").map((line) => line.replace(/^[-*]\s+/, "").trim()).filter(Boolean).slice(0, 3).join(" ");
}

function sections(markdown) {
  return [...markdown.matchAll(/^##\s+(.+)$/gm)].map((match) => match[1].trim());
}

const entries = [];
for (const name of await readdir(outDir).catch(() => [])) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(name)) continue;
  const reportPath = path.join(outDir, name, "report.md");
  try {
    const markdown = await readFile(reportPath, "utf8");
    if (!markdown.trim()) continue;
    entries.push({
      date: name,
      title: markdown.match(/^#\s+(.+)$/m)?.[1]?.trim() ?? `Daily Work Report - ${name}`,
      excerpt: excerpt(markdown),
      sections: sections(markdown),
      markdown,
    });
  } catch {
    // Date folders can exist before report generation finishes.
  }
}

entries.sort((a, b) => b.date.localeCompare(a.date));
await mkdir(targetDir, { recursive: true });
await writeFile(targetFile, `${JSON.stringify(entries, null, 2)}\n`);
console.log(`Built ${entries.length} reports into ${path.relative(repoRoot, targetFile)}`);
