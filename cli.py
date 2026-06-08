from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import Command

from app.config import DB_URL, THREAD_ID
from app.db import (
    fetch_channel_info,
    migrate_audio_beat_prompts_table,
    migrate_audio_beats_table,
    migrate_audio_seg_prompts_table,
    migrate_audio_table,
    migrate_channel_info_style,
    migrate_channel_info_table,
    migrate_characters_sheet_table,
    migrate_ideas_table,
    migrate_image_prompts_table,
    migrate_images_table,
    migrate_scenarios_table,
    migrate_visual_styles_table,
    upsert_channel_info,
    upsert_channel_style_info,
)
from app.graph import build_app

config = {"configurable": {"thread_id": THREAD_ID}}

with PostgresSaver.from_conn_string(DB_URL) as checkpointer:
    checkpointer.setup()
    migrate_channel_info_table()
    migrate_channel_info_style()
    migrate_ideas_table()
    migrate_scenarios_table()
    migrate_characters_sheet_table()
    migrate_visual_styles_table()
    migrate_image_prompts_table()
    migrate_images_table()
    migrate_audio_seg_prompts_table()
    migrate_audio_beat_prompts_table()
    migrate_audio_table()
    migrate_audio_beats_table()
    app = build_app(checkpointer)

    initial_state = fetch_channel_info()

    state = app.get_state(config)
    if state and state.next:
        interrupted = state.tasks[0].interrupts if state.tasks else []
        result = (
            {"__interrupt__": interrupted}
            if interrupted
            else app.invoke(Command(resume=None), config)
        )
    else:
        result = app.invoke(initial_state, config)

    while "__interrupt__" in result:
        question = result["__interrupt__"][0].value
        user_text = input(f"\n{question}\n> ")
        result = app.invoke(Command(resume=user_text), config)

    final = app.get_state(config).values
    if final.get("channel_info_complete"):
        upsert_channel_info(final)
    if final.get("channel_style_complete"):
        upsert_channel_style_info(
            final["channel_style"], final.get("transcript_obsidian_files", [])
        )

    checkpointer.delete_thread(THREAD_ID)

    print("\n--- готово, финальное состояние: ---")
    print(result)
