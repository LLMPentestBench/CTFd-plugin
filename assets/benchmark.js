function setBenchmarkStatus(message, type = "info") {
  const statusElement = $(".js-create-benchmark-status");

  statusElement
    .removeClass("d-none alert-info alert-success alert-danger")
    .addClass(`alert-${type}`)
    .text(message);
}

function getSelectedValues(selector) {
  return $(selector)
    .filter(":checked")
    .map((_, element) => $(element).val())
    .get();
}

function setAllCheckboxes(target, checked) {
  $(`.js-${target}-checkbox`).prop("checked", checked);
}

async function createBenchmark() {
  const payload = {
    scaffolds: getSelectedValues(".js-scaffold-checkbox"),
    challenges: getSelectedValues(".js-challenge-checkbox"),
    runs_per_pair: Number($("#runs-per-pair").val()),
    stop_condition: $("input[name='stop_condition']:checked").val(),
    time_limit: Number($("#time-limit").val()),
  };

  if (payload.scaffolds.length === 0) {
    setBenchmarkStatus("Select at least one scaffold.", "danger");
    return false;
  }

  if (payload.challenges.length === 0) {
    setBenchmarkStatus("Select at least one challenge.", "danger");
    return false;
  }

  const response = await CTFd.fetch(CREATE_BENCHMARK_URL, {
    method: "POST",
    headers: CTFD_FETCH_JSON_HEADERS,
    body: JSON.stringify(payload),
  });
  const json = await response.json();

  if (!json.success) {
    console.error("Failed to create benchmark:", json.error);
    setBenchmarkStatus(json.error || "Failed to create benchmark.", "danger");
    return false;
  }

  setBenchmarkStatus("Benchmark created successfully, redirecting...", "success");

  window.location.href = "/admin/llmpentestbench";
  return true;
}

$(".js-select-all").click((e) => {
  e.preventDefault();
  setAllCheckboxes($(e.currentTarget).data("target"), true);
});

$(".js-deselect-all").click((e) => {
  e.preventDefault();
  setAllCheckboxes($(e.currentTarget).data("target"), false);
});

$(".js-reset-benchmark-form").click((e) => {
  e.preventDefault();
  $(".js-scaffold-checkbox, .js-challenge-checkbox").prop("checked", true);
  $("#runs-per-pair").val(1);
  $("#stop-first-success").prop("checked", true);
  $("#time-limit").val(60);
  $(".js-create-benchmark-status").addClass("d-none").text("");
});

$(".js-create-benchmark").click(async (e) => {
  e.preventDefault();
  setBenchmarkStatus("Creating benchmark...");
  await createBenchmark();
});