import os

# Tests render screenshots without displaying windows; the real application uses the Windows platform.
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
