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

function renderScoreboard() {
	const root = document.getElementById("benchmark-scoreboard-root");
	const payloadElement = document.getElementById("benchmark-data");
	let payload = null;

	if (payloadElement) {
		try {
			payload = JSON.parse(payloadElement.textContent || "{}");
		} catch (error) {
			console.error("Failed to parse benchmark payload:", error);
			payload = null;
		}
	}

	if (!root || !payload) {
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

		const cells = [
			String(index + 1),
			group.scaffoldName,
			group.model,
			solvedPercentage === null ? "N/A" : `${formatNumber(solvedPercentage)}%`,
			averageCost === null ? "N/A" : `$${formatNumber(averageCost, digits=4)}`,
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
