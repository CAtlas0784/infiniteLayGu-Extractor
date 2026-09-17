"""
InfiniteLaygu Extractor - Universal Game Asset Suite, Media Inspector & Multilingual Audio Syncer
4K High-DPI Modern Desktop UI built with CustomTkinter.
Supports:
- Universal Asset Extraction across Any Game or Custom Folder (Videos, 3D Models, Audio/Wwise, Datamine)
- Pre-configured High-Performance Pipeline for Project Mugen / Ananta CBT (Client 4229938)
- In-App Cutscene Player & Asset Dependency Inspector with Strict Audio Syncing (No fake tracks, Native priority)
- High-Performance Paginated UI rendering (0% lag on 4K multi-monitor dragging)
"""
import os
import sys
import json
import time
import shutil
import threading
import subprocess
import customtkinter as ctk
from tkinter import filedialog, messagebox
from typing import Optional, List, Dict, Any

from core.utils import load_config, save_config, resolve_path, format_size, ProgressLogger, InterruptedJobError
from core.video_extractor import VideoExtractor
from core.audio_extractor import AudioExtractor
from core.model_extractor import ModelExtractor
from core.datamine_extractor import DatamineExtractor
from core.cutscene_syncer import CutsceneCatalog, CutscenePlayerEngine, CutsceneMetadata

