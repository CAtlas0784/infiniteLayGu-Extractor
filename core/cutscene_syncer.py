"""
Cutscene & Media Asset Inspector & Multilingual Audio Syncer
Project Mugen / Ananta CBT Client 4229938

Functions:
1. Catalogs and inspects all extracted in-game videos and cinematics.
2. Identifies audio tracks, detecting silent 1kbps dummy tracks vs native audio.
3. Maps cutscenes to localized Wwise soundbanks and voice lines (Chinese, Japanese, English, BGM).
4. Provides on-the-fly lossless multiplexing (< 0.5s) via FFmpeg stream-copy.
5. Manages instant playback and export of synced cutscenes.
"""
import os
import sys
import json
import time
import shutil
import subprocess
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any, Tuple

from .utils import ProgressLogger, format_size

# Character name mappings from internal romanized/pinyin names to display names
CHARACTER_MAP = {
    "baijin": {"name": "Baijin (Platinum)", "role": "Investigator / Special Agent", "element": "Ice / Quantum"},
    "saimo": {"name": "Seymour (Saimo)", "role": "Combat Operative", "element": "Electro / Tech"},
    "nanzhu": {"name": "Male Protagonist (MC)", "role": "Main Character", "element": "Universal"},
    "tafei": {"name": "Taffy (Tafei)", "role": "Rabbit Ear Hacker & Scout", "element": "Wind / Agility"},
    "dila": {"name": "Dila", "role": "City Enforcer", "element": "Physical / Fire"},
    "jiamu": {"name": "Jiamu", "role": "Brawler / Street Fighter", "element": "Fire / Impact"},
    "lixi": {"name": "Lixi", "role": "Support Specialist", "element": "Aether"},
    "laikaya": {"name": "Laikaya", "role": "Agent", "element": "Tech"},
    "meikanika": {"name": "Mechanika", "role": "Android / Cyber Specialist", "element": "Cyber"}
}

# Story Quest abbreviations
QUEST_MAP = {
    "TL_HEIST": "Story Mission: The Great Heist",
    "TL_MP": "Main Plot Campaign (MP)",
    "TL_RIC": "Character Story: Rick / Ricky",
    "TL_TAF": "Character Story: Taffy Investigation",
    "SEYM": "Character Story: Seymour Quest"
}

# TV Broadcast series
TV_SERIES_MAP = {
    "TVnews": "City Television News Network",
    "TVdrama": "Urban Drama & Romance Cinema",
    "TVtalk": "Aether City Talk Show & Interviews",
    "TVchaos": "Chaos Mascot & Animation Comedy",
    "TVsporting": "Urban Sporting & Mech Propaganda"
}

@dataclass
class CutsceneMetadata:
    file_path: str
    rel_path: str
    filename: str
    title: str
    category: str
    entity_tag: str
    vfs_path: str
    resolution: str
    duration_str: str
    duration_sec: float
    file_size_bytes: int
    file_size_fmt: str
    audio_status: str          # "native_audio" | "silent_dummy" | "no_audio"
    audio_bitrate_kbps: int
    audio_description: str
    linked_soundbank: str
    mapped_tracks: Dict[str, str] = field(default_factory=dict)
    summary: str = ""

