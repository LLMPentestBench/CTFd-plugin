async function stopRun() {
  try {
    const response = await CTFd.fetch(`/api/v1/plugins/llmpentestbench/run/${RUN_ID}/stop`, {
      method: "POST",
    });
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const json = await response.json();
    if (!json.success) {
      throw new Error(json.error || "Unknown error");
    }

    window.location.reload();
  } catch (error) {
    console.error("Failed to stop run:", error);
    CTFd.ui.ezq.ezAlert({
      title: "Error",
      body: `Failed to stop run ${RUN_ID}: ${error.message}`,
      button: "OK",
    });
    return;
  }
}

function loadTerminal(containerElem) {
  const term = new Terminal({
    cols: 132,
    rows: 24,
    disableStdin: true,
    cursorStyle: "bar",
    cursorBlink: true,
  });

  // Allow for unicode wide chars to be displayed properly
  const unicode11Addon = new Unicode11Addon.Unicode11Addon();
  term.options.allowProposedApi = true;
  term.loadAddon(unicode11Addon);
  term.unicode.activeVersion = '11';

  term.open(containerElem);

  // Hack to prevent terminal from taking focus, as it's read-only anyway, prevents keybinds like ctrl+r for reload otherwise
  containerElem.addEventListener('focus', (e) => {
    e.target.blur();
  }, true);

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

// UI interactions
$("#llmpentestbench-stop-run").click(async (e) => {
  if (RUN_FINISHED) {
    return;
  }
  e.preventDefault();
  CTFd.ui.ezq.ezQuery({
    title: "Stop Run",
    body: "Are you sure you want to stop this run?",
    success: stopRun,
  });
});


// Load terminal and initiate log streaming
const terminalElem = document.getElementById('terminal');
const runId = terminalElem.getAttribute('data-run-id');

const term = loadTerminal(terminalElem);

// TODO error handling
const source = new EventSource("/api/v1/plugins/llmpentestbench/run/" + runId + "/log_stream");
source.addEventListener("log_update", (event) => {
  const log_data = base64ToUint8Array(event.data);
  term.write(log_data);
});