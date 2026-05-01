const CTFD_FETCH_JSON_HEADERS = {
  "Accept": "application/json",
  "Content-Type": "application/json"
};

async function startScaffold(scaffoldId) {
  const response = await CTFd.fetch(`/api/v1/plugins/masterthesis/scaffold/${scaffoldId}/start`, {
    method: "POST",
    headers: CTFD_FETCH_JSON_HEADERS,
  });
  const json = await response.json();

  if (!json.success) {
    console.error("Failed to start scaffold:", json.error);
    CTFd.ui.ezq.ezAlert({
      title: "Error",
      body: `Failed to start scaffold: ${json.error || "Unknown error"}`,
      button: "OK",
    });
    return false;
  }

  return true;
}

async function stopScaffold(scaffoldId) {
  const response = await CTFd.fetch(`/api/v1/plugins/masterthesis/scaffold/${scaffoldId}/stop`, {
    method: "POST",
    headers: CTFD_FETCH_JSON_HEADERS,
  });
  const json = await response.json();

  if (!json.success) {
    console.error("Failed to stop scaffold:", json.error);
    CTFd.ui.ezq.ezAlert({
      title: "Error",
      body: `Failed to stop scaffold: ${json.error || "Unknown error"}`,
      button: "OK",
    });
    return false;
  }

  return true;
}



$(".masterthesis-start").click((e) => {
  e.preventDefault();
  let scaffoldId = $(e.currentTarget).closest("tr").attr("scaffold-id");

  startScaffold(scaffoldId).then((success) => {
    if (success) location.reload();
  });
});

$(".masterthesis-stop").click(async (e) => {
  e.preventDefault();
  let scaffoldId = $(e.currentTarget).closest("tr").attr("scaffold-id");
  
  stopScaffold(scaffoldId).then((success) => {
    if (success) location.reload();
  });
});
