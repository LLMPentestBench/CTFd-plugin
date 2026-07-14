from dataclasses import dataclass
import enum
import os
import datetime

from CTFd.models import Challenges, Files, db

from .scaffoldmgr import get_scaffold

AGENT_RUNS_FOLDER = os.path.join(os.path.dirname(__file__), "runs")
if not os.path.exists(AGENT_RUNS_FOLDER):
    os.makedirs(AGENT_RUNS_FOLDER)

AGENT_RUN_HEARTBEAT_INTERVAL = 1 # seconds
AGENT_RUN_HEARTBEAT_TIMEOUT = 5 # seconds

class AgentRunStatus(enum.Enum):
    QUEUED = "queued"
    INITIATING = "initiating"
    RUNNING = "running"
    STOPPED = "stopped"
    FINISHED = "finished"
    TIMED_OUT = "timed_out"
    ERRORED = "errored"
    ZOMBIE = "zombie"

@dataclass
class AgentRunLLMStatistics:
    calls_total: int
    calls_failed: int
    total_spend: float
    total_prompt_tokens: int
    total_completion_tokens: int
    total_time: float

    @property
    def average_tps(self):
        return self.total_completion_tokens / self.total_time if self.total_time > 0 else 0

class AgentRun(db.Model):
    __tablename__ = "llmptb_agent_runs"

    id = db.Column(db.Integer, primary_key=True)
    challenge_id = db.Column(db.Integer, db.ForeignKey("challenges.id"), nullable=False)
    scaffold_id = db.Column(db.String(64), nullable=False)
    benchmark = db.Column(db.Integer, db.ForeignKey("llmptb_benchmarks.id"), nullable=True)

    _status = db.Column('status', db.Enum(AgentRunStatus), nullable=False)
    last_heartbeat = db.Column(db.DateTime, nullable=True)
    
    creation_time = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)

    submitted_flag = db.Column(db.Text, nullable=True)
    flag_correct = db.Column(db.Boolean, nullable=True)

    # LLM statistics
    llm_calls_total = db.Column(db.Integer, nullable=True)
    llm_calls_failed = db.Column(db.Integer, nullable=True)
    llm_total_spend = db.Column(db.Float, nullable=True)
    llm_total_prompt_tokens = db.Column(db.Integer, nullable=True)
    llm_total_completion_tokens = db.Column(db.Integer, nullable=True)
    llm_total_time = db.Column(db.Float, nullable=True)

    files = db.relationship(
        "AgentRunFiles", backref="run", foreign_keys="AgentRunFiles.run_id", lazy="joined"
    )

    def __init__(self, scaffold_id, challenge_id, status):
        self.scaffold_id = scaffold_id
        self.challenge_id = challenge_id
        self._status = status

    @property
    def status(self):
        if self._status == AgentRunStatus.RUNNING:
            # check heartbeat timeout
            if self.last_heartbeat is not None and (datetime.datetime.utcnow() - self.last_heartbeat).total_seconds() > AGENT_RUN_HEARTBEAT_TIMEOUT:
                self._status = AgentRunStatus.ZOMBIE
                db.session.commit()

        return self._status
    
    @property
    def llm_statistics(self):
        if self.llm_calls_total is None:
            return None

        return AgentRunLLMStatistics(
            calls_total=self.llm_calls_total,
            calls_failed=self.llm_calls_failed,
            total_spend=self.llm_total_spend,
            total_prompt_tokens=self.llm_total_prompt_tokens,
            total_completion_tokens=self.llm_total_completion_tokens,
            total_time=self.llm_total_time
        )
    
    def is_finished(self):
        return self.status != AgentRunStatus.RUNNING

    def mark_running(self):
        self._status = AgentRunStatus.RUNNING
        self.start_time = datetime.datetime.utcnow()
        db.session.commit()

    def mark_stopped(self):
        self._status = AgentRunStatus.STOPPED
        self.end_time = datetime.datetime.utcnow()
        db.session.commit()

    def mark_finished(self):
        self._status = AgentRunStatus.FINISHED
        self.end_time = datetime.datetime.utcnow()
        db.session.commit()
    
    def mark_timed_out(self):
        self._status = AgentRunStatus.TIMED_OUT
        self.end_time = datetime.datetime.utcnow()
        db.session.commit()
    
    def mark_errored(self):
        self._status = AgentRunStatus.ERRORED
        self.end_time = datetime.datetime.utcnow()
        db.session.commit()
    
    def submit_flag(self, flag, correct):
        self.submitted_flag = flag
        self.flag_correct = correct
        db.session.commit()

    def set_llm_statistics(self, stats: AgentRunLLMStatistics):
        self.llm_calls_total = stats.calls_total
        self.llm_calls_failed = stats.calls_failed
        self.llm_total_spend = stats.total_spend
        self.llm_total_prompt_tokens = stats.total_prompt_tokens
        self.llm_total_completion_tokens = stats.total_completion_tokens
        self.llm_total_time = stats.total_time
        db.session.commit()
    
    def get_folder(self):
        return f"{AGENT_RUNS_FOLDER}/{self.id}"
    
    def get_input_folder(self):
        return f"{self.get_folder()}/input"

    def get_output_folder(self):
        return f"{self.get_folder()}/output"

    def heartbeat(self):
        self.last_heartbeat = datetime.datetime.utcnow()
        db.session.commit()
    
    @property
    def challenge(self):
        return Challenges.query.filter_by(id=self.challenge_id).first()
    
    @property
    def scaffold(self):
        return get_scaffold(self.scaffold_id)
    
    @property
    def logger(self):
        from .runmgr import logger
        return logger.getChild(f"run_{self.id:04d}")

