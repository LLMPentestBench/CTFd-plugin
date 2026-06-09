This directory contains vendored third-party assets used by LLMPentestBench.

Files:
- xterm.js (from xterm)
- xterm.css (from xterm)
- addon-unicode11.js (from xterm-addon-unicode11)

Do not edit these files manually.

To update:
1. From the plugin root (CTFd/plugins/LLMPentestBench), run ./scripts/update-xterm-lib.sh.
2. Optionally pass versions:
   ./scripts/update-xterm-lib.sh <xterm_version> <unicode11_addon_version>
3. Review changes in this directory, including VENDORED.yml.

The source versions and integrity hashes are tracked in VENDORED.yml.
