from unittest.mock import patch

from app.cameras.base import CameraConfig
from app.cameras.dahua import DahuaCamera
from app.cameras.hikvision import HikvisionCamera


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
    print("ALL TESTS PASSED")