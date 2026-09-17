"""
Video Extraction Module for Project Mugen / Ananta CBT
Extracts:
1. 186+ hidden gameplay & guide MP4 video streams inside StreamingAssets/numPath
2. Login cutscene background (v02_login_bg.mp4)
3. Movie paths from 746192410294089491.data
4. Any other embedded MP4, USM, BK2, or WebM media
"""
import os
import sys
import shutil
import subprocess
from typing import Optional, List, Dict, Tuple
from .utils import ProgressLogger, format_size

class VideoExtractor:
    def __init__(self, streaming_assets: str, output_dir: str, ffmpeg_path: Optional[str] = None, logger: Optional[ProgressLogger] = None):
        self.streaming_assets = os.path.normpath(streaming_assets)
        self.output_dir = os.path.normpath(os.path.join(output_dir, "videos"))
        self.ffmpeg_path = ffmpeg_path if (ffmpeg_path and os.path.exists(ffmpeg_path)) else None
        self.logger = logger or ProgressLogger()

    def _read_movie_path_list(self) -> List[str]:
        """Read the list of internal movie paths if available."""
        paths = []
        numpath_dir = os.path.join(self.streaming_assets, "numPath")
        if not os.path.exists(numpath_dir):
            return paths

        target_file = "746192410294089491.data"
        found_path = None
        for root, _, files in os.walk(numpath_dir):
            if target_file in files:
                found_path = os.path.join(root, target_file)
                break

        if found_path and os.path.exists(found_path):
            try:
                with open(found_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if line and (line.endswith(".mp4") or line.endswith(".usm") or "Movie" in line or "Guide" in line):
                            paths.append(line)
                self.logger.log(f"[*] Loaded {len(paths)} internal movie paths from {target_file}")
            except Exception as e:
                self.logger.log(f"[WARN] Failed to read movie path list: {e}")
        return paths

    def extract_login_video(self) -> Optional[str]:
        """Extract login background video."""
        candidate = os.path.join(self.streaming_assets, "AssetsNotPatch", "pc", "v02_login_bg.mp4")
        if os.path.exists(candidate):
            dst_dir = os.path.join(self.output_dir, "login")
            os.makedirs(dst_dir, exist_ok=True)
            dst = os.path.join(dst_dir, "v02_login_bg.mp4")
            self.logger.log(f"[*] Copying login background video ({format_size(os.path.getsize(candidate))})...")
            shutil.copy2(candidate, dst)
            self.logger.log(f"[OK] Login video saved to: {dst}")
            return dst
        return None

    def extract_numpath_videos(self) -> List[str]:
        """Scan and extract all MP4 videos in numPath."""
        numpath_dir = os.path.join(self.streaming_assets, "numPath")
        if not os.path.exists(numpath_dir):
            self.logger.log(f"[WARN] numPath directory not found: {numpath_dir}")
            return []

        # Find all .data files
        data_files = []
        for root, _, files in os.walk(numpath_dir):
            for f in files:
                if f.endswith(".data") and f != "746192410294089491.data":
                    data_files.append(os.path.join(root, f))

        self.logger.log(f"[*] Found {len(data_files)} candidates in numPath. Checking signatures...")
        extracted = []
        movie_paths = self._read_movie_path_list()
        
        # Output directory for numPath videos
        num_out = os.path.join(self.output_dir, "gameplay_and_guides")
        os.makedirs(num_out, exist_ok=True)

        total = len(data_files)
        for idx, src in enumerate(data_files):
            if self.logger.is_cancelled:
                self.logger.log("[CANCEL] Video extraction stopped by user.")
                break

            file_name = os.path.basename(src)
            file_stem = os.path.splitext(file_name)[0]
            
            # Check magic bytes for MP4 (ftyp)
            try:
                with open(src, "rb") as f:
                    head = f.read(32)
                
                is_mp4 = b"ftyp" in head
                is_usm = b"CRID" in head
                is_webm = head.startswith(b"\x1a\x45\xdf\xa3")
                is_bink = head.startswith(b"KB2") or head.startswith(b"BIKi")

                if not (is_mp4 or is_usm or is_webm or is_bink):
                    continue

                ext = ".mp4" if is_mp4 else (".usm" if is_usm else (".webm" if is_webm else ".bk2"))

                # Determine output subfolder & name
                # If we have matching name from index, use it; otherwise use clean numeric hash
                mapped_name = None
                if idx < len(movie_paths):
                    rel = movie_paths[idx].replace("\\", "/").strip()
                    if rel.startswith("Movies/"):
                        rel = rel[len("Movies/"):]
                    mapped_name = rel
                
                if mapped_name:
                    dst = os.path.join(num_out, mapped_name)
                    # If extension didn't match
                    if not dst.endswith(ext):
                        dst += ext
                else:
                    dst = os.path.join(num_out, f"video_{file_stem}{ext}")

                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                extracted.append(dst)

                if (idx + 1) % 20 == 0 or (idx + 1) == total:
                    self.logger.log(f"  Extracted {len(extracted)} videos... ({idx+1}/{total})", (idx + 1) / total)

            except Exception as e:
                self.logger.log(f"[WARN] Error reading {src}: {e}")

        self.logger.log(f"[OK] Successfully extracted {len(extracted)} videos from numPath into: {num_out}")
        return extracted

    def extract_all(self) -> Dict[str, Any]:
        """Run all video extraction routines."""
        self.logger.log("=== STARTING VIDEO EXTRACTION ===")
        os.makedirs(self.output_dir, exist_ok=True)

        login_video = self.extract_login_video()
        num_videos = self.extract_numpath_videos()

        total_extracted = (1 if login_video else 0) + len(num_videos)
        total_size = 0
        if login_video and os.path.exists(login_video):
            total_size += os.path.getsize(login_video)
        for v in num_videos:
            if os.path.exists(v):
                total_size += os.path.getsize(v)

        self.logger.log(f"[DONE] Video extraction finished! Total: {total_extracted} files ({format_size(total_size)})")
        return {
            "total_count": total_extracted,
            "total_size": total_size,
            "login_video": login_video,
            "videos": num_videos,
            "output_dir": self.output_dir
        }

    def upscale_to_4k(self, input_video: str, out_4k: Optional[str] = None) -> Optional[str]:
        """Upscale video to 4K (3840x2160) using high-quality Lanczos scaling via FFmpeg."""
        if not self.ffmpeg_path or not os.path.exists(self.ffmpeg_path):
            self.logger.log("[ERROR] FFmpeg not available for 4K upscaling.")
            return None

        if not os.path.exists(input_video):
            self.logger.log(f"[ERROR] Video not found: {input_video}")
            return None

        if not out_4k:
            d = os.path.join(self.output_dir, "4k_upscaled")
            os.makedirs(d, exist_ok=True)
            stem = os.path.splitext(os.path.basename(input_video))[0]
            out_4k = os.path.join(d, f"{stem}_4K.mp4")

        self.logger.log(f"[*] Upscaling to 4K: {os.path.basename(input_video)} -> {os.path.basename(out_4k)} ...")
        vf = "scale=3840:2160:force_original_aspect_ratio=decrease:flags=lanczos,pad=3840:2160:(ow-iw)/2:(oh-ih)/2"
        cmd = [
            self.ffmpeg_path, "-y",
            "-i", input_video,
            "-vf", vf,
            "-c:v", "libx264",
            "-crf", "18",
            "-preset", "fast",
            "-c:a", "copy",
            out_4k
        ]
        proc = None
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.logger.register_process(proc)
            proc.wait()
        except Exception as e:
            self.logger.log(f"[WARN] Upscaling interrupted: {e}")
        finally:
            if proc:
                self.logger.unregister_process(proc)

        if os.path.exists(out_4k) and os.path.getsize(out_4k) > 0:
            self.logger.log(f"[OK] 4K Video created: {out_4k} ({format_size(os.path.getsize(out_4k))})")
            return out_4k
        else:
            if not self.logger.is_cancelled:
                self.logger.log(f"[ERROR] 4K upscaling failed for: {input_video}")
            return None

    def scan_generic_directory(self, source_dir: str) -> List[str]:
        """
        Universal Video Scanner: Recursively scan ANY game folder on disk.
        Detects MP4, CRI USM, WebM, MKV, Bink Video, and AVI by signature.
        """
        source_dir = os.path.normpath(source_dir)
        if not os.path.exists(source_dir):
            self.logger.log(f"[ERROR] Source directory does not exist: {source_dir}")
            return []

        self.logger.log(f"[*] Starting universal video scan in: {source_dir}...")
        generic_out = os.path.join(self.output_dir, "generic")
        os.makedirs(generic_out, exist_ok=True)

        found_videos = []
        scanned_count = 0

        for root, _, files in os.walk(source_dir):
            if self.logger.is_cancelled:
                self.logger.log("[CANCEL] Universal video scan stopped by user.")
                break
            for file in files:
                if self.logger.is_cancelled:
                    break
                scanned_count += 1
                full_src = os.path.join(root, file)
                try:
                    size = os.path.getsize(full_src)
                    if size < 1024:
                        continue

                    # Read magic bytes
                    with open(full_src, "rb") as fp:
                        head = fp.read(64)

                    is_mp4 = b"ftyp" in head
                    is_usm = b"CRID" in head
                    is_webm = head.startswith(b"\x1a\x45\xdf\xa3")
                    is_bink = head.startswith(b"KB2") or head.startswith(b"BIKi")
                    is_avi = head.startswith(b"RIFF") and b"AVI " in head[8:16]

                    if not (is_mp4 or is_usm or is_webm or is_bink or is_avi):
                        continue

                    ext = ".mp4" if is_mp4 else (".usm" if is_usm else (".webm" if is_webm else (".bk2" if is_bink else ".avi")))
                    rel = os.path.relpath(full_src, source_dir)
                    stem = os.path.splitext(rel)[0]
                    dest_path = os.path.join(generic_out, f"{stem}{ext}")

                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    shutil.copy2(full_src, dest_path)
                    found_videos.append(dest_path)
                    self.logger.log(f"  [+] Discovered {ext[1:].upper()}: {os.path.basename(dest_path)} ({format_size(size)})")
                except Exception:
                    pass

        self.logger.log(f"[DONE] Universal video scan complete! Scanned {scanned_count} files, extracted {len(found_videos)} videos into: {generic_out}")
        return found_videos