# Set modern dark appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class InfiniteLayguApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("InfiniteLaygu Extractor - Universal Game Asset & Cutscene Suite")
        self.geometry("1180x820")
        self.minsize(1050, 720)

        # Force High-DPI scaling check
        self.scaling = ctk.ScalingTracker.get_widget_scaling(self)
        
        self.cfg = load_config()
        self.game_root_var = ctk.StringVar(value=resolve_path(self.cfg.get("game_root", "")))
        self.output_dir_var = ctk.StringVar(value=resolve_path(self.cfg.get("output_dir", "output")))
        self.status_var = ctk.StringVar(value="Ready")
        self.is_running = False
        self.current_logger: Optional[ProgressLogger] = None
        self.stop_buttons: List[ctk.CTkButton] = []
        self.action_buttons: List[ctk.CTkButton] = []

        # Cutscene Player state
        self.catalog = CutsceneCatalog(self.output_dir_var.get(), ffmpeg_path=self.cfg.get("ffmpeg"))
        self.player_engine = CutscenePlayerEngine(self.output_dir_var.get(), ffmpeg_path=self.cfg.get("ffmpeg"))
        self.selected_cutscene: Optional[CutsceneMetadata] = None
        self.selected_lang_var = ctk.StringVar(value="orig")
        self.custom_audio_override: Optional[str] = None
        self.player_status_var = ctk.StringVar(value="Select a cutscene from the list to inspect and play")
        self.search_query_var = ctk.StringVar(value="")
        self.cat_filter_var = ctk.StringVar(value="All")

        # Performance & Pagination state (prevents multi-monitor dragging lag)
        self.filtered_videos: List[CutsceneMetadata] = []
        self.rendered_count: int = 0
        self.load_more_btn: Optional[ctk.CTkButton] = None
        self._search_timer = None

        self._build_ui()
        self._check_environment()
        self._init_player_catalog()

    def _build_ui(self):
        # 1. Top Header Banner
        header = ctk.CTkFrame(self, height=80, corner_radius=12, fg_color=("#1e2029", "#181920"))
        header.pack(fill="x", padx=16, pady=(14, 10))

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left", padx=20, pady=10)

        title_lbl = ctk.CTkLabel(title_box, text="INFINITELAYGU EXTRACTOR", font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"))
        title_lbl.pack(anchor="w")

        sub_lbl = ctk.CTkLabel(title_box, text="Universal Game Asset Extractor, Media Inspector & Multilingual Syncer", font=ctk.CTkFont(family="Segoe UI", size=12), text_color="#8c909e")
        sub_lbl.pack(anchor="w")

        btn_box = ctk.CTkFrame(header, fg_color="transparent")
        btn_box.pack(side="right", padx=16, pady=14)

        open_btn = ctk.CTkButton(btn_box, text="📂 Open Output Folder", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                                 fg_color="#2b5c8f", hover_color="#1f4268", height=36, corner_radius=8,
                                 command=self.open_output_folder)
        open_btn.pack(side="right", padx=6)

        # 2. Main Tabview
        self.tabview = ctk.CTkTabview(self, corner_radius=12, fg_color=("#22242e", "#1c1d24"))
        self.tabview.pack(fill="both", expand=True, padx=16, pady=(0, 10))

        self.tab_dash = self.tabview.add(" 📊 Dashboard ")
        self.tab_play = self.tabview.add(" 🎬 Cutscene Player & Inspector ")
        self.tab_vids = self.tabview.add(" 📹 Video Extractor ")
        self.tab_mods = self.tabview.add(" 🧊 3D Models & Textures ")
        self.tab_audi = self.tabview.add(" 🎵 Audio & Voices ")
        self.tab_data = self.tabview.add(" 📦 Data Mining ")

        self._build_dashboard_tab()
        self._build_player_tab()
        self._build_videos_tab()
        self._build_models_tab()
        self._build_audio_tab()
        self._build_datamine_tab()

        # 3. Bottom Console & Progress Bar
        bottom = ctk.CTkFrame(self, height=160, corner_radius=12, fg_color=("#1e2029", "#181920"))
        bottom.pack(fill="x", side="bottom", padx=16, pady=(0, 14))

        status_row = ctk.CTkFrame(bottom, fg_color="transparent")
        status_row.pack(fill="x", padx=16, pady=(8, 4))

        st_title = ctk.CTkLabel(status_row, text="Status:", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color="#8c909e")
        st_title.pack(side="left")

        self.status_lbl = ctk.CTkLabel(status_row, textvariable=self.status_var, font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color="#2ecc71")
        self.status_lbl.pack(side="left", padx=8)

        self.btn_bottom_stop = ctk.CTkButton(
            status_row,
            text="⏹️ STOP EXTRACTION (หยุด)",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            width=185,
            height=26,
            fg_color="#343746",
            hover_color="#424659",
            corner_radius=6,
            command=self.stop_current_job,
            state="disabled"
        )
        self.btn_bottom_stop.pack(side="right", padx=(8, 0))
        self.stop_buttons.append(self.btn_bottom_stop)

        clear_btn = ctk.CTkButton(status_row, text="Clear Log", font=ctk.CTkFont(family="Segoe UI", size=11), width=75, height=24,
                                  fg_color="#2c2e38", hover_color="#383a47", corner_radius=6,
                                  command=self._clear_log)
        clear_btn.pack(side="right")

        self.progress_bar = ctk.CTkProgressBar(bottom, height=6, corner_radius=3, progress_color="#2ecc71")
        self.progress_bar.pack(fill="x", padx=16, pady=(0, 6))
        self.progress_bar.set(0)

        self.log_text = ctk.CTkTextbox(bottom, height=80, font=ctk.CTkFont(family="Consolas", size=11),
                                       fg_color="#121317", text_color="#e0e2ec", corner_radius=8)
        self.log_text.pack(fill="both", expand=True, padx=16, pady=(0, 8))

    # =========================================================================
    # TAB 1: DASHBOARD
    # =========================================================================
    def _build_dashboard_tab(self):
        p = self.tab_dash

        # Target Game Directory & Mode Card (Universal Game Support)
        game_card = ctk.CTkFrame(p, corner_radius=10, fg_color="#242631")
        game_card.pack(fill="x", padx=12, pady=(10, 6))

        game_title = ctk.CTkLabel(game_card, text="🎯 Target Game Client / Folder (รองรับทุกเกม & โฟลเดอร์ทั่วไป)",
                                 font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"))
        game_title.pack(anchor="w", padx=16, pady=(10, 4))

        game_row = ctk.CTkFrame(game_card, fg_color="transparent")
        game_row.pack(fill="x", padx=16, pady=(0, 10))

        game_entry = ctk.CTkEntry(game_row, textvariable=self.game_root_var, font=ctk.CTkFont(family="Segoe UI", size=12), height=34)
        game_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        change_game_btn = ctk.CTkButton(game_row, text="🎮 Change Game...", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                                        fg_color="#16a085", hover_color="#117a65", width=140, height=34,
                                        command=self._browse_game_root)
        change_game_btn.pack(side="right")

        # Environment Status Card
        env_card = ctk.CTkFrame(p, corner_radius=10, fg_color="#242631")
        env_card.pack(fill="x", padx=12, pady=6)

        card_title = ctk.CTkLabel(env_card, text="Decoders & Engines Status", font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"))
        card_title.pack(anchor="w", padx=16, pady=(10, 4))

        self.lbl_game = ctk.CTkLabel(env_card, text="Game Directory: Checking...", font=ctk.CTkFont(family="Segoe UI", size=12), text_color="#8c909e", anchor="w")
        self.lbl_game.pack(fill="x", padx=16, pady=2)

        self.lbl_vfs = ctk.CTkLabel(env_card, text="Native VFS Core (CoreLib.dll): Checking...", font=ctk.CTkFont(family="Segoe UI", size=12), text_color="#8c909e", anchor="w")
        self.lbl_vfs.pack(fill="x", padx=16, pady=2)

        self.lbl_anime = ctk.CTkLabel(env_card, text="AnimeStudio Engine: Checking...", font=ctk.CTkFont(family="Segoe UI", size=12), text_color="#8c909e", anchor="w")
        self.lbl_anime.pack(fill="x", padx=16, pady=2)

        self.lbl_wwise = ctk.CTkLabel(env_card, text="Audio Tools (vgmstream & ffmpeg): Checking...", font=ctk.CTkFont(family="Segoe UI", size=12), text_color="#8c909e", anchor="w")
        self.lbl_wwise.pack(fill="x", padx=16, pady=(2, 10))

        # Output Destination Card
        dest_card = ctk.CTkFrame(p, corner_radius=10, fg_color="#242631")
        dest_card.pack(fill="x", padx=12, pady=6)

        dest_title = ctk.CTkLabel(dest_card, text="Extraction Destination Folder", font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"))
        dest_title.pack(anchor="w", padx=16, pady=(10, 4))

        dest_row = ctk.CTkFrame(dest_card, fg_color="transparent")
        dest_row.pack(fill="x", padx=16, pady=(0, 10))

        dest_entry = ctk.CTkEntry(dest_row, textvariable=self.output_dir_var, font=ctk.CTkFont(family="Segoe UI", size=12), height=34)
        dest_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        browse_btn = ctk.CTkButton(dest_row, text="Browse...", font=ctk.CTkFont(family="Segoe UI", size=12), width=100, height=34,
                                   fg_color="#343746", hover_color="#424659",
                                   command=self._browse_output)
        browse_btn.pack(side="right")

        # Big All-in-One Button & STOP Button
        action_box = ctk.CTkFrame(p, fg_color="transparent")
        action_box.pack(fill="x", padx=12, pady=12)

        self.btn_all = ctk.CTkButton(action_box, text="⚡ EXTRACT EVERYTHING (ALL-IN-ONE)",
                                font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
                                fg_color="#27ae60", hover_color="#219150", height=46, corner_radius=10,
                                command=self.start_extract_all)
        self.btn_all.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.action_buttons.append(self.btn_all)

        self.btn_dash_stop = ctk.CTkButton(action_box, text="⏹️ STOP (หยุดการสกัด)",
                                           font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
                                           fg_color="#343746", hover_color="#424659", height=46, width=190, corner_radius=10,
                                           command=self.stop_current_job,
                                           state="disabled")
        self.btn_dash_stop.pack(side="right")
        self.stop_buttons.append(self.btn_dash_stop)

    # =========================================================================
    # TAB 2: CUTSCENE PLAYER & ASSET INSPECTOR
    # =========================================================================
    def _build_player_tab(self):
        p = self.tab_play

        container = ctk.CTkFrame(p, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=8, pady=8)

        # ------------------ LEFT COLUMN: VIDEO BROWSER ------------------
        left_pane = ctk.CTkFrame(container, width=420, corner_radius=10, fg_color="#1e2029")
        left_pane.pack(side="left", fill="both", padx=(0, 8), pady=0)
        left_pane.pack_propagate(False)

        # Filter & Search Header
        filter_header = ctk.CTkFrame(left_pane, fg_color="transparent")
        filter_header.pack(fill="x", padx=10, pady=(10, 6))

        cat_lbl = ctk.CTkLabel(filter_header, text="Category Filter:", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#8c909e")
        cat_lbl.pack(anchor="w", padx=2, pady=(0, 2))

        self.cat_menu = ctk.CTkOptionMenu(filter_header, values=["All"], variable=self.cat_filter_var,
                                          font=ctk.CTkFont(family="Segoe UI", size=11), height=28,
                                          fg_color="#2c2e38", button_color="#383a47",
                                          command=lambda _: self._update_video_list(reset_page=True))
        self.cat_menu.pack(fill="x", pady=(0, 6))

        # Search box with Import Button
        search_box = ctk.CTkFrame(filter_header, fg_color="transparent")
        search_box.pack(fill="x")

        search_entry = ctk.CTkEntry(search_box, textvariable=self.search_query_var, placeholder_text="🔍 Search video, character, quest...",
                                    font=ctk.CTkFont(family="Segoe UI", size=11), height=30)
        search_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.search_query_var.trace_add("write", self._on_search_query_change)

        import_btn = ctk.CTkButton(search_box, text="📁 Import...", width=70, height=30,
                                   font=ctk.CTkFont(family="Segoe UI", size=11),
                                   fg_color="#2980b9", hover_color="#20638f",
                                   command=self._import_custom_video)
        import_btn.pack(side="right", padx=(0, 4))

        refresh_btn = ctk.CTkButton(search_box, text="🔄", width=30, height=30,
                                    fg_color="#2c2e38", hover_color="#383a47",
                                    command=self._reload_catalog)
        refresh_btn.pack(side="right")

        # Scrollable list of cutscenes (Paginated to prevent lag)
        self.video_list_frame = ctk.CTkScrollableFrame(left_pane, corner_radius=8, fg_color="#171820")
        self.video_list_frame.pack(fill="both", expand=True, padx=10, pady=(4, 10))

        # ------------------ RIGHT COLUMN: INSPECTOR & CONTROLS ------------------
        right_pane = ctk.CTkFrame(container, corner_radius=10, fg_color="#1e2029")
        right_pane.pack(side="right", fill="both", expand=True, padx=(0, 0), pady=0)

        # 1. Inspector Card ("ดึงข้อมูลว่าดึงอะไรมาใช้")
        self.insp_frame = ctk.CTkFrame(right_pane, corner_radius=10, fg_color="#242631")
        self.insp_frame.pack(fill="x", padx=12, pady=(12, 8))

        insp_header = ctk.CTkFrame(self.insp_frame, fg_color="transparent")
        insp_header.pack(fill="x", padx=14, pady=(12, 4))

        self.insp_title_lbl = ctk.CTkLabel(insp_header, text="Select a Cutscene to Inspect",
                                           font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
                                           anchor="w", text_color="#ffffff")
        self.insp_title_lbl.pack(side="left", fill="x", expand=True)

        self.insp_badge_lbl = ctk.CTkLabel(insp_header, text="Ready", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                                           fg_color="#34495e", corner_radius=6, padx=8, pady=3)
        self.insp_badge_lbl.pack(side="right")

        # Metadata grid
        grid_frame = ctk.CTkFrame(self.insp_frame, fg_color="transparent")
        grid_frame.pack(fill="x", padx=14, pady=(4, 12))

        # Row 1: VFS Path
        vfs_title = ctk.CTkLabel(grid_frame, text="Internal Game VFS:", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#8c909e", width=140, anchor="w")
        vfs_title.grid(row=0, column=0, sticky="w", pady=2)
        self.lbl_meta_vfs = ctk.CTkLabel(grid_frame, text="-", font=ctk.CTkFont(family="Consolas", size=11), text_color="#3498db", anchor="w")
        self.lbl_meta_vfs.grid(row=0, column=1, sticky="w", pady=2)

        # Row 2: Character / Quest Tag
        tag_title = ctk.CTkLabel(grid_frame, text="Entity / Quest Tag:", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#8c909e", width=140, anchor="w")
        tag_title.grid(row=1, column=0, sticky="w", pady=2)
        self.lbl_meta_tag = ctk.CTkLabel(grid_frame, text="-", font=ctk.CTkFont(family="Segoe UI", size=12), text_color="#f1c40f", anchor="w")
        self.lbl_meta_tag.grid(row=1, column=1, sticky="w", pady=2)

        # Row 3: Video Specs
        specs_title = ctk.CTkLabel(grid_frame, text="Resolution & Format:", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#8c909e", width=140, anchor="w")
        specs_title.grid(row=2, column=0, sticky="w", pady=2)
        self.lbl_meta_specs = ctk.CTkLabel(grid_frame, text="-", font=ctk.CTkFont(family="Segoe UI", size=12), text_color="#e0e2ec", anchor="w")
        self.lbl_meta_specs.grid(row=2, column=1, sticky="w", pady=2)

        # Row 4: Native Audio Status
        audio_title = ctk.CTkLabel(grid_frame, text="Native Audio Track:", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#8c909e", width=140, anchor="w")
        audio_title.grid(row=3, column=0, sticky="w", pady=2)
        self.lbl_meta_audio = ctk.CTkLabel(grid_frame, text="-", font=ctk.CTkFont(family="Segoe UI", size=12), text_color="#e67e22", anchor="w")
        self.lbl_meta_audio.grid(row=3, column=1, sticky="w", pady=2)

        # Row 5: Linked SoundBank
        bank_title = ctk.CTkLabel(grid_frame, text="Linked SoundBank:", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#8c909e", width=140, anchor="w")
        bank_title.grid(row=4, column=0, sticky="w", pady=2)
        self.lbl_meta_bank = ctk.CTkLabel(grid_frame, text="-", font=ctk.CTkFont(family="Segoe UI", size=12), text_color="#9b59b6", anchor="w")
        self.lbl_meta_bank.grid(row=4, column=1, sticky="w", pady=2)

        # Summary text
        self.lbl_meta_summary = ctk.CTkLabel(self.insp_frame, text="Select any cutscene to examine asset dependencies and playback audio options.",
                                             font=ctk.CTkFont(family="Segoe UI", size=11), text_color="#8c909e", justify="left", wraplength=620, anchor="w")
        self.lbl_meta_summary.pack(fill="x", padx=14, pady=(0, 12))

        # 2. Audio Track & Language Selector Card (Strict, Honest, No Fake Mappings)
        self.lang_card = ctk.CTkFrame(right_pane, corner_radius=10, fg_color="#242631")
        self.lang_card.pack(fill="x", padx=12, pady=6)

        lang_header = ctk.CTkFrame(self.lang_card, fg_color="transparent")
        lang_header.pack(fill="x", padx=14, pady=(10, 4))

        self.lang_card_title = ctk.CTkLabel(lang_header, text="Audio Track Selection (เลือกแทร็กเสียง):",
                                           font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"))
        self.lang_card_title.pack(side="left")

        pick_custom_btn = ctk.CTkButton(lang_header, text="🎵 Custom Audio...", font=ctk.CTkFont(family="Segoe UI", size=11),
                                        width=110, height=26, fg_color="#34495e", hover_color="#2c3e50",
                                        command=self._choose_custom_audio)
        pick_custom_btn.pack(side="right")

        # Segmented Button - dynamically populated with ONLY available genuine tracks
        self.lang_seg = ctk.CTkSegmentedButton(self.lang_card,
                                              values=["🎬 Original"],
                                              font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                                              height=36,
                                              command=self._on_lang_segmented_change)
        self.lang_seg.pack(fill="x", padx=14, pady=4)
        self.lang_seg.set("🎬 Original")

        # Current audio file description
        self.lbl_current_audio_track = ctk.CTkLabel(self.lang_card, text="Audio Track: Ready",
                                                    font=ctk.CTkFont(family="Consolas", size=11),
                                                    text_color="#2ecc71", anchor="w")
        self.lbl_current_audio_track.pack(fill="x", padx=14, pady=(4, 10))

        # 3. Action Buttons & Controls Card
        action_card = ctk.CTkFrame(right_pane, corner_radius=10, fg_color="#242631")
        action_card.pack(fill="x", padx=12, pady=6)

        btn_grid = ctk.CTkFrame(action_card, fg_color="transparent")
        btn_grid.pack(fill="x", padx=14, pady=12)

        self.btn_play = ctk.CTkButton(btn_grid, text="▶️ เล่นวิดีโอ (Play Video)",
                                      font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
                                      fg_color="#27ae60", hover_color="#219150", height=44, corner_radius=8,
                                      command=self._play_current_cutscene)
        self.btn_play.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.btn_export = ctk.CTkButton(btn_grid, text="⚡ บันทึกไฟล์พร้อมเสียง (Export MP4)",
                                        font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                                        fg_color="#2980b9", hover_color="#20638f", height=44, corner_radius=8,
                                        command=self._export_current_cutscene)
        self.btn_export.pack(side="left", fill="x", expand=True, padx=6)

        self.btn_reveal = ctk.CTkButton(btn_grid, text="📂 เปิดโฟลเดอร์",
                                        font=ctk.CTkFont(family="Segoe UI", size=12),
                                        fg_color="#34495e", hover_color="#2c3e50", height=44, width=110, corner_radius=8,
                                        command=self._reveal_current_cutscene)
        self.btn_reveal.pack(side="right", padx=(6, 0))

        # 4. Player Status Box
        status_box = ctk.CTkFrame(right_pane, corner_radius=8, fg_color="#171820")
        status_box.pack(fill="both", expand=True, padx=12, pady=(6, 12))

        st_header = ctk.CTkLabel(status_box, text="⚡ Fast Mux & Playback Status:", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#8c909e")
        st_header.pack(anchor="w", padx=12, pady=(8, 2))

        self.player_log_lbl = ctk.CTkLabel(status_box, textvariable=self.player_status_var,
                                           font=ctk.CTkFont(family="Consolas", size=11),
                                           text_color="#e0e2ec", justify="left", anchor="nw")
        self.player_log_lbl.pack(fill="both", expand=True, padx=12, pady=(0, 8))

    def _init_player_catalog(self):
        """Load catalog in background and populate UI."""
        def load():
            try:
                items = self.catalog.scan()
                cats = ["All"] + self.catalog.get_categories()
                self.after(0, lambda: self.cat_menu.configure(values=cats))
                self.after(0, lambda: self._update_video_list(reset_page=True))
                if items:
                    self.after(0, lambda: self._select_cutscene(items[0]))
            except Exception as e:
                self.log(f"[WARN] Catalog init failed: {e}")

        threading.Thread(target=load, daemon=True).start()

    def _reload_catalog(self):
        """Force rescan of video catalog."""
        self.player_status_var.set("Rescanning video directory and audio library...")
        def rescan():
            try:
                self.catalog.scan(force_refresh=True)
                cats = ["All"] + self.catalog.get_categories()
                self.after(0, lambda: self.cat_menu.configure(values=cats))
                self.after(0, lambda: self._update_video_list(reset_page=True))
                self.after(0, lambda: self.player_status_var.set("Catalog refreshed successfully!"))
            except Exception as e:
                self.after(0, lambda: self.player_status_var.set(f"Rescan error: {e}"))
        threading.Thread(target=rescan, daemon=True).start()

    def _import_custom_video(self):
        """Import an external video from anywhere on disk."""
        path = filedialog.askopenfilename(
            title="Import Any Video File",
            filetypes=[("Video Files", "*.mp4;*.webm;*.usm;*.bk2;*.mkv;*.avi"), ("All Files", "*.*")]
        )
        if path:
            meta = self.catalog.import_custom_video(path)
            if meta:
                cats = ["All"] + self.catalog.get_categories()
                self.cat_menu.configure(values=cats)
                self.cat_filter_var.set("All")
                self._update_video_list(reset_page=True)
                self._select_cutscene(meta)
                self.player_status_var.set(f"✅ Imported custom video: {os.path.basename(path)}")

    def _choose_custom_audio(self):
        """Allow user to pick any custom audio file for the active video."""
        path = filedialog.askopenfilename(
            title="Select Custom Audio Track",
            filetypes=[("Audio Files", "*.wav;*.mp3;*.ogg;*.flac;*.m4a;*.wem"), ("All Files", "*.*")]
        )
        if path and self.selected_cutscene:
            self.custom_audio_override = path
            name = os.path.basename(path)
            size = format_size(os.path.getsize(path))
            self._refresh_language_segmented_options()
            self.player_status_var.set(f"Custom audio track assigned: {name}")

    def _on_search_query_change(self, *args):
        """Debounce search query to prevent lag when typing."""
        if hasattr(self, "_search_timer") and self._search_timer:
            self.after_cancel(self._search_timer)
        self._search_timer = self.after(250, lambda: self._update_video_list(reset_page=True))

    def _update_video_list(self, reset_page: bool = True):
        """
        Update scrollable list with pagination (25 items per chunk).
        Ensures silky-smooth 120/144Hz performance when moving window across screens.
        """
        if reset_page:
            self.rendered_count = 0
            for widget in self.video_list_frame.winfo_children():
                widget.destroy()
        else:
            if hasattr(self, "load_more_btn") and self.load_more_btn and self.load_more_btn.winfo_exists():
                self.load_more_btn.destroy()

        category = self.cat_filter_var.get()
        query = self.search_query_var.get()
        self.filtered_videos = self.catalog.filter(category=category, query=query)
        total_count = len(self.filtered_videos)

        start_idx = self.rendered_count
        end_idx = min(start_idx + 25, total_count)

        for idx in range(start_idx, end_idx):
            item = self.filtered_videos[idx]
            card = ctk.CTkFrame(self.video_list_frame, corner_radius=8, fg_color="#242631")
            card.pack(fill="x", pady=4, padx=2)

            top_row = ctk.CTkFrame(card, fg_color="transparent")
            top_row.pack(fill="x", padx=10, pady=(8, 2))

            title_lbl = ctk.CTkLabel(top_row, text=item.title, font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                                     anchor="w", text_color="#ffffff")
            title_lbl.pack(side="left", fill="x", expand=True)

            if item.audio_status == "native_audio":
                badge_text = "🔊 Native"
                badge_color = "#27ae60"
            elif item.audio_status == "silent_dummy":
                badge_text = "🔇 Localized"
                badge_color = "#d35400"
            else:
                badge_text = "🔇 No Audio"
                badge_color = "#7f8c8d"

            badge = ctk.CTkLabel(top_row, text=badge_text, font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                                 fg_color=badge_color, corner_radius=4, padx=6, pady=2)
            badge.pack(side="right")

            sub_row = ctk.CTkFrame(card, fg_color="transparent")
            sub_row.pack(fill="x", padx=10, pady=(0, 6))

            info_text = f"⏱️ {item.duration_str}  |  💾 {item.file_size_fmt}  |  {item.resolution}"
            info_lbl = ctk.CTkLabel(sub_row, text=info_text, font=ctk.CTkFont(family="Segoe UI", size=10), text_color="#8c909e", anchor="w")
            info_lbl.pack(side="left")

            def make_click_handler(meta):
                return lambda e: self._select_cutscene(meta)

            card.bind("<Button-1>", make_click_handler(item))
            title_lbl.bind("<Button-1>", make_click_handler(item))
            info_lbl.bind("<Button-1>", make_click_handler(item))

        self.rendered_count = end_idx

        if self.rendered_count < total_count:
            self.load_more_btn = ctk.CTkButton(
                self.video_list_frame,
                text=f"⬇️ โหลดเพิ่มอีก 25 รายการ (กำลังแสดง {self.rendered_count} จาก {total_count} คลิป)",
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                fg_color="#2c2e38", hover_color="#383a47", height=32,
                command=lambda: self._update_video_list(reset_page=False)
            )
            self.load_more_btn.pack(fill="x", pady=(8, 12), padx=4)

    def _select_cutscene(self, meta: CutsceneMetadata):
        """Display selected cutscene details in the right inspector pane."""
        self.selected_cutscene = meta
        self.custom_audio_override = None

        self.insp_title_lbl.configure(text=meta.title)
        self.lbl_meta_vfs.configure(text=meta.vfs_path)
        self.lbl_meta_tag.configure(text=f"{meta.entity_tag} ({meta.category})")
        self.lbl_meta_specs.configure(text=f"{meta.resolution} | Duration: {meta.duration_str} | Size: {meta.file_size_fmt}")
        
        if meta.audio_status == "native_audio":
            self.lbl_meta_audio.configure(text=f"มีเสียงในตัวสมบูรณ์ ({meta.audio_bitrate_kbps} kb/s) - ไม่จำเป็นต้องซิงค์เสียงแยก", text_color="#2ecc71")
            self.insp_badge_lbl.configure(text="🔊 มีเสียงต้นฉบับในตัว", fg_color="#27ae60")
        elif meta.audio_status == "silent_dummy":
            self.lbl_meta_audio.configure(text=f"Silent Dummy Track ({meta.audio_bitrate_kbps} kb/s) - เสียงในเกมจริงสตรีมผ่าน Wwise", text_color="#e67e22")
            self.insp_badge_lbl.configure(text="🔇 คลิปไม่มีเสียงในตัว", fg_color="#d35400")
        else:
            self.lbl_meta_audio.configure(text="ไม่มีสตรีมเสียงในไฟล์", text_color="#7f8c8d")
            self.insp_badge_lbl.configure(text="🔇 ไม่มีเสียง", fg_color="#7f8c8d")

        self.lbl_meta_bank.configure(text=meta.linked_soundbank)
        self.lbl_meta_summary.configure(text=meta.summary or f"Extracted video from {meta.rel_path}")

        # Update language selector options strictly based on genuine availability
        self._refresh_language_segmented_options()

    def _refresh_language_segmented_options(self):
        """Only show genuine, available audio options. Never show fake/random tracks."""
        if not self.selected_cutscene:
            return

        meta = self.selected_cutscene
        options = []

        if meta.audio_status == "native_audio":
            options.append("🎬 Original (มีเสียงในตัว)")
            if self.custom_audio_override:
                options.append("🎵 Custom Audio")
            self.lang_seg.configure(values=options)
            chosen = "🎵 Custom Audio" if self.custom_audio_override else "🎬 Original (มีเสียงในตัว)"
            self.lang_seg.set(chosen)
            self.selected_lang_var.set("custom" if self.custom_audio_override else "orig")
        else:
            # Silent Dummy / No audio clip
            options.append("🎬 Original (ไม่มีเสียง)")
            if "ja" in meta.mapped_tracks:
                options.append("🇯🇵 日本語 (JP)")
            if "zh" in meta.mapped_tracks:
                options.append("🇨🇳 中文 (CN)")
            if "en" in meta.mapped_tracks:
                options.append("🇺🇸 English (EN)")
            if "bgm" in meta.mapped_tracks:
                options.append("🎼 BGM Only")
            if self.custom_audio_override:
                options.append("🎵 Custom Audio")

            self.lang_seg.configure(values=options)
            if self.custom_audio_override:
                self.lang_seg.set("🎵 Custom Audio")
                self.selected_lang_var.set("custom")
            elif "ja" in meta.mapped_tracks:
                self.lang_seg.set("🇯🇵 日本語 (JP)")
                self.selected_lang_var.set("ja")
            else:
                self.lang_seg.set("🎬 Original (ไม่มีเสียง)")
                self.selected_lang_var.set("orig")

        self._update_audio_selection_display()

    def _on_lang_segmented_change(self, value):
        """Map segmented button choice to language key."""
        lang_map = {
            "🎬 Original (มีเสียงในตัว)": "orig",
            "🎬 Original (ไม่มีเสียง)": "orig",
            "🇯🇵 日本語 (JP)": "ja",
            "🇨🇳 中文 (CN)": "zh",
            "🇺🇸 English (EN)": "en",
            "🎼 BGM Only": "bgm",
            "🎵 Custom Audio": "custom"
        }
        key = lang_map.get(value, "orig")
        self.selected_lang_var.set(key)
        self._update_audio_selection_display()

    def _update_audio_selection_display(self):
        """Update label and play button state strictly based on active selection."""
        if not self.selected_cutscene:
            return

        meta = self.selected_cutscene
        lang = self.selected_lang_var.get()

        # 1. Custom Audio Override
        if lang == "custom" and self.custom_audio_override:
            name = os.path.basename(self.custom_audio_override)
            size = format_size(os.path.getsize(self.custom_audio_override))
            self.lbl_current_audio_track.configure(text=f"Custom Track: {name} ({size}) [พร้อมซิงค์ & เล่น]", text_color="#f1c40f")
            self.btn_play.configure(state="normal", text="▶️ รวมและเล่นเสียง Custom (Play Synced)")
            self.player_status_var.set(f"พร้อมรวมเสียง Custom '{name}' เข้ากับวิดีโอ")
            return

        # 2. Original Audio
        if lang == "orig":
            if meta.audio_status == "native_audio":
                self.lbl_current_audio_track.configure(text="ใช้แทร็กเสียงเดิม: มีเสียงต้นฉบับสมบูรณ์ในตัว (AAC Stereo)", text_color="#2ecc71")
                self.btn_play.configure(state="normal", text="▶️ เล่นวิดีโอพร้อมเสียงต้นฉบับ (Play Video)")
                self.player_status_var.set(f"วิดีโอนี้มีเสียงในตัวอยู่แล้ว ({meta.audio_bitrate_kbps} kbps) พร้อมเปิดเล่นทันที")
            else:
                self.lbl_current_audio_track.configure(text="ใช้แทร็กเสียงเดิม: วิดีโอนี้ไม่มีเสียง (Silent Dummy) หากต้องการเสียงกรุณาเลือก 'Custom Audio'", text_color="#e67e22")
                self.btn_play.configure(state="normal", text="▶️ เล่นวิดีโอ (ไม่มีเสียง / Silent)")
                self.player_status_var.set(f"คลิปนี้ไม่มีเสียงในตัว (หากต้องการเสียงให้กด '🎵 Custom Audio...' เพื่อเลือกไฟล์เสียง)")
            return

        # 3. Verified Language Tracks
        track_path = meta.mapped_tracks.get(lang)
        if track_path and os.path.exists(track_path):
            name = os.path.basename(track_path)
            size = format_size(os.path.getsize(track_path))
            self.lbl_current_audio_track.configure(text=f"แทร็กเสียงที่ตรงกัน: {name} ({size}) [พร้อมเล่น]", text_color="#2ecc71")
            self.btn_play.configure(state="normal", text=f"▶️ รวมและเล่นเสียง {lang.upper()} (Play Synced)")
            self.player_status_var.set(f"พร้อมรวมเสียง {lang.upper()} เข้ากับวิดีโอ")
        else:
            self.lbl_current_audio_track.configure(text=f"❌ ไม่มีไฟล์เสียงที่ตรงกับภาษานี้สำหรับคลิปนี้ (คลิก 'Custom Audio...' เพื่อเลือกไฟล์เสียง)", text_color="#e74c3c")
            self.btn_play.configure(state="disabled", text="⚠️ ไม่มีไฟล์เสียงสำหรับภาษานี้")
            self.player_status_var.set(f"คลิปนี้ไม่มีไฟล์เสียง {lang.upper()} ที่ตรงกัน กรุณาเลือก Custom Audio หรือ Original")

    def _play_current_cutscene(self):
        """Play cutscene immediately, prioritizing native audio without unnecessary muxing."""
        if not self.selected_cutscene:
            messagebox.showinfo("No Video", "Please select a cutscene from the list first.")
            return

        meta = self.selected_cutscene
        lang = self.selected_lang_var.get()

        # If native audio and user chose original, play immediately without muxing!
        if lang == "orig" and meta.audio_status == "native_audio":
            self.player_status_var.set(f"▶️ กำลังเปิดเล่นวิดีโอพร้อมเสียงต้นฉบับ: {meta.filename}")
            self.player_engine.play_media(meta.file_path)
            return

        # If user chose original on silent video, play directly
        if lang == "orig":
            self.player_status_var.set(f"▶️ กำลังเปิดเล่นวิดีโอ (ไม่มีเสียง): {meta.filename}")
            self.player_engine.play_media(meta.file_path)
            return

        # Otherwise mux with selected track
        audio_path = self.custom_audio_override if lang == "custom" else meta.mapped_tracks.get(lang)
        if not audio_path or not os.path.exists(audio_path):
            messagebox.showwarning("No Audio", "ไม่มีไฟล์เสียงสำหรับตัวเลือกนี้ กรุณาเลือก 'Custom Audio...'")
            return

        self.btn_play.configure(state="disabled", text="⏳ Muxing Audio...")
        self.player_status_var.set(f"⚡ Muxing video '{meta.filename}' with audio via FFmpeg...")

        def worker():
            t0 = time.time()
            ok, media_path, elapsed = self.player_engine.mux_video_with_audio(meta.file_path, audio_path, lang_code=lang)
            if ok:
                self.after(0, lambda: self.player_status_var.set(f"✅ Muxed in {elapsed:.2f}s! Launching media player...\nPlaying: {os.path.basename(media_path)}"))
                self.player_engine.play_media(media_path)
            else:
                self.after(0, lambda: self.player_status_var.set(f"❌ Playback failed: {media_path}"))
            self.after(0, self._update_audio_selection_display)

        threading.Thread(target=worker, daemon=True).start()

    def _export_current_cutscene(self):
        """Export synced MP4 to custom location."""
        if not self.selected_cutscene:
            messagebox.showinfo("No Video", "Please select a cutscene first.")
            return

        meta = self.selected_cutscene
        lang = self.selected_lang_var.get()

        stem = os.path.splitext(meta.filename)[0]
        default_name = f"{stem}_{lang}.mp4"

        dest = filedialog.asksaveasfilename(initialfile=default_name,
                                            defaultextension=".mp4",
                                            filetypes=[("MP4 Video", "*.mp4"), ("All Files", "*.*")],
                                            title="Export Video")
        if not dest:
            return

        # If native audio, copy directly
        if lang == "orig":
            shutil.copy2(meta.file_path, dest)
            messagebox.showinfo("Export Successful", f"Saved video to:\n{dest}")
            self.player_status_var.set(f"✅ Exported: {dest}")
            return

        audio_path = self.custom_audio_override if lang == "custom" else meta.mapped_tracks.get(lang)
        if not audio_path or not os.path.exists(audio_path):
            messagebox.showwarning("No Audio", "ไม่มีไฟล์เสียงสำหรับตัวเลือกนี้")
            return

        self.btn_export.configure(state="disabled", text="⏳ Exporting...")
        self.player_status_var.set(f"Exporting synced MP4 to {dest}...")

        def worker():
            ok, msg = self.player_engine.export_synced_video(meta.file_path, audio_path, dest)
            if ok:
                self.after(0, lambda: self.player_status_var.set(f"✅ Export completed!\nSaved to: {dest}"))
                self.after(0, lambda: messagebox.showinfo("Export Successful", f"Video saved with synced audio!\n\nDestination:\n{dest}"))
            else:
                self.after(0, lambda: self.player_status_var.set(f"❌ Export failed: {msg}"))
            self.after(0, lambda: self.btn_export.configure(state="normal", text="⚡ บันทึกไฟล์พร้อมเสียง (Export MP4)"))

        threading.Thread(target=worker, daemon=True).start()

    def _reveal_current_cutscene(self):
        """Highlight current video file in Windows Explorer."""
        if not self.selected_cutscene:
            return
        p = self.selected_cutscene.file_path
        if os.path.exists(p):
            if sys.platform == "win32":
                subprocess.run(["explorer", "/select,", os.path.normpath(p)])
            else:
                os.startfile(os.path.dirname(p))

    # =========================================================================
    # TAB 3: VIDEOS
    # =========================================================================
    def _build_videos_tab(self):
        p = self.tab_vids

        desc = ctk.CTkLabel(p, text="Universal video extraction suite. Scans and pulls videos from Project Mugen / Ananta or ANY custom game folder.",
                            font=ctk.CTkFont(family="Segoe UI", size=13), text_color="#8c909e", justify="left")
        desc.pack(anchor="w", padx=16, pady=(16, 12))

        btn_vids = ctk.CTkButton(p, text="🎬 Extract Ananta / Mugen Videos (numPath 186+ Clips)",
                                 font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
                                 fg_color="#2980b9", hover_color="#20638f", height=44, corner_radius=8,
                                 command=lambda: self._run_job(self._job_extract_videos))
        btn_vids.pack(fill="x", padx=16, pady=8)

        btn_univ_vids = ctk.CTkButton(p, text="🌐 Universal Video Scanner (Scan ANY game or custom folder for MP4/USM/WebM/BK2)",
                                      font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                                      fg_color="#16a085", hover_color="#117a65", height=40, corner_radius=8,
                                      command=self._scan_universal_videos)
        btn_univ_vids.pack(fill="x", padx=16, pady=6)

        btn_login = ctk.CTkButton(p, text="🌅 Extract Login Background Video (v02_login_bg.mp4)",
                                  font=ctk.CTkFont(family="Segoe UI", size=13),
                                  fg_color="#34495e", hover_color="#2c3e50", height=38, corner_radius=8,
                                  command=lambda: self._run_job(self._job_extract_login_video))
        btn_login.pack(fill="x", padx=16, pady=6)

        btn_upscale = ctk.CTkButton(p, text="✨ Upscale Extracted Videos to 4K UHD (3840x2160 Lanczos via FFmpeg)",
                                    font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                                    fg_color="#8e44ad", hover_color="#73368c", height=40, corner_radius=8,
                                    command=lambda: self._run_job(self._job_upscale_videos))
        btn_upscale.pack(fill="x", padx=16, pady=6)

        btn_stop_v = ctk.CTkButton(p, text="⏹️ STOP RUNNING TASK (หยุดการสกัด)",
                                   font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                                   fg_color="#343746", hover_color="#424659", height=38, corner_radius=8,
                                   command=self.stop_current_job, state="disabled")
        btn_stop_v.pack(fill="x", padx=16, pady=(10, 6))
        self.stop_buttons.append(btn_stop_v)

    # =========================================================================
    # TAB 4: 3D MODELS
    # =========================================================================
    def _build_models_tab(self):
        p = self.tab_mods

        desc = ctk.CTkLabel(p, text="Extract 3D models and textures from Unity Asset archives using AnimeStudio and Il2Cpp DummyDlls.",
                            font=ctk.CTkFont(family="Segoe UI", size=13), text_color="#8c909e", justify="left")
        desc.pack(anchor="w", padx=16, pady=(16, 12))

        btn_m = ctk.CTkButton(p, text="🧊 Extract 3D Models (Mesh, GameObject -> OBJ/glTF)",
                              font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
                              fg_color="#8e44ad", hover_color="#6c3483", height=44, corner_radius=8,
                              command=lambda: self._run_job(self._job_extract_models))
        btn_m.pack(fill="x", padx=16, pady=8)

        btn_t = ctk.CTkButton(p, text="🖼️ Extract Textures & UI Sprites (Texture2D, Sprite -> PNG)",
                              font=ctk.CTkFont(family="Segoe UI", size=13),
                              fg_color="#34495e", hover_color="#2c3e50", height=38, corner_radius=8,
                              command=lambda: self._run_job(self._job_extract_textures))
        btn_t.pack(fill="x", padx=16, pady=6)

        btn_stop_m = ctk.CTkButton(p, text="⏹️ STOP RUNNING TASK (หยุดการสกัด)",
                                   font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                                   fg_color="#343746", hover_color="#424659", height=38, corner_radius=8,
                                   command=self.stop_current_job, state="disabled")
        btn_stop_m.pack(fill="x", padx=16, pady=(10, 6))
        self.stop_buttons.append(btn_stop_m)

    # =========================================================================
    # TAB 5: AUDIO & VOICES
    # =========================================================================
    def _build_audio_tab(self):
        p = self.tab_audi

        desc = ctk.CTkLabel(p, text="Unpack Wwise SoundBanks (*.pck, *.bnk) and convert voice lines & background music to WAV.",
                            font=ctk.CTkFont(family="Segoe UI", size=13), text_color="#8c909e", justify="left")
        desc.pack(anchor="w", padx=16, pady=(16, 12))

        btn_all_audio = ctk.CTkButton(p, text="🎵 Extract All Ananta / Mugen Audio (Voices + BGM + SFX)",
                                      font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
                                      fg_color="#d35400", hover_color="#a04000", height=44, corner_radius=8,
                                      command=lambda: self._run_job(self._job_extract_all_audio))
        btn_all_audio.pack(fill="x", padx=16, pady=8)

        btn_univ_audi = ctk.CTkButton(p, text="🌐 Universal Audio Scanner (Scan ANY game/custom folder for Wwise PCK/BNK -> WAV)",
                                      font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                                      fg_color="#16a085", hover_color="#117a65", height=40, corner_radius=8,
                                      command=self._scan_universal_audio)
        btn_univ_audi.pack(fill="x", padx=16, pady=6)

        sub_btns = ctk.CTkFrame(p, fg_color="transparent")
        sub_btns.pack(fill="x", padx=16, pady=6)

        ctk.CTkButton(sub_btns, text="🇨🇳 Chinese Voices", font=ctk.CTkFont(family="Segoe UI", size=12), height=36,
                      fg_color="#34495e", hover_color="#2c3e50",
                      command=lambda: self._run_job(lambda lg: self._job_extract_audio_cat("chinese_voice", lg))).pack(side="left", fill="x", expand=True, padx=4)

        ctk.CTkButton(sub_btns, text="🇯🇵 Japanese Voices", font=ctk.CTkFont(family="Segoe UI", size=12), height=36,
                      fg_color="#34495e", hover_color="#2c3e50",
                      command=lambda: self._run_job(lambda lg: self._job_extract_audio_cat("japanese_voice", lg))).pack(side="left", fill="x", expand=True, padx=4)

        ctk.CTkButton(sub_btns, text="🇺🇸 English Voices", font=ctk.CTkFont(family="Segoe UI", size=12), height=36,
                      fg_color="#34495e", hover_color="#2c3e50",
                      command=lambda: self._run_job(lambda lg: self._job_extract_audio_cat("english_voice", lg))).pack(side="left", fill="x", expand=True, padx=4)

        ctk.CTkButton(sub_btns, text="🎼 BGM Streams", font=ctk.CTkFont(family="Segoe UI", size=12), height=36,
                      fg_color="#34495e", hover_color="#2c3e50",
                      command=lambda: self._run_job(lambda lg: self._job_extract_audio_cat("bgm_streams", lg))).pack(side="left", fill="x", expand=True, padx=4)

        btn_stop_a = ctk.CTkButton(p, text="⏹️ STOP RUNNING TASK (หยุดการสกัด)",
                                   font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                                   fg_color="#343746", hover_color="#424659", height=38, corner_radius=8,
                                   command=self.stop_current_job, state="disabled")
        btn_stop_a.pack(fill="x", padx=16, pady=(10, 6))
        self.stop_buttons.append(btn_stop_a)

    # =========================================================================
    # TAB 6: DATAMINE
    # =========================================================================
    def _build_datamine_tab(self):
        p = self.tab_data

        desc = ctk.CTkLabel(p, text="Export game configuration tables, world item coordinates, vehicle parameters, and protocol definitions.",
                            font=ctk.CTkFont(family="Segoe UI", size=13), text_color="#8c909e", justify="left")
        desc.pack(anchor="w", padx=16, pady=(16, 12))

        btn_all_data = ctk.CTkButton(p, text="📦 Export All Datamine Tables & Manifests",
                                     font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
                                     fg_color="#2980b9", hover_color="#20638f", height=44, corner_radius=8,
                                     command=lambda: self._run_job(self._job_extract_datamine))
        btn_all_data.pack(fill="x", padx=16, pady=8)

        btn_vfs = ctk.CTkButton(p, text="📋 Dump Native VFS Manifest (227,378 Files via CoreLib.dll)",
                                font=ctk.CTkFont(family="Segoe UI", size=13),
                                fg_color="#34495e", hover_color="#2c3e50", height=38, corner_radius=8,
                                command=lambda: self._run_job(self._job_dump_vfs))
        btn_vfs.pack(fill="x", padx=16, pady=6)

        btn_world = ctk.CTkButton(p, text="🗺️ Export World Placement & NPC Coords (sceneitem_placements.json)",
                                  font=ctk.CTkFont(family="Segoe UI", size=13),
                                  fg_color="#34495e", hover_color="#2c3e50", height=38, corner_radius=8,
                                  command=lambda: self._run_job(self._job_export_world))
        btn_world.pack(fill="x", padx=16, pady=6)

        btn_stop_d = ctk.CTkButton(p, text="⏹️ STOP RUNNING TASK (หยุดการสกัด)",
                                   font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                                   fg_color="#343746", hover_color="#424659", height=38, corner_radius=8,
                                   command=self.stop_current_job, state="disabled")
        btn_stop_d.pack(fill="x", padx=16, pady=(10, 6))
        self.stop_buttons.append(btn_stop_d)

    # =========================================================================
    # HELPERS & SYSTEM CALLS
    # =========================================================================
    def _browse_game_root(self):
        """Allow user to point to ANY game folder."""
        d = filedialog.askdirectory(initialdir=self.game_root_var.get(), title="Select Target Game Directory")
        if d:
            self.game_root_var.set(d)
            self.cfg["game_root"] = d
            
            # Check for StreamingAssets inside selected game
            sa_candidate = os.path.join(d, "Ananta_Data", "StreamingAssets")
            if not os.path.exists(sa_candidate):
                for sub in os.listdir(d):
                    if sub.endswith("_Data"):
                        sa_test = os.path.join(d, sub, "StreamingAssets")
                        if os.path.exists(sa_test):
                            sa_candidate = sa_test
                            break
            if not os.path.exists(sa_candidate):
                sa_candidate = d

            self.cfg["streaming_assets"] = sa_candidate
            save_config(self.cfg)
            self._check_environment()
            self.log(f"[OK] Target game directory switched to: {d}")
            messagebox.showinfo("Game Directory Updated", f"Target game directory set to:\n{d}\nStreamingAssets: {sa_candidate}")

    def _check_environment(self):
        gr = self.cfg.get("game_root", "")
        if os.path.exists(gr):
            self.lbl_game.configure(text=f"Target Game:  [OK] Found at {gr}", text_color="#2ecc71")
        else:
            self.lbl_game.configure(text=f"Target Game:  [NOT FOUND]", text_color="#e67e22")

        corelib = self.cfg.get("corelib_dll", "")
        if os.path.exists(corelib):
            self.lbl_vfs.configure(text="Native VFS Core (CoreLib.dll):  [OK] Ready", text_color="#2ecc71")
        else:
            self.lbl_vfs.configure(text="Native VFS Core (CoreLib.dll):  [NOT FOUND / Non-Mugen]", text_color="#e67e22")

        anime = self.cfg.get("animestudio_cli", "")
        if os.path.exists(anime):
            self.lbl_anime.configure(text="AnimeStudio Engine:  [OK] Ready", text_color="#2ecc71")
        else:
            self.lbl_anime.configure(text="AnimeStudio Engine:  [NOT FOUND]", text_color="#e67e22")

        vgm = self.cfg.get("vgmstream", "")
        ff = self.cfg.get("ffmpeg", "")
        if os.path.exists(vgm) and os.path.exists(ff):
            self.lbl_wwise.configure(text="Audio Decoders (vgmstream & ffmpeg):  [OK] Ready", text_color="#2ecc71")
        else:
            self.lbl_wwise.configure(text="Audio Decoders:  [PARTIAL OR MISSING]", text_color="#e67e22")

    def _browse_output(self):
        d = filedialog.askdirectory(initialdir=self.output_dir_var.get(), title="Select Output Folder")
        if d:
            self.output_dir_var.set(d)
            self.cfg["output_dir"] = d
            save_config(self.cfg)
            self.catalog = CutsceneCatalog(d, ffmpeg_path=self.cfg.get("ffmpeg"))
            self.player_engine = CutscenePlayerEngine(d, ffmpeg_path=self.cfg.get("ffmpeg"))
            self._reload_catalog()

    def open_output_folder(self):
        out = self.output_dir_var.get()
        os.makedirs(out, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(out)
        else:
            subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", out])

    def log(self, message: str, progress: float = -1.0):
        self.after(0, self._append_log, message, progress)

    def _append_log(self, message: str, progress: float):
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        if progress >= 0.0:
            self.progress_bar.set(progress)

    def _clear_log(self):
        self.log_text.delete("1.0", "end")

    def _run_job(self, target_func):
        if self.is_running:
            messagebox.showwarning("Task Busy", "An extraction job is already running! Please wait or click 'STOP'.\nกำลังมีงานสกัดไฟล์ทำงานอยู่ กรุณารอหรือกดปุ่ม 'STOP'")
            return

        self.is_running = True
        self.status_var.set("Running...")
        self.status_lbl.configure(text_color="#e67e22")
        self.progress_bar.set(0)

        # Enable all stop buttons and highlight them in red
        for btn in self.stop_buttons:
            try:
                btn.configure(state="normal", fg_color="#c0392b", hover_color="#962d22", text="⏹️ STOP (หยุดการสกัด)")
            except Exception:
                pass

        logger = ProgressLogger(callback=self.log)
        self.current_logger = logger

        def worker():
            try:
                target_func(logger)
                if logger.is_cancelled:
                    self.after(0, lambda: self.status_var.set("Cancelled by User"))
                    self.after(0, lambda: self.status_lbl.configure(text_color="#e74c3c"))
                    self.after(0, lambda: self.log("[STOPPED] Extraction was cancelled by user."))
                else:
                    self.after(0, lambda: self.status_var.set("Completed Successfully"))
                    self.after(0, lambda: self.status_lbl.configure(text_color="#2ecc71"))
                    self.after(0, lambda: self.progress_bar.set(1.0))
                self.after(0, self._reload_catalog)
            except InterruptedJobError:
                self.after(0, lambda: self.status_var.set("Cancelled by User"))
                self.after(0, lambda: self.status_lbl.configure(text_color="#e74c3c"))
                self.after(0, lambda: self.log("[STOPPED] Extraction process aborted by user."))
                self.after(0, self._reload_catalog)
            except Exception as e:
                logger.log(f"[EXCEPTION] Task failed: {e}")
                self.after(0, lambda: self.status_var.set("Error"))
                self.after(0, lambda: self.status_lbl.configure(text_color="#e74c3c"))
            finally:
                self.is_running = False
                self.current_logger = None
                self.after(0, self._reset_stop_buttons)

        threading.Thread(target=worker, daemon=True).start()

    def stop_current_job(self):
        """Immediately stop the ongoing extraction job and terminate any active subprocesses."""
        if not self.is_running or not self.current_logger:
            return

        self.log("[!] Stop signal requested. Halting extraction processes...")
        self.status_var.set("Stopping...")
        self.status_lbl.configure(text_color="#e74c3c")

        for btn in self.stop_buttons:
            try:
                btn.configure(state="disabled", fg_color="#d35400", text="⏳ Stopping...")
            except Exception:
                pass

        self.current_logger.cancel()

    def _reset_stop_buttons(self):
        """Reset all stop buttons back to disabled state."""
        for btn in self.stop_buttons:
            try:
                btn.configure(state="disabled", fg_color="#343746", hover_color="#424659", text="⏹️ STOP (หยุดการสกัด)")
            except Exception:
                pass

    # Universal scanner callbacks
    def _scan_universal_videos(self):
        folder = filedialog.askdirectory(title="Select Any Game / Folder to Scan for Videos")
        if not folder:
            return
        def job(logger):
            v = VideoExtractor(self.cfg.get("streaming_assets", folder), self.output_dir_var.get(), ffmpeg_path=self.cfg.get("ffmpeg"), logger=logger)
            v.scan_generic_directory(folder)
        self._run_job(job)

    def _scan_universal_audio(self):
        folder = filedialog.askdirectory(title="Select Any Game / Folder to Scan for Audio/SoundBanks")
        if not folder:
            return
        def job(logger):
            a = AudioExtractor(self.cfg.get("streaming_assets", folder), self.output_dir_var.get(), vgmstream_path=self.cfg["vgmstream"], ffmpeg_path=self.cfg.get("ffmpeg"), logger=logger)
            a.scan_generic_directory(folder)
        self._run_job(job)

    # Job implementations
    def _job_extract_videos(self, logger):
        v = VideoExtractor(self.cfg["streaming_assets"], self.output_dir_var.get(), ffmpeg_path=self.cfg.get("ffmpeg"), logger=logger)
        v.extract_all()

    def _job_extract_login_video(self, logger):
        v = VideoExtractor(self.cfg["streaming_assets"], self.output_dir_var.get(), ffmpeg_path=self.cfg.get("ffmpeg"), logger=logger)
        v.extract_login_video()

    def _job_upscale_videos(self, logger):
        v = VideoExtractor(self.cfg["streaming_assets"], self.output_dir_var.get(), ffmpeg_path=self.cfg.get("ffmpeg"), logger=logger)
        vid_dir = os.path.join(self.output_dir_var.get(), "videos")
        login_v = os.path.join(vid_dir, "login", "v02_login_bg.mp4")
        if os.path.exists(login_v):
            v.upscale_to_4k(login_v)
        gp_dir = os.path.join(vid_dir, "gameplay_and_guides")
        if os.path.exists(gp_dir):
            count = 0
            for root, _, files in os.walk(gp_dir):
                for f in files:
                    if f.endswith(".mp4"):
                        p = os.path.join(root, f)
                        if os.path.getsize(p) > 2 * 1024 * 1024:
                            v.upscale_to_4k(p)
                            count += 1
                            if count >= 3:
                                break
                if count >= 3:
                    break

    def _job_extract_models(self, logger):
        m = ModelExtractor(self.cfg["animestudio_cli"], self.cfg.get("dummy_dlls"), self.output_dir_var.get(), logger=logger)
        target = os.path.join(self.cfg["streaming_assets"], "Blocks")
        m.extract_3d_models(target)

    def _job_extract_textures(self, logger):
        m = ModelExtractor(self.cfg["animestudio_cli"], self.cfg.get("dummy_dlls"), self.output_dir_var.get(), logger=logger)
        target = os.path.join(self.cfg["streaming_assets"], "Blocks")
        m.extract_textures(target)

    def _job_extract_all_audio(self, logger):
        a = AudioExtractor(self.cfg["streaming_assets"], self.output_dir_var.get(), vgmstream_path=self.cfg["vgmstream"], ffmpeg_path=self.cfg.get("ffmpeg"), logger=logger)
        a.extract_all()

    def _job_extract_audio_cat(self, cat, logger):
        a = AudioExtractor(self.cfg["streaming_assets"], self.output_dir_var.get(), vgmstream_path=self.cfg["vgmstream"], ffmpeg_path=self.cfg.get("ffmpeg"), logger=logger)
        a.extract_category(cat)

    def _job_extract_datamine(self, logger):
        d = DatamineExtractor(self.cfg["streaming_assets"], self.cfg["corelib_dll"], self.output_dir_var.get(), logger=logger)
        d.export_all()

    def _job_dump_vfs(self, logger):
        d = DatamineExtractor(self.cfg["streaming_assets"], self.cfg["corelib_dll"], self.output_dir_var.get(), logger=logger)
        d.dump_vfs_manifest()

    def _job_export_world(self, logger):
        d = DatamineExtractor(self.cfg["streaming_assets"], self.cfg["corelib_dll"], self.output_dir_var.get(), logger=logger)
        d.export_world_data()

    def start_extract_all(self):
        def all_worker(logger):
            logger.log("==============================================")
            logger.log("   INFINITELAYGU EXTRACTOR - ALL-IN-ONE PIPELINE")
            logger.log("==============================================")
            logger.log("[STAGE 1/4] Extracting Game Videos...")
            self._job_extract_videos(logger)
            logger.check_cancelled()

            logger.log("\n[STAGE 2/4] Exporting Datamine Tables & VFS...")
            self._job_extract_datamine(logger)
            logger.check_cancelled()

            logger.log("\n[STAGE 3/4] Extracting Voiceovers & BGM...")
            self._job_extract_all_audio(logger)
            logger.check_cancelled()

            logger.log("\n[STAGE 4/4] Extracting 3D Models & Textures...")
            m = ModelExtractor(self.cfg["animestudio_cli"], self.cfg.get("dummy_dlls"), self.output_dir_var.get(), logger=logger)
            target = os.path.join(self.cfg["streaming_assets"], "Blocks")
            m.extract_all_types(target)
            logger.check_cancelled()

            logger.log("\n[SUCCESS] Universal extraction completed successfully!")

        self._run_job(all_worker)

def main():
    app = InfiniteLayguApp()
    app.mainloop()

if __name__ == "__main__":
    main()
