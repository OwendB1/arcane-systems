"""Compatibility entry point: generate direct-script geometry (no Animation Engine)."""
from pathlib import Path
import runpy

if __name__ == '__main__':
    runpy.run_path(str(Path(__file__).with_name('build_animation_geometry.py')), run_name='__main__')
