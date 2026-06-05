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
    # для опционального второго шага - нужно ли анализоровать скриншоты для определения брендинга
    use_screenshots: bool
    # step 3: style analysis results
    channel_style: dict
    channel_style_complete: bool
    transcript_obsidian_files: list[str]
    # step 4: video idea selection
    generated_ideas: list[str]
    idea_name: str
    idea_id: int
    raw_idea_exists: bool
    # step 5+: маршрутизация по статусам идей (диспетчер)
    pipeline_step: int  # курсор текущего шага (старт 5)
    executed_steps: list[int]  # шаги, выполненные за этот прогон (защита от зацикливания)
    pipeline_target: int  # шаг, выбранный диспетчером (для роутера)
