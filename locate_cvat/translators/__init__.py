"""
Universal Annotation Translators for CVAT, COCO, Skeletons, and 3D Cuboids.
"""

from locate_cvat.translators.coco_translator import COCOTranslator
from locate_cvat.translators.skeleton_translator import SkeletonCOCOTranslator
from locate_cvat.translators.cuboid_3d_translator import CuboidAndPolylineTranslator

__all__ = ["COCOTranslator", "SkeletonCOCOTranslator", "CuboidAndPolylineTranslator"]
