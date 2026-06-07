GENERATE_AUDIO_PROMPTS_PROMPT = """\
Split the scenario into beats of max 3–5 seconds each, AND group the spoken text into prosodic audio segments.

Output ONLY valid JSON, no commentary, in exactly this shape:

{
  "audio_segments": [
    {
      "seg_id": 1,
      "speaker": "Narrator",
      "emotion": "calm, reflective",
      "tts_text": "<one coherent prosodic unit: full sentence(s), single speaker>",
      "beat_ids": [1, 2]
    }
  ],
  "beats": [
    {
      "id": 1,
      "seg_id": 1,
      "audio_text": "<exact contiguous span of its segment's tts_text, or empty string if silent>"
    }
  ]
}

audio_segments rules:
- A segment is ONE prosodic unit: complete sentence(s), never cut mid-thought.
- ONE speaker per segment. A new speaker = a new segment (clean cut at turns).
- emotion describes delivery for the whole segment (for the TTS pass).
- tts_text is exactly what gets sent to TTS in a single pass.
- beat_ids lists, in order, every beat that consumes audio from this segment.

bridge rules (so the synthesized audio can be sliced back per beat):
- Concatenating the audio_text of a segment's beats, in id order, must EQUAL
  that segment's tts_text exactly — verbatim, no gaps, no overlaps.
- Beat boundaries inside a spoken segment fall ONLY at sentence or clause ends
  (natural pauses) — never mid-word, never mid-phrase.
- A beat may be silent: audio_text = empty string, and seg_id = null. Use this
  for pure action / B-roll beats.
- audio_text uses the exact script words (verbatim, no paraphrase).
- duration_estimate uses STATE 5 words-per-second and is an ESTIMATE only.
  Final beat duration is set from the aligned audio in my pipeline, not here.

Cover every beat in script order, ids starting at 1, no gaps.

Output raw JSON only — no markdown fences, no "BEAT 1 —" labels, no prose.\
"""
