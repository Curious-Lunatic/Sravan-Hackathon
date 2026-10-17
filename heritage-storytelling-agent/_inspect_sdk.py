import inspect
from sarvamai import SarvamAI
from sarvamai.text.client import TextClient
from sarvamai.speech_to_text.client import SpeechToTextClient

c = SarvamAI(api_subscription_key="x")
print("identify", inspect.signature(c.text.identify_language))
print("translate", inspect.signature(c.text.translate))
print("transcribe", inspect.signature(c.speech_to_text.transcribe))
print("tts", inspect.signature(c.text_to_speech.convert))
print("digitise", inspect.signature(c.doc_ai.digitise))
print("get_status", inspect.signature(c.doc_ai.get_status))
print("get_download_url", inspect.signature(c.doc_ai.get_download_url))
print("stt_job", [m for m in dir(c.speech_to_text_job) if not m.startswith("_")])
print("create_job", inspect.signature(c.speech_to_text_job.create_job))
