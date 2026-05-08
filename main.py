import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import os
import subprocess
import shutil
import re
from datetime import datetime

# Backend Imports
from course_manager import CourseManager
from rag_engine import RAGEngine
from chat_engine import ChatEngine
from llm_compiler import LLMCompiler
from audio_processor import MeetingTranscriber

class KurtApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Kurt")
        self.geometry("1450x950")
        
        self.user_name = "User"
        self.bubble_radius = 15
        self.font_size_chat = 14
        
        self.C_BG_MAIN = ("#F9FAFB", "#0A0A0A")       
        self.C_BG_SIDEBAR = ("#FFFFFF", "#121212")    
        self.C_BG_RAIL = ("#E5E7EB", "#000000")       
        self.C_ACCENT = "#2563EB"                     
        self.C_ACCENT_HOVER = "#1D4ED8"
        self.C_TEXT = ("#111827", "#F9FAFB")
        self.C_TEXT_MUTED = ("#6B7280", "#9CA3AF")
        self.C_CARD = ("#FFFFFF", "#1E1E1E")          
        self.C_USER_BUBBLE = ("#DBEAFE", "#1E3A8A")   
        self.C_AI_BUBBLE = ("#F3F4F6", "#1E1E1E")
        self.C_CODE_BG = ("#E5E7EB", "#000000")
        self.C_DANGER = ("#DC2626", "#EF4444")
        self.C_SUCCESS = ("#059669", "#10B981")
        
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.dynamic_accent_buttons = []

        self.cm = CourseManager()
        self.rag = RAGEngine(self.cm)
        self.chat_engine = ChatEngine(self.log)
        self.compiler = LLMCompiler(self.log)
        self.transcriber = MeetingTranscriber(self.log)
        
        self.active_course = None
        self.navigation_history = []
        self.shared_audio_path = None 
        self.strategy_var = ctk.StringVar(value="translate")
        self.enable_web_search_var = ctk.BooleanVar(value=False) 
        
        # COMPLETE GEMINI SUITE
        self.gemini_models_list = [
            "gemini-3.1-pro-preview",
            "gemini-3.0-flash-preview",
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-2.0-pro-exp",
            "gemini-2.0-flash",
            "gemini-1.5-pro",
            "gemini-1.5-flash"
        ]
        
        self.ctx_values = [4096, 8192, 16384, 32768, 65536, 131072]
        self.keep_alive_map = {"5 min": "5m", "10 min": "10m", "20 min": "20m", "1 hr": "1h", "Unlimited": "-1"}
        self.elements_config = [
            {"name": "Table of Contents", "input": False}, {"name": "Colored Callout Boxes", "input": False},
            {"name": "Header & Footer", "input": True, "placeholder": "Project Alpha"},
            {"name": "Draft Watermark", "input": True, "placeholder": "CONFIDENTIAL"},
            {"name": "Two-Column Layout", "input": False}, {"name": "Explicit Definitions Block", "input": False},
            {"name": "Highlighted Key Points", "input": False}, {"name": "Timeline / Gantt Chart", "input": False},
            {"name": "Checklist Action Items", "input": False}, {"name": "Glossary of Terms", "input": False},
            {"name": "Decision Matrix", "input": False}, {"name": "Code Snippet Formatting", "input": False}
        ]

        self._build_ui()
        self.refresh_course_list()
        self.refresh_home_dashboard()
        
        threading.Thread(target=self._initial_gpu_load, daemon=True).start()
        self.scan_ollama() 

    def _create_accent_btn(self, parent, text, command=None, width=120, height=40, font=None):
        btn = ctk.CTkButton(parent, text=text, command=command, width=width, height=height, 
                            fg_color=self.C_ACCENT, hover_color=self.C_ACCENT_HOVER, font=font)
        self.dynamic_accent_buttons.append(btn)
        return btn

    def _build_ui(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0) 
        self.grid_columnconfigure(1, weight=0) 
        self.grid_columnconfigure(2, weight=1) 

        # --- PANE 1: NAV RAIL ---
        self.nav_rail = ctk.CTkFrame(self, width=75, corner_radius=0, fg_color=self.C_BG_RAIL)
        self.nav_rail.grid(row=0, column=0, sticky="nsew")
        ctk.CTkButton(self.nav_rail, text="🏠\nHome", width=60, height=60, fg_color="transparent", text_color=self.C_TEXT, command=lambda: self.show_frame("home")).pack(pady=10)
        ctk.CTkButton(self.nav_rail, text="⚡\nGuest", width=60, height=60, fg_color="transparent", text_color=self.C_TEXT, command=lambda: self.show_frame("guest_summary")).pack(pady=10)
        ctk.CTkButton(self.nav_rail, text="⚙️\nSettings", width=60, height=60, fg_color="transparent", text_color=self.C_TEXT, command=lambda: self.show_frame("settings")).pack(side="bottom", pady=20)

        # --- PANE 2: SIDEBAR ---
        self.sidebar = ctk.CTkFrame(self, width=280, corner_radius=0, fg_color=self.C_BG_SIDEBAR)
        self.sidebar.grid(row=0, column=1, sticky="nsew")
        self.sidebar.grid_propagate(False)

        ctk.CTkLabel(self.sidebar, text="YOUR COURSES", font=("Arial", 14, "bold"), text_color=self.C_TEXT_MUTED).pack(pady=(20, 10), padx=15, anchor="w")
        btn_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10)
        
        self.btn_new_course = self._create_accent_btn(btn_frame, "+ New", self.add_course_dialog, width=110, height=35)
        self.btn_new_course.pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="📥 Import", width=110, height=35, fg_color=self.C_CARD, border_width=1, text_color=self.C_TEXT, command=self.import_course_dialog).pack(side="right", padx=5)

        self.course_list_frame = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent")
        self.course_list_frame.pack(fill="both", expand=True, padx=5, pady=10)
        self.lbl_tps = ctk.CTkLabel(self.sidebar, text="Speed: -- t/s", font=("Consolas", 12, "bold"), text_color="#F59E0B")
        self.lbl_tps.pack(side="bottom", pady=15)

        # --- PANE 3: MAIN WORKSPACE ---
        self.main_workspace = ctk.CTkFrame(self, corner_radius=0, fg_color=self.C_BG_MAIN)
        self.main_workspace.grid(row=0, column=2, sticky="nsew")
        self.main_workspace.grid_rowconfigure(1, weight=1)
        self.main_workspace.grid_columnconfigure(0, weight=1)

        self.header = ctk.CTkFrame(self.main_workspace, height=70, corner_radius=0, fg_color=self.C_BG_SIDEBAR)
        self.header.grid(row=0, column=0, sticky="ew")
        
        self.btn_back = ctk.CTkButton(self.header, text="< Back", width=70, fg_color="transparent", border_width=1, text_color=self.C_TEXT, command=self.go_back)
        self.btn_back.pack(side="left", padx=20, pady=15)
        
        self.lbl_workspace_title = ctk.CTkLabel(self.header, text="Welcome to Kurt", font=("Arial", 22, "bold"), text_color=self.C_TEXT)
        self.lbl_workspace_title.pack(side="left", padx=10, pady=15)
        
        self.btn_delete_course = ctk.CTkButton(self.header, text="🗑️ Delete", width=80, height=35, fg_color=self.C_DANGER, hover_color="#B91C1C", font=("Arial", 12, "bold"), command=self.delete_active_course)
        
        self.nav_model_frame = ctk.CTkFrame(self.header, fg_color="transparent")
        self.nav_model_frame.pack(side="right", padx=20, pady=15)
        ctk.CTkLabel(self.nav_model_frame, text="Active AI:", text_color=self.C_TEXT).pack(side="left", padx=5)
        self.combo_global_model = ctk.CTkComboBox(self.nav_model_frame, values=["Scanning..."], width=200, command=self.on_nav_model_change)
        self.combo_global_model.pack(side="left")

        self.log_area = ctk.CTkTextbox(self.main_workspace, height=120, font=("Consolas", 11), border_width=1, fg_color=self.C_CARD, text_color=self.C_TEXT)
        self.log_area.grid(row=2, column=0, padx=20, pady=15, sticky="ew")

        self.screen_container = ctk.CTkFrame(self.main_workspace, fg_color="transparent")
        self.screen_container.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)

        self.frames = {}
        self.build_settings_screen()
        self.build_guest_screen()
        self.build_course_screen()
        self.build_home_screen()
        
        self.show_frame("home")

    def build_home_screen(self):
        frame = ctk.CTkScrollableFrame(self.screen_container, fg_color="transparent")
        self.lbl_greeting = ctk.CTkLabel(frame, text=f"Good Evening, {self.user_name}.", font=("Arial", 32, "bold"), text_color=self.C_TEXT)
        self.lbl_greeting.pack(pady=(40, 5), anchor="w", padx=20)
        ctk.CTkLabel(frame, text="What would you like to learn today with Kurt?", font=("Arial", 16), text_color=self.C_TEXT_MUTED).pack(anchor="w", padx=20, pady=(0, 30))
        
        stats_frame = ctk.CTkFrame(frame, fg_color="transparent")
        stats_frame.pack(fill="x", padx=20, pady=10)
        self.lbl_stat_courses = self._create_stat_card(stats_frame, "Total Courses", "0")
        self.lbl_stat_files = self._create_stat_card(stats_frame, "Ingested Files", "0")
        self.lbl_stat_engine = self._create_stat_card(stats_frame, "Active Engine", self.compiler.engine.upper())
        
        ctk.CTkLabel(frame, text="Recent Courses", font=("Arial", 20, "bold"), text_color=self.C_TEXT).pack(pady=(40, 10), anchor="w", padx=20)
        self.tile_grid = ctk.CTkFrame(frame, fg_color="transparent")
        self.tile_grid.pack(fill="both", expand=True, padx=20)
        self.frames["home"] = frame

    def _create_stat_card(self, parent, title, value):
        card = ctk.CTkFrame(parent, fg_color=self.C_CARD, corner_radius=10)
        card.pack(side="left", fill="x", expand=True, padx=10)
        ctk.CTkLabel(card, text=title, font=("Arial", 12), text_color=self.C_TEXT_MUTED).pack(pady=(15, 0))
        val_lbl = ctk.CTkLabel(card, text=value, font=("Arial", 24, "bold"), text_color=self.C_TEXT)
        val_lbl.pack(pady=(5, 15))
        return val_lbl

    def refresh_home_dashboard(self):
        self.lbl_greeting.configure(text=f"Welcome Back, {self.user_name}.")
        courses = self.cm.list_courses()
        self.lbl_stat_courses.configure(text=str(len(courses)))
        self.lbl_stat_engine.configure(text=self.compiler.engine.upper())
        total_files = sum(len(self.cm.list_course_files(c)) for c in courses)
        self.lbl_stat_files.configure(text=str(total_files))
        
        for widget in self.tile_grid.winfo_children(): widget.destroy()
        col, row = 0, 0
        for course in courses:
            tile = ctk.CTkButton(self.tile_grid, text=f"📘\n\n{course}", font=("Arial", 16, "bold"), 
                                 fg_color=self.C_CARD, text_color=self.C_TEXT, hover_color=self.C_BG_RAIL,
                                 width=200, height=120, command=lambda c=course: self.load_course(c))
            tile.grid(row=row, column=col, padx=10, pady=10)
            col += 1
            if col > 3: 
                col = 0
                row += 1

    def build_settings_screen(self):
        frame = ctk.CTkFrame(self.screen_container, fg_color="transparent")
        tabs = ctk.CTkTabview(frame, fg_color=self.C_CARD, segmented_button_selected_color=self.C_ACCENT)
        tabs.pack(fill="both", expand=True)
        tab_engine = tabs.add("🧠 Engine & API")
        tab_ui = tabs.add("🎨 Customization")
        tab_data = tabs.add("🔒 Privacy")

        def add_setting_stack(parent, label_text, widget, description=""):
            container = ctk.CTkFrame(parent, fg_color="transparent")
            container.pack(fill="x", padx=40, pady=15)
            ctk.CTkLabel(container, text=label_text, font=("Arial", 15, "bold"), text_color=self.C_TEXT).pack(anchor="w")
            if description: ctk.CTkLabel(container, text=description, font=("Arial", 12), text_color=self.C_TEXT_MUTED).pack(anchor="w", pady=(0, 5))
            widget.pack(fill="x", expand=True, pady=(5,0))

        # --- ENGINE TAB ---
        ctk.CTkLabel(tab_engine, text="Active Intelligence Engine", font=("Arial", 22, "bold"), text_color=self.C_TEXT).pack(pady=(20,10), anchor="w", padx=40)
        engine_box = ctk.CTkFrame(tab_engine, fg_color="transparent")
        engine_box.pack(fill="x", padx=40, pady=5)
        self.engine_var = ctk.StringVar(value="ollama")
        ctk.CTkRadioButton(engine_box, text="Local Ollama (100% Private, Free)", variable=self.engine_var, value="ollama", font=("Arial", 14), text_color=self.C_TEXT, command=self.on_engine_change).pack(anchor="w", pady=10)
        ctk.CTkRadioButton(engine_box, text="Google Gemini API (Cloud, High Speed Vision)", variable=self.engine_var, value="gemini", font=("Arial", 14), text_color=self.C_TEXT, command=self.on_engine_change).pack(anchor="w", pady=10)
        
        self.gemini_frame = ctk.CTkFrame(tab_engine, fg_color="transparent")
        self.entry_api = ctk.CTkEntry(self.gemini_frame, show="*", height=40, placeholder_text="AIzaSy...")
        add_setting_stack(self.gemini_frame, "Gemini API Key:", self.entry_api, "Required for processing handwritten notes and connecting to Google Cloud.")
        
        self.chk_web_search = ctk.CTkCheckBox(self.gemini_frame, text="Enable Google Search Grounding (Gemini 1.5/2.0/2.5 Flash Models Only - 500 RPD Free)", variable=self.enable_web_search_var, font=("Arial", 14), text_color=self.C_TEXT)
        add_setting_stack(self.gemini_frame, "Live Web Search:", self.chk_web_search, "Allows Kurt to browse the live internet for answers. Disabled automatically for Pro/Gemini-3 models.")

        # --- UI TAB ---
        ui_scroll = ctk.CTkScrollableFrame(tab_ui, fg_color="transparent")
        ui_scroll.pack(fill="both", expand=True)
        ctk.CTkLabel(ui_scroll, text="Personalize Kurt", font=("Arial", 22, "bold"), text_color=self.C_TEXT).pack(pady=(20,10), anchor="w", padx=40)

        self.entry_name = ctk.CTkEntry(ui_scroll, height=40)
        self.entry_name.insert(0, self.user_name)
        add_setting_stack(ui_scroll, "Display Name", self.entry_name, "How Kurt addresses you.")

        self.theme_var = ctk.StringVar(value="Dark")
        seg_theme = ctk.CTkSegmentedButton(ui_scroll, values=["Dark", "Light", "System"], variable=self.theme_var, height=40, command=self.change_theme)
        add_setting_stack(ui_scroll, "Color Theme", seg_theme)

        self.accent_var = ctk.StringVar(value="Blue (Default)")
        opt_accent = ctk.CTkOptionMenu(ui_scroll, values=["Blue (Default)", "Emerald Green", "Royal Purple", "Crimson Red"], variable=self.accent_var, height=40)
        add_setting_stack(ui_scroll, "Accent Color", opt_accent, "Changes primary button colors.")

        self.bubble_var = ctk.StringVar(value="Rounded (Modern)")
        opt_bubble = ctk.CTkOptionMenu(ui_scroll, values=["Rounded (Modern)", "Square (Terminal)"], variable=self.bubble_var, height=40)
        add_setting_stack(ui_scroll, "Chat Bubble Style", opt_bubble)

        self.font_var = ctk.StringVar(value="Medium (Default)")
        opt_font = ctk.CTkOptionMenu(ui_scroll, values=["Small", "Medium (Default)", "Large"], variable=self.font_var, height=40)
        add_setting_stack(ui_scroll, "Chat Font Size", opt_font)

        self.scale_var = ctk.StringVar(value="100%")
        opt_scale = ctk.CTkOptionMenu(ui_scroll, values=["80%", "90%", "100%", "110%", "120%"], variable=self.scale_var, height=40, command=self.change_scaling)
        add_setting_stack(ui_scroll, "Interface Scale", opt_scale)

        # --- PRIVACY TAB ---
        ctk.CTkLabel(tab_data, text="Data Management", font=("Arial", 22, "bold"), text_color=self.C_TEXT).pack(pady=(20,10), anchor="w", padx=40)
        self.chk_telemetry = ctk.BooleanVar(value=False)
        chk = ctk.CTkCheckBox(tab_data, text="Share Anonymous Diagnostics (Disabled for Privacy)", variable=self.chk_telemetry, state="disabled", font=("Arial", 14), text_color=self.C_TEXT)
        add_setting_stack(tab_data, "Telemetry", chk)

        btn_save = self._create_accent_btn(frame, "Save All Settings", self.save_settings, height=50, font=("Arial", 16, "bold"))
        btn_save.pack(pady=20)
        self.frames["settings"] = frame

    def build_guest_screen(self):
        frame = ctk.CTkFrame(self.screen_container, fg_color="transparent")
        control_frame = ctk.CTkFrame(frame, fg_color=self.C_CARD)
        control_frame.pack(fill="x", pady=10)
        
        ctk.CTkButton(control_frame, text="Select Audio", fg_color=self.C_BG_RAIL, text_color=self.C_TEXT, hover_color=self.C_BG_SIDEBAR, command=self.select_audio).pack(side="left", padx=15, pady=15)
        self.lbl_guest_audio = ctk.CTkLabel(control_frame, text="No file selected", text_color=self.C_TEXT_MUTED)
        self.lbl_guest_audio.pack(side="left", padx=10)
        
        ctk.CTkRadioButton(control_frame, text="Translate", variable=self.strategy_var, value="translate", text_color=self.C_TEXT).pack(side="left", padx=10)
        ctk.CTkRadioButton(control_frame, text="Romanized", variable=self.strategy_var, value="romanized", text_color=self.C_TEXT).pack(side="left", padx=10)
        
        btn_gen = self._create_accent_btn(control_frame, "GENERATE SUMMARY", lambda: self.run_pipeline("meeting", is_guest=True), font=("Arial", 14, "bold"))
        btn_gen.pack(side="right", padx=15)

        self.guest_adv_vars = self.build_advanced_settings_ui(frame)
        self.frames["guest_summary"] = frame

    def build_course_screen(self):
        frame = ctk.CTkFrame(self.screen_container, fg_color="transparent")
        self.course_tabs = ctk.CTkTabview(frame, fg_color=self.C_BG_SIDEBAR, segmented_button_selected_color=self.C_ACCENT)
        self.course_tabs.pack(fill="both", expand=True)
        
        tab_mat = self.course_tabs.add("📚 Materials")
        tab_sum = self.course_tabs.add("🎙️ Summarize")
        tab_chat = self.course_tabs.add("💬 Tutor Chat")
        tab_data = self.course_tabs.add("📁 Course Data")

        # --- MATERIALS TAB ---
        ctk.CTkLabel(tab_mat, text="Add Knowledge to Course Database", font=("Arial", 18, "bold"), text_color=self.C_TEXT).pack(pady=(30,10))
        ctk.CTkButton(tab_mat, text="📄 Upload PDF / Text Document", width=350, height=50, font=("Arial", 14), fg_color=self.C_CARD, border_width=1, text_color=self.C_TEXT, hover_color=self.C_BG_RAIL, command=self.upload_doc).pack(pady=10)
        img_frame = ctk.CTkFrame(tab_mat, fg_color="transparent")
        img_frame.pack(pady=20)
        ctk.CTkButton(img_frame, text="📝 Parse Handwriting, Graphs & Photos", width=350, height=50, font=("Arial", 14), fg_color="#D97706", hover_color="#B45309", command=self.upload_image).pack()
        ctk.CTkLabel(img_frame, text="*Requires Gemini API Key.", font=("Arial", 11), text_color="#D97706").pack(pady=5)

        # --- SUMMARIZE TAB ---
        ctrl = ctk.CTkFrame(tab_sum, fg_color=self.C_CARD)
        ctrl.pack(fill="x", pady=10)
        ctk.CTkButton(ctrl, text="Select Audio/Video", fg_color=self.C_BG_RAIL, text_color=self.C_TEXT, hover_color=self.C_BG_SIDEBAR, command=self.select_audio).pack(side="left", padx=15, pady=15)
        self.lbl_course_audio = ctk.CTkLabel(ctrl, text="No file selected", text_color=self.C_TEXT_MUTED)
        self.lbl_course_audio.pack(side="left", padx=10)
        ctk.CTkRadioButton(ctrl, text="Translate", variable=self.strategy_var, value="translate", text_color=self.C_TEXT).pack(side="left", padx=5)
        ctk.CTkRadioButton(ctrl, text="Romanized", variable=self.strategy_var, value="romanized", text_color=self.C_TEXT).pack(side="left", padx=5)
        
        ctk.CTkButton(ctrl, text="EXPLAIN CLASS", fg_color="#7C3AED", hover_color="#6D28D9", font=("Arial", 12, "bold"), command=lambda: self.run_pipeline("class", is_guest=False)).pack(side="right", padx=15)
        btn_sum = self._create_accent_btn(ctrl, "SUMMARY", lambda: self.run_pipeline("meeting", is_guest=False), font=("Arial", 12, "bold"))
        btn_sum.pack(side="right", padx=5)
        self.course_adv_vars = self.build_advanced_settings_ui(tab_sum)

        # --- RICH CHAT TAB ---
        self.chat_scroll = ctk.CTkScrollableFrame(tab_chat, fg_color="transparent")
        self.chat_scroll.pack(fill="both", expand=True, pady=(0, 10))
        input_frame = ctk.CTkFrame(tab_chat, fg_color="transparent", height=60)
        input_frame.pack(fill="x", side="bottom")
        self.chat_input = ctk.CTkEntry(input_frame, placeholder_text="Ask Kurt a question...", height=45, font=("Arial", 14))
        self.chat_input.pack(fill="x", side="left", expand=True, padx=(0, 10))
        self.chat_input.bind("<Return>", lambda e: self.send_chat())
        btn_send = self._create_accent_btn(input_frame, "Send", self.send_chat, width=90, height=45, font=("Arial", 14, "bold"))
        btn_send.pack(side="right")

        # --- COURSE DATA TAB ---
        ctk.CTkLabel(tab_data, text="Uploaded Knowledge Base Files", font=("Arial", 16, "bold"), text_color=self.C_TEXT).pack(pady=(10,5), anchor="w", padx=20)
        self.file_list_box = ctk.CTkScrollableFrame(tab_data, fg_color=self.C_CARD, height=300)
        self.file_list_box.pack(fill="x", padx=20, pady=5)
        action_box = ctk.CTkFrame(tab_data, fg_color="transparent")
        action_box.pack(fill="x", padx=20, pady=30)
        ctk.CTkButton(action_box, text="⬇️ Download Course as .ZIP", fg_color=self.C_SUCCESS, hover_color="#047857", height=45, font=("Arial", 14, "bold"), command=self.export_course).pack(side="left")

        self.frames["course_view"] = frame

    def build_advanced_settings_ui(self, parent_frame):
        scroll = ctk.CTkScrollableFrame(parent_frame, fg_color=self.C_CARD)
        scroll.pack(fill="both", expand=True, padx=10, pady=10)
        vars_dict = {"checkboxes": {}, "entries": {}}

        ctk.CTkLabel(scroll, text="Approx. Pages:", font=("Arial", 12, "bold"), text_color=self.C_TEXT).pack(anchor="w", pady=(10,0), padx=10)
        vars_dict["pages"] = ctk.CTkEntry(scroll, placeholder_text="Any")
        vars_dict["pages"].pack(fill="x", pady=(5,15), padx=10)
        vars_dict["lbl_temp"] = ctk.CTkLabel(scroll, text="Formalness (Temp: 0.2)", font=("Arial", 12, "bold"), text_color=self.C_TEXT)
        vars_dict["lbl_temp"].pack(anchor="w", padx=10)
        vars_dict["temp"] = ctk.CTkSlider(scroll, from_=0.0, to=1.0, command=lambda v: vars_dict["lbl_temp"].configure(text=f"Formalness (Temp: {v:.2f})"))
        vars_dict["temp"].set(0.2)
        vars_dict["temp"].pack(fill="x", pady=(5,15), padx=10)

        vars_dict["lbl_ctx"] = ctk.CTkLabel(scroll, text="Context Window (Ollama Only): 4k", font=("Arial", 12, "bold"), text_color=self.C_TEXT)
        vars_dict["lbl_ctx"].pack(anchor="w", padx=10)
        vars_dict["ctx"] = ctk.CTkSlider(scroll, from_=0, to=5, number_of_steps=5, command=lambda v: vars_dict["lbl_ctx"].configure(text=f"Context Window: {self.ctx_labels[int(v)]}"))
        vars_dict["ctx"].set(0)
        vars_dict["ctx"].pack(fill="x", pady=(5,15), padx=10)
        
        vars_dict["lbl_keep"] = ctk.CTkLabel(scroll, text="Keep Alive (Ollama Only):", font=("Arial", 12, "bold"), text_color=self.C_TEXT)
        vars_dict["lbl_keep"].pack(anchor="w", padx=10)
        vars_dict["keep"] = ctk.CTkComboBox(scroll, values=list(self.keep_alive_map.keys()))
        vars_dict["keep"].set("10 min")
        vars_dict["keep"].pack(fill="x", pady=(5,20), padx=10)

        ctk.CTkLabel(scroll, text="Styling Elements:", font=("Arial", 14, "bold"), text_color="#3B82F6").pack(pady=(10,10), anchor="w", padx=10)
        for item in self.elements_config:
            name = item["name"]
            var = ctk.BooleanVar(value=False)
            vars_dict["checkboxes"][name] = var
            ctk.CTkCheckBox(scroll, text=name, variable=var, font=("Arial", 12), text_color=self.C_TEXT).pack(anchor="w", pady=4, padx=15)
            if item["input"]:
                entry = ctk.CTkEntry(scroll, placeholder_text=item["placeholder"], height=28)
                entry.pack(fill="x", padx=35, pady=(0, 10))
                vars_dict["entries"][name] = entry
        return vars_dict

    # ==========================================
    # SETTINGS & ENGINE LOGIC
    # ==========================================
    def change_theme(self, choice):
        if choice == "System": ctk.set_appearance_mode("system")
        elif choice == "Light": ctk.set_appearance_mode("light")
        else: ctk.set_appearance_mode("dark")

    def change_scaling(self, choice):
        scale = int(choice.replace("%", "")) / 100.0
        ctk.set_widget_scaling(scale)

    def on_engine_change(self):
        engine = self.engine_var.get()
        if engine == "gemini":
            self.gemini_frame.pack(fill="x", padx=40, pady=10)
            self.combo_global_model.configure(values=self.gemini_models_list, state="normal")
            self.combo_global_model.set(self.gemini_models_list[0])
            self.compiler.active_model = self.gemini_models_list[0]
        else:
            self.gemini_frame.pack_forget()
            self.scan_ollama()

    def save_settings(self):
        engine = self.engine_var.get()
        self.compiler.engine = engine
        self.compiler.api_key = self.entry_api.get()
        self.compiler.enable_web_search = self.enable_web_search_var.get()
        
        if engine == "gemini":
            self.combo_global_model.configure(values=self.gemini_models_list, state="normal")
        else:
            self.scan_ollama() 
            
        self.user_name = self.entry_name.get() or "User"
        self.bubble_radius = 5 if "Square" in self.bubble_var.get() else 15
        fs = self.font_var.get()
        self.font_size_chat = 12 if "Small" in fs else 16 if "Large" in fs else 14
        
        accent_choice = self.accent_var.get()
        if "Emerald" in accent_choice: self.C_ACCENT, self.C_ACCENT_HOVER = ("#059669", "#047857")
        elif "Purple" in accent_choice: self.C_ACCENT, self.C_ACCENT_HOVER = ("#7C3AED", "#6D28D9")
        elif "Crimson" in accent_choice: self.C_ACCENT, self.C_ACCENT_HOVER = ("#DC2626", "#B91C1C")
        else: self.C_ACCENT, self.C_ACCENT_HOVER = ("#2563EB", "#1D4ED8")
        
        for btn in self.dynamic_accent_buttons:
            if btn.winfo_exists(): btn.configure(fg_color=self.C_ACCENT, hover_color=self.C_ACCENT_HOVER)
        try: self.course_tabs.configure(segmented_button_selected_color=self.C_ACCENT)
        except: pass
            
        self.log("[+] Settings applied.")
        self.refresh_home_dashboard()
        messagebox.showinfo("Saved", "All customizations applied!")

    def scan_ollama(self):
        if self.compiler.engine == "gemini": return
        try:
            result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
            lines = result.stdout.strip().split('\n')
            models = [line.split()[0] for line in lines[1:] if line.strip()]
            if models:
                self.combo_global_model.configure(values=models, state="normal")
                self.combo_global_model.set(models[0])
                self.compiler.active_model = models[0] 
            else:
                self.combo_global_model.set("No models found")
                self.combo_global_model.configure(state="disabled")
        except: pass

    def on_nav_model_change(self, choice):
        self.compiler.active_model = choice
        self.log(f"[*] Active model switched to: {choice}")

    def _initial_gpu_load(self):
        self.log("[*] Securing Whisper to GPU...")
        self.transcriber.load_onto_gpu()

    # ==========================================
    # NAVIGATION LOGIC
    # ==========================================
    def show_frame(self, frame_name, title=None):
        if not title:
            titles = {"home": "Home Dashboard", "settings": "Settings & Configuration", "guest_summary": "Guest Summarizer"}
            title = titles.get(frame_name, "")
        for frame in self.frames.values(): frame.pack_forget()
        if not self.navigation_history or self.navigation_history[-1] != (frame_name, title):
            self.navigation_history.append((frame_name, title))
        self.frames[frame_name].pack(fill="both", expand=True)
        self.lbl_workspace_title.configure(text=title)
        if len(self.navigation_history) <= 1: self.btn_back.pack_forget()
        else: self.btn_back.pack(side="left", padx=15, pady=15)
        if frame_name == "course_view": self.btn_delete_course.pack(side="right", padx=15, pady=15)
        else: self.btn_delete_course.pack_forget()

    def go_back(self):
        if len(self.navigation_history) > 1:
            self.navigation_history.pop()
            prev_frame, prev_title = self.navigation_history[-1]
            for frame in self.frames.values(): frame.pack_forget()
            self.frames[prev_frame].pack(fill="both", expand=True)
            self.lbl_workspace_title.configure(text=prev_title)
            if len(self.navigation_history) <= 1: self.btn_back.pack_forget()
            if prev_frame == "course_view": self.btn_delete_course.pack(side="right", padx=15, pady=15)
            else: self.btn_delete_course.pack_forget()

    # ==========================================
    # COURSE MANAGEMENT
    # ==========================================
    def add_course_dialog(self):
        dialog = ctk.CTkInputDialog(text="Enter new course name:", title="New Course")
        name = dialog.get_input()
        if name and self.cm.create_course(name):
            self.refresh_course_list()
            self.refresh_home_dashboard()
            self.load_course(name)

    def import_course_dialog(self):
        path = filedialog.askopenfilename(filetypes=[("ZIP Archive", "*.zip")])
        if path:
            success, message = self.cm.import_course_zip(path)
            if success:
                messagebox.showinfo("Import Success", f"Course '{message}' imported successfully!")
                self.refresh_course_list()
                self.refresh_home_dashboard()
                self.load_course(message)
            else: messagebox.showerror("Import Failed", message)

    def refresh_course_list(self):
        for w in self.course_list_frame.winfo_children(): w.destroy()
        for course in self.cm.list_courses():
            ctk.CTkButton(self.course_list_frame, text=course, fg_color="transparent", text_color=self.C_TEXT, hover_color=self.C_CARD, anchor="w", command=lambda c=course: self.load_course(c)).pack(fill="x", pady=2)

    def load_course(self, course_name):
        self.active_course = course_name
        self.show_frame("course_view", f"Course: {course_name}")
        self.refresh_file_list()
        for widget in self.chat_scroll.winfo_children(): widget.destroy() 
        
    def refresh_file_list(self):
        for w in self.file_list_box.winfo_children(): w.destroy()
        if not self.active_course: return
        files = self.cm.list_course_files(self.active_course)
        if not files: ctk.CTkLabel(self.file_list_box, text="No files uploaded yet.", text_color=self.C_TEXT_MUTED).pack(pady=20)
        for f in files:
            icon = "📄 " if f.endswith(".pdf") else ("📝 " if f.endswith(".md") else "📁 ")
            ctk.CTkLabel(self.file_list_box, text=f"{icon}{f}", font=("Arial", 12), text_color=self.C_TEXT).pack(anchor="w", pady=4, padx=10)

    def export_course(self):
        if not self.active_course: return
        save_path = filedialog.asksaveasfilename(title="Export Course", defaultextension=".zip", initialfile=f"{self.active_course.replace(' ','_')}_Export.zip", filetypes=[("ZIP Archive", "*.zip")])
        if save_path:
            if self.cm.export_course_zip(self.active_course, save_path): messagebox.showinfo("Export Complete", f"Course successfully exported to:\n{save_path}")
            else: messagebox.showerror("Export Failed", "Error creating ZIP file.")

    def delete_active_course(self):
        if not self.active_course: return
        confirm = messagebox.askyesno("Delete Course", f"Are you sure you want to PERMANENTLY delete '{self.active_course}' and all its files?")
        if confirm:
            course_path = os.path.join(self.cm.courses_dir, self.active_course.replace(" ", "_").lower())
            try:
                shutil.rmtree(course_path)
                self.active_course = None
                self.refresh_course_list()
                self.refresh_home_dashboard()
                self.go_back()
                self.log("[+] Course deleted successfully.")
            except Exception as e: self.log(f"[-] Delete error: {e}")

    # ==========================================
    # RICH CHATBOT UI & LOGIC
    # ==========================================
    def render_chat_bubble(self, sender, text):
        is_user = (sender == self.user_name)
        bg_color = self.C_USER_BUBBLE if is_user else self.C_AI_BUBBLE
        display_name = self.user_name if is_user else "Kurt"
        
        container = ctk.CTkFrame(self.chat_scroll, fg_color="transparent")
        container.pack(fill="x", pady=10, padx=20)
        
        bubble = ctk.CTkFrame(container, fg_color=bg_color, corner_radius=self.bubble_radius)
        bubble.pack(side="right" if is_user else "left", ipadx=15, ipady=10, fill="x", expand=False)
        
        ctk.CTkLabel(bubble, text=display_name, font=("Arial", 11, "bold"), text_color=self.C_TEXT_MUTED).pack(anchor="w", padx=10, pady=(5,0))

        blocks = re.split(r"(```.*?```)", text, flags=re.DOTALL)
        for block in blocks:
            if not block.strip(): continue
            if block.startswith("```") and block.endswith("```"):
                code_content = block.strip("`").strip()
                if "\n" in code_content:
                    first_line, rest = code_content.split("\n", 1)
                    if len(first_line.split()) == 1: code_content = rest 
                code_frame = ctk.CTkFrame(bubble, fg_color=self.C_CODE_BG, corner_radius=5)
                code_frame.pack(fill="x", padx=10, pady=5)
                ctk.CTkLabel(code_frame, text=code_content, font=("Consolas", self.font_size_chat - 1), text_color=self.C_TEXT, justify="left", wraplength=650).pack(padx=15, pady=15, anchor="w")
            else:
                ctk.CTkLabel(bubble, text=block.strip(), font=("Arial", self.font_size_chat), text_color=self.C_TEXT, justify="left", wraplength=650).pack(anchor="w", padx=10, pady=5)
                
        self.chat_scroll._parent_canvas.yview_moveto(1.0)

    def send_chat(self):
        if not self.active_course: return
        question = self.chat_input.get()
        if not question.strip(): return
        
        self.chat_input.delete(0, 'end')
        self.render_chat_bubble(self.user_name, question)
        
        def process():
            context = self.rag.query_course(question, self.active_course)
            answer = self.chat_engine.ask_tutor(
                self.compiler.engine, 
                self.compiler.active_model, 
                self.compiler.api_key, 
                question, 
                context,
                self.enable_web_search_var.get() 
            )
            self.after(0, lambda: self.render_chat_bubble("Kurt", answer))
            self.rag.ingest_chat_exchange(self.active_course, question, answer, self.log)
            
        threading.Thread(target=process, daemon=True).start()

    # ==========================================
    # MEDIA & SUMMARIZATION
    # ==========================================
    def select_audio(self):
        self.shared_audio_path = filedialog.askopenfilename(filetypes=[("Audio/Video", "*.mp3 *.wav *.m4a *.mp4 *.mkv")])
        if self.shared_audio_path:
            name = os.path.basename(self.shared_audio_path)
            self.lbl_guest_audio.configure(text=name, text_color=self.C_SUCCESS[1])
            self.lbl_course_audio.configure(text=name, text_color=self.C_SUCCESS[1])

    def upload_doc(self):
        path = filedialog.askopenfilename(filetypes=[("Documents", "*.pdf *.txt *.md")])
        if path: threading.Thread(target=self._ingest_and_refresh, args=(path, False), daemon=True).start()

    def upload_image(self):
        if not self.compiler.api_key:
            messagebox.showerror("API Key Required", "Enter a Google Gemini API Key in Settings to parse visual data.")
            return
        path = filedialog.askopenfilename(filetypes=[("Images/Graphs", "*.png *.jpg *.jpeg")])
        if path: threading.Thread(target=self._ingest_and_refresh, args=(path, True), daemon=True).start()

    def _ingest_and_refresh(self, path, is_image):
        safe_course = self.active_course.replace(" ", "_").lower()
        dest_path = os.path.join(self.cm.courses_dir, safe_course, "raw_files", os.path.basename(path))
        try:
            if path != dest_path: shutil.copy(path, dest_path)
            if is_image: self.rag.ingest_image_via_gemini(dest_path, self.active_course, self.compiler.api_key, self.compiler.active_model, self.log)
            else: self.rag.ingest_document(dest_path, self.active_course, self.log)
            self.after(0, self.refresh_file_list)
            self.after(0, self.refresh_home_dashboard)
        except Exception as e: self.log(f"[-] Import error: {e}")

    def run_pipeline(self, mode, is_guest):
        if not self.shared_audio_path:
            messagebox.showwarning("File Missing", "Select an audio/video file first!")
            return
        threading.Thread(target=self._execute_pipeline, args=(mode, is_guest), daemon=True).start()

    def _execute_pipeline(self, mode, is_guest):
        try:
            self.lbl_tps.configure(text="Speed: Processing...")
            self.log("\n" + "="*40)
            
            ui_vars = self.guest_adv_vars if is_guest else self.course_adv_vars
            self.compiler.temperature = ui_vars["temp"].get()
            self.compiler.pages = ui_vars["pages"].get()
            self.compiler.active_elements = [name for name, var in ui_vars["checkboxes"].items() if var.get()]
            if "Header & Footer" in ui_vars["entries"]: self.compiler.custom_header = ui_vars["entries"]["Header & Footer"].get()
            if "Draft Watermark" in ui_vars["entries"]: self.compiler.custom_watermark = ui_vars["entries"]["Draft Watermark"].get()

            if self.compiler.engine == "ollama":
                self.compiler.context_length = self.ctx_values[int(ui_vars["ctx"].get())]
                self.compiler.keep_alive = self.keep_alive_map[ui_vars["keep"].get()]

            transcript = self.transcriber.transcribe(self.shared_audio_path, self.strategy_var.get())
            self.log("[+] Transcription finished.")

            context = ""
            if not is_guest and self.active_course:
                context = self.rag.query_course(transcript, self.active_course)
                
            latex, tps_string = self.compiler.generate_document(transcript, context, mode=mode)
            self.lbl_tps.configure(text=tps_string)
            
            clean_filename = f"{os.path.basename(self.shared_audio_path).rsplit('.', 1)[0]}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
            pdf_path = self.compiler.compile_to_pdf(latex, clean_filename)
            
            if not is_guest and self.active_course:
                md_path = os.path.join(self.cm.courses_dir, self.active_course.replace(" ","_").lower(), "raw_files", f"{clean_filename}.md")
                with open(md_path, "w", encoding="utf-8") as f:
                    f.write(f"# Transcript\n{transcript}\n\n# LaTeX Notes\n```latex\n{latex}\n```")
                self.rag.ingest_document(md_path, self.active_course, self.log)
                self.after(0, self.refresh_file_list)
                self.after(0, self.refresh_home_dashboard)

            if pdf_path and os.path.exists(pdf_path):
                save_path = filedialog.asksaveasfilename(title="Save PDF", defaultextension=".pdf", initialfile=f"{clean_filename}.pdf")
                if save_path:
                    shutil.copy(pdf_path, save_path)
                    messagebox.showinfo("Done", "PDF successfully saved!")

        except Exception as e: self.log(f"[-] Pipeline Error: {e}")
        finally: self.lbl_tps.configure(text="Speed: -- t/s")

    def log(self, text):
        self.log_area.insert("end", f"{text}\n")
        self.log_area.see("end")

if __name__ == "__main__":
    app = KurtApp()
    app.mainloop()