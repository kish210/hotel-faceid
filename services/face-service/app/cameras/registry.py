"""Brand -> adapter mapping. Register a new brand here and nowhere else."""

from .axis import AxisCamera
from .base import BaseCamera, CameraConfig
from .dahua import DahuaCamera
from .hikvision import HikvisionCamera
from .onvif_camera import GenericCamera, OnvifCamera

ADAPTERS: dict[str, type[BaseCamera]] = {
    DahuaCamera.brand: DahuaCamera,
    HikvisionCamera.brand: HikvisionCamera,
    AxisCamera.brand: AxisCamera,
    OnvifCamera.brand: OnvifCamera,
    GenericCamera.brand: GenericCamera,
}


def build_camera(config: CameraConfig) -> BaseCamera:
    adapter = ADAPTERS.get(config.brand, OnvifCamera)
    return adapter(config)
