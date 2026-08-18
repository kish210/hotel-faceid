"""Face-service package.

The RTSP transport is pinned here, before anything imports OpenCV: UDP drops
frames badly over Wi-Fi and VLAN hops, and this used to be set by the
container image. An operator who exports the variable themselves wins.
"""

import os

os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
