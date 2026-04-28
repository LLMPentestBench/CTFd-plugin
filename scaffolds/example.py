# import masterthesis.py
from ..masterthesis import Scaffold, ScaffoldStatus

class ExampleScaffold(Scaffold):
    def __init__(self):
        super().__init__("Example Scaffold")
        print("Initializing example scaffold")
    
    def start(self):
        print(f"Starting scaffold {self.name}")
    def stop(self):
        print(f"Stopping scaffold {self.name}")
    def status(self) -> ScaffoldStatus:
        return ScaffoldStatus.RUNNING

def load():
    return ExampleScaffold()