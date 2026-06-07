from google import genai
from google.genai import types

from app.config import GOOGLE_API_KEY


def get_client() -> genai.Client:
    return genai.Client(api_key=GOOGLE_API_KEY)


def synthesize(prompt: str, voice_name: str, model: str) -> bytes:
    # Один проход TTS (single-speaker): текст prompt озвучивается голосом voice_name моделью model.
    # Возвращает сырые PCM-байты (signed 16-bit LE, 24000 Hz, mono). Обёртка в WAV — задача утилиты.
    client = get_client()
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name)
                )
            ),
        ),
    )
    return response.candidates[0].content.parts[0].inline_data.data
