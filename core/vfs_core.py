"""
Native NetEase VFS (Virtual File System) Bridge using CoreLib.dll
Directly interfaces with game engine's C++ VFSBuilder and EzFile subsystems.
"""
import os
import sys
import ctypes
from typing import Optional, List, Dict, Any
from .utils import ProgressLogger

class VFSBridge:
    def __init__(self, corelib_path: str, logger: Optional[ProgressLogger] = None):
        self.corelib_path = corelib_path
        self.logger = logger or ProgressLogger()
        self.corelib = None
        self.builder = None
        self.is_opened = False
        self._init_dll()

    def _init_dll(self):
        if not os.path.exists(self.corelib_path):
            self.logger.log(f"[ERROR] CoreLib.dll not found at: {self.corelib_path}")
            return
        
        try:
            # Set DLL directory to resolve dependencies if any
            dll_dir = os.path.dirname(self.corelib_path)
            if hasattr(os, 'add_dll_directory'):
                os.add_dll_directory(dll_dir)
            
            self.corelib = ctypes.CDLL(self.corelib_path)
            
            # Setup VFSBuilderCreate
            self.corelib.VFSBuilderCreate.restype = ctypes.c_void_p
            self.corelib.VFSBuilderCreate.argtypes = []

            # Setup VFSBuilderRelease
            self.corelib.VFSBuilderRelease.restype = None
            self.corelib.VFSBuilderRelease.argtypes = [ctypes.c_void_p]

            # Setup VFSBuilderOpen(builder, outputDir, headerName)
            self.corelib.VFSBuilderOpen.restype = ctypes.c_bool
            self.corelib.VFSBuilderOpen.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]

            # Setup VFSBuilderExportByHash(builder, nameHash, dst)
            self.corelib.VFSBuilderExportByHash.restype = ctypes.c_bool
            self.corelib.VFSBuilderExportByHash.argtypes = [ctypes.c_void_p, ctypes.c_uint64, ctypes.c_char_p]

            # Setup VFSPrintAllFileInfo(builder, dst)
            self.corelib.VFSPrintAllFileInfo.restype = None
            self.corelib.VFSPrintAllFileInfo.argtypes = [ctypes.c_void_p, ctypes.c_char_p]

            # Setup VFSBuilderGetBlockCount(builder)
            self.corelib.VFSBuilderGetBlockCount.restype = ctypes.c_int
            self.corelib.VFSBuilderGetBlockCount.argtypes = [ctypes.c_void_p]

            self.logger.log("[OK] CoreLib.dll loaded successfully.")
        except Exception as e:
            self.logger.log(f"[ERROR] Failed to load CoreLib.dll: {e}")

    def open_vfs(self, blocks_dir: str, header_name: str = "ipa_header.ehd") -> bool:
        """Open the VFS archive from Blocks directory."""
        if not self.corelib:
            self.logger.log("[ERROR] CoreLib DLL not loaded.")
            return False

        if not os.path.exists(blocks_dir):
            self.logger.log(f"[ERROR] Blocks directory does not exist: {blocks_dir}")
            return False

        # Ensure directory path ends with slash
        norm_dir = os.path.normpath(blocks_dir) + os.sep
        header_path = os.path.join(norm_dir, header_name)
        if not os.path.exists(header_path):
            self.logger.log(f"[ERROR] Header not found: {header_path}")
            return False

        try:
            self.builder = self.corelib.VFSBuilderCreate()
            if not self.builder:
                self.logger.log("[ERROR] Failed to instantiate VFSBuilder native object.")
                return False

            res = self.corelib.VFSBuilderOpen(
                self.builder,
                norm_dir.encode('utf-8', errors='ignore'),
                header_name.encode('utf-8', errors='ignore')
            )
            if res:
                self.is_opened = True
                block_count = self.corelib.VFSBuilderGetBlockCount(self.builder)
                self.logger.log(f"[OK] VFS opened successfully! Block count: {block_count}")
                return True
            else:
                self.logger.log("[ERROR] VFSBuilderOpen returned False.")
                return False
        except Exception as e:
            self.logger.log(f"[ERROR] Exception during VFS open: {e}")
            return False

    def export_by_hash(self, name_hash: int, out_path: str) -> bool:
        """Export a single file by 64-bit hash from the open VFS."""
        if not self.is_opened or not self.builder:
            return False
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        try:
            return bool(self.corelib.VFSBuilderExportByHash(
                self.builder,
                ctypes.c_uint64(name_hash),
                out_path.encode('utf-8', errors='ignore')
            ))
        except Exception as e:
            self.logger.log(f"[ERROR] Export error for hash {name_hash}: {e}")
            return False

    def dump_vfs_manifest(self, out_manifest_path: str) -> bool:
        """Dump the entire VFS file table into a text manifest using native function."""
        if not self.is_opened or not self.builder:
            return False
        os.makedirs(os.path.dirname(os.path.abspath(out_manifest_path)), exist_ok=True)
        try:
            self.logger.log(f"[*] Dumping full VFS directory table to: {out_manifest_path} ...")
            self.corelib.VFSPrintAllFileInfo(
                self.builder,
                out_manifest_path.encode('utf-8', errors='ignore')
            )
            return os.path.exists(out_manifest_path) and os.path.getsize(out_manifest_path) > 0
        except Exception as e:
            self.logger.log(f"[ERROR] Failed to dump manifest: {e}")
            return False

    def close(self):
        """Release native builder resources."""
        if self.builder and self.corelib:
            try:
                self.corelib.VFSBuilderRelease(self.builder)
            except Exception:
                pass
            self.builder = None
            self.is_opened = False
