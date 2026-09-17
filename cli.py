"""
Command-line Interface for Ananta Asset Extractor & Dataminer
"""
import os
import sys
import argparse
from core.utils import load_config, resolve_path, ProgressLogger
from core.video_extractor import VideoExtractor
from core.audio_extractor import AudioExtractor
from core.model_extractor import ModelExtractor
from core.datamine_extractor import DatamineExtractor

def main():
    parser = argparse.ArgumentParser(description="Ananta Asset Extractor & Dataminer CLI")
    parser.add_argument("--all", action="store_true", help="Extract all assets (Videos, Models, Audio, Datamine)")
    parser.add_argument("--videos", action="store_true", help="Extract in-game videos and cutscenes")
    parser.add_argument("--models", action="store_true", help="Extract 3D models (Mesh, GameObject)")
    parser.add_argument("--textures", action="store_true", help="Extract textures and UI sprites")
    parser.add_argument("--audio", action="store_true", help="Extract audio and character voiceovers")
    parser.add_argument("--datamine", action="store_true", help="Export world data, configs, and VFS manifest")
    parser.add_argument("--output", type=str, default="", help="Custom output directory")
    parser.add_argument("--max-audio", type=int, default=0, help="Limit audio tracks per soundbank (0 = unlimited)")

    args = parser.parse_args()
    cfg = load_config()

    output_dir = resolve_path(args.output if args.output else cfg.get("output_dir", "output"))
    streaming_assets = cfg.get("streaming_assets", "")
    corelib_dll = cfg.get("corelib_dll", "")
    animestudio_cli = cfg.get("animestudio_cli", "")
    dummy_dlls = cfg.get("dummy_dlls", "")
    ffmpeg = cfg.get("ffmpeg", "")
    vgmstream = cfg.get("vgmstream", "")

    logger = ProgressLogger()
    logger.log("==================================================")
    logger.log("   ANANTA ASSET EXTRACTOR & DATAMINER CLI")
    logger.log("==================================================")
    logger.log(f"Output Directory: {output_dir}")

    # If no specific flag passed, default to showing help or running all
    if not (args.all or args.videos or args.models or args.textures or args.audio or args.datamine):
        parser.print_help()
        sys.exit(0)

    # 1. Videos
    if args.all or args.videos:
        v_ext = VideoExtractor(streaming_assets, output_dir, ffmpeg_path=ffmpeg, logger=logger)
        v_ext.extract_all()

    # 2. Audio
    if args.all or args.audio:
        a_ext = AudioExtractor(streaming_assets, output_dir, vgmstream_path=vgmstream, ffmpeg_path=ffmpeg, logger=logger)
        a_ext.extract_all(max_per_file=args.max_audio)

    # 3. Models / Textures
    if args.all or args.models or args.textures:
        m_ext = ModelExtractor(animestudio_cli, dummy_dlls, output_dir, logger=logger)
        target_path = os.path.join(streaming_assets, "Blocks")
        if args.models:
            m_ext.extract_3d_models(target_path)
        if args.textures:
            m_ext.extract_textures(target_path)
        if args.all and not (args.models or args.textures):
            m_ext.extract_all_types(target_path)

    # 4. Datamine
    if args.all or args.datamine:
        d_ext = DatamineExtractor(streaming_assets, corelib_dll, output_dir, logger=logger)
        d_ext.export_all()

    logger.log("\n[SUCCESS] All requested extraction jobs completed!")

if __name__ == "__main__":
    main()
