import os
import sys
from PyInstaller.utils.hooks import get_hook_config

def _qt_get_plugin_directories():
    import PyQt6
    qt_root = os.path.dirname(PyQt6.__file__)
    return [os.path.join(qt_root, 'Qt6', 'plugins')]

def hook(hook_api):
    # Get the Qt plugin directories
    plugin_directories = _qt_get_plugin_directories()
    
    # Add each plugin directory to PATH
    for plugin_dir in plugin_directories:
        if os.path.exists(plugin_dir):
            if sys.platform == 'darwin':
                hook_api.runtime_hooks.append(os.path.join(os.path.dirname(__file__), 'rthook.py'))
