"""
Audio & Voiceover Extraction Module for Project Mugen / Ananta CBT
Extracts:
1. Character voice lines (Chinese, English, Japanese) from Wwise soundbanks (*.pck)
2. Background music (BGM) and ambient music from Streams*.pck
3. Sound effects (SFX) from Bank*.pck
Converts all extracted Wwise streams to standard high-quality WAV files using vgmstream.
"""
import os
import sys
import struct
import shutil
import subprocess
from typing import Optional, List, Dict, Tuple, Any
from .utils import ProgressLogger, format_size

class AudioExtractor:
    def __init__(self, streaming_assets: str, output_dir: str, vgmstream_path: str, ffmpeg_path: Optional[str] = None, logger: Optional[ProgressLogger] = None):
        self.streaming_assets = os.path.normpath(streaming_assets)
        self.audio_base = os.path.join(self.streaming_assets, "GameRes", "Audio", "GeneratedSoundBanks", "Windows")
        self.output_dir = os.path.normpath(os.path.join(output_dir, "audio"))
        self.vgmstream_path = vgmstream_path
        self.ffmpeg_path = ffmpeg_path
        self.logger = logger or ProgressLogger()

    def find_pck_files(self) -> Dict[str, List[str]]:
        """Categorize available PCK files by language and type."""
        categories = {
            "chinese_voice": [],
            "english_voice": [],
            "japanese_voice": [],
            "bgm_streams": [],
            "sfx_banks": [],
            "other": []
        }
        
        if not os.path.exists(self.audio_base):
            self.logger.log(f"[WARN] Audio directory not found: {self.audio_base}")
            return categories

        for root, _, files in os.walk(self.audio_base):
            for f in files:
                if f.lower().endswith(".pck"):
                    full_path = os.path.join(root, f)
                    lower_name = f.lower()
                    rel_dir = os.path.relpath(root, self.audio_base).lower()

                    if "chinese" in rel_dir or "chinese" in lower_name:
                        categories["chinese_voice"].append(full_path)
                    elif "english" in rel_dir or "english" in lower_name:
                        categories["english_voice"].append(full_path)
                    elif "japanese" in rel_dir or "japanese" in lower_name:
                        categories["japanese_voice"].append(full_path)
                    elif "stream" in lower_name:
                        categories["bgm_streams"].append(full_path)
                    elif "bank" in lower_name:
                        categories["sfx_banks"].append(full_path)
                    else:
                        categories["other"].append(full_path)

        return categories

    def extract_riff_streams_from_pck(self, pck_path: str, out_folder: str, max_files: int = 0) -> List[str]:
        """Scan and extract all embedded RIFF/WAVE audio streams from a PCK file."""
        if not os.path.exists(pck_path):
            return []

        os.makedirs(out_folder, exist_ok=True)
        file_size = os.path.getsize(pck_path)
        base_name = os.path.splitext(os.path.basename(pck_path))[0]

        self.logger.log(f"[*] Scanning audio streams in {os.path.basename(pck_path)} ({format_size(file_size)})...")
        
        extracted_wavs = []
        chunk_size = 32 * 1024 * 1024  # 32MB chunks
        overlap = 64 * 1024           # 64KB overlap

        temp_dir = os.path.join(self.output_dir, ".tmp")
        os.makedirs(temp_dir, exist_ok=True)

        found_offsets = set()
        count = 0

        with open(pck_path, "rb") as f:
            offset = 0
            while offset < file_size:
                f.seek(offset)
                buf = f.read(chunk_size + overlap)
                if not buf:
                    break

                pos = 0
                while True:
                    pos = buf.find(b"RIFF", pos)
                    if pos == -1 or pos + 12 > len(buf):
                        break

                    # Check for WAVE
                    if buf[pos+8:pos+12] == b"WAVE":
                        stream_offset = offset + pos
                        if stream_offset not in found_offsets:
                            found_offsets.add(stream_offset)
                            
                            # Read total RIFF size (field at pos+4 is size - 8)
                            riff_len = struct.unpack_from("<I", buf, pos + 4)[0] + 8
                            if 32 < riff_len < 100 * 1024 * 1024:  # sane audio file size
                                # Extract slice
                                if pos + riff_len <= len(buf):
                                    audio_bytes = buf[pos:pos+riff_len]
                                else:
                                    f.seek(stream_offset)
                                    audio_bytes = f.read(riff_len)

                                count += 1
                                temp_wem = os.path.join(temp_dir, f"{base_name}_{count:05d}.wem")
                                out_wav = os.path.join(out_folder, f"{base_name}_{count:05d}.wav")

                                with open(temp_wem, "wb") as wem_f:
                                    wem_f.write(audio_bytes)

                                # Convert with vgmstream
                                if os.path.exists(self.vgmstream_path):
                                    cmd = [self.vgmstream_path, "-o", out_wav, temp_wem]
                                    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                    if os.path.exists(out_wav) and os.path.getsize(out_wav) > 0:
                                        extracted_wavs.append(out_wav)
                                
                                try:
                                    if os.path.exists(temp_wem):
                                        os.remove(temp_wem)
                                except Exception:
                                    pass

                                if count % 50 == 0:
                                    self.logger.log(f"  Extracted {count} audio tracks from {base_name}...")

                                if max_files > 0 and count >= max_files:
                                    break

                    pos += 4

                if max_files > 0 and count >= max_files:
                    break

                offset += chunk_size

        try:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass

        self.logger.log(f"[OK] Extracted {len(extracted_wavs)} WAV tracks from {base_name} into: {out_folder}")
        return extracted_wavs

    def extract_category(self, category_key: str, max_per_file: int = 0) -> List[str]:
        """Extract all audio files in a specific category."""
        pck_map = self.find_pck_files()
        targets = pck_map.get(category_key, [])
        if not targets:
            self.logger.log(f"[INFO] No files found for category: {category_key}")
            return []

        out_sub = os.path.join(self.output_dir, category_key)
        all_wavs = []
        for pck in targets:
            wavs = self.extract_riff_streams_from_pck(pck, out_sub, max_files=max_per_file)
            all_wavs.extend(wavs)
        return all_wavs

    def extract_all(self, max_per_file: int = 0) -> Dict[str, Any]:
        """Extract all audio categories (Chinese, English, Japanese, BGM, SFX)."""
        self.logger.log("=== STARTING AUDIO & VOICEOVER EXTRACTION ===")
        pck_map = self.find_pck_files()
        results = {}
        total_wavs = 0

        for cat, files in pck_map.items():
            if files:
                self.logger.log(f"[*] Processing category: {cat} ({len(files)} soundbank archives)...")
                wavs = self.extract_category(cat, max_per_file=max_per_file)
                results[cat] = len(wavs)
                total_wavs += len(wavs)

        self.logger.log(f"[DONE] Audio extraction completed! Total: {total_wavs} tracks saved to: {self.output_dir}")
        return {
            "total_tracks": total_wavs,
            "categories": results,
            "output_dir": self.output_dir
        }

    def scan_generic_directory(self, source_dir: str, max_per_file: int = 50) -> List[str]:
        """
        Universal Audio Scanner: Recursively scan ANY game directory for Wwise soundbanks (*.pck, *.bnk)
        or embedded audio streams and convert them to standard WAV files.
        """
        source_dir = os.path.normpath(source_dir)
        if not os.path.exists(source_dir):
            self.logger.log(f"[ERROR] Audio source directory does not exist: {source_dir}")
            return []

        self.logger.log(f"[*] Starting universal audio scan in: {source_dir}...")
        generic_out = os.path.join(self.output_dir, "generic")
        os.makedirs(generic_out, exist_ok=True)

        found_pcks = []
        for root, _, files in os.walk(source_dir):
            for file in files:
                if file.lower().endswith((".pck", ".bnk", ".wem")):
                    found_pcks.append(os.path.join(root, file))

        self.logger.log(f"[*] Found {len(found_pcks)} soundbank archives in {source_dir}.")
        all_extracted = []
        for pck in found_pcks:
            base_name = os.path.splitext(os.path.basename(pck))[0]
            out_sub = os.path.join(generic_out, base_name)
            wavs = self.extract_riff_streams_from_pck(pck, out_sub, max_files=max_per_file)
            all_extracted.extend(wavs)

        self.logger.log(f"[DONE] Universal audio scan complete! Extracted {len(all_extracted)} WAV tracks into: {generic_out}")
        return all_extracted

