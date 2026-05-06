import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import os
import subprocess
import ollama

# Backend Imports
from audio_processor import MeetingTranscriber
from rag_engine import NotebookEngine
from llm_compiler import LLMCompiler
from bootstrapper import check_setup

class MeetingApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- Window Config ---
        self.title("AI Meeting Pro - Blackwell Optimized")
        self.geometry("1150x800")
        ctk.set_appearance_mode("dark")
        
        # --- State Management ---
        self.audio_path = None
        self.transcriber = MeetingTranscriber(self.log)
        self.rag = NotebookEngine()
        self.compiler = LLMCompiler(self.log)

        # --- UI Construction ---
        self._build_ui()

        # --- Startup Sequence ---
        # 1. Sweep VRAM and load Whisper
        threading.Thread(target=self._initial_gpu_load, daemon=True).start()
        # 2. Scan Ollama models via CLI
        threading.Thread(target=self.init_ollama_list, daemon=True).start()

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # SIDEBAR
        self.sidebar = ctk.CTkFrame(self, width=280, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        ctk.CTkLabel(self.sidebar, text="MEETING PRO", font=("Helvetica", 24, "bold")).pack(pady=20)

        # 1. LLM Model Management (LOCKED ON START)
        ctk.CTkLabel(self.sidebar, text="1. LLM Selection", text_color="gray").pack(pady=(15, 0))
        self.model_dropdown = ctk.CTkComboBox(self.sidebar, values=["Scanning..."], state="disabled", width=220)
        self.model_dropdown.pack(pady=10)
        
        self.btn_init_llm = ctk.CTkButton(
            self.sidebar, text="Initialize LLM", state="disabled", 
            command=self.lazy_init_llm, fg_color="#34495E"
        )
        self.btn_init_llm.pack(pady=5)

        # 2. RAG Notebook
        ctk.CTkLabel(self.sidebar, text="2. Supporting Materials", text_color="gray").pack(pady=(25, 0))
        self.btn_add_pdf = ctk.CTkButton(self.sidebar, text="Add PDF to Notebook", command=self.lazy_add_pdf)
        self.btn_add_pdf.pack(pady=10)

        # 3. Audio Input
        ctk.CTkLabel(self.sidebar, text="3. Audio Recording", text_color="gray").pack(pady=(25, 0))
        self.btn_select_audio = ctk.CTkButton(self.sidebar, text="Select Audio File", fg_color="#E67E22", command=self.select_audio)
        self.btn_select_audio.pack(pady=10)
        self.audio_info = ctk.CTkLabel(self.sidebar, text="No file selected", font=("Arial", 11), text_color="#BDC3C7")
        self.audio_info.pack()

        # 4. Final Processing
        ctk.CTkLabel(self.sidebar, text="4. Translation Mode", text_color="gray").pack(pady=(25, 0))
        self.strategy_var = ctk.StringVar(value="translate")
        ctk.CTkRadioButton(self.sidebar, text="Translate (to English)", variable=self.strategy_var, value="translate").pack(pady=5)
        ctk.CTkRadioButton(self.sidebar, text="Romanized (Hindi Script)", variable=self.strategy_var, value="romanized").pack(pady=5)

        self.btn_run = ctk.CTkButton(
            self.sidebar, text="WAIT: BOOTING ENGINES", height=50, 
            font=("Arial", 14, "bold"), command=self.run_main_workflow, state="disabled"
        )
        self.btn_run.pack(pady=40, padx=20)

        # MAIN LOGGING AREA
        self.log_area = ctk.CTkTextbox(self, font=("Consolas", 12), border_width=1)
        self.log_area.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")

    def log(self, text):
        self.log_area.insert("end", f"{text}\n")
        self.log_area.see("end")

    # --- LOGIC & THREADING ---

    def _clear_vram(self):
        """Scans for currently active Ollama models and forces them to unload."""
        self.log("[*] VRAM SWEEP: Checking for leftover AI processes...")
        try:
            # Check 'ollama ps' for running models
            result = subprocess.run(["ollama", "ps"], capture_output=True, text=True)
            lines = result.stdout.strip().split('\n')
            
            running_models = []
            if len(lines) > 1:
                for line in lines[1:]:
                    if line.strip():
                        # Extract the first word (model name) from the row
                        model_name = line.split()[0]
                        running_models.append(model_name)
            
            if running_models:
                for model in running_models:
                    self.log(f"[*] Stopping leftover model: {model}...")
                    # Officially stop the model to clear its memory
                    subprocess.run(["ollama", "stop", model], capture_output=True)
                self.log("[+] VRAM Sweep Complete: GPU memory is completely clear.")
            else:
                self.log("[+] VRAM Sweep Complete: No leftover models found.")
                
        except Exception as e:
            self.log(f"[-] VRAM Sweep Note: Could not verify running models ({e})")

    def _initial_gpu_load(self):
        """Clears memory, then forces Whisper to claim VRAM."""
        self.log("[!] SYSTEM BOOT: Initiating startup sequence...")
        
        # 1. Clear the VRAM explicitly
        self._clear_vram()
        
        # 2. Lock Whisper onto GPU
        self.log("\n[!] SYSTEM LOCK: Whisper is securing GPU priority...")
        success = self.transcriber.load_onto_gpu()
        
        # 3. Once Whisper is ready, unlock UI
        self.model_dropdown.configure(state="normal")
        self.btn_init_llm.configure(state="normal", fg_color="#2E86C1")
        
        if success:
            self.btn_run.configure(state="normal", text="GENERATE SUMMARY", fg_color="#27AE60")
            self.log("\n[+] VRAM SECURED: Whisper is ready. You may now initialize LLM.")
        else:
            self.btn_run.configure(state="normal", text="GENERATE (CPU FALLBACK)", fg_color="#E67E22")
            self.log("\n[-] GPU LOCK FAILED: Whisper is on CPU. You may still proceed.")

    def init_ollama_list(self):
        if check_setup():
            try:
                result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
                lines = result.stdout.strip().split('\n')
                models = [line.split()[0] for line in lines[1:] if line.strip()]
                self.model_dropdown.configure(values=models)
                if models: self.model_dropdown.set(models[0])
                self.log("[+] Ollama models detected.")
            except:
                self.log("[-] Error scanning Ollama via CLI.")

    def lazy_init_llm(self):
        model_name = self.model_dropdown.get()
        if model_name in ["Scanning...", "No models found"]: return

        self.log(f"[*] Pre-loading {model_name} (10m Keep-Alive)...")
        def run_init():
            try:
                ollama.generate(model=model_name, prompt="", keep_alive="10m")
                self.log(f"[+] {model_name} locked in VRAM for 10 minutes.")
            except Exception as e:
                self.log(f"[-] Init failed: {e}")

        threading.Thread(target=run_init, daemon=True).start()

    def lazy_add_pdf(self):
        path = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if path:
            threading.Thread(target=lambda: self.rag.ingest_pdf(path, self.log), daemon=True).start()

    def select_audio(self):
        self.audio_path = filedialog.askopenfilename(filetypes=[("Audio", "*.mp3 *.wav *.m4a")])
        if self.audio_path:
            self.audio_info.configure(text=os.path.basename(self.audio_path), text_color="#2ECC71")
            self.log(f"[+] Selected: {self.audio_path}")

    def run_main_workflow(self):
        if not self.audio_path:
            messagebox.showwarning("File Missing", "Please select an audio file first!")
            return
        
        self.btn_run.configure(state="disabled", text="PROCESSING...")
        threading.Thread(target=self._execute_pipeline, daemon=True).start()

    def _execute_pipeline(self):
        try:
            self.log("\n" + "="*40)
            transcript = self.transcriber.transcribe(self.audio_path, self.strategy_var.get())
            self.log("[+] Transcription finished.")

            context = self.rag.query_context(transcript)
            
            self.compiler.model_name = self.model_dropdown.get()
            latex = self.compiler.generate_summary(transcript, context)
            
            filename = os.path.basename(self.audio_path).rsplit('.', 1)[0]
            if self.compiler.compile_to_pdf(latex, filename):
                self.log(f"\n[!!!] SUCCESS [!!!]\nPDF generated: exports/{filename}.pdf")
                messagebox.showinfo("Done", f"Summary created: {filename}.pdf")
        except Exception as e:
            self.log(f"\n[-] Critical Pipeline Error: {e}")
        finally:
            self.btn_run.configure(state="normal", text="GENERATE SUMMARY")

if __name__ == "__main__":
    app = MeetingApp()
    app.mainloop()