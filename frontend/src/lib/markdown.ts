/** Minimal markdown -> HTML for previews (headings, lists, bold/italic/code). */
export function markdownToHtml(md: string): string {
  if (!md) return "";
  const esc = (s: string) =>
    s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const inline = (t: string) =>
    esc(t)
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
      .replace(/(?<!\*)\*([^*]+?)\*(?!\*)/g, "<em>$1</em>")
      .replace(/`([^`]+)`/g, "<code>$1</code>");

  let html = "";
  let inList = false;
  for (const raw of md.split("\n")) {
    const line = raw.trim();
    if (!line) {
      if (inList) { html += "</ul>"; inList = false; }
      continue;
    }
    if (line.startsWith("### ")) { if (inList) { html += "</ul>"; inList = false; } html += `<h3>${inline(line.slice(4))}</h3>`; }
    else if (line.startsWith("## ")) { if (inList) { html += "</ul>"; inList = false; } html += `<h2>${inline(line.slice(3))}</h2>`; }
    else if (line.startsWith("# ")) { if (inList) { html += "</ul>"; inList = false; } html += `<h1>${inline(line.slice(2))}</h1>`; }
    else if (line.startsWith("- ") || line.startsWith("* ")) {
      if (!inList) { html += "<ul>"; inList = true; }
      html += `<li>${inline(line.slice(2))}</li>`;
    } else {
      if (inList) { html += "</ul>"; inList = false; }
      html += `<p>${inline(line)}</p>`;
    }
  }
  if (inList) html += "</ul>";
  return html;
}
