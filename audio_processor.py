import os
from faster_whisper import WhisperModel
import torch

class MeetingTranscriber:
    def __init__(self, log_callback):
        self.model = None
        self.model_size = "large-v3-turbo"
        self.log = log_callback
        self.ready = False # NEW: Track readiness

    def load_onto_gpu(self):
        try:
            self.log(f"[*] Pre-loading {self.model_size} onto RTX 5070 Ti...")
            # Optimized for SM120: float16 + CUDA
            self.model = WhisperModel(
                self.model_size, 
                device="cuda", 
                compute_type="float16",
                device_index=0
            )
            self.ready = True # Set to true once loaded
            self.log("[+] Whisper successfully locked onto GPU.")
            return True
        except Exception as e:
            self.log(f"[-] GPU Load failed: {e}. Falling back to CPU.")
            self.model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
            self.ready = True
            return False

    def transcribe(self, file_path, mode):
        if not self.ready or self.model is None:
            raise Exception("Whisper engine is still warming up. Please wait for the success message!")
            
        self.log(f"[*] Transcribing in {mode} mode...")
        if mode == "translate":
            segments, info = self.model.transcribe(file_path, task="translate")
        else:
            primer = "Umeed hai sab theek honge. Aaj ki meeting summary yahan hai."
            segments, info = self.model.transcribe(file_path, language="hi", initial_prompt=primer)

        return " ".join([s.text for s in segments])