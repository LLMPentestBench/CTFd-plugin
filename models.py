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
    INITIATING = "initiating"
    RUNNING = "running"
    STOPPED = "stopped"
    FINISHED = "finished"
    TIMED_OUT = "timed_out"
    ERRORED = "errored"
    ZOMBIE = "zombie"

class AgentRun(db.Model):
    __tablename__ = "llmptb_agent_runs"

    id = db.Column(db.Integer, primary_key=True)
    challenge_id = db.Column(db.Integer, db.ForeignKey("challenges.id"), nullable=False)
    scaffold_id = db.Column(db.String(64), nullable=False)

    _status = db.Column('status', db.Enum(AgentRunStatus), nullable=False)
    last_heartbeat = db.Column(db.DateTime, nullable=True)
    
    start_time = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    end_time = db.Column(db.DateTime, nullable=True)

    submitted_flag = db.Column(db.Text, nullable=True)
    flag_correct = db.Column(db.Boolean, nullable=True)

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
    
    def is_finished(self):
        return self.status != AgentRunStatus.RUNNING

    def mark_running(self):
        self._status = AgentRunStatus.RUNNING
        db.session.commit()

    def mark_stopped(self):
        self._status = AgentRunStatus.STOPPED
        self.end_time = db.func.now()
        db.session.commit()

    def mark_finished(self):
        self._status = AgentRunStatus.FINISHED
        self.end_time = db.func.now()
        db.session.commit()
    
    def mark_timed_out(self):
        self._status = AgentRunStatus.TIMED_OUT
        self.end_time = db.func.now()
        db.session.commit()
    
    def mark_errored(self):
        self._status = AgentRunStatus.ERRORED
        self.end_time = db.func.now()
        db.session.commit()
    
    def submit_flag(self, flag, correct):
        self.submitted_flag = flag
        self.flag_correct = correct
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

def create_all():
    db.create_all()
