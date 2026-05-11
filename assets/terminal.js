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

async function getLogs(scaffoldId) {
  const response = await CTFd.fetch(`/api/v1/plugins/llmpentestbench/scaffold/${scaffoldId}/logs`, {
    method: "GET",
    headers: CTFD_FETCH_JSON_HEADERS,
  });
  const json = await response.json();

  if (!json.success) {
    console.error("Failed to get logs for scaffold:", json.error);
    CTFd.ui.ezq.ezAlert({
      title: "Error",
      body: `Failed to get logs for scaffold ${scaffoldId}: ${json.error || "Unknown error"}`,
      button: "OK",
    });
    return null;
  }

  return base64ToUint8Array(json.logs);
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
const scaffoldId = terminalElem.getAttribute('data-scaffold-id');

const term = loadTerminal(terminalElem);

getLogs(scaffoldId).then(logs => {
  if (logs) {
    term.write(logs);
  }
});
