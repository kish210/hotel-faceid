"""Camera auto-detection.

Every vendor answers a different "who are you" endpoint, and none of them is
guarded behind the same auth scheme, so identification is a short sequence of
attempts rather than one lookup:

    Hikvision  GET /ISAPI/System/deviceInfo          (XML,  digest)
    Dahua      GET /cgi-bin/magicBox.cgi?action=…    (k=v,  digest)
    Axis       GET /axis-cgi/basicdeviceinfo.cgi     (JSON, digest)  → param.cgi
    Foscam     GET /cgi-bin/CGIProxy.fcgi            (XML,  credentials in query)
    anything   ONVIF GetDeviceInformation            (SOAP, WS-Security)

The first vendor that answers wins; ONVIF is the catch-all so an unknown brand
still comes back with a usable model string instead of nothing.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from urllib.parse import quote

import requests
from requests.auth import HTTPBasicAuth, HTTPDigestAuth

from ..models import CameraBrand
from ..schemas import CameraProbeResult

log = logging.getLogger(__name__)

TIMEOUT = (3.0, 5.0)

# TOPSEE OEM boards — TH38J and the rest of the TH series — plus the Hisilicon
# chip names integrators leave behind in the ONVIF model string. These boards
# are sold under whatever name is printed on the housing, so the model string
# is the only reliable giveaway.
TOPSEE_MODEL = re.compile(r"\bTH\d{2}[A-Z]?\d?\b|topsee|tpsee|hi35\d{2}", re.I)

# Devices whose model name matches this run face detection on the edge, so the
# "use the camera's own engine" switch is worth offering for them.
FACE_CAPABLE = re.compile(
    r"face|deepin|acusense|wizmind|wizsense|guardian|object.?analytics", re.I
)


@dataclass(slots=True)
class Device:
    brand: CameraBrand
    model: str | None = None
    firmware: str | None = None
    serial_number: str | None = None


def probe(host: str, port: int, username: str | None, password: str | None) -> CameraProbeResult:
    """Identify the device at host:port. Never raises — failures come back as
    `detected=False` with a human-readable reason."""
    probes = (_probe_hikvision, _probe_dahua, _probe_axis, _probe_foscam, _probe_onvif)

    unreachable = True
    for attempt in probes:
        try:
            device = attempt(host, port, username, password)
        except requests.Timeout:
            continue
        except requests.ConnectionError:
            continue  # this port/path is closed, another probe may still work
        except Exception:
            log.debug("Probe %s failed for %s", attempt.__name__, host, exc_info=True)
            unreachable = False
            continue

        unreachable = False
        if device is not None:
            return CameraProbeResult(
                detected=True,
                brand=device.brand,
                model=device.model,
                firmware=device.firmware,
                serial_number=device.serial_number,
                rtsp_url=default_rtsp_path(device.brand),
                supports_device_face_engine=bool(device.model and FACE_CAPABLE.search(device.model)),
            )

    detail = (
        "دستگاه در این آدرس پاسخ نداد"
        if unreachable
        else "دستگاه پاسخ داد اما شناسایی نشد — نام کاربری/رمز را بررسی کنید"
    )
    return CameraProbeResult(detected=False, detail=detail)


def default_rtsp_path(brand: CameraBrand) -> str | None:
    """The main-stream path each vendor uses, minus host and credentials."""
    return {
        CameraBrand.hikvision: "/Streaming/Channels/101",
        CameraBrand.dahua: "/cam/realmonitor?channel=1&subtype=0",
        CameraBrand.axis: "/axis-media/media.amp",
        CameraBrand.foscam: "/videoMain",
        CameraBrand.topsee: "/0",
    }.get(brand)


# ----------------------------------------------------------------- transports
def _get(host: str, port: int, path: str, username: str | None, password: str | None):
    """GET with digest auth, retried as basic — Axis and older Dahua use basic."""
    url = f"http://{host}:{port}{path}"
    response = requests.get(
        url, auth=HTTPDigestAuth(username or "", password or ""), timeout=TIMEOUT
    )
    if response.status_code == 401:
        response = requests.get(
            url, auth=HTTPBasicAuth(username or "", password or ""), timeout=TIMEOUT
        )
    return response


# -------------------------------------------------------------------- vendors
def _probe_hikvision(host: str, port: int, username: str | None, password: str | None) -> Device | None:
    response = _get(host, port, "/ISAPI/System/deviceInfo", username, password)
    if response.status_code != 200 or "<DeviceInfo" not in response.text:
        return None

    return Device(
        brand=CameraBrand.hikvision,
        model=_xml(response.text, "model"),
        firmware=_xml(response.text, "firmwareVersion"),
        serial_number=_xml(response.text, "serialNumber"),
    )


def _probe_dahua(host: str, port: int, username: str | None, password: str | None) -> Device | None:
    response = _get(host, port, "/cgi-bin/magicBox.cgi?action=getDeviceType", username, password)
    if response.status_code != 200 or "type=" not in response.text:
        return None

    model = _kv(response.text, "type")
    firmware = serial = None

    # Firmware and serial live behind two more calls; a failure there must not
    # sink an otherwise successful identification.
    try:
        firmware = _kv(
            _get(host, port, "/cgi-bin/magicBox.cgi?action=getSoftwareVersion", username, password).text,
            "version",
        )
        serial = _kv(
            _get(host, port, "/cgi-bin/magicBox.cgi?action=getSerialNo", username, password).text,
            "sn",
        )
    except requests.RequestException:
        log.debug("Dahua detail lookup failed for %s", host, exc_info=True)

    return Device(brand=CameraBrand.dahua, model=model, firmware=firmware, serial_number=serial)


def _probe_axis(host: str, port: int, username: str | None, password: str | None) -> Device | None:
    # Modern firmware: one JSON-RPC call returns everything.
    url = f"http://{host}:{port}/axis-cgi/basicdeviceinfo.cgi"
    body = {"apiVersion": "1.0", "method": "getAllProperties"}
    try:
        response = requests.post(
            url, json=body, auth=HTTPDigestAuth(username or "", password or ""), timeout=TIMEOUT
        )
        if response.status_code == 200:
            properties = response.json()["data"]["propertyList"]
            return Device(
                brand=CameraBrand.axis,
                model=properties.get("ProdNbr") or properties.get("ProdShortName"),
                firmware=properties.get("Version"),
                serial_number=properties.get("SerialNumber"),
            )
    except (requests.RequestException, KeyError, ValueError, json.JSONDecodeError):
        log.debug("Axis basicdeviceinfo unavailable on %s", host, exc_info=True)

    # Older firmware: the classic VAPIX parameter dump.
    response = _get(
        host, port, "/axis-cgi/param.cgi?action=list&group=Brand,Properties.Firmware", username, password
    )
    if response.status_code != 200 or "Brand.Brand=AXIS" not in response.text:
        return None

    return Device(
        brand=CameraBrand.axis,
        model=_kv(response.text, "root.Brand.ProdNbr") or _kv(response.text, "root.Brand.ProdShortName"),
        firmware=_kv(response.text, "root.Properties.Firmware.Version"),
        serial_number=None,
    )


def _probe_foscam(host: str, port: int, username: str | None, password: str | None) -> Device | None:
    """Foscam's CGIProxy takes the credentials as query parameters."""
    user = quote(username or "", safe="")
    secret = quote(password or "", safe="")
    url = (
        f"http://{host}:{port}/cgi-bin/CGIProxy.fcgi"
        f"?cmd=getDevInfo&usr={user}&pwd={secret}"
    )
    response = requests.get(url, timeout=TIMEOUT)
    if response.status_code != 200 or "<productName>" not in response.text:
        return None

    return Device(
        brand=CameraBrand.foscam,
        model=_xml(response.text, "productName"),
        firmware=_xml(response.text, "firmwareVer"),
        serial_number=_xml(response.text, "serialNo"),
    )


