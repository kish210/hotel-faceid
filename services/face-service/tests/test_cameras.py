from types import SimpleNamespace
from unittest.mock import patch

from app.cameras.axis import AxisCamera
from app.cameras.base import CameraConfig, describe_rtsp
from app.cameras.dahua import DahuaCamera
from app.cameras.hikvision import HikvisionCamera
from app.cameras.topsee import TopseeCamera


def make(cls, purpose="bidirectional"):
    cfg = CameraConfig(
        id="cam1",
        name="test",
        brand=cls.brand,
        purpose=purpose,
        host="192.168.1.100",
    )
    return cls(cfg)


def test_hikvision_face():
    cam = make(HikvisionCamera)
    part = (
        b"--boundary\r\n"
        b"Content-Type: application/xml\r\n\r\n"
        b"<EventNotificationAlert>\r\n"
        b"<eventType>faceCapture</eventType>\r\n"
        b"<detectionTarget>left-right</detectionTarget>\r\n"
        b"</EventNotificationAlert>\r\n"
    )
    event = cam._parse_part(part)
    assert event is not None, "faceCapture part should parse"
    assert event.direction == "in", event.direction
    assert event.image is None


def test_hikvision_facepicurl_extracted_at_unit_level():
    cam = make(HikvisionCamera)
    text = "<facePicURL>/ISAPI/Intelligent/FDLib/faceDataRecord?pos=1</facePicURL>"
    assert cam._field(text, "facePicURL") == "/ISAPI/Intelligent/FDLib/faceDataRecord?pos=1"


def test_hikvision_motion_ignored():
    cam = make(HikvisionCamera)
    part = b"<EventNotificationAlert><eventType>VideoMotion</eventType></EventNotificationAlert>"
    assert cam._parse_part(part) is None


def test_hikvision_embedded_jpeg():
    cam = make(HikvisionCamera)
    jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\xff\xd9"
    part = b"<EventNotificationAlert><eventType>faceCapture</eventType></EventNotificationAlert>" + jpeg
    event = cam._parse_part(part)
    assert event is not None and event.image == jpeg


WITH_HEADERS = lambda body, length="99": (
    f"\r\nContent-Type: text/plain\r\nContent-Length: {length}\r\n\r\n".encode() + body
)


def test_dahua_start():
    cam = make(DahuaCamera)
    part = WITH_HEADERS(b'Code=FaceDetection;action=Start;index=0;data={"RegionDirection":"Enter"}')
    with patch.object(cam, "snapshot", return_value=None):
        event = cam._parse_event(part)
    assert event is not None, "Start event should parse"
    assert event.direction == "in", event.direction


def test_dahua_stop_ignored():
    cam = make(DahuaCamera)
    part = WITH_HEADERS(b"Code=FaceDetection;action=Stop;index=0")
    with patch.object(cam, "snapshot", return_value=None):
        event = cam._parse_event(part)
    assert event is None


def test_dahua_motion_ignored():
    cam = make(DahuaCamera)
    part = WITH_HEADERS(b"Code=VideoMotion;action=Start;index=0")
    with patch.object(cam, "snapshot", return_value=None):
        event = cam._parse_event(part)
    assert event is None


def test_dahua_exit_direction():
    cam = make(DahuaCamera)
    part = WITH_HEADERS(
        b'Code=CrossLineDetection;action=Start;index=0;data={"CrossLineDirection":"RightToLeft"}'
    )
    with patch.object(cam, "snapshot", return_value=None):
        event = cam._parse_event(part)
    assert event is not None and event.direction == "out"


def test_dahua_snapshot_used_as_image():
    cam = make(DahuaCamera)
    jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\xff\xd9"
    part = WITH_HEADERS(b"Code=FaceDetection;action=Start;index=0")
    with patch.object(cam, "snapshot", return_value=jpeg):
        event = cam._parse_event(part)
    assert event is not None and event.image == jpeg


# ------------------------------------------------------------------- Axis
def axis_message(topic, items=None):
    """Build the zeep-shaped object an ONVIF PullPoint hands back."""
    simple = [SimpleNamespace(Name=name, Value=value) for name, value in (items or {}).items()]
    return SimpleNamespace(
        Topic=SimpleNamespace(_value_1=topic),
        Message=SimpleNamespace(
            _value_1=SimpleNamespace(
                Source=SimpleNamespace(SimpleItem=[]),
                Key=None,
                Data=SimpleNamespace(SimpleItem=simple),
            )
        ),
    )


def test_axis_rtsp_url():
    cam = make(AxisCamera)
    assert cam.rtsp_url().startswith("rtsp://192.168.1.100:554/axis-media/media.amp")


def test_axis_object_analytics_event():
    cam = make(AxisCamera)
    message = axis_message(
        "tns1:RuleEngine/ObjectDetect/Object", {"active": "1", "direction": "leftToRight"}
    )
    with patch.object(cam, "snapshot", return_value=None):
        event = cam._parse_message(message)
    assert event is not None, "object-detect topic should parse"
    assert event.direction == "in", event.direction


