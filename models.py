import os

from CTFd.models import Challenges, db

from .scaffoldmgr import get_scaffold

AGENT_RUNS_FOLDER = os.path.join(os.path.dirname(__file__), "runs")
if not os.path.exists(AGENT_RUNS_FOLDER):
    os.makedirs(AGENT_RUNS_FOLDER)

class AgentRun(db.Model):
    __tablename__ = "llmptb_agent_runs"

    id = db.Column(db.Integer, primary_key=True)
    challenge_id = db.Column(db.Integer, db.ForeignKey("challenges.id"), nullable=False)
    scaffold_id = db.Column(db.String(64), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    end_time = db.Column(db.DateTime, nullable=True)

    def __init__(self, scaffold_id, challenge_id):
        self.scaffold_id = scaffold_id
        self.challenge_id = challenge_id
    
    def is_finished(self):
        return self.end_time is not None

    def mark_finished(self):
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

def create_all():
    db.create_all()
