ANALYZE_TRANSCRIPTS_PROMPT = (
    "You are a video content analyst. Analyze the provided video transcripts and extract the "
    "channel's content style characteristics.\n\n"
    "Output ONLY valid JSON (no commentary, no markdown) with exactly these keys:\n"
    "{\n"
    '  "niche": "description what the niche of these video transcripts",\n'
    '  "target_audience": "description of who the content targets",\n'
    '  "hook_style": "how videos open and grab attention in the first 30 seconds",\n'
    '  "script_flow": "overall structure and pacing of the script",\n'
    '  "sentence_rhythm": "length and cadence of sentences used",\n'
    '  "tone": "emotional tone and energy level of the narration",\n'
    '  "transitions": "how the speaker moves between topics or sections",\n'
    '  "curiosity_gaps": "techniques used to create information gaps that keep viewers watching",\n'
    '  "emotional_triggers": "emotional appeals and motivators used",\n'
    '  "retention_techniques": "specific methods used to keep viewers watching",\n'
    '  "direct_address": "how the speaker addresses the viewer directly",\n'
    '  "words_per_second": "estimated speech rate as a number string, e.g. \\"2.5\\"",\n'
    '  "average_word_count": "average word count per video as a number string",\n'
    '  "target_word_count": "recommended word count for new scripts as a number string"\n'
    "}"
)
