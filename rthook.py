import os
import sys

if sys.platform == 'darwin':
    # Get the application path
    if getattr(sys, 'frozen', False):
        # Running in a bundle
        bundle_dir = os.path.dirname(sys.executable)
        if '.app' in bundle_dir:
            # Get the .app bundle directory
            while not bundle_dir.endswith('.app'):
                bundle_dir = os.path.dirname(bundle_dir)
            # Set the plugin path
            os.environ['QT_PLUGIN_PATH'] = os.path.join(bundle_dir, 'Contents', 'Resources', 'PyQt6', 'Qt6', 'plugins')