def test_axis_inactive_state_ignored():
    cam = make(AxisCamera)
    message = axis_message("tns1:RuleEngine/LineDetector/Crossed", {"active": "false"})
    with patch.object(cam, "snapshot", return_value=None):
        assert cam._parse_message(message) is None


def test_axis_unrelated_topic_ignored():
    cam = make(AxisCamera)
    message = axis_message("tns1:Device/HardwareFailure/StorageFailure", {"active": "1"})
    with patch.object(cam, "snapshot", return_value=None):
        assert cam._parse_message(message) is None


def test_axis_purpose_overrides_payload_direction():
    cam = make(AxisCamera, purpose="exit")
    message = axis_message("tns1:RuleEngine/ObjectDetect/Object", {"direction": "leftToRight"})
    jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\xff\xd9"
    with patch.object(cam, "snapshot", return_value=jpeg):
        event = cam._parse_message(message)
    assert event is not None and event.direction == "out"
    assert event.image == jpeg


# ----------------------------------------------------------------- TOPSEE
def test_topsee_uses_a_configured_url_verbatim():
    cfg = CameraConfig(
        id="cam1", name="lobby", brand="topsee", purpose="entry",
        host="192.168.1.50", rtsp_url="rtsp://192.168.1.50:554/custom",
    )
    assert TopseeCamera(cfg).rtsp_url() == "rtsp://192.168.1.50:554/custom"


def test_topsee_probes_paths_when_onvif_is_silent():
    cam = make(TopseeCamera)
    tried = []

    def answer(url, timeout=3.0):
        tried.append(url)
        return url.endswith("/11")  # this board happens to use /11

    with patch.object(TopseeCamera, "_discover_stream_uri", return_value=None), \
         patch("app.cameras.topsee.describe_rtsp", side_effect=answer):
        url = cam.rtsp_url()

    assert url.endswith("/11"), url
    assert tried[0].endswith("/0"), "the most common path should be tried first"


def test_topsee_remembers_the_path_it_found():
    cam = make(TopseeCamera)
    calls = []

    def answer(url, timeout=3.0):
        calls.append(url)
        return url.endswith("/onvif1")

    with patch.object(TopseeCamera, "_discover_stream_uri", return_value=None), \
         patch("app.cameras.topsee.describe_rtsp", side_effect=answer):
        first = cam.rtsp_url()
        probed = len(calls)
        second = cam.rtsp_url()

    assert first == second
    assert len(calls) == probed, "a second call must not probe again"


def test_topsee_falls_back_when_nothing_answers():
    cam = make(TopseeCamera)
    with patch.object(TopseeCamera, "_discover_stream_uri", return_value=None), \
         patch("app.cameras.topsee.describe_rtsp", return_value=False):
        # The worker's reconnect loop is a better place to give up than here.
        assert cam.rtsp_url().endswith("/0")


def test_topsee_prefers_onvif_discovery():
    cam = make(TopseeCamera)
    with patch.object(
        TopseeCamera, "_discover_stream_uri", return_value="rtsp://from-onvif/stream"
    ), patch("app.cameras.topsee.describe_rtsp") as probe:
        assert cam.rtsp_url() == "rtsp://from-onvif/stream"
        probe.assert_not_called()


def test_describe_rtsp_accepts_401():
    # An unauthenticated DESCRIBE proves the path exists; the real client
    # negotiates credentials afterwards.
    import socket as socket_module

    class FakeSocket:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def settimeout(self, _): pass
        def sendall(self, _): pass
        def recv(self, _): return b"RTSP/1.0 401 Unauthorized\r\n\r\n"

    with patch.object(socket_module, "create_connection", return_value=FakeSocket()):
        assert describe_rtsp("rtsp://192.168.1.50:554/0") is True


def test_describe_rtsp_rejects_404():
    import socket as socket_module

    class FakeSocket:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def settimeout(self, _): pass
        def sendall(self, _): pass
        def recv(self, _): return b"RTSP/1.0 404 Not Found\r\n\r\n"

    with patch.object(socket_module, "create_connection", return_value=FakeSocket()):
        assert describe_rtsp("rtsp://192.168.1.50:554/nope") is False


if __name__ == "__main__":
    test_hikvision_face()
    test_hikvision_motion_ignored()
    test_hikvision_embedded_jpeg()
    test_hikvision_facepicurl_extracted_at_unit_level()
    test_dahua_start()
    test_dahua_stop_ignored()
    test_dahua_motion_ignored()
    test_dahua_exit_direction()
    test_dahua_snapshot_used_as_image()
    test_topsee_uses_a_configured_url_verbatim()
    test_topsee_probes_paths_when_onvif_is_silent()
    test_topsee_remembers_the_path_it_found()
    test_topsee_falls_back_when_nothing_answers()
    test_topsee_prefers_onvif_discovery()
    test_describe_rtsp_accepts_401()
    test_describe_rtsp_rejects_404()
    test_axis_rtsp_url()
    test_axis_object_analytics_event()
    test_axis_inactive_state_ignored()
    test_axis_unrelated_topic_ignored()
    test_axis_purpose_overrides_payload_direction()
    print("ALL TESTS PASSED")