"""
3D Models, Textures, and Asset Extraction Module
Integrates AnimeStudio CLI with custom NetEase engine parameters and Il2Cpp DummyDlls.
Extracts:
1. 3D Meshes & GameObjects -> Wavefront OBJ / glTF / FBX
2. Textures & UI Sprites -> PNG
3. Materials & Shaders
4. TextAssets, Monobehaviours, and Configurations
"""
import os
import sys
import subprocess
from typing import Optional, List, Dict, Any
from .utils import ProgressLogger, format_size

class ModelExtractor:
    def __init__(self, animestudio_cli: str, dummy_dlls: str, output_dir: str, logger: Optional[ProgressLogger] = None):
        self.animestudio_cli = os.path.normpath(animestudio_cli)
        self.dummy_dlls = os.path.normpath(dummy_dlls) if dummy_dlls else None
        self.output_dir = os.path.normpath(os.path.join(output_dir, "models_and_textures"))
        self.logger = logger or ProgressLogger()

    def is_available(self) -> bool:
        """Check if AnimeStudio CLI is available."""
        return os.path.exists(self.animestudio_cli)

    def run_animestudio(self, input_path: str, out_folder: str, types: List[str], game: str = "NetEase", export_type: str = "Convert") -> bool:
        """Execute AnimeStudio CLI with the specified options."""
        if not self.is_available():
            self.logger.log(f"[ERROR] AnimeStudio CLI not found at: {self.animestudio_cli}")
            return False

        if not os.path.exists(input_path):
            self.logger.log(f"[ERROR] Input target does not exist: {input_path}")
            return False

        os.makedirs(out_folder, exist_ok=True)
        types_arg = "|".join(types)

        cmd = [
            self.animestudio_cli,
            input_path,
            out_folder,
            "--game", game,
            "--types", types_arg,
            "--export_type", export_type,
            "--group_assets", "ByType"
        ]

        if self.dummy_dlls and os.path.exists(self.dummy_dlls):
            cmd.extend(["--dummy_dlls", self.dummy_dlls])

        self.logger.log(f"[*] Launching AnimeStudio [{game}] on {os.path.basename(input_path)}...")
        self.logger.log(f"    Types: {types_arg} | Mode: {export_type}")
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace'
            )

            for line in process.stdout:
                line_str = line.strip()
                if line_str and ("[Info]" in line_str or "[Error]" in line_str or "[Warning]" in line_str):
                    self.logger.log(f"    {line_str}")

            process.wait()
            return process.returncode == 0
        except Exception as e:
            self.logger.log(f"[ERROR] AnimeStudio execution error: {e}")
            return False

    def extract_3d_models(self, input_path: str) -> bool:
        """Extract 3D models (Mesh, GameObject, Animator, Avatar)."""
        out_folder = os.path.join(self.output_dir, "models_3d")
        types = ["Mesh", "GameObject", "Animator", "Avatar", "SkinnedMeshRenderer"]
        return self.run_animestudio(input_path, out_folder, types=types, game="NetEase", export_type="Convert")

    def extract_textures(self, input_path: str) -> bool:
        """Extract textures, sprites, UI elements (Texture2D, Sprite)."""
        out_folder = os.path.join(self.output_dir, "textures_and_ui")
        types = ["Texture2D", "Sprite"]
        return self.run_animestudio(input_path, out_folder, types=types, game="NetEase", export_type="Convert")

    def extract_all_types(self, input_path: str) -> bool:
        """Extract all supported game assets (Mesh, Texture2D, Sprite, TextAsset, VideoClip)."""
        out_folder = os.path.join(self.output_dir, "full_export")
        types = ["Mesh", "Texture2D", "Sprite", "TextAsset", "VideoClip", "Shader", "GameObject"]
        return self.run_animestudio(input_path, out_folder, types=types, game="NetEase", export_type="Convert")
