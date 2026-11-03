#!/usr/bin/env bash
# Install stock-analysis-teardown as a personal Claude Code skill.
# Links the skill folder into ~/.claude/skills so edits to this repo go live,
# then installs the renderer's single npm dependency (ECharts).
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
src="$here/skills/stock-analysis-teardown"
dest="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}/stock-analysis-teardown"

command -v python3 >/dev/null || { echo "python3 is required"; exit 1; }
command -v node >/dev/null || { echo "Node 22 or newer is required"; exit 1; }
node_major="$(node -p 'process.versions.node.split(".")[0]')"
if [ "$node_major" -lt 22 ]; then echo "Node 22 or newer is required (found $(node --version))"; exit 1; fi

mkdir -p "$(dirname "$dest")"
if [ -L "$dest" ] || [ -e "$dest" ]; then
  if [ "$(readlink "$dest" 2>/dev/null || true)" = "$src" ]; then
    echo "Already linked: $dest"
  else
    echo "Something already exists at $dest. Move it away and run this again."; exit 1
  fi
else
  ln -s "$src" "$dest"
  echo "Linked $dest -> $src"
fi

npm install --prefix "$src/renderer" --no-audit --no-fund --silent
echo "Renderer ready."

chrome=""
for c in "${CHROME_PATH:-}" "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
         "/Applications/Chromium.app/Contents/MacOS/Chromium" /usr/bin/google-chrome /usr/bin/chromium /usr/bin/chromium-browser; do
  if [ -n "$c" ] && [ -x "$c" ]; then chrome="$c"; break; fi
done
if [ -z "$chrome" ]; then
  echo "Note: no Chrome or Chromium found. Install one or set CHROME_PATH before rendering."
fi
if [ -z "${SEC_USER_AGENT:-}" ]; then
  echo "Tip: SEC asks for a contact in requests. Add to your shell profile:"
  echo '  export SEC_USER_AGENT="Your Name you@example.com"'
fi
echo "Done. In Claude Code, run: /stock-analysis-teardown MRVL"
