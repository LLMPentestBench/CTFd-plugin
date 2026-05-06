const CTFD_FETCH_JSON_HEADERS = {
  "Accept": "application/json",
  "Content-Type": "application/json"
};

async function getLogs(scaffoldId) {
  const response = await CTFd.fetch(`/api/v1/plugins/masterthesis/scaffold/${scaffoldId}/logs`, {
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

  return atob(json.logs);
}

var term = new Terminal();
term.open(document.getElementById('terminal'));
// term.write('Hello from \x1B[1;3;31mxterm.js\x1B[0m $ ');
getLogs("example").then(logs => {
  if (logs) {
    term.write(logs);
  }
});
