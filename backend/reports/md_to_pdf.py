"""Render FULL_AUDIT_REPORT.md -> styled HTML -> PDF via Chrome/Edge headless."""
import os, subprocess, sys, markdown

REPORT_DIR = os.path.dirname(os.path.abspath(__file__))
MD   = os.path.join(REPORT_DIR, "FULL_AUDIT_REPORT.md")
HTML = os.path.join(REPORT_DIR, "FULL_AUDIT_REPORT.html")
PDF  = os.path.join(REPORT_DIR, "FULL_AUDIT_REPORT.pdf")

with open(MD, encoding="utf-8") as f:
    body = markdown.markdown(
        f.read(),
        extensions=["tables", "fenced_code", "codehilite", "toc", "sane_lists"],
        extension_configs={"codehilite": {"noclasses": True, "pygments_style": "friendly"}},
    )

CSS = """
@page { size: A4; margin: 16mm 14mm; }
* { box-sizing: border-box; }
body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 10.5px; line-height: 1.45;
       color: #1a1a1a; max-width: 100%; }
h1 { font-size: 21px; border-bottom: 3px solid #1f4e79; padding-bottom: 6px; color: #1f4e79;
     page-break-after: avoid; }
h2 { font-size: 16px; margin-top: 22px; border-bottom: 1px solid #b8c6d6; padding-bottom: 3px;
     color: #1f4e79; page-break-after: avoid; }
h3 { font-size: 13px; margin-top: 16px; color: #2e5c8a; page-break-after: avoid; }
h4 { font-size: 11.5px; margin-top: 12px; color: #333; page-break-after: avoid; }
p, li { font-size: 10.5px; }
code { font-family: 'Consolas','Courier New',monospace; font-size: 9.5px;
       background: #f2f4f7; padding: 1px 3px; border-radius: 3px; }
pre { background: #f6f8fa; border: 1px solid #d7dde3; border-left: 3px solid #1f4e79;
      border-radius: 4px; padding: 8px 10px; overflow-x: auto; page-break-inside: avoid; }
pre code { background: none; padding: 0; font-size: 9px; line-height: 1.35; }
table { border-collapse: collapse; width: 100%; margin: 8px 0; font-size: 9px;
        page-break-inside: avoid; }
th { background: #1f4e79; color: #fff; padding: 4px 6px; text-align: right; border: 1px solid #1f4e79; }
th:first-child { text-align: left; }
td { padding: 3px 6px; border: 1px solid #cdd6e0; text-align: right; }
td:first-child { text-align: left; }
tr:nth-child(even) td { background: #f4f7fa; }
blockquote { border-left: 4px solid #c79100; background: #fffbe6; margin: 8px 0;
             padding: 6px 12px; font-size: 10px; page-break-inside: avoid; }
hr { border: none; border-top: 1px solid #d0d7de; margin: 18px 0; }
strong { color: #11324f; }
"""

with open(HTML, "w", encoding="utf-8") as f:
    f.write(f"<!DOCTYPE html><html><head><meta charset='utf-8'>"
            f"<style>{CSS}</style></head><body>{body}</body></html>")

def find_browser():
    pf, pf86 = os.environ.get("ProgramFiles",""), os.environ.get("ProgramFiles(x86)","")
    cands = [
        os.path.join(pf,   "Google","Chrome","Application","chrome.exe"),
        os.path.join(pf86, "Google","Chrome","Application","chrome.exe"),
        os.path.join(pf,   "Microsoft","Edge","Application","msedge.exe"),
        os.path.join(pf86, "Microsoft","Edge","Application","msedge.exe"),
    ]
    return next((c for c in cands if os.path.isfile(c)), None)

browser = find_browser()
if not browser:
    sys.exit("No Chrome/Edge found")

subprocess.run([
    browser, "--headless", "--disable-gpu", "--no-sandbox",
    "--no-pdf-header-footer", f"--print-to-pdf={PDF}",
    "file:///" + HTML.replace("\\", "/"),
], check=True, timeout=120)

print("PDF:", PDF, os.path.getsize(PDF), "bytes" if os.path.isfile(PDF) else "MISSING")
