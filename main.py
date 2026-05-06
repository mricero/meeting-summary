import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import os
import subprocess
import shutil
import ollama

# Backend Imports
from audio_processor import MeetingTranscriber
from rag_engine import NotebookEngine
from llm_compiler import LLMCompiler
from bootstrapper import check_setup

class MeetingApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("AI Meeting Pro - Ultimate Edition")
        self.geometry("1200x850")
        ctk.set_appearance_mode("dark")
        
        self.audio_path = None
        self.transcriber = MeetingTranscriber(self.log)
        self.rag = NotebookEngine()
        self.compiler = LLMCompiler(self.log)

        # STATE TRACKING FOR DYNAMIC RELOADS
        self.loaded_model = None
        self.loaded_ctx = None

        # Config Maps
        self.ctx_values = [4096, 8192, 16384, 32768, 65536, 131072]
        self.ctx_labels = ["4k", "8k", "16k", "32k", "64k", "128k"]
        
        self.keep_alive_map = {
            "5 min": "5m", "10 min": "10m", "20 min": "20m", 
            "30 min": "30m", "40 min": "40m", "1 hr": "1h", "Unlimited": "-1"
        }

        # Elements setup. We use dictionaries to flag items that need custom input boxes.
        self.elements_config = [
            {"name": "Title Page (\\maketitle)", "input": False},
            {"name": "Table of Contents", "input": False},
            {"name": "Colored Callout Boxes (tcolorbox)", "input": False},
            {"name": "Header & Footer (fancyhdr)", "input": True, "placeholder": "E.g., Project Alpha"},
            {"name": "Draft Watermark", "input": True, "placeholder": "E.g., CONFIDENTIAL"},
            {"name": "Two-Column Layout", "input": False},
            {"name": "Explicit Definitions Block", "input": False},
            {"name": "Highlighted Key Points (xcolor)", "input": False},
            {"name": "Quotation Blocks", "input": False},
            {"name": "Checklist Action Items (\\square)", "input": False},
            {"name": "Glossary of Terms", "input": False},
            {"name": "Timeline / Gantt Chart (TikZ)", "input": False},
            {"name": "Pros & Cons Table", "input": False},
            {"name": "Decision Matrix", "input": False},
            {"name": "Code Snippet Formatting (listings)", "input": False},
            {"name": "Colored Section Headings", "input": False},
            {"name": "Appendix", "input": False},
            {"name": "Page Borders (pgfpages)", "input": False},
            {"name": "Sign-off Signature Block", "input": False},
            {"name": "Visual Data Plots (pgfplots)", "input": False}
        ]
        
        self.checkbox_vars = {}
        self.entry_widgets = {} # Stores the specific text boxes

        self._build_ui()

        threading.Thread(target=self._initial_gpu_load, daemon=True).start()
        threading.Thread(target=self.init_ollama_list, daemon=True).start()

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=360, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        ctk.CTkLabel(self.sidebar, text="MEETING PRO", font=("Helvetica", 24, "bold")).pack(pady=15)

        self.tabs = ctk.CTkTabview(self.sidebar, width=340)
        self.tabs.pack(expand=True, fill="both", padx=10, pady=5)
        
        self.tab_main = self.tabs.add("Workflow")
        self.tab_adv = self.tabs.add("Advanced")

        # ==========================================
        # TAB 1: WORKFLOW
        # ==========================================
        ctk.CTkLabel(self.tab_main, text="LLM Model Selection", text_color="gray").pack(pady=(5,0))
        self.model_dropdown = ctk.CTkComboBox(self.tab_main, values=["Scanning..."], state="disabled", width=220)
        self.model_dropdown.pack(pady=5)
        
        self.btn_init_llm = ctk.CTkButton(self.tab_main, text="Initialize LLM", state="disabled", command=self.lazy_init_llm)
        self.btn_init_llm.pack(pady=5)

        ctk.CTkLabel(self.tab_main, text="Supporting Materials", text_color="gray").pack(pady=(15,0))
        self.btn_add_pdf = ctk.CTkButton(self.tab_main, text="Add PDF to Notebook", command=self.lazy_add_pdf)
        self.btn_add_pdf.pack()

        ctk.CTkLabel(self.tab_main, text="Audio Input", text_color="gray").pack(pady=(15,0))
        self.btn_select_audio = ctk.CTkButton(self.tab_main, text="Select Audio File", fg_color="#E67E22", command=self.select_audio)
        self.btn_select_audio.pack(pady=5)
        self.audio_info = ctk.CTkLabel(self.tab_main, text="No file selected", font=("Arial", 11), text_color="#BDC3C7")
        self.audio_info.pack()

        ctk.CTkLabel(self.tab_main, text="Translation Strategy", text_color="gray").pack(pady=(15,0))
        self.strategy_var = ctk.StringVar(value="translate")
        ctk.CTkRadioButton(self.tab_main, text="Translate (English)", variable=self.strategy_var, value="translate").pack(pady=2)
        ctk.CTkRadioButton(self.tab_main, text="Romanized (Hindi)", variable=self.strategy_var, value="romanized").pack(pady=2)

        # ==========================================
        # TAB 2: ADVANCED
        # ==========================================
        self.adv_scroll = ctk.CTkScrollableFrame(self.tab_adv)
        self.adv_scroll.pack(fill="both", expand=True)

        ctk.CTkLabel(self.adv_scroll, text="Approx. Pages:", font=("Arial", 12, "bold")).pack(pady=(5,0), anchor="w")
        self.entry_pages = ctk.CTkEntry(self.adv_scroll, placeholder_text="Any")
        self.entry_pages.pack(fill="x", pady=5)

        ctk.CTkLabel(self.adv_scroll, text="Keep Alive Time:", font=("Arial", 12, "bold")).pack(pady=(10,0), anchor="w")
        self.dropdown_keep_alive = ctk.CTkComboBox(self.adv_scroll, values=list(self.keep_alive_map.keys()))
        self.dropdown_keep_alive.set("10 min")
        self.dropdown_keep_alive.pack(fill="x", pady=5)

        self.lbl_temp = ctk.CTkLabel(self.adv_scroll, text="Formalness (Temp: 0.2)", font=("Arial", 12, "bold"))
        self.lbl_temp.pack(pady=(10,0), anchor="w")
        self.slider_temp = ctk.CTkSlider(self.adv_scroll, from_=0.0, to=1.0, command=self.update_temp_lbl)
        self.slider_temp.set(0.2)
        self.slider_temp.pack(fill="x", pady=5)

        self.lbl_ctx = ctk.CTkLabel(self.adv_scroll, text="Context Window: 4k", font=("Arial", 12, "bold"))
        self.lbl_ctx.pack(pady=(10,0), anchor="w")
        self.ctx_slider = ctk.CTkSlider(self.adv_scroll, from_=0, to=5, number_of_steps=5, command=self.update_ctx_lbl)
        self.ctx_slider.set(0)
        self.ctx_slider.pack(fill="x", pady=5)

        self.lbl_graph = ctk.CTkLabel(self.adv_scroll, text="Graphics / Tables: Balanced", font=("Arial", 12, "bold"))
        self.lbl_graph.pack(pady=(10,0), anchor="w")
        self.slider_graphics = ctk.CTkSlider(self.adv_scroll, from_=0.0, to=1.0, command=self.update_graph_lbl)
        self.slider_graphics.set(0.5)
        self.slider_graphics.pack(fill="x", pady=5)

        # OPTIONAL STYLIZED ELEMENTS
        ctk.CTkLabel(self.adv_scroll, text="Other Elements (Styling):", font=("Arial", 12, "bold"), text_color="#3498DB").pack(pady=(20,5), anchor="w")
        
        for item in self.elements_config:
            name = item["name"]
            var = ctk.BooleanVar(value=False)
            self.checkbox_vars[name] = var
            
            chk = ctk.CTkCheckBox(self.adv_scroll, text=name, variable=var, font=("Arial", 11))
            chk.pack(anchor="w", pady=3, padx=10)
            
            # If element needs text input (like Watermark)
            if item["input"]:
                entry = ctk.CTkEntry(self.adv_scroll, placeholder_text=item["placeholder"], height=24)
                entry.pack(fill="x", padx=30, pady=(0, 5))
                self.entry_widgets[name] = entry

        # ==========================================
        # GLOBAL GENERATE BUTTON
        # ==========================================
        self.btn_run = ctk.CTkButton(
            self.sidebar, text="WAITING FOR ENGINE...", height=55, 
            font=("Arial", 18, "bold"), command=self.run_main_workflow, state="disabled", corner_radius=8
        )
        self.btn_run.pack(pady=20, padx=20, fill="x")

        self.log_area = ctk.CTkTextbox(self, font=("Consolas", 12), border_width=1)
        self.log_area.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")

    # --- UI UPDATERS ---
    def update_temp_lbl(self, val): self.lbl_temp.configure(text=f"Formalness (Temp: {val:.2f})")
    def update_ctx_lbl(self, val): self.lbl_ctx.configure(text=f"Context Window: {self.ctx_labels[int(val)]}")
    def update_graph_lbl(self, val):
        mode = "None" if val < 0.2 else "Maximum" if val > 0.8 else "Balanced"
        self.lbl_graph.configure(text=f"Graphics / Tables: {mode}")

    def log(self, text):
        self.log_area.insert("end", f"{text}\n")
        self.log_area.see("end")

    # --- STARTUP LOGIC ---
    def _clear_vram(self):
        try:
            result = subprocess.run(["ollama", "ps"], capture_output=True, text=True)
            lines = result.stdout.strip().split('\n')
            running_models = [line.split()[0] for line in lines[1:] if line.strip()]
            for model in running_models:
                subprocess.run(["ollama", "stop", model], capture_output=True)
        except: pass

    def _initial_gpu_load(self):
        self.log("[!] SYSTEM BOOT: Clearing VRAM & Securing Whisper...")
        self._clear_vram()
        success = self.transcriber.load_onto_gpu()
        
        self.model_dropdown.configure(state="normal")
        self.btn_init_llm.configure(state="normal", fg_color="#2E86C1")
        
        if success:
            self.btn_run.configure(state="normal", text="GENERATE", fg_color="#27AE60")
            self.log("[+] VRAM SECURED: Ready for operation.")
        else:
            self.btn_run.configure(state="normal", text="GENERATE (CPU)", fg_color="#E67E22")

    def init_ollama_list(self):
        if check_setup():
            try:
                result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
                lines = result.stdout.strip().split('\n')
                models = [line.split()[0] for line in lines[1:] if line.strip()]
                self.model_dropdown.configure(values=models)
                if models: self.model_dropdown.set(models[0])
            except: pass

    def lazy_init_llm(self):
        model_name = self.model_dropdown.get()
        if model_name in ["Scanning...", "No models found"]: return

        ctx_val = self.ctx_values[int(self.ctx_slider.get())]
        keep_alive_val = self.keep_alive_map[self.dropdown_keep_alive.get()]
        
        self.log(f"[*] Pre-loading {model_name} (Ctx: {ctx_val}, Keep-Alive: {keep_alive_val})...")
        
        def run_init():
            try:
                ollama.generate(model=model_name, prompt="", options={"num_ctx": ctx_val}, keep_alive=keep_alive_val)
                self.loaded_model = model_name
                self.loaded_ctx = ctx_val
                self.log(f"[+] {model_name} initialized successfully.")
            except Exception as e:
                self.log(f"[-] Init failed: {e}")

        threading.Thread(target=run_init, daemon=True).start()

    def lazy_add_pdf(self):
        path = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if path: threading.Thread(target=lambda: self.rag.ingest_pdf(path, self.log), daemon=True).start()

    def select_audio(self):
        self.audio_path = filedialog.askopenfilename(filetypes=[("Audio", "*.mp3 *.wav *.m4a")])
        if self.audio_path: self.audio_info.configure(text=os.path.basename(self.audio_path), text_color="#2ECC71")

    # --- CORE PIPELINE ---
    def run_main_workflow(self):
        if not self.audio_path:
            messagebox.showwarning("File Missing", "Please select an audio file first!")
            return
        self.btn_run.configure(state="disabled", text="PROCESSING...", fg_color="#7F8C8D")
        threading.Thread(target=self._execute_pipeline, daemon=True).start()

    def _execute_pipeline(self):
        try:
            self.log("\n" + "="*40)
            
            # --- DYNAMIC MODEL RELOADER ---
            target_model = self.model_dropdown.get()
            target_ctx = self.ctx_values[int(self.ctx_slider.get())]
            target_keep = self.keep_alive_map[self.dropdown_keep_alive.get()]

            if self.loaded_model != target_model or self.loaded_ctx != target_ctx:
                self.log("[*] Model or Context settings changed. Reloading LLM into VRAM...")
                if self.loaded_model:
                    subprocess.run(["ollama", "stop", self.loaded_model], capture_output=True)
                
                # Warm up new settings
                ollama.generate(model=target_model, prompt="", options={"num_ctx": target_ctx}, keep_alive=target_keep)
                self.loaded_model = target_model
                self.loaded_ctx = target_ctx
                self.log("[+] Reload successful. Whisper remains unaffected.")

            # --- SYNC COMPILER SETTINGS ---
            self.compiler.model_name = target_model
            self.compiler.context_length = target_ctx
            self.compiler.keep_alive = target_keep
            self.compiler.temperature = self.slider_temp.get()
            self.compiler.pages = self.entry_pages.get()
            self.compiler.graphics_level = self.slider_graphics.get()
            self.compiler.active_elements = [name for name, var in self.checkbox_vars.items() if var.get()]
            
            # Fetch Custom Text inputs
            if "Header & Footer (fancyhdr)" in self.entry_widgets:
                self.compiler.custom_header = self.entry_widgets["Header & Footer (fancyhdr)"].get()
            if "Draft Watermark" in self.entry_widgets:
                self.compiler.custom_watermark = self.entry_widgets["Draft Watermark"].get()

            # 1. Transcribe
            transcript = self.transcriber.transcribe(self.audio_path, self.strategy_var.get())
            self.log("[+] Transcription finished.")

            # 2. RAG & 3. Compile
            context = self.rag.query_context(transcript)
            latex = self.compiler.generate_summary(transcript, context)
            
            clean_filename = os.path.basename(self.audio_path).rsplit('.', 1)[0]
            generated_pdf_path = self.compiler.compile_to_pdf(latex, clean_filename)
            
            # --- NATIVE SAVE-AS DIALOG ---
            if generated_pdf_path and os.path.exists(generated_pdf_path):
                self.log(f"[+] Summary created locally. Prompting Save location...")
                
                # Open Windows File Dialog
                save_path = filedialog.asksaveasfilename(
                    title="Save Meeting Summary As",
                    defaultextension=".pdf",
                    initialfile=f"{clean_filename}.pdf",
                    filetypes=[("PDF Documents", "*.pdf"), ("All Files", "*.*")]
                )
                
                if save_path: # If user didn't hit cancel
                    shutil.copy(generated_pdf_path, save_path)
                    self.log(f"[!!!] SUCCESS: Saved permanently to {save_path}")
                    messagebox.showinfo("Done", "PDF successfully saved!")
                else:
                    self.log("[*] Save cancelled by user. File remains in exports folder.")

        except Exception as e:
            self.log(f"\n[-] Critical Pipeline Error: {e}")
        finally:
            self.btn_run.configure(state="normal", text="GENERATE", fg_color="#27AE60")

if __name__ == "__main__":
    app = MeetingApp()
    app.mainloop()  