class AgentRunFiles(Files):
    # Give this its own table, to avoid having to edit the CTFd Files table columns
    __tablename__ = "llmptb_agent_run_files"
    __mapper_args__ = {"polymorphic_identity": "llmptb_run"}

    id = db.Column(db.Integer, db.ForeignKey("files.id"), primary_key=True)
    run_id = db.Column(
        db.Integer, db.ForeignKey("llmptb_agent_runs.id", ondelete="CASCADE")
    )
    path = db.Column(db.Text, nullable=False)

    def __init__(self, *args, **kwargs):
        super(AgentRunFiles, self).__init__(**kwargs)

class Benchmark(db.Model):
    __tablename__ = "llmptb_benchmarks"

    id = db.Column(db.Integer, primary_key=True)
    display_name = db.Column(db.String(128), nullable=False)

    attempts = db.Column(db.Integer, nullable=False)
    stop_after_first_success = db.Column(db.Boolean, nullable=False)
    time_limit = db.Column(db.Integer, nullable=False) # seconds

    creation_time = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)

    challenges = db.relationship(
        "Challenges",
        secondary="llmptb_benchmark_challenges",
        lazy="select",
    )
    benchmark_scaffolds = db.relationship("BenchmarkScaffold", lazy="joined")
    
    def __init__(self, *args, **kwargs):
        super(Benchmark, self).__init__(**kwargs)

    @property
    def scaffolds(self):
        return [get_scaffold(bs.scaffold_id) for bs in self.benchmark_scaffolds]

class BenchmarkScaffold(db.Model):
    __tablename__ = "llmptb_benchmark_scaffolds"

    id = db.Column(db.Integer, primary_key=True)
    benchmark_id = db.Column(db.Integer, db.ForeignKey("llmptb_benchmarks.id"), nullable=False)
    scaffold_id = db.Column(db.String(64), nullable=False)

class BenchmarkChallenge(db.Model):
    __tablename__ = "llmptb_benchmark_challenges"

    id = db.Column(db.Integer, primary_key=True)
    benchmark_id = db.Column(db.Integer, db.ForeignKey("llmptb_benchmarks.id"), nullable=False)
    challenge_id = db.Column(db.Integer, db.ForeignKey("challenges.id"), nullable=False)

def create_all():
    db.create_all()