def _probe_onvif(host: str, port: int, username: str | None, password: str | None) -> Device | None:
    """Brand-neutral fallback: ONVIF GetDeviceInformation.

    Sent as a plain SOAP POST so the API container needs no ONVIF client
    library; devices that demand WS-Security simply answer 401 and we give up.
    """
    envelope = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">'
        "<s:Body>"
        '<GetDeviceInformation xmlns="http://www.onvif.org/ver10/device/wsdl"/>'
        "</s:Body></s:Envelope>"
    )
    response = requests.post(
        f"http://{host}:{port}/onvif/device_service",
        data=envelope.encode(),
        headers={"Content-Type": "application/soap+xml; charset=utf-8"},
        auth=HTTPDigestAuth(username or "", password or ""),
        timeout=TIMEOUT,
    )
    if response.status_code != 200 or "GetDeviceInformationResponse" not in response.text:
        return None

    manufacturer = (_xml(response.text, "Manufacturer") or "").lower()
    model = _xml(response.text, "Model") or ""
    brand = CameraBrand.onvif
    for known, value in (
        ("hikvision", CameraBrand.hikvision),
        ("dahua", CameraBrand.dahua),
        ("axis", CameraBrand.axis),
        ("foscam", CameraBrand.foscam),
        ("topsee", CameraBrand.topsee),
        ("tpsee", CameraBrand.topsee),
    ):
        if known in manufacturer:
            brand = value
            break
    else:
        # OEM boards (TH38J and relatives) answer ONVIF with the integrator's
        # own name, or none at all — the model string is the real giveaway.
        if TOPSEE_MODEL.search(model) or TOPSEE_MODEL.search(manufacturer):
            brand = CameraBrand.topsee

    return Device(
        brand=brand,
        model=_xml(response.text, "Model"),
        firmware=_xml(response.text, "FirmwareVersion"),
        serial_number=_xml(response.text, "SerialNumber"),
    )


# --------------------------------------------------------------- tiny parsers
def _xml(text: str, tag: str) -> str | None:
    """Read one element, ignoring any namespace prefix on it."""
    match = re.search(rf"<(?:\w+:)?{tag}[^>]*>([^<]+)</(?:\w+:)?{tag}>", text, re.I)
    return match.group(1).strip() or None if match else None


def _kv(text: str, key: str) -> str | None:
    """Read `key=value` from a CGI response body."""
    match = re.search(rf"^{re.escape(key)}=(.*)$", text, re.I | re.M)
    return match.group(1).strip() or None if match else None
