# Фиксированные фрагменты позитивного промпта видеомодели (собирает build_video_prompt_text).
# Утвердительная hold-фраза вместо прежнего запретительного списка («Do not end on lap, legs,
# jeans…»): видеомодель не понимает отрицаний — токены запрещённых объектов работали как призыв
# их нарисовать (бит заканчивался ровно запрещённым torso-only кадром). Запреты живут только в
# инструкции LLM ниже (GENERATE_VIDEO_PROMPTS_PROMPT) — LLM отрицания понимает.
FINAL_FRAME_HOLD_SENTENCE = (
    "The final frame holds the character's face fully visible, sharp and clearly readable."
)

CAMERA_DISCIPLINE_BLOCK = (
    "CAMERA DISCIPLINE\n"
    "Unless a camera move is explicitly described above, the camera is locked and "
    "perfectly static: no drift, no shake, no pan, no zoom, no reframing. If a move is "
    "described, it completes and settles into a static hold before the final frame."
)

# Текст-якорь стартового кадра для LTX (build_video_prompt_text). end_frame ПРЕДЫДУЩЕГО бита —
# буквальный входной freeze этого клипа (frame 0); фраза велит модели НАЧАТЬ движение ровно из
# этого состояния, а не доигрывать действие мгновенно (иначе поза/реквизит/мимика «прыгают» на
# стыке). Утвердительная, короткая — чтобы не пере-описывать статичную сцену (I2V-минимализм).
STARTING_FRAME_LEAD_SENTENCE = (
    "This clip's first frame is exactly the state below; all motion begins from it and "
    "continues forward — the subject's pose, hands, any held prop and expression start "
    "here, with no jump."
)