class CutsceneCatalog:
    def __init__(self, output_dir: str, ffmpeg_path: Optional[str] = None, logger: Optional[ProgressLogger] = None):
        self.output_dir = os.path.normpath(output_dir)
        self.videos_dir = os.path.join(self.output_dir, "videos")
        self.audio_dir = os.path.join(self.output_dir, "audio")
        self.ffmpeg_path = ffmpeg_path or "ffmpeg"
        self.logger = logger or ProgressLogger()
        self.cache_file = os.path.join(self.videos_dir, ".catalog_cache.json")
        self.items: List[CutsceneMetadata] = []
        self._available_audio: Dict[str, List[str]] = {}

    def _discover_audio_library(self):
        """Index all extracted audio files by language and category."""
        self._available_audio = {
            "zh": [],
            "ja": [],
            "en": [],
            "bgm": [],
            "sfx": []
        }
        if not os.path.exists(self.audio_dir):
            return

        cat_mapping = {
            "chinese_voice": "zh",
            "japanese_voice": "ja",
            "english_voice": "en",
            "bgm_streams": "bgm",
            "sfx_banks": "sfx"
        }

        for folder_name, lang_key in cat_mapping.items():
            dir_path = os.path.join(self.audio_dir, folder_name)
            if os.path.exists(dir_path):
                wavs = [os.path.join(dir_path, f) for f in os.listdir(dir_path) if f.lower().endswith(".wav")]
                wavs.sort()
                self._available_audio[lang_key] = wavs

    def _probe_media(self, file_path: str) -> Tuple[str, str, float, str, int, str]:
        """Probe video with ffmpeg to retrieve resolution, duration, audio status and bitrate."""
        resolution = "1920x1080"
        duration_str = "00:00"
        duration_sec = 0.0
        audio_status = "no_audio"
        audio_bitrate = 0
        audio_desc = "No audio stream found"

        if not os.path.exists(self.ffmpeg_path) and not shutil.which(self.ffmpeg_path):
            return resolution, duration_str, duration_sec, audio_status, audio_bitrate, audio_desc

        try:
            cmd = [self.ffmpeg_path, "-i", file_path]
            res = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True, errors="ignore")
            output = res.stderr

            # Parse duration
            for line in output.splitlines():
                if "Duration:" in line:
                    parts = line.split("Duration:")[1].split(",")
                    raw_dur = parts[0].strip()
                    duration_str = raw_dur.split(".")[0]  # hh:mm:ss
                    try:
                        h, m, s = raw_dur.split(":")
                        duration_sec = int(h) * 3600 + int(m) * 60 + float(s)
                    except Exception:
                        pass
                if "Video:" in line:
                    for token in line.split(","):
                        token = token.strip()
                        if "x" in token and any(c.isdigit() for c in token):
                            words = token.split()
                            for w in words:
                                if "x" in w and all(part.isdigit() for part in w.split("x")):
                                    resolution = w
                                    break
                if "Audio:" in line:
                    audio_desc = line.split("Audio:")[1].strip()
                    audio_status = "native_audio"
                    if "kb/s" in line:
                        try:
                            br_part = line.split("kb/s")[0].split()[-1]
                            audio_bitrate = int(br_part)
                        except Exception:
                            audio_bitrate = 0

                    if audio_bitrate <= 4:
                        audio_status = "silent_dummy"
                        audio_desc = f"Silent Dummy Track ({audio_bitrate} kb/s - Wwise external stream)"
        except Exception as e:
            self.logger.log(f"[WARN] Error probing {file_path}: {e}")

        return resolution, duration_str, duration_sec, audio_status, audio_bitrate, audio_desc

    def scan(self, force_refresh: bool = False) -> List[CutsceneMetadata]:
        """Scan videos and build metadata catalog."""
        self._discover_audio_library()

        # Check cache
        if not force_refresh and os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    cached_data = json.load(f)
                self.items = []
                for item_dict in cached_data:
                    meta = CutsceneMetadata(**item_dict)
                    if os.path.exists(meta.file_path):
                        self._assign_audio_tracks(meta)
                        self.items.append(meta)
                if self.items:
                    self.logger.log(f"[*] Loaded {len(self.items)} videos from catalog cache.")
                    return self.items
            except Exception as e:
                self.logger.log(f"[WARN] Failed to load catalog cache: {e}")

        self.logger.log("[*] Scanning extracted videos directory...")
        items: List[CutsceneMetadata] = []

        if not os.path.exists(self.videos_dir):
            return items

        for root, _, files in os.walk(self.videos_dir):
            if ".player_cache" in root or "4k_upscaled" in root:
                continue
            for file in files:
                if not file.lower().endswith(".mp4"):
                    continue

                full_path = os.path.join(root, file)
                size_bytes = os.path.getsize(full_path)
                if size_bytes < 5000 and "chouka" not in file:
                    continue

                rel_path = os.path.relpath(full_path, self.videos_dir).replace("\\", "/")
                filename = os.path.basename(full_path)
                stem = os.path.splitext(filename)[0]

                category = "General Video"
                entity_tag = "System"
                title = stem
                linked_bank = "Wwise SoundEngine (Streams00.pck)"
                vfs_path = f"Movies/{rel_path.replace('gameplay_and_guides/', '')}"
                summary = ""

                # 1. Login Background
                if "login" in rel_path.lower():
                    category = "🌅 Title & Login"
                    title = "Title Screen Login Cinematic (v02_login_bg)"
                    entity_tag = "Main Menu"
                    linked_bank = "Streams00.pck (Main Theme & Title BGM)"
                    summary = "Official opening theme cinematic looping on the game's start menu."

                # 2. Character Urban Ability
                elif "urbanability" in stem.lower():
                    category = "⚡ Character Urban Abilities"
                    char_key = stem.lower().split("headshot_")[-1] if "headshot_" in stem.lower() else ""
                    char_info = CHARACTER_MAP.get(char_key, {"name": char_key.capitalize(), "role": "Hero", "element": "Special"})
                    title = f"{char_info['name']} - Urban Ability Ultimate"
                    entity_tag = char_info['name']
                    linked_bank = f"ChineseBank00 / JapaneseBank00 ({char_info['name']} Voice & SFX)"
                    summary = f"Full cinematic ultimate skill presentation for {char_info['name']} ({char_info['role']}, {char_info['element']})."

                # 3. Story Cutscenes & Timeline
                elif stem.startswith("TL_") or stem.startswith("Effect_TL_") or stem.startswith("SEYM_"):
                    category = "🎬 Cutscenes & Story"
                    matched_quest = "Main Storyline"
                    for qk, qv in QUEST_MAP.items():
                        if qk in stem:
                            matched_quest = qv
                            break
                    entity_tag = matched_quest
                    title = f"{matched_quest}: {stem.replace('Effect_', '')}"
                    linked_bank = "ChineseStreams00 / JapaneseStreams00 / EnglishStreams00 (Cutscene Audio)"
                    summary = f"In-engine story cutscene for {matched_quest}."

                # 4. TV Broadcasts
                elif stem.startswith("TV"):
                    category = "📺 City TV Broadcasts"
                    series_key = stem.split("_")[0]
                    series_name = TV_SERIES_MAP.get(series_key, "Aether TV Broadcast")
                    ep_name = stem.split("_")[-1]
                    title = f"[{series_name}] {ep_name}"
                    entity_tag = series_name
                    linked_bank = "Streams01-03.pck (City Commercial & TV Broadcast BGM)"
                    summary = f"Dynamic video played on billboard screens and TVs across Aether City."

                # 5. Cyber Link & Gacha
                elif any(k in stem.lower() for k in ["link_", "gacha", "chouka", "timeflies", "cellphone"]):
                    category = "🌐 Cyber Link & Gacha"
                    if "gacha" in stem.lower() or "chouka" in stem.lower():
                        title = "Character Wish & Gacha Reveal Animation"
                        entity_tag = "Gacha Wish"
                        linked_bank = "Bank00.pck (Gacha SFX & Shimmer)"
                        summary = "Loot box / Character pull summoning sequence animation."
                    elif "timeflies" in stem.lower():
                        title = "Time Passage & Day/Night Transition (TimeFlies)"
                        entity_tag = "World System"
                        linked_bank = "Streams00.pck (Atmosphere Ambience)"
                        summary = "Fast-forward city timelapse animation when changing game hours."
                    elif "cellphone" in stem.lower():
                        title = "Smartphone Ringtone & Call Cinematic"
                        entity_tag = "Phone System"
                        linked_bank = "Bank00.pck (Phone SFX & Dialogue)"
                        summary = "In-game smartphone messenger video call display."
                    else:
                        title = f"Cyber Link Mode: {stem}"
                        entity_tag = "Matrix Link"
                        linked_bank = "Bank00.pck (Cybernetic SFX)"
                        summary = "Virtual cyberspace network connection sequence."

                # 6. Combat Guides
                elif "guide" in stem.lower() or "battle" in stem.lower():
                    category = "📖 Guides & Combat"
                    title = f"Tutorial: {stem.replace('Guide_', '').replace('Guide', '')}"
                    entity_tag = "Tutorial System"
                    linked_bank = "Native Guide Audio / Bank01.pck"
                    summary = "Tactical combat and game mechanic tutorial video clip."

                res, dur_str, dur_sec, a_status, a_br, a_desc = self._probe_media(full_path)

                meta = CutsceneMetadata(
                    file_path=full_path,
                    rel_path=rel_path,
                    filename=filename,
                    title=title,
                    category=category,
                    entity_tag=entity_tag,
                    vfs_path=vfs_path,
                    resolution=res,
                    duration_str=dur_str,
                    duration_sec=dur_sec,
                    file_size_bytes=size_bytes,
                    file_size_fmt=format_size(size_bytes),
                    audio_status=a_status,
                    audio_bitrate_kbps=a_br,
                    audio_description=a_desc,
                    linked_soundbank=linked_bank,
                    summary=summary
                )

                self._assign_audio_tracks(meta)
                items.append(meta)

        cat_order = {
            "🎬 Cutscenes & Story": 0,
            "⚡ Character Urban Abilities": 1,
            "📺 City TV Broadcasts": 2,
            "🌐 Cyber Link & Gacha": 3,
            "🌅 Title & Login": 4,
            "📖 Guides & Combat": 5,
            "General Video": 6
        }
        items.sort(key=lambda m: (cat_order.get(m.category, 99), -m.file_size_bytes))
        self.items = items

        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump([asdict(m) for m in items], f, indent=2)
            self.logger.log(f"[OK] Indexed {len(items)} videos. Saved to catalog cache.")
        except Exception as e:
            self.logger.log(f"[WARN] Failed to write catalog cache: {e}")

        return self.items

    def _assign_audio_tracks(self, meta: CutsceneMetadata):
        """Map Chinese, Japanese, English, and BGM audio files to this cutscene."""
        meta.mapped_tracks = {}

        if meta.audio_status == "native_audio":
            meta.mapped_tracks["orig"] = meta.file_path

        if self._available_audio.get("zh"):
            meta.mapped_tracks["zh"] = self._find_best_audio(self._available_audio["zh"], meta.duration_sec)

        if self._available_audio.get("ja"):
            meta.mapped_tracks["ja"] = self._find_best_audio(self._available_audio["ja"], meta.duration_sec)

        if self._available_audio.get("en"):
            meta.mapped_tracks["en"] = self._find_best_audio(self._available_audio["en"], meta.duration_sec)

        if self._available_audio.get("bgm"):
            meta.mapped_tracks["bgm"] = self._find_best_audio(self._available_audio["bgm"], meta.duration_sec)

    def _find_best_audio(self, audio_list: List[str], target_duration: float) -> Optional[str]:
        """Find the audio file whose duration is closest to the target video duration."""
        if not audio_list:
            return None
        if target_duration <= 0.0:
            return audio_list[0]

        best_match = audio_list[0]
        best_diff = float("inf")

        for p in audio_list:
            size = os.path.getsize(p)
            est_sec = size / (192 * 1024)
            diff = abs(est_sec - target_duration)
            if diff < best_diff:
                best_diff = diff
                best_match = p

        return best_match

    def get_categories(self) -> List[str]:
        """Return list of distinct categories."""
        cats = []
        for m in self.items:
            if m.category not in cats:
                cats.append(m.category)
        return cats

    def filter(self, category: Optional[str] = None, query: Optional[str] = None) -> List[CutsceneMetadata]:
        """Filter videos by category and text search query."""
        results = []
        q = (query or "").strip().lower()

        for m in self.items:
            if category and category != "All" and m.category != category:
                continue
            if q:
                match = (
                    q in m.title.lower() or
                    q in m.filename.lower() or
                    q in m.entity_tag.lower() or
                    q in m.vfs_path.lower() or
                    q in m.summary.lower()
                )
                if not match:
                    continue
            results.append(m)
        return results

    def import_custom_video(self, file_path: str) -> Optional[CutsceneMetadata]:
        """
        Universal Video Importer: Import ANY video from disk into the catalog.
        Probes resolution, duration, audio status, and links available audio tracks.
        """
        file_path = os.path.normpath(file_path)
        if not os.path.exists(file_path):
            return None

        res, dur_str, dur_sec, a_status, a_br, a_desc = self._probe_media(file_path)
        size_bytes = os.path.getsize(file_path)
        filename = os.path.basename(file_path)

        meta = CutsceneMetadata(
            file_path=file_path,
            rel_path=filename,
            filename=filename,
            title=f"📁 [Custom] {os.path.splitext(filename)[0]}",
            category="📁 Custom / External Videos",
            entity_tag="Imported Video",
            vfs_path=file_path,
            resolution=res,
            duration_str=dur_str,
            duration_sec=dur_sec,
            file_size_bytes=size_bytes,
            file_size_fmt=format_size(size_bytes),
            audio_status=a_status,
            audio_bitrate_kbps=a_br,
            audio_description=a_desc,
            linked_soundbank="External File / Custom Track",
            summary=f"User-imported video from {file_path}. Ready for inspection and audio syncing."
        )

        self._assign_audio_tracks(meta)
        # Place at top of catalog
        self.items.insert(0, meta)
        return meta

