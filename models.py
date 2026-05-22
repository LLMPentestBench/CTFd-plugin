import enum
import os

from CTFd.models import Challenges, db

from .scaffoldmgr import get_scaffold

AGENT_RUNS_FOLDER = os.path.join(os.path.dirname(__file__), "runs")
if not os.path.exists(AGENT_RUNS_FOLDER):
    os.makedirs(AGENT_RUNS_FOLDER)

class AgentRunStatus(enum.Enum):
    # TODO int values for better version control. also adapt config.html cause it displays string values currently
    INITIATING = "initiating"
    RUNNING = "running"
    FINISHED = "finished"
    ERRORED = "errored"
    ZOMBIE = "zombie"

class AgentRun(db.Model):
    __tablename__ = "llmptb_agent_runs"

    id = db.Column(db.Integer, primary_key=True)
    challenge_id = db.Column(db.Integer, db.ForeignKey("challenges.id"), nullable=False)
    scaffold_id = db.Column(db.String(64), nullable=False)
    status = db.Column(db.Enum(AgentRunStatus), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    end_time = db.Column(db.DateTime, nullable=True)

    def __init__(self, scaffold_id, challenge_id, status):
        self.scaffold_id = scaffold_id
        self.challenge_id = challenge_id
        self.status = status
    
    def is_finished(self):
        return self.status != AgentRunStatus.RUNNING
    
    def mark_running(self):
        self.status = AgentRunStatus.RUNNING
        db.session.commit()

    def mark_finished(self):
        self.status = AgentRunStatus.FINISHED
        self.end_time = db.func.now()
        db.session.commit()
    
    def mark_errored(self):
        self.status = AgentRunStatus.ERRORED
        self.end_time = db.func.now()
        db.session.commit()
    
    def get_folder(self):
        return f"{AGENT_RUNS_FOLDER}/{self.id}"
    
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

def create_all():
    db.create_all()
