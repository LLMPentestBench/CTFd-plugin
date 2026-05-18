function loadTerminal(containerElem) {
  const term = new Terminal({
    cols: 132,
    rows: 24,
  });

  // Allow for unicode wide chars to be displayed properly
  const unicode11Addon = new Unicode11Addon.Unicode11Addon();
  term.options.allowProposedApi = true;
  term.loadAddon(unicode11Addon);
  term.unicode.activeVersion = '11';

  term.open(containerElem);

  return term;
}

function base64ToUint8Array(b64) {
  const binaryString = atob(b64);
  const bytes = new Uint8Array(binaryString.length);
  for (let i = 0; i < binaryString.length; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  return bytes;
}

const terminalElem = document.getElementById('terminal');
const runId = terminalElem.getAttribute('data-run-id');

const term = loadTerminal(terminalElem);

// TODO error handling
const source = new EventSource("/api/v1/plugins/llmpentestbench/run/" + runId + "/log_stream");
source.addEventListener("log_update", (event) => {
  const log_data = base64ToUint8Array(event.data);
  term.write(log_data);
});