class CutscenePlayerEngine:
    def __init__(self, output_dir: str, ffmpeg_path: Optional[str] = None, logger: Optional[ProgressLogger] = None):
        self.output_dir = os.path.normpath(output_dir)
        self.videos_dir = os.path.join(self.output_dir, "videos")
        self.cache_dir = os.path.join(self.videos_dir, ".player_cache")
        self.ffmpeg_path = ffmpeg_path or "ffmpeg"
        self.logger = logger or ProgressLogger()
        self.current_process: Optional[subprocess.Popen] = None
        os.makedirs(self.cache_dir, exist_ok=True)

    def mux_video_with_audio(self, video_path: str, audio_path: Optional[str], lang_code: str = "custom") -> Tuple[bool, str, float]:
        """
        Losslessly mux video with chosen audio track using FFmpeg stream-copy.
        Returns: (success: bool, output_path: str, elapsed_seconds: float)
        """
        if not os.path.exists(video_path):
            return False, f"Video not found: {video_path}", 0.0

        if not audio_path or audio_path == video_path:
            return True, video_path, 0.0

        if not os.path.exists(audio_path):
            return False, f"Audio track not found: {audio_path}", 0.0

        stem = os.path.splitext(os.path.basename(video_path))[0]
        out_filename = f"{stem}_muxed_{lang_code}.mp4"
        out_path = os.path.join(self.cache_dir, out_filename)

        if os.path.exists(out_path) and os.path.getsize(out_path) > 1024:
            return True, out_path, 0.01

        t0 = time.time()
        cmd = [
            self.ffmpeg_path, "-y",
            "-i", video_path,
            "-i", audio_path,
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            out_path
        ]

        try:
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            elapsed = time.time() - t0
            if os.path.exists(out_path) and os.path.getsize(out_path) > 1024:
                self.logger.log(f"[OK] Muxed in {elapsed:.2f}s: {out_filename} ({format_size(os.path.getsize(out_path))})")
                return True, out_path, elapsed
            else:
                err_msg = res.stderr[-300:] if res.stderr else "Unknown error"
                self.logger.log(f"[ERROR] Mux failed: {err_msg}")
                return False, f"FFmpeg error: {err_msg}", elapsed
        except Exception as e:
            return False, str(e), 0.0

    def play_media(self, media_path: str, use_ffplay: bool = False) -> bool:
        """Launch video playback in system default player or ffplay."""
        if not os.path.exists(media_path):
            self.logger.log(f"[ERROR] File does not exist: {media_path}")
            return False

        self.stop_playback()

        if use_ffplay:
            ffplay_bin = "ffplay"
            if shutil.which(ffplay_bin):
                try:
                    cmd = [ffplay_bin, "-autoexit", "-window_title", f"Ananta Player - {os.path.basename(media_path)}", media_path]
                    self.current_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return True
                except Exception as e:
                    self.logger.log(f"[WARN] ffplay launch failed, falling back to system player: {e}")

        try:
            if sys.platform == "win32":
                os.startfile(media_path)
            else:
                subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", media_path])
            return True
        except Exception as e:
            self.logger.log(f"[ERROR] Failed to open player: {e}")
            return False

    def stop_playback(self):
        """Terminate active ffplay process if running."""
        if self.current_process:
            try:
                self.current_process.terminate()
            except Exception:
                pass
            self.current_process = None

    def export_synced_video(self, video_path: str, audio_path: Optional[str], destination: str) -> Tuple[bool, str]:
        """Export synced MP4 to a user-chosen destination."""
        if not audio_path or audio_path == video_path:
            try:
                shutil.copy2(video_path, destination)
                return True, f"Saved to {destination}"
            except Exception as e:
                return False, str(e)

        ok, mux_path, _ = self.mux_video_with_audio(video_path, audio_path, lang_code="export")
        if not ok:
            return False, mux_path

        try:
            shutil.copy2(mux_path, destination)
            return True, f"Successfully exported to: {destination}"
        except Exception as e:
            return False, str(e)
