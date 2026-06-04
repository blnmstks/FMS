from typing import TypedDict

# Description of what Graph "remembers"
class ProjectState(TypedDict, total=False):
    channel: str
    transcripts: list[str]
    channel_name: str
    channel_description: str
    channel_avatar: str
    channel_banner: str
    channel_info_complete: bool