GENERATE_VIDEO_PROMPTS_PROMPT = """\
You are a film director generating per-beat video prompts for a short-form video shot as one
continuous take. You are given the full scenario, the Visual Style Profile, the locked Character
Reference Sheet, and the ALREADY DECIDED segments of the script.

Input shape — the script is given to you GROUPED INTO SEGMENTS, not as a flat list of beats:

  segments: [
    {
      "seg_id": <int>,
      "speaker": "<who speaks this segment>",
      "emotion": "<delivery emotion for the whole segment>",
      "tts_text": "<the full spoken line of this segment>",
      "duration": <segment's total real duration in seconds>,
      "beats": [ { "id": <int>, "audio_text": "<this beat's spoken span>", "duration": <seconds> } ]
    }
  ]

A SEGMENT is ONE speaker delivering ONE continuous prosodic unit. Do NOT re-split the script, do
NOT invent beats or segments, do NOT change ids or durations. Cover EVERY given beat of EVERY
segment, in id order.

For each beat produce a `video_prompt` and an `end_frame`.

Output ONLY valid JSON, no commentary, in exactly this shape:

{
  "beats": [
    {
      "id": <the given beat id>,
      "video_prompt": "<motion-focused shot description, see rules>",
      "end_frame": "<exactly how the clip ENDS, see rules>"
    }
  ]
}

HOW THE PIPELINE WORKS (read first — it dictates every camera rule below):
- Each beat is rendered as a separate clip. The clip's input image is the FROZEN final frame of
  the previous beat's clip. A still image carries no motion: camera velocity does NOT survive a
  beat boundary. If the camera is mid-move when a beat ends, the next clip starts from a freeze
  and the footage stutters. Only SETTLED, STATIC frames chain seamlessly.
- The input image is also the ONLY carrier of the character's identity (the video model locks the
  face from the input image, not from text). A final frame without a readable face breaks the
  character in every following clip.

FIRST-BEAT INPUT FRAME (grounding — applies when an image is attached to this request):
- The attached image IS the literal input frame of beat 1: the video model will animate beat 1
  starting from EXACTLY this picture. The "First-beat image prompt" section, when present,
  describes how that frame was generated.
- Beat 1's video_prompt MUST animate exactly the depicted scene: same location, framing, outfit
  and props — no restaging, no teleports, no new room, no different clothes. Describe motion
  that begins in that exact composition.
- If the script demands a different master framing than the attached frame shows, do NOT cut or
  jump to it: script the change INSIDE beat 1 as visible on-screen motion (the subject moves, or
  ONE deliberate camera move executes) that completes and settles into the new framing before
  the beat ends.

GRAPHICS & TEXT (hard model limit — LTX-2 cannot render readable or consistent text):
- NEVER request on-screen text, words, captions, numbers, prices, receipts, labels, logos, UI,
  charts, or small/multiple detailed icons. The model renders these as garbled scribble — this
  was a real failure (a "grocery receipt" came out as unreadable smear; a beat collapsed into
  graphics-and-text noise).
- If the script needs a supporting visual, allow at MOST ONE large, simple, text-free symbolic
  object (a plain silhouette-level shape), held in the negative space well away from the face,
  entering on a described path and persisting for the whole clip. No text on it, no fine detail.
- When in doubt, drop the graphic entirely and keep the shot on the presenter.

AUDIO (the soundtrack is supplied separately — do NOT write any audio):
- The clip is rendered against a pre-made voice track and lip-synced to it. NEVER put spoken
  lines, quotation marks, dialogue, voiceover, narration, music, or sound-effect descriptions in
  the prompt. Describe only the VISIBLE articulation: lip movement matching speech, breaths,
  pauses, gestures timed to the delivery.

CAMERA DOCTRINE — tripod-first (this is the core of professional-looking footage):
- DEFAULT for EVERY beat: a locked-off static shot. The video_prompt MUST then contain this exact
  sentence: "Static camera. Locked frame. No camera movement."
- The frame is animated by the SUBJECT, never by an idle camera: gestures, gaze shifts, posture
  changes, handling props, walking within the frame, natural speech articulation. Move the
  subject, not the camera.
- A camera move is the EXCEPTION: allowed only with a clear motivation from the script (revealing
  an object the script mentions, following a character who walks, one deliberate emphasis). No
  unmotivated drift, sway, push-in, or "atmosphere" moves — ever.
- Rhythm: at most ONE move-beat per segment, NEVER two move-beats in a row, and only a few in the
  whole video. When in doubt, stay static.
- A camera move NEVER crosses a beat boundary. The move starts from stillness, executes as ONE
  simple move (one axis, one purpose: a slow dolly, pan, or tilt — prefer these over zoom), and
  settles into a static hold WITH TIME TO SPARE before the beat ends. Always describe the exact
  framing where it settles — the state of the frame AFTER the move completes.
- Composition: hold ONE master framing per segment — a stable, deliberate composition in which the
  primary speaker's face is clearly readable. All static beats of the segment sit in this exact
  framing. A composition change happens ONLY at a segment boundary (new seg_id / new speaker /
  scene change), executed as that segment's single completed move in its FIRST beat — or simply
  keep the previous framing.

CONTINUITY ACROSS THE BEAT BOUNDARY (subject, not just camera — the dominant seam):
- Each beat's clip starts from the FROZEN final frame of the previous beat — that frozen frame IS
  this clip's frame 0. Just as camera velocity does not survive the boundary, neither does the
  subject's motion: the position of the hands and arms, the posture, the gaze, the facial
  expression, and any prop held in the hands at the START of a beat are EXACTLY those in the
  previous beat's end_frame. Never start a beat in a pose, expression, or prop-state the previous
  end_frame did not end in.
- Write each action as BEGINNING from that resting state and progressing through the clip — NEVER
  as an already-completed state. The model renders frame 0 as the input freeze and then animates
  forward; a process written as a finished state ("his hand is raised holding a bag") makes the
  model snap into it instantly, so the real first frame diverges from the freeze and the cut jumps.
  Phrase motion as a continuation from rest: "from his hands resting at his sides, his right hand
  slowly begins to lift", not "his hand is up".
- Expression continuity: the expression at a beat's first instant equals the previous end_frame's
  expression. Any emotional shift is PERFORMED visibly across the beat (a smile that grows, a brow
  that furrows), never already present at frame 0.

video_prompt rules (image-to-video: the start frame ALREADY EXISTS — write MOTION, not a painting):
- Do NOT re-describe the static appearance, outfit, set dressing, or framing already visible in
  the input frame. Describe what HAPPENS during the beat: the subject's actions as a natural
  sequence flowing from beginning to end, present tense, one flowing paragraph. Describe motion in
  DETAIL — roughly 3-6 sentences — but ONLY the dynamics (action, performance, and the camera's
  relationship to the subject); never the static scene the input frame already carries.
- ONE clear main action per beat. Keep motion smooth and physically plausible: no fast, jerky,
  chaotic, jumping, spinning or twisting motion, and do not stack several actions or objects into
  one short beat — the model drops or garbles overloaded prompts.
- Identity tag: refer to each character on screen by name plus 2-3 key locked traits in one short
  phrase (e.g. "Jack, the lean young man with tousled jet-black hair in the olive hoodie") — NOT
  the full reference sheet.
- Exactly ONE camera sentence per beat: either the exact static sentence ("Static camera. Locked
  frame. No camera movement.") or, on a rare move-beat, the single motivated move with its settle
  framing described.
- Spoken delivery: the beat's audio_text is what is spoken during the clip (empty string = silent
  B-roll beat). Break the delivery into short phrases with physical acting beats between them
  ("he pauses, glances to the side, then continues"). Use physical cues, not inner emotional
  labels; the segment's `emotion` sets the tone of the performance.
- No new, undescribed characters or objects at ANY point in the clip. Every object a character
  uses must already be in frame OR enter on a described path. Held props persist for the whole
  clip and are stated explicitly.
- Props NEVER materialize on the boundary: an object the subject will hold is EITHER already in the
  hand in the input frame, OR enters on a described physical path (the hand moves off-frame and
  brings it back in). It never simply appears in the hand between beats. NEVER describe a prop by
  metaphor or suggestion ("a loose cup shape to suggest holding a bag", "as if holding a phone") —
  the model materializes a concrete object abruptly at frame 0. State plainly whether the hand is
  empty or holds ONE specific simple object; if it must appear, script its entrance.
- Do not put any duration text inside video_prompt.
- Follow the Visual Style Profile exactly.

end_frame rules — TECHNICAL HANDOFF CONTRACT (not a creative choice):
- The end_frame is, verbatim, the first frame of the next clip: the pipeline extracts this clip's
  final frame and feeds it as the start image of the next beat. EVERY beat's end_frame keeps the
  primary character's face present, sharp, in focus, and identity-readable (front, 3/4, or a
  readable profile; key locked traits visible).
- STATIC beat: the end_frame is the SAME master framing the whole beat sat in — explicitly state
  the composition is unchanged; the subject is simply caught at the final instant of their action
  (a mid-speech mouth position is fine). Do NOT introduce any new framing language ("settles into
  a close-up", "the camera now frames...") on a static beat: the camera has not moved.
- MOVE beat: the end_frame is the NEW settled composition after the move has fully completed —
  stable, at rest, no motion blur.
- Identity: name the character with the same short identity tag (name + 2-3 locked traits) so the
  text reinforces the face the image already carries. Appearance unchanged from the locked sheet.
- Sharp and in focus: no motion blur, no defocus, no smear. Held props still in hand. NO fades,
  dissolves, or fade-to-black — the clip ends lit and stable.
- NEVER end on an object, product, prop, empty space, scenery, lap, legs, jeans, hands, phone,
  torso-only framing, window-only framing, back-to-camera framing, silhouette-only framing, or any
  frame where the character is absent or the face is not readable. Phrases such as "no characters are present", "close-up of the <object>", or any object-only / insert framing are FORBIDDEN as an
  end_frame on EVERY beat.
- The end_frame is the RESOLVED final state, not the action: it MUST DIFFER from video_prompt. Do
  NOT copy video_prompt text into end_frame.
- Pin the FULL handoff pose, not only the face. Because the end_frame is the literal first frame of
  the next beat, it must lock the exact state the next clip continues from: the position of the
  hands and arms, whether they hold a prop or are at rest or out of frame, the posture, the gaze,
  and the facial expression at the final instant. The face-readability requirement stays, but a
  face-only end_frame is insufficient — an unpinned hand/prop state is exactly what makes the next
  clip jump.

Output raw JSON only — no markdown fences, no "BEAT 1 —" labels, no prose.\
"""

