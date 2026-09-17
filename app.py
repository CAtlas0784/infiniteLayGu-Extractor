"""
Ananta Unified Asset Extractor & Dataminer - 4K High-DPI Modern Desktop UI
Built with CustomTkinter for vector-sharp typography and native 4K scaling.
Includes:
- Full Asset Extraction Engine (Videos, 3D Models, Audio/Voices, Datamine)
- In-App Cutscene Player & Asset Dependency Inspector with Multilingual Audio Syncing
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

from core.utils import load_config, save_config, resolve_path, format_size, ProgressLogger
from core.video_extractor import VideoExtractor
from core.audio_extractor import AudioExtractor
from core.model_extractor import ModelExtractor
from core.datamine_extractor import DatamineExtractor
from core.cutscene_syncer import CutsceneCatalog, CutscenePlayerEngine, CutsceneMetadata

# Set modern dark appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class ModernExtractorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Ananta Asset Suite & Cutscene Player (Client 4229938)")
        self.geometry("1180x820")
        self.minsize(1050, 720)

        # Force High-DPI scaling check
        self.scaling = ctk.ScalingTracker.get_widget_scaling(self)
        
        self.cfg = load_config()
        self.output_dir_var = ctk.StringVar(value=resolve_path(self.cfg.get("output_dir", "output")))
        self.status_var = ctk.StringVar(value="Ready")
        self.is_running = False

        # Cutscene Player state
        self.catalog = CutsceneCatalog(self.output_dir_var.get(), ffmpeg_path=self.cfg.get("ffmpeg"))
        self.player_engine = CutscenePlayerEngine(self.output_dir_var.get(), ffmpeg_path=self.cfg.get("ffmpeg"))
        self.selected_cutscene: Optional[CutsceneMetadata] = None
        self.selected_lang_var = ctk.StringVar(value="ja")  # default Japanese
        self.player_status_var = ctk.StringVar(value="Select a cutscene from the list to inspect and play")
        self.search_query_var = ctk.StringVar(value="")
        self.cat_filter_var = ctk.StringVar(value="All")
        self.video_card_buttons: List[ctk.CTkButton] = []

        self._build_ui()
        self._check_environment()
        self._init_player_catalog()

    def _build_ui(self):
        # 1. Top Header Banner
        header = ctk.CTkFrame(self, height=80, corner_radius=12, fg_color=("#1e2029", "#181920"))
        header.pack(fill="x", padx=16, pady=(14, 10))

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left", padx=20, pady=10)

        title_lbl = ctk.CTkLabel(title_box, text="PROJECT MUGEN / ANANTA ASSET EXTRACTOR", font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"))
        title_lbl.pack(anchor="w")

        sub_lbl = ctk.CTkLabel(title_box, text="4K Ultra-Sharp Edition | Datamining & Cutscene Inspector Suite", font=ctk.CTkFont(family="Segoe UI", size=12), text_color="#8c909e")
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

        # Environment Status Card
        env_card = ctk.CTkFrame(p, corner_radius=10, fg_color="#242631")
        env_card.pack(fill="x", padx=12, pady=10)

        card_title = ctk.CTkLabel(env_card, text="Game Engine & Decoders Status", font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"))
        card_title.pack(anchor="w", padx=16, pady=(12, 6))

        self.lbl_game = ctk.CTkLabel(env_card, text="Game Directory: Checking...", font=ctk.CTkFont(family="Segoe UI", size=12), text_color="#8c909e", anchor="w")
        self.lbl_game.pack(fill="x", padx=16, pady=2)

        self.lbl_vfs = ctk.CTkLabel(env_card, text="Native VFS Core (CoreLib.dll): Checking...", font=ctk.CTkFont(family="Segoe UI", size=12), text_color="#8c909e", anchor="w")
        self.lbl_vfs.pack(fill="x", padx=16, pady=2)

        self.lbl_anime = ctk.CTkLabel(env_card, text="AnimeStudio Engine: Checking...", font=ctk.CTkFont(family="Segoe UI", size=12), text_color="#8c909e", anchor="w")
        self.lbl_anime.pack(fill="x", padx=16, pady=2)

        self.lbl_wwise = ctk.CTkLabel(env_card, text="Audio Tools (vgmstream & ffmpeg): Checking...", font=ctk.CTkFont(family="Segoe UI", size=12), text_color="#8c909e", anchor="w")
        self.lbl_wwise.pack(fill="x", padx=16, pady=(2, 12))

        # Output Destination Card
        dest_card = ctk.CTkFrame(p, corner_radius=10, fg_color="#242631")
        dest_card.pack(fill="x", padx=12, pady=6)

        dest_title = ctk.CTkLabel(dest_card, text="Extraction Destination Folder", font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"))
        dest_title.pack(anchor="w", padx=16, pady=(10, 4))

        dest_row = ctk.CTkFrame(dest_card, fg_color="transparent")
        dest_row.pack(fill="x", padx=16, pady=(0, 12))

        dest_entry = ctk.CTkEntry(dest_row, textvariable=self.output_dir_var, font=ctk.CTkFont(family="Segoe UI", size=12), height=34)
        dest_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        browse_btn = ctk.CTkButton(dest_row, text="Browse...", font=ctk.CTkFont(family="Segoe UI", size=12), width=100, height=34,
                                   fg_color="#343746", hover_color="#424659",
                                   command=self._browse_output)
        browse_btn.pack(side="right")

        # Big All-in-One Button
        action_box = ctk.CTkFrame(p, fg_color="transparent")
        action_box.pack(fill="x", padx=12, pady=16)

        btn_all = ctk.CTkButton(action_box, text="⚡ EXTRACT EVERYTHING (ALL-IN-ONE)",
                                font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
                                fg_color="#27ae60", hover_color="#219150", height=48, corner_radius=10,
                                command=self.start_extract_all)
        btn_all.pack(fill="x")

    # =========================================================================
    # TAB 2: CUTSCENE PLAYER & ASSET INSPECTOR
    # =========================================================================
    def _build_player_tab(self):
        p = self.tab_play

        # Container with 2 columns: Left (Browser) and Right (Inspector & Player)
        container = ctk.CTkFrame(p, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=8, pady=8)

        # ------------------ LEFT COLUMN: VIDEO BROWSER ------------------
        left_pane = ctk.CTkFrame(container, width=420, corner_radius=10, fg_color="#1e2029")
        left_pane.pack(side="left", fill="both", padx=(0, 8), pady=0)
        left_pane.pack_propagate(False)

        # Filter & Search Header
        filter_header = ctk.CTkFrame(left_pane, fg_color="transparent")
        filter_header.pack(fill="x", padx=10, pady=(10, 6))

        # Category dropdown
        cat_lbl = ctk.CTkLabel(filter_header, text="Category Filter:", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#8c909e")
        cat_lbl.pack(anchor="w", padx=2, pady=(0, 2))

        self.cat_menu = ctk.CTkOptionMenu(filter_header, values=["All"], variable=self.cat_filter_var,
                                          font=ctk.CTkFont(family="Segoe UI", size=11), height=28,
                                          fg_color="#2c2e38", button_color="#383a47",
                                          command=lambda _: self._update_video_list())
        self.cat_menu.pack(fill="x", pady=(0, 6))

        # Search box
        search_box = ctk.CTkFrame(filter_header, fg_color="transparent")
        search_box.pack(fill="x")

        search_entry = ctk.CTkEntry(search_box, textvariable=self.search_query_var, placeholder_text="🔍 Search character, quest, or file...",
                                    font=ctk.CTkFont(family="Segoe UI", size=11), height=30)
        search_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.search_query_var.trace_add("write", lambda *_: self._update_video_list())

        refresh_btn = ctk.CTkButton(search_box, text="🔄", width=30, height=30,
                                    fg_color="#2c2e38", hover_color="#383a47",
                                    command=self._reload_catalog)
        refresh_btn.pack(side="right")

        # Scrollable list of cutscenes
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
        bank_title = ctk.CTkLabel(grid_frame, text="Linked Wwise Bank:", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#8c909e", width=140, anchor="w")
        bank_title.grid(row=4, column=0, sticky="w", pady=2)
        self.lbl_meta_bank = ctk.CTkLabel(grid_frame, text="-", font=ctk.CTkFont(family="Segoe UI", size=12), text_color="#9b59b6", anchor="w")
        self.lbl_meta_bank.grid(row=4, column=1, sticky="w", pady=2)

        # Summary text
        self.lbl_meta_summary = ctk.CTkLabel(self.insp_frame, text="Select any cutscene to examine asset dependencies and playback audio options.",
                                             font=ctk.CTkFont(family="Segoe UI", size=11), text_color="#8c909e", justify="left", wraplength=620, anchor="w")
        self.lbl_meta_summary.pack(fill="x", padx=14, pady=(0, 12))

        # 2. Audio Track & Language Selector Card
        lang_card = ctk.CTkFrame(right_pane, corner_radius=10, fg_color="#242631")
        lang_card.pack(fill="x", padx=12, pady=6)

        lang_title = ctk.CTkLabel(lang_card, text="Multilingual Voice Track Selector (เลือกภาษาเสียง):",
                                  font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"))
        lang_title.pack(anchor="w", padx=14, pady=(10, 6))

        # Segmented Button for languages
        self.lang_seg = ctk.CTkSegmentedButton(lang_card,
                                              values=["🇯🇵 日本語 (JP)", "🇨🇳 中文 (CN)", "🇺🇸 English (EN)", "🎼 BGM Only", "🎬 Original"],
                                              font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                                              height=36,
                                              command=self._on_lang_segmented_change)
        self.lang_seg.pack(fill="x", padx=14, pady=4)
        self.lang_seg.set("🇯🇵 日本語 (JP)")

        # Current audio file description
        self.lbl_current_audio_track = ctk.CTkLabel(lang_card, text="Audio Track: Ready",
                                                    font=ctk.CTkFont(family="Consolas", size=11),
                                                    text_color="#2ecc71", anchor="w")
        self.lbl_current_audio_track.pack(fill="x", padx=14, pady=(4, 10))

        # 3. Action Buttons & Controls Card
        action_card = ctk.CTkFrame(right_pane, corner_radius=10, fg_color="#242631")
        action_card.pack(fill="x", padx=12, pady=6)

        btn_grid = ctk.CTkFrame(action_card, fg_color="transparent")
        btn_grid.pack(fill="x", padx=14, pady=12)

        self.btn_play = ctk.CTkButton(btn_grid, text="▶️ เล่นวิดีโอพร้อมเสียง (Play with Audio)",
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
                self.after(0, self._update_video_list)
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
                self.after(0, self._update_video_list)
                self.after(0, lambda: self.player_status_var.set("Catalog refreshed successfully!"))
            except Exception as e:
                self.after(0, lambda: self.player_status_var.set(f"Rescan error: {e}"))
        threading.Thread(target=rescan, daemon=True).start()

    def _update_video_list(self):
        """Update scrollable list based on category and search query."""
        for widget in self.video_list_frame.winfo_children():
            widget.destroy()

        category = self.cat_filter_var.get()
        query = self.search_query_var.get()
        filtered = self.catalog.filter(category=category, query=query)

        self.video_card_buttons = []

        for item in filtered:
            card = ctk.CTkFrame(self.video_list_frame, corner_radius=8, fg_color="#242631")
            card.pack(fill="x", pady=4, padx=2)

            # Top row: Title and audio badge
            top_row = ctk.CTkFrame(card, fg_color="transparent")
            top_row.pack(fill="x", padx=10, pady=(8, 2))

            title_lbl = ctk.CTkLabel(top_row, text=item.title, font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                                     anchor="w", text_color="#ffffff")
            title_lbl.pack(side="left", fill="x", expand=True)

            # Badge
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

            # Sub row: Details (Duration, Size, Category)
            sub_row = ctk.CTkFrame(card, fg_color="transparent")
            sub_row.pack(fill="x", padx=10, pady=(0, 6))

            info_text = f"⏱️ {item.duration_str}  |  💾 {item.file_size_fmt}  |  {item.resolution}"
            info_lbl = ctk.CTkLabel(sub_row, text=info_text, font=ctk.CTkFont(family="Segoe UI", size=10), text_color="#8c909e", anchor="w")
            info_lbl.pack(side="left")

            # Make card clickable
            def make_click_handler(meta):
                return lambda e: self._select_cutscene(meta)

            card.bind("<Button-1>", make_click_handler(item))
            title_lbl.bind("<Button-1>", make_click_handler(item))
            info_lbl.bind("<Button-1>", make_click_handler(item))

    def _select_cutscene(self, meta: CutsceneMetadata):
        """Display selected cutscene details in the right inspector pane."""
        self.selected_cutscene = meta

        self.insp_title_lbl.configure(text=meta.title)
        self.lbl_meta_vfs.configure(text=meta.vfs_path)
        self.lbl_meta_tag.configure(text=f"{meta.entity_tag} ({meta.category})")
        self.lbl_meta_specs.configure(text=f"{meta.resolution} | Duration: {meta.duration_str} | Size: {meta.file_size_fmt}")
        
        # Audio status label
        if meta.audio_status == "native_audio":
            self.lbl_meta_audio.configure(text=f"Native Track Present ({meta.audio_bitrate_kbps} kb/s) - {meta.audio_description}", text_color="#2ecc71")
            self.insp_badge_lbl.configure(text="🔊 Native Audio Ready", fg_color="#27ae60")
        elif meta.audio_status == "silent_dummy":
            self.lbl_meta_audio.configure(text=f"Silent Dummy Track ({meta.audio_bitrate_kbps} kb/s) - Voice streamed dynamically via Wwise", text_color="#e67e22")
            self.insp_badge_lbl.configure(text="🔇 Requires Audio Sync", fg_color="#d35400")
        else:
            self.lbl_meta_audio.configure(text="No embedded audio stream", text_color="#7f8c8d")
            self.insp_badge_lbl.configure(text="🔇 Silent Video", fg_color="#7f8c8d")

        self.lbl_meta_bank.configure(text=meta.linked_soundbank)
        self.lbl_meta_summary.configure(text=meta.summary or f"Extracted video from {meta.rel_path}")

        # Update audio track label based on selected language
        self._update_audio_selection_display()

        self.player_status_var.set(f"Ready: {meta.filename}\nSelect your preferred language track, then click Play or Export.")

    def _on_lang_segmented_change(self, value):
        """Map segmented button choice to language key."""
        lang_map = {
            "🇯🇵 日本語 (JP)": "ja",
            "🇨🇳 中文 (CN)": "zh",
            "🇺🇸 English (EN)": "en",
            "🎼 BGM Only": "bgm",
            "🎬 Original": "orig"
        }
        key = lang_map.get(value, "ja")
        self.selected_lang_var.set(key)
        self._update_audio_selection_display()

    def _update_audio_selection_display(self):
        """Update label showing which audio file will be used."""
        if not self.selected_cutscene:
            return

        lang = self.selected_lang_var.get()
        tracks = self.selected_cutscene.mapped_tracks

        if lang == "orig":
            if self.selected_cutscene.audio_status == "native_audio":
                self.lbl_current_audio_track.configure(text="Using: Original embedded native audio track", text_color="#2ecc71")
            else:
                self.lbl_current_audio_track.configure(text="Warning: Original track is silent/dummy! Recommend picking JP, CN, or EN.", text_color="#e67e22")
            return

        track_path = tracks.get(lang)
        if track_path and os.path.exists(track_path):
            name = os.path.basename(track_path)
            size = format_size(os.path.getsize(track_path))
            self.lbl_current_audio_track.configure(text=f"Linked Audio: {name} ({size}) [Synced & Ready]", text_color="#2ecc71")
        else:
            self.lbl_current_audio_track.configure(text=f"Notice: No extracted track found for '{lang}'. Will fallback to original or BGM.", text_color="#e67e22")

    def _play_current_cutscene(self):
        """Losslessly mux and play cutscene immediately."""
        if not self.selected_cutscene:
            messagebox.showinfo("No Video", "Please select a cutscene from the list first.")
            return

        meta = self.selected_cutscene
        lang = self.selected_lang_var.get()
        audio_path = meta.mapped_tracks.get(lang) if lang != "orig" else None

        self.btn_play.configure(state="disabled", text="⏳ Muxing Audio...")
        self.player_status_var.set(f"⚡ Muxing video '{meta.filename}' with {lang.upper()} audio track via FFmpeg...")

        def worker():
            t0 = time.time()
            ok, media_path, elapsed = self.player_engine.mux_video_with_audio(meta.file_path, audio_path, lang_code=lang)
            if ok:
                self.after(0, lambda: self.player_status_var.set(f"✅ Muxed in {elapsed:.2f}s! Launching media player...\nPlaying: {os.path.basename(media_path)}"))
                self.player_engine.play_media(media_path)
            else:
                self.after(0, lambda: self.player_status_var.set(f"❌ Playback failed: {media_path}"))
            self.after(0, lambda: self.btn_play.configure(state="normal", text="▶️ เล่นวิดีโอพร้อมเสียง (Play with Audio)"))

        threading.Thread(target=worker, daemon=True).start()

    def _export_current_cutscene(self):
        """Export synced MP4 to custom location."""
        if not self.selected_cutscene:
            messagebox.showinfo("No Video", "Please select a cutscene first.")
            return

        meta = self.selected_cutscene
        lang = self.selected_lang_var.get()
        audio_path = meta.mapped_tracks.get(lang) if lang != "orig" else None

        stem = os.path.splitext(meta.filename)[0]
        default_name = f"{stem}_synced_{lang}.mp4"

        dest = filedialog.asksaveasfilename(initialfile=default_name,
                                            defaultextension=".mp4",
                                            filetypes=[("MP4 Video", "*.mp4"), ("All Files", "*.*")],
                                            title="Export Synced Video With Audio")
        if not dest:
            return

        self.btn_export.configure(state="disabled", text="⏳ Exporting...")
        self.player_status_var.set(f"Exporting synced MP4 to {dest}...")

        def worker():
            ok, msg = self.player_engine.export_synced_video(meta.file_path, audio_path, dest)
            if ok:
                self.after(0, lambda: self.player_status_var.set(f"✅ Export completed!\nSaved to: {dest}"))
                self.after(0, lambda: messagebox.showinfo("Export Successful", f"Cutscene saved with synced audio!\n\nDestination:\n{dest}"))
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

        desc = ctk.CTkLabel(p, text="Extract all in-game videos, cutscenes, and character skill tutorials.\nIncludes 186+ raw MP4 videos discovered inside numPath, login background videos, and 4K upscaling.",
                            font=ctk.CTkFont(family="Segoe UI", size=13), text_color="#8c909e", justify="left")
        desc.pack(anchor="w", padx=16, pady=(16, 12))

        btn_vids = ctk.CTkButton(p, text="🎬 Extract All Gameplay & Guide Videos (numPath 186+ Clips)",
                                 font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
                                 fg_color="#2980b9", hover_color="#20638f", height=44, corner_radius=8,
                                 command=lambda: self._run_job(self._job_extract_videos))
        btn_vids.pack(fill="x", padx=16, pady=8)

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

    # =========================================================================
    # TAB 5: AUDIO & VOICES
    # =========================================================================
    def _build_audio_tab(self):
        p = self.tab_audi

        desc = ctk.CTkLabel(p, text="Unpack Wwise SoundBanks (*.pck) and convert voice lines & background music to WAV.",
                            font=ctk.CTkFont(family="Segoe UI", size=13), text_color="#8c909e", justify="left")
        desc.pack(anchor="w", padx=16, pady=(16, 12))

        btn_all_audio = ctk.CTkButton(p, text="🎵 Extract All Audio (Voices + BGM + SFX)",
                                      font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
                                      fg_color="#d35400", hover_color="#a04000", height=44, corner_radius=8,
                                      command=lambda: self._run_job(self._job_extract_all_audio))
        btn_all_audio.pack(fill="x", padx=16, pady=8)

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

    # =========================================================================
    # HELPERS & SYSTEM CALLS
    # =========================================================================
    def _check_environment(self):
        gr = self.cfg.get("game_root", "")
        if os.path.exists(gr):
            self.lbl_game.configure(text=f"Game Client:  [OK] Found at {gr}", text_color="#2ecc71")
        else:
            self.lbl_game.configure(text=f"Game Client:  [NOT FOUND]", text_color="#e67e22")

        corelib = self.cfg.get("corelib_dll", "")
        if os.path.exists(corelib):
            self.lbl_vfs.configure(text="Native VFS Core (CoreLib.dll):  [OK] Ready", text_color="#2ecc71")
        else:
            self.lbl_vfs.configure(text="Native VFS Core (CoreLib.dll):  [NOT FOUND]", text_color="#e67e22")

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
            messagebox.showwarning("Task Busy", "An extraction job is already running! Please wait.")
            return

        self.is_running = True
        self.status_var.set("Running...")
        self.status_lbl.configure(text_color="#e67e22")
        self.progress_bar.set(0)

        logger = ProgressLogger(callback=self.log)

        def worker():
            try:
                target_func(logger)
                self.after(0, lambda: self.status_var.set("Completed Successfully"))
                self.after(0, lambda: self.status_lbl.configure(text_color="#2ecc71"))
                self.after(0, lambda: self.progress_bar.set(1.0))
                # Refresh player catalog after extraction
                self.after(0, self._reload_catalog)
            except Exception as e:
                logger.log(f"[EXCEPTION] Task failed: {e}")
                self.after(0, lambda: self.status_var.set("Error"))
                self.after(0, lambda: self.status_lbl.configure(text_color="#e74c3c"))
            finally:
                self.is_running = False

        threading.Thread(target=worker, daemon=True).start()

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
            logger.log("   STARTING ALL-IN-ONE EXTRACTION PIPELINE")
            logger.log("==============================================")
            logger.log("[STAGE 1/4] Extracting Game Videos...")
            self._job_extract_videos(logger)

            logger.log("\n[STAGE 2/4] Exporting Datamine Tables & VFS...")
            self._job_extract_datamine(logger)

            logger.log("\n[STAGE 3/4] Extracting Voiceovers & BGM...")
            self._job_extract_all_audio(logger)

            logger.log("\n[STAGE 4/4] Extracting 3D Models & Textures...")
            m = ModelExtractor(self.cfg["animestudio_cli"], self.cfg.get("dummy_dlls"), self.output_dir_var.get(), logger=logger)
            target = os.path.join(self.cfg["streaming_assets"], "Blocks")
            m.extract_all_types(target)

            logger.log("\n[SUCCESS] All-in-one extraction completed successfully!")

        self._run_job(all_worker)

def main():
    app = ModernExtractorApp()
    app.mainloop()

if __name__ == "__main__":
    main()
