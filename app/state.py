from typing import TypedDict

# Description of what Graph "remembers"
class ProjectState(TypedDict, total=False):
    channel: str
    transcripts: list[str]