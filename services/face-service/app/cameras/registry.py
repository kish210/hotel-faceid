"""Brand -> adapter mapping. Register a new brand here and nowhere else."""

from .axis import AxisCamera
from .base import BaseCamera, CameraConfig
from .dahua import DahuaCamera
from .foscam import FoscamCamera
from .hikvision import HikvisionCamera
from .topsee import TopseeCamera
from .onvif_camera import GenericCamera, OnvifCamera

ADAPTERS: dict[str, type[BaseCamera]] = {
    DahuaCamera.brand: DahuaCamera,
    HikvisionCamera.brand: HikvisionCamera,
    AxisCamera.brand: AxisCamera,
    FoscamCamera.brand: FoscamCamera,
    TopseeCamera.brand: TopseeCamera,
    OnvifCamera.brand: OnvifCamera,
    GenericCamera.brand: GenericCamera,
}


def build_camera(config: CameraConfig) -> BaseCamera:
    adapter = ADAPTERS.get(config.brand, OnvifCamera)
    return adapter(config)