"""
This is v9. Changes vs v8 (fixes the subject-pose jump at the beat boundary — idea-1 beat-1→2: the
hand snapped up and a bag materialized on frame 0, the expression jumped calm→surprised, so the
cut between the two clips jumped despite the extract_last_frame handoff working):
- New CONTINUITY ACROSS THE BEAT BOUNDARY section. v6-v8 enforced CAMERA continuity across the
  frozen-frame handoff but said nothing about the SUBJECT — and since the doctrine moved all
  animation onto the subject, the subject's pose/hands/prop/expression became the dominant seam.
  Now: a beat's start state (hands, posture, gaze, expression, held prop) EQUALS the previous beat's
  end_frame; actions are written as BEGINNING from rest and progressing, never as an already-
  completed state (which makes the model snap into it at frame 0); expression shifts are performed
  visibly within the beat, not present at frame 0.
- Prop materialization banned. A held prop is either already in the input frame or enters on a
  described path — it never simply appears in the hand between beats — and metaphor/suggestion
  phrasing for props ("to suggest holding a bag", "as if holding…") is forbidden (it made the model
  materialize a concrete object abruptly).
- end_frame must pin the FULL handoff pose (hands/arms, prop or rest, posture, gaze, expression),
  not only the face: a face-only end_frame left the next beat's hand/prop state undefined, which is
  what jumped. Paired with a code-level anchor — build_video_prompt_text now prepends a STARTING
  FRAME block (the previous beat's end_frame, via STARTING_FRAME_LEAD_SENTENCE) so LTX is told its
  frame 0 explicitly.

This is v8. Changes vs v7 (aligned with the official LTX-2 prompting & workflow guides):
- New GRAPHICS & TEXT section. LTX-2 "does not currently generate readable or consistent text"
  (official guide), yet the pipeline kept asking for icons / a receipt / labels — which rendered
  as garbled scribble (beat 5 "receipt" smear; beat 35 collapsed into graphics+text noise). Now:
  never request text/numbers/labels/logos/UI/small icons; at most ONE large, simple, text-free
  symbolic object in negative space away from the face, or drop the graphic entirely.
- New AUDIO section. This is an image+audio→video (ia2v) pipeline: the voice track is supplied
  separately and the clip is lip-synced to it. The prompt must NOT contain dialogue, quotes,
  voiceover, music or SFX (the t2v guide puts speech in quotes — that is the WRONG mode here).
  Only visible articulation is described. Prevents the LLM from leaking spoken lines into the
  video-model prompt.
- Motion detail rebalanced. The guide wants a detailed "natural sequence flowing from beginning
  to end" and "the camera's relationship to the subject"; v7's "keep it proportionally short"
  underspecified the dynamics. Now ~3-6 sentences of DETAILED motion, but still dynamics-only
  (no static re-description), plus ONE clear main action per beat and a ban on fast/chaotic/
  jumping/twisting motion and overloaded prompts (guide: complex physics & overload cause
  artifacts and dropped instructions).

This is v7. Changes vs v6:
- New "FIRST-BEAT INPUT FRAME" grounding section. Root cause: step 12 never SAW the real step-8
  image, so beat 1's prompt restaged the scene (image: character in a car with groceries; prompt:
  talking head at a desk) and the first half-second of the clip was an ugly iris-wipe morph. The
  service now attaches the actual image (vision) + the step-7 image prompt text; the doctrine
  requires beat 1 to animate from exactly the depicted frame — no restaging/teleports — and to
  script any framing change as visible on-screen motion that completes and settles inside beat 1.
- Fixed positive-prompt fragments for the video model moved here as constants
  (FINAL_FRAME_HOLD_SENTENCE, CAMERA_DISCIPLINE_BLOCK — prompt text lives only in app/prompts/).
  The old "FINAL-FRAME NEGATIVE CONSTRAINTS / Do not end on lap, legs..." block is GONE from the
  video-model prompt: the video model does not understand negations — the forbidden-object tokens
  acted as an invitation to draw them (a beat ended on exactly the forbidden torso-only frame).
  The NEVER-list below stays: it instructs the LLM (which does understand negations), not the
  video model.

This is v6. Changes vs v5:
- v5's "one continuous camera arc per segment, beats are slices of it" FAILED in practice: the
  camera still shifted on every beat. Root cause is pipeline physics — each beat's clip starts
  from a FROZEN still frame (extract_last_frame of the previous clip), so camera velocity does NOT
  survive the beat boundary. An arc sliced across beats renders as move-stop-move-stop stutter,
  and v5 explicitly demanded motion on every beat ("the camera is still moving and will keep
  moving into the next beat"). Only settled, static states chain seamlessly.
- New doctrine — "tripod-first" (classic cinematography adapted to the I2V chain): the default for
  EVERY beat is a locked static shot (exact sentence "Static camera. Locked frame. No camera
  movement." required in video_prompt); the frame is animated by the subject's performance, not
  the camera. A camera move is rare, script-motivated, at most one move-beat per segment, never
  two in a row, and must complete AND settle into a static hold INSIDE one beat — a move never
  crosses a beat boundary. ONE master framing per segment (face readable in it → the identity
  handoff is satisfied with zero motion); composition changes only at a segment boundary, as that
  segment's single completed move in its first beat.
- Per the official LTX-2.3 I2V guidance ("avoid describing the static elements already visible in
  the input image; focus the prompt on motion and action"), video_prompt no longer pastes the full
  Character Reference Sheet verbatim: identity is carried by the input frame; the text uses a
  SHORT identity tag (name + 2-3 locked traits). The full re-description was "re-establishing"
  (= moving) the shot every beat and hurting adherence of short 2-4s clips.
- end_frame on a static beat is the SAME unchanged master framing (no reframing language like
  "settles into a close-up" — that text itself caused camera moves); on a move-beat it is the new
  settled composition. All identity bans stay on every beat.

This is v5. Changes vs v4:
- Input is now SEGMENT-GROUPED: beats arrive nested inside their segment (one speaker, one prosodic
  unit) instead of as a flat list. The model is told a segment is ONE continuous visual moment and
  must plan ONE continuous camera arc per segment that spans its beats, distributed across the
  segment's TOTAL duration. Each beat's video_prompt is a consecutive slice of that arc, continuing
  from the previous beat's end_frame — no per-beat camera reset. This fixes the v4 failure mode where
  every 2-4s beat was planned in isolation and the camera jittered/yo-yoed.
- end_frame contract relaxed by position in the segment. Within a segment (beat is NOT its last), the
  end_frame is a mid-arc handoff: the primary speaker's face must stay READABLE (sharp, identity-clear)
  but need NOT be a re-centered front face — profile/3-4/medium during continuous motion is fine. On
  the LAST beat of a segment (and on any speaker/scene change) the shot settles into a clean, stable,
  sharp front/3-4 face — a clean anchor for the cut to the next segment. The object-only / "no
  characters present" / cut-off / back-to-camera bans still apply to EVERY beat (the face is always
  present in the handoff).

This is v4. Changes vs v3:
- end_frame no longer forces a specific final shot scale. Wide, medium, or close shots are
  acceptable if the final frame clearly shows most of the primary character's face and keeps
  identity readable. Front, 3/4, or a readable profile may be used; unreadable face endings are
  still forbidden.
- Final-frame bans now explicitly include lap, legs, jeans, hands, phone, torso-only, window-only,
  empty space, back-to-camera, and silhouette-only endings.

This is v3. Changes vs v2:
- end_frame reframed as a TECHNICAL HANDOFF CONTRACT, not a creative shot: it is the literal
  first frame of the next clip and the only carrier of character identity across the I2V chain
  (LTX-2.3 anchors identity on the input image, not on the text sheet). The "why" is now stated.
- end_frame MUST always end on the primary character's face (front/3-4, sharp, per locked sheet);
  object-only / "no characters present" / cut-off / back-to-camera endings are forbidden. It must
  restate the character's face traits and MUST NOT duplicate video_prompt (a beat previously
  returned end_frame == video_prompt on an object, the camera never returned to the face, and the
  next clip reinvented the character).
- Camera: a clip MAY move to show an object/detail mid-clip (variety is welcome), but it MUST
  return to the character's face before the clip ends. Prefer camera TRANSLATION/ROTATION (pan,
  truck/dolly, tilt, orbit, lateral moves) over zoom in/out: lateral moves keep the face at a
  stable scale and make the return clean, whereas a hard push-in on an object crops the face out
  and yields an object-only final frame (the original bug). The move AND the return must both
  finish inside the clip's duration. (The earlier "keep the face in frame the whole clip" idea is
  dropped — beats are short, 2-4s, so it would pin the character on screen the entire video.)

This is v2. Changes:
- replace blocks:
(old): 'Camera movements must be specific and limited.
Vague language such as "rotate the camera to capture the atmosphere"
or any movements that reveal space outside the screen are prohibited.
The camera only shows what is described.'
(new): 'Camera movements must be specific and limited. If a new space outside the screen is shown,
 it must be precisely and thoroughly described to avoid "inventing" video generation models (ltx-2.3 and others).'
"""
