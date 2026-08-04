function formatBoolean(value) {
	if (value === true) {
		return "Yes";
	}
	if (value === false) {
		return "No";
	}
	return "N/A";
}

function formatNumber(value, digits = 2) {
	if (value === null || value === undefined || Number.isNaN(value)) {
		return "N/A";
	}

	return new Intl.NumberFormat(undefined, {
		minimumFractionDigits: digits,
		maximumFractionDigits: digits,
	}).format(value);
}

function formatDuration(seconds) {
	if (seconds === null || seconds === undefined || Number.isNaN(seconds)) {
		return "N/A";
	}

	const totalMilliseconds = Math.round(seconds * 1000);
	const hours = Math.floor(totalMilliseconds / 3600000);
	const minutes = Math.floor((totalMilliseconds % 3600000) / 60000);
	const remainingSeconds = Math.floor((totalMilliseconds % 60000) / 1000);
	const milliseconds = totalMilliseconds % 1000;

	return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(remainingSeconds).padStart(2, "0")}.${String(milliseconds).padStart(3, "0")}`;
}

function formatDateTime(value) {
	if (!value) {
		return "N/A";
	}

	const date = new Date(value);
	if (Number.isNaN(date.getTime())) {
		return value;
	}

	return new Intl.DateTimeFormat(undefined, {
		year: "numeric",
		month: "short",
		day: "numeric",
		hour: "2-digit",
		minute: "2-digit",
	}).format(date);
}

function average(values) {
	if (values.length === 0) {
		return null;
	}

	return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function renderGroupDetail(modalBody, modalTitle, payload, group) {
	const challenges = payload.challenges;
	const attemptCount = payload.benchmark.attempts;

	modalBody.innerHTML = "";
	modalTitle.textContent = `${group.scaffoldName} / ${group.model}`;

	const wrapper = document.createElement("div");

	const table = document.createElement("table");
	table.className = "table table-striped mb-0";
	table.innerHTML = `
		<thead>
			<tr>
				<td><b>Button</b></td>
				<td><b>Challenge</b></td>
				<td><b>Attempt</b></td>
				<td><b>Run ID</b></td>
				<td><b>Status</b></td>
				<td><b>Flag Correct</b></td>
				<td><b>Submitted Flag</b></td>
				<td><b>Cost</b></td>
				<td><b>Duration</b></td>
				<td><b>LLM Calls</b></td>
				<td><b>LLM Calls Failed</b></td>
				<td><b>Prompt Tokens</b></td>
				<td><b>Completion Tokens</b></td>
				<td><b>LLM Time (s)</b></td>
				<td><b>Created</b></td>
				<td><b>Started</b></td>
				<td><b>Ended</b></td>
			</tr>
		</thead>
	`;

	const tbody = document.createElement("tbody");

	for (const runIndex in group.runs) {
		const run = group.runs[runIndex];
		const challenge = challenges.find((c) => c.id === run.challenge_id);
		const attempt = run.attempt;

		console.log(run);
		
		const row = document.createElement("tr");

		const detailsButton = document.createElement("a");
		detailsButton.className = "btn btn-primary llmpentestbench-open-run";
		detailsButton.href = `/admin/llmpentestbench/run/${run.id}`;
		detailsButton.textContent = "View";

		const challLink = document.createElement("a");
		challLink.href = `/admin/challenges/${challenge.id}`;
		challLink.textContent = challenge.name;
		challLink.appendChild(document.createTextNode(" "));
		const challIcon = document.createElement("i");
		challIcon.className = "fa-solid fa-arrow-up-right-from-square fa-xs";
		challLink.appendChild(challIcon);

		const cells = [
			detailsButton,
			challLink,
			String(attempt),
			String(run.id),
			run.status,
			formatBoolean(run.flag_correct),
			run.submitted_flag ? run.submitted_flag : "N/A",
			Number.isFinite(run.llm_total_spend) ? `$${formatNumber(run.llm_total_spend, 4)}` : "N/A",
			Number.isFinite(run.duration_seconds) ? formatDuration(run.duration_seconds) : "N/A",
			Number.isFinite(run.llm_calls_total) ? String(run.llm_calls_total) : "N/A",
			Number.isFinite(run.llm_calls_failed) ? String(run.llm_calls_failed) : "N/A",
			Number.isFinite(run.llm_total_prompt_tokens) ? String(run.llm_total_prompt_tokens) : "N/A",
			Number.isFinite(run.llm_total_completion_tokens) ? String(run.llm_total_completion_tokens) : "N/A",
			Number.isFinite(run.llm_total_time) ? formatNumber(run.llm_total_time, 2) : "N/A",
			formatDateTime(run.creation_time),
			formatDateTime(run.start_time),
			formatDateTime(run.end_time),
		];

		cells.forEach((content) => {
			const cell = document.createElement("td");
			if (content instanceof Node) {
				cell.appendChild(content);
			} else {
				cell.textContent = content;
			}
			row.appendChild(cell);
		});

		tbody.appendChild(row);
	}

	table.appendChild(tbody);
	wrapper.appendChild(table);
	modalBody.appendChild(wrapper);
}

function renderScoreboard() {
	const root = document.getElementById("benchmark-scoreboard-root");
	const payloadElement = document.getElementById("benchmark-data");
	const detailsModalBody = document.getElementById("benchmark-group-details-body");
	const detailsModalTitle = document.getElementById("benchmark-group-details-title");
	let payload = null;

	if (payloadElement) {
		try {
			payload = JSON.parse(payloadElement.textContent || "{}");
		} catch (error) {
			console.error("Failed to parse benchmark payload:", error);
			payload = null;
		}
	}

	if (!root || !payload || !detailsModalBody || !detailsModalTitle) {
		return;
	}

	const runs = payload.runs;
	const challengeCount = payload.challenges.length;

	// Group by scaffold and model
	const groups = new Map();
	for (const run of runs) {
		const key = `${run.scaffold_id}::${run.model}`;
		if (!groups.has(key)) {
			groups.set(key, {
				scaffoldId: run.scaffold_id,
				scaffoldName: run.scaffold_name || run.scaffold_id,
				model: run.model,
				runs: [],
			});
		}

		groups.get(key).runs.push(run);
	}

	// Sort groups by solved chall count, then by name
	const orderedGroups = [...groups.values()].sort((left, right) => {
		const leftSolved = left.runs.filter((run) => run.flag_correct === true).length;
		const rightSolved = right.runs.filter((run) => run.flag_correct === true).length;

		if (rightSolved !== leftSolved) {
			return rightSolved - leftSolved;
		}

		return `${left.scaffoldName} ${left.model}`.localeCompare(`${right.scaffoldName} ${right.model}`);
	});

	root.innerHTML = "";

	if (orderedGroups.length === 0) {
		const emptyState = document.createElement("div");
		emptyState.className = "alert alert-info mb-0";
		emptyState.textContent = "No benchmark runs are available yet.";
		root.appendChild(emptyState);
		return;
	}

	const table = document.createElement("table");
	table.className = "table table-striped mb-0";

	table.innerHTML = `
		<thead>
			<tr>
				<td><b>#</b></td>
				<td><b>Scaffold</b></td>
				<td><b>Model</b></td>
				<td><b>% Challs Solved</b></td>
				<td><b>Avg Cost / Correct Run</b></td>
				<td><b>Avg Runtime / Correct Run</b></td>
				<td><b>Correct Runs</b></td>
			</tr>
		</thead>
	`;

	const tbody = document.createElement("tbody");

	orderedGroups.forEach((group, index) => {
		const correctRuns = group.runs.filter((run) => run.flag_correct === true);
		const solvedChallengeCount = new Set(correctRuns.map((run) => run.challenge_id)).size;
		const solvedPercentage = challengeCount > 0 ? (solvedChallengeCount / challengeCount) * 100 : null;
		const averageCost = average(correctRuns.map((run) => run.llm_total_spend).filter((value) => Number.isFinite(value)));
		const averageRuntime = average(correctRuns.map((run) => run.duration_seconds).filter((value) => Number.isFinite(value)));

		const row = document.createElement("tr");
		row.style.cursor = "pointer";
		row.title = "Show details";
		row.addEventListener("click", () => {
			renderGroupDetail(detailsModalBody, detailsModalTitle, payload, group);
			$(`#benchmark-group-details-modal`).modal("toggle");
		});

		const cells = [
			String(index + 1),
			group.scaffoldName,
			group.model,
			solvedPercentage === null ? "N/A" : `${formatNumber(solvedPercentage)}%`,
			averageCost === null ? "N/A" : `$${formatNumber(averageCost, 4)}`,
			averageRuntime === null ? "N/A" : formatDuration(averageRuntime),
			`${correctRuns.length}`,
		];

		cells.forEach((text) => {
			const cell = document.createElement("td");
			cell.textContent = text;
			row.appendChild(cell);
		});

		tbody.appendChild(row);
	});

	table.appendChild(tbody);
	root.appendChild(table);
}

renderScoreboard();
