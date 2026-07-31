import logging

from CTFd.models import db, Challenges

from . import runner
from .scaffoldmgr import Scaffold
from .models import Benchmark, BenchmarkModel, BenchmarkScaffold

logger = logging.getLogger("llmpentestbench.benchmark")

def create_benchmark(
    display_name: str,
    scaffolds: list[Scaffold],
    challenges: list[Challenges],
    models: list[str],
    attempts: int,
    stop_after_first_success: bool,
    time_limit: int,
) -> Benchmark:
    benchmark = Benchmark(
        display_name=display_name,
        attempts=attempts,
        stop_after_first_success=stop_after_first_success,
        time_limit=time_limit,
        benchmark_scaffolds=[
            BenchmarkScaffold(scaffold_id=scaffold.id) for scaffold in scaffolds
        ],
        challenges=challenges,
        benchmark_models=[
            BenchmarkModel(model_name=model) for model in models
        ]
    )
    db.session.add(benchmark)
    db.session.commit()

    logger.info(
        f"Created benchmark '{display_name}' with ID {benchmark.id}, "
        f"scaffolds {scaffolds}, challenges {challenges}, "
        f"attempts {attempts}, stop after first success {stop_after_first_success}, "
        f"time limit {time_limit}"
    )

    queue_benchmark_runs(benchmark)

    return benchmark

def queue_benchmark_runs(benchmark: Benchmark):
    for scaffold in benchmark.scaffolds:
        for challenge in benchmark.challenges:
            for model in benchmark.models:
                runner.queue_run(scaffold, challenge, model,
                                benchmark=benchmark, benchmark_attempt=1)
