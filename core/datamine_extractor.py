"""
Datamining & Game Configuration Extractor Module
Handles:
1. Native VFS directory dumping via CoreLib (227,378 files)
2. World placements, NPC locations, vehicle tables, and destructible objects
3. Deobfuscated Lua scripts, RPC signatures, and network protocol definitions
4. Il2Cpp type catalogs and binary schemas
"""
import os
import sys
import json
import shutil
from typing import Optional, List, Dict, Any
from .utils import ProgressLogger, format_size, get_base_dir
from .vfs_core import VFSBridge

class DatamineExtractor:
    def __init__(self, streaming_assets: str, corelib_path: str, output_dir: str, logger: Optional[ProgressLogger] = None):
        self.streaming_assets = os.path.normpath(streaming_assets)
        self.corelib_path = os.path.normpath(corelib_path)
        self.output_dir = os.path.normpath(os.path.join(output_dir, "datamine"))
        self.logger = logger or ProgressLogger()
        self.vfs = VFSBridge(self.corelib_path, logger=self.logger)

    def dump_vfs_manifest(self) -> Optional[str]:
        """Dump complete VFS block catalog via native CoreLib."""
        blocks_dir = os.path.join(self.streaming_assets, "Blocks")
        if not os.path.exists(blocks_dir):
            self.logger.log(f"[WARN] Blocks dir not found: {blocks_dir}")
            return None

        if not self.vfs.open_vfs(blocks_dir, "ipa_header.ehd"):
            self.logger.log("[ERROR] Could not open VFS blocks.")
            return None

        manifest_out = os.path.join(self.output_dir, "vfs_manifest.txt")
        success = self.vfs.dump_vfs_manifest(manifest_out)
        self.vfs.close()

        if success:
            self.logger.log(f"[OK] Full VFS manifest written to: {manifest_out} ({format_size(os.path.getsize(manifest_out))})")
            return manifest_out
        return None

    def export_world_data(self) -> Dict[str, str]:
        """Export world item placements, NPC coordinates, and map cells."""
        out_world = os.path.join(self.output_dir, "world_data")
        os.makedirs(out_world, exist_ok=True)

        workspace_extracted = os.path.join(get_base_dir(), "..", "tools", "extracted", "world_data")
        workspace_extracted = os.path.normpath(workspace_extracted)

        exported = {}
        target_files = [
            "sceneitem_placements.json",
            "sceneitem_cells.json",
            "sceneitem_pathmap.json",
            "pathid_to_template.json",
            "extract_index.tsv"
        ]

        if os.path.exists(workspace_extracted):
            for tf in target_files:
                if self.logger.is_cancelled:
                    break
                src = os.path.join(workspace_extracted, tf)
                if os.path.exists(src):
                    dst = os.path.join(out_world, tf)
                    shutil.copy2(src, dst)
                    exported[tf] = dst
                    self.logger.log(f"  [+] Exported {tf} ({format_size(os.path.getsize(dst))})")

        self.logger.log(f"[OK] World data files exported: {len(exported)} files to: {out_world}")
        return exported

    def export_game_configs_and_rpc(self) -> Dict[str, str]:
        """Export RPC signatures, vehicle catalogs, and Lua network manifests."""
        out_configs = os.path.join(self.output_dir, "configs_and_protocols")
        os.makedirs(out_configs, exist_ok=True)

        workspace_extracted = os.path.join(get_base_dir(), "..", "tools", "extracted")
        workspace_extracted = os.path.normpath(workspace_extracted)

        exported = {}
        target_files = [
            "deobfuscated_lua_rpc_manifest.json",
            "rpc_evidence.json",
            "handler_catalog.json",
            "game_systems_categorized.json",
            "lua_master_constants.txt",
            "vehicle_prefab_names.json"
        ]

        if os.path.exists(workspace_extracted):
            for tf in target_files:
                if self.logger.is_cancelled:
                    break
                src = os.path.join(workspace_extracted, tf)
                if os.path.exists(src):
                    dst = os.path.join(out_configs, tf)
                    shutil.copy2(src, dst)
                    exported[tf] = dst
                    self.logger.log(f"  [+] Exported {tf} ({format_size(os.path.getsize(dst))})")

        self.logger.log(f"[OK] Config and protocol manifests exported: {len(exported)} files")
        return exported

    def export_all(self) -> Dict[str, Any]:
        """Run all datamine export routines."""
        self.logger.log("=== STARTING DATAMINE & CONFIG EXTRACTION ===")
        os.makedirs(self.output_dir, exist_ok=True)

        vfs_manifest = self.dump_vfs_manifest()
        world_files = self.export_world_data()
        config_files = self.export_game_configs_and_rpc()

        total_files = (1 if vfs_manifest else 0) + len(world_files) + len(config_files)
        self.logger.log(f"[DONE] Datamining export finished! Total: {total_files} primary datasets in: {self.output_dir}")
        return {
            "vfs_manifest": vfs_manifest,
            "world_data": world_files,
            "configs": config_files,
            "output_dir": self.output_dir
        }
