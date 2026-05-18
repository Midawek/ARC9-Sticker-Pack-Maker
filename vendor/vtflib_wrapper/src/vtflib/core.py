import os
import platform
import sys
import logging
from ctypes import (
    CDLL, WinDLL, POINTER, cast, byref, c_int, c_uint32, c_bool, c_char_p,
    c_int32, c_float, c_byte, c_ubyte, create_string_buffer, c_uint
)
from typing import Optional, Union, Any

from . import enums
from . import structures

logger = logging.getLogger(__name__)

PLATFORM_NAME = platform.system()
BASE_DIR = os.path.dirname(__file__)
BIN_DIR = os.path.join(BASE_DIR, 'bin')


def pointer_to_array(ptr, size, type_cls=c_ubyte):
    """
    Casts a pointer to a ctypes array of a specific size and type.
    Returns a pointer to the array. Access .contents to get the array itself.
    """
    return cast(ptr, POINTER(type_cls * size))


class VTFLib:
    _lib: Union[CDLL, WinDLL] = None

    def __init__(self):
        self._load_library()
        self.initialize()
        self.image_buffer = c_int()
        self.create_image(byref(self.image_buffer))
        self.bind_image(self.image_buffer)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()

    def _load_library(self):
        if self._lib is not None:
            return

        if PLATFORM_NAME == "Windows":
            is64bit = platform.architecture(executable=sys.executable, bits='', linkage='')[0] == "64bit"
            lib_name = "VTFLib.x64.dll" if is64bit else "VTFLib.x86.dll"
            lib_path = os.path.join(BIN_DIR, lib_name)
            self._lib = WinDLL(lib_path)
        elif PLATFORM_NAME == "Linux":
            # On linux we assume this lib is in a predictable location or in bin
            # VTFLib Linux: https://github.com/panzi/VTFLib
            # requires: libtxc_dxtn
            dxtn_lib_name = os.path.join(BIN_DIR, "libtxc_dxtn.so")
            lib_name = os.path.join(BIN_DIR, "libVTFLib13.so")
            
            try:
                CDLL(dxtn_lib_name)
            except OSError:
                logger.warning(f"Could not load {dxtn_lib_name}. Trying system default or ignoring.")

            try:
                self._lib = CDLL(lib_name)
            except OSError:
                # Fallback to system library
                self._lib = CDLL("libVTFLib.so")
        else:
            raise NotImplementedError(f"Platform {PLATFORM_NAME} is not supported.")
        
        self._setup_prototypes()

    def _setup_prototypes(self):
        lib = self._lib

        # Version
        lib.vlGetVersion.argtypes = []
        lib.vlGetVersion.restype = c_uint32

        lib.vlGetVersionString.argtypes = []
        lib.vlGetVersionString.restype = c_char_p

        # Init/Shutdown
        lib.vlInitialize.argtypes = []
        lib.vlInitialize.restype = c_bool

        lib.vlShutdown.argtypes = []
        lib.vlShutdown.restype = c_bool

        # Error
        lib.vlGetLastError.argtypes = []
        lib.vlGetLastError.restype = c_char_p

        # Options
        lib.vlGetBoolean.argtypes = [enums.Option]
        lib.vlGetBoolean.restype = c_bool
        lib.vlSetBoolean.argtypes = [enums.Option, c_bool]
        lib.vlSetBoolean.restype = None

        lib.vlGetInteger.argtypes = [c_int32]
        lib.vlGetInteger.restype = c_int32
        lib.vlSetInteger.argtypes = [enums.Option, c_int32]
        lib.vlSetInteger.restype = None

        lib.vlGetFloat.argtypes = [c_int32]
        lib.vlGetFloat.restype = c_float
        lib.vlSetFloat.argtypes = [enums.Option, c_float]
        lib.vlSetFloat.restype = None

        # Image Management
        lib.vlImageIsBound.argtypes = []
        lib.vlImageIsBound.restype = c_bool

        lib.vlBindImage.argtypes = [c_int32]
        lib.vlBindImage.restype = c_bool

        lib.vlCreateImage.argtypes = [POINTER(c_int)]
        lib.vlCreateImage.restype = c_bool

        lib.vlDeleteImage.argtypes = [POINTER(c_int32)]
        lib.vlDeleteImage.restype = None

        lib.vlImageCreateDefaultCreateStructure.argtypes = [POINTER(structures.CreateOptions)]
        lib.vlImageCreateDefaultCreateStructure.restype = None

        lib.vlImageCreate.argtypes = [c_int32, c_int32, c_int32, c_int32, c_int32, enums.ImageFormat, c_bool, c_bool, c_bool]
        lib.vlImageCreate.restype = c_byte

        lib.vlImageCreateSingle.argtypes = [c_int32, c_int32, POINTER(c_byte), POINTER(structures.CreateOptions)]
        lib.vlImageCreateSingle.restype = c_bool

        lib.vlImageDestroy.argtypes = []
        lib.vlImageDestroy.restype = None

        lib.vlImageIsLoaded.argtypes = []
        lib.vlImageIsLoaded.restype = c_bool

        lib.vlImageLoad.argtypes = [c_char_p, c_bool]
        lib.vlImageLoad.restype = c_bool

        lib.vlImageSave.argtypes = [c_char_p]
        lib.vlImageSave.restype = c_bool

        # Image Info
        lib.vlImageGetSize.argtypes = []
        lib.vlImageGetSize.restype = c_int32

        lib.vlImageGetWidth.argtypes = []
        lib.vlImageGetWidth.restype = c_int32

        lib.vlImageGetHeight.argtypes = []
        lib.vlImageGetHeight.restype = c_int32

        lib.vlImageGetDepth.argtypes = []
        lib.vlImageGetDepth.restype = c_int32

        lib.vlImageGetFrameCount.argtypes = []
        lib.vlImageGetFrameCount.restype = c_int32

        lib.vlImageGetFaceCount.argtypes = []
        lib.vlImageGetFaceCount.restype = c_int32

        lib.vlImageGetMipmapCount.argtypes = []
        lib.vlImageGetMipmapCount.restype = c_int32

        lib.vlImageGetStartFrame.argtypes = []
        lib.vlImageGetStartFrame.restype = c_int32
        lib.vlImageSetStartFrame.argtypes = [c_int32]
        lib.vlImageSetStartFrame.restype = None

        lib.vlImageGetFlags.argtypes = []
        lib.vlImageGetFlags.restype = c_int32
        lib.vlImageSetFlags.argtypes = [c_uint32] # Changed from c_float to c_uint32
        lib.vlImageSetFlags.restype = None

        lib.vlImageGetFormat.argtypes = []
        lib.vlImageGetFormat.restype = enums.ImageFormat

        lib.vlImageGetData.argtypes = [c_uint32, c_uint32, c_uint32, c_uint32]
        lib.vlImageGetData.restype = POINTER(c_byte)

        lib.vlImageSetData.argtypes = [c_uint32, c_uint32, c_uint32, c_uint32, POINTER(c_byte)]
        lib.vlImageSetData.restype = None

        # Thumbnail
        lib.vlImageGetHasThumbnail.argtypes = []
        lib.vlImageGetHasThumbnail.restype = c_bool

        lib.vlImageGetThumbnailWidth.argtypes = []
        lib.vlImageGetThumbnailWidth.restype = c_int32

        lib.vlImageGetThumbnailHeight.argtypes = []
        lib.vlImageGetThumbnailHeight.restype = c_int32

        lib.vlImageGetThumbnailFormat.argtypes = []
        lib.vlImageGetThumbnailFormat.restype = enums.ImageFormat

        lib.vlImageGetThumbnailData.argtypes = []
        lib.vlImageGetThumbnailData.restype = POINTER(c_byte)

        lib.vlImageSetThumbnailData.argtypes = [POINTER(c_byte)]
        lib.vlImageSetThumbnailData.restype = None

        # Generation
        lib.vlImageGenerateMipmaps.argtypes = [c_uint32, c_uint32, c_uint32, c_uint32]
        lib.vlImageGenerateMipmaps.restype = c_bool

        lib.vlImageGenerateAllMipmaps.argtypes = [c_uint32, c_uint32]
        lib.vlImageGenerateAllMipmaps.restype = c_bool

        lib.vlImageGenerateThumbnail.argtypes = []
        lib.vlImageGenerateThumbnail.restype = c_bool

        lib.vlImageGenerateNormalMap.argtypes = [c_uint32, c_uint32, c_uint32, c_uint32]
        lib.vlImageGenerateNormalMap.restype = c_bool

        lib.vlImageGenerateAllNormalMaps.argtypes = [c_uint32, c_uint32, c_uint32, c_uint32]
        lib.vlImageGenerateAllNormalMaps.restype = c_bool

        lib.vlImageGenerateSphereMap.argtypes = []
        lib.vlImageGenerateSphereMap.restype = c_bool

        lib.vlImageComputeReflectivity.argtypes = []
        lib.vlImageComputeReflectivity.restype = c_bool

        lib.vlImageComputeImageSize.argtypes = [c_int32, c_uint32, c_int32, c_uint32, c_int32]
        lib.vlImageComputeImageSize.restype = c_uint32

        # Transform
        lib.vlImageFlipImage.argtypes = [POINTER(c_byte), c_uint32, c_int32]
        lib.vlImageFlipImage.restype = None

        lib.vlImageMirrorImage.argtypes = [POINTER(c_byte), c_uint32, c_int32]
        lib.vlImageMirrorImage.restype = None

        lib.vlImageConvertToRGBA8888.argtypes = [POINTER(c_byte), POINTER(c_byte), c_uint32, c_uint32, c_uint32]
        lib.vlImageConvertToRGBA8888.restype = c_bool # Changed from None to c_bool

        lib.vlImageConvert.argtypes = [POINTER(c_byte), POINTER(c_byte), c_uint32, c_uint32, c_uint32, c_int32]
        lib.vlImageConvert.restype = c_bool # Changed from None to c_bool

        # Proc
        lib.vlGetProc.argtypes = [enums.Proc]
        lib.vlGetProc.restype = POINTER(c_int32)
        lib.vlSetProc.argtypes = [enums.Proc, POINTER(c_int32)]
        lib.vlSetProc.restype = None

    def get_version(self) -> int:
        return self._lib.vlGetVersion()

    def initialize(self) -> bool:
        return self._lib.vlInitialize()

    def shutdown(self) -> bool:
        return self._lib.vlShutdown()

    def get_str_version(self) -> str:
        return self._lib.vlGetVersionString().decode('utf-8')

    def get_last_error(self) -> str:
        # According to original code, need to decode potentially
        error = self._lib.vlGetLastError().decode('utf-8', "replace")
        return error if error else "No errors"

    def get_boolean(self, option: enums.Option) -> bool:
        return self._lib.vlGetBoolean(option)

    def set_boolean(self, option: enums.Option, value: bool) -> None:
        self._lib.vlSetBoolean(option, value)

    def get_integer(self, option: enums.Option) -> int:
        return self._lib.vlGetInteger(option)

    def set_integer(self, option: enums.Option, value: int) -> None:
        self._lib.vlSetInteger(option, value)

    def get_float(self, option: enums.Option) -> float:
        return self._lib.vlGetFloat(option)

    def set_float(self, option: enums.Option, value: float) -> None:
        self._lib.vlSetFloat(option, value)

    def image_is_bound(self) -> bool:
        return self._lib.vlImageIsBound()

    def bind_image(self, image: int) -> bool:
        return self._lib.vlBindImage(image)

    def create_image(self, image) -> bool:
        return self._lib.vlCreateImage(image)

    def delete_image(self, image) -> None:
        self._lib.vlDeleteImage(image)

    def create_default_params_structure(self) -> structures.CreateOptions:
        create_options = structures.CreateOptions()
        self._lib.vlImageCreateDefaultCreateStructure(byref(create_options))
        return create_options

    def image_create(self, width, height, frames, faces, slices,
                     image_format, thumbnail, mipmaps, nulldata) -> int:
        return self._lib.vlImageCreate(width, height, frames, faces,
                                       slices, image_format, thumbnail, mipmaps, nulldata)

    def image_create_single(self, width: int, height: int, image_data, options) -> bool:
        image_data = cast(image_data, POINTER(c_byte))
        return self._lib.vlImageCreateSingle(width, height, image_data, options)

    def image_destroy(self) -> None:
        self._lib.vlImageDestroy()

    def image_is_loaded(self) -> bool:
        return self._lib.vlImageIsLoaded()

    def image_load(self, filename: str, header_only: bool = False) -> bool:
        return self._lib.vlImageLoad(create_string_buffer(filename.encode('ascii')), header_only)

    def image_save(self, filename: str) -> bool:
        return self._lib.vlImageSave(create_string_buffer(filename.encode('ascii')))

    def get_size(self) -> int:
        return self._lib.vlImageGetSize()

    def width(self) -> int:
        return self._lib.vlImageGetWidth()

    def height(self) -> int:
        return self._lib.vlImageGetHeight()

    def depth(self) -> int:
        return self._lib.vlImageGetDepth()

    def frame_count(self) -> int:
        return self._lib.vlImageGetFrameCount()

    def face_count(self) -> int:
        return self._lib.vlImageGetFaceCount()

    def mipmap_count(self) -> int:
        return self._lib.vlImageGetMipmapCount()

    def get_start_frame(self) -> int:
        return self._lib.vlImageGetStartFrame()

    def set_start_frame(self, start_frame: int) -> None:
        self._lib.vlImageSetStartFrame(start_frame)

    def get_image_flags(self) -> enums.ImageFlag:
        return enums.ImageFlag(self._lib.vlImageGetFlags())

    def set_image_flags(self, flags: Union[int, float]) -> None:
        # Original code used c_float for argtype? That seems odd for flags.
        # Checking logic: vlImageSetFlags.argtypes = [c_float] in original wrapper.
        # But flags are usually uint. C++ header says vlImageSetFlags(vlUInt uiImageFlags).
        # Wrapper might have been wrong. I will keep it compatible with original wrapper logic if I must, but fixing it is better.
        # But if the DLL expects int and we send float, ctypes might cast or fail.
        # Original: ImageSetFlags.argtypes = [c_float]
        # I will change it to c_uint32 in _setup_prototypes, assuming the original wrapper was copy-pasted wrong or I'm right.
        # Actually, let's look at `vlImageSetFlags` in C. It takes `vlUInt`.
        # I will fix the argtype in `_setup_prototypes` to `c_uint32`.
        self._lib.vlImageSetFlags(flags)

    def image_format(self) -> enums.ImageFormat:
        return self._lib.vlImageGetFormat()

    def get_image_data(self, frame=0, face=0, slice=0, mipmap_level=0):
        size = self.compute_image_size(self.width(), self.height(), self.depth(), self.mipmap_count(),
                                       self.image_format().value)
        buff = self._lib.vlImageGetData(frame, face, slice, mipmap_level)
        return pointer_to_array(buff, size)

    def get_rgba8888(self):
        size = self.compute_image_size(self.width(), self.height(), self.depth(), self.mipmap_count(),
                                       enums.ImageFormat.ImageFormatRGBA8888)
        if self.image_format() == enums.ImageFormat.ImageFormatRGBA8888:
            return pointer_to_array(self.get_image_data(0, 0, 0, 0), size)

        return pointer_to_array(self.convert_to_rgba8888(), size)

    def set_image_data(self, frame, face, slice, mipmap_level, data) -> None:
        self._lib.vlImageSetData(frame, face, slice, mipmap_level, data)

    def has_thumbnail(self) -> bool:
        return self._lib.vlImageGetHasThumbnail()

    def thumbnail_width(self) -> int:
        return self._lib.vlImageGetThumbnailWidth()

    def thumbnail_height(self) -> int:
        return self._lib.vlImageGetThumbnailHeight()

    def thumbnail_format(self) -> enums.ImageFormat:
        return self._lib.vlImageGetThumbnailFormat()

    def get_thumbnail_format_data(self):
        return self._lib.vlImageGetThumbnailData()

    def set_thumbnail_format_data(self, data) -> None:
        self._lib.vlImageSetThumbnailData(data)

    def generate_mipmaps(self, face, frame, mipmap_filter, sharpness_filter) -> bool:
        return self._lib.vlImageGenerateMipmaps(face, frame, mipmap_filter, sharpness_filter)

    def generate_all_mipmaps(self, mipmap_filter, sharpness_filter) -> bool:
        return self._lib.vlImageGenerateAllMipmaps(mipmap_filter, sharpness_filter)

    def generate_thumbnail(self) -> bool:
        return self._lib.vlImageGenerateThumbnail()

    def generate_normal_maps(self, frame, kernel_filter,
                             height_conversion_method, normal_alpha_result) -> bool:
        return self._lib.vlImageGenerateNormalMap(
            frame, kernel_filter, height_conversion_method, normal_alpha_result)

    def generate_all_normal_maps(self, kernel_filter, height_conversion_method, normal_alpha_result) -> bool:
        return self._lib.vlImageGenerateAllNormalMaps(
            kernel_filter, height_conversion_method, normal_alpha_result)

    def generate_sphere_map(self) -> bool:
        return self._lib.vlImageGenerateSphereMap()

    def compute_reflectivity(self) -> bool:
        return self._lib.vlImageComputeReflectivity()

    def compute_image_size(self, width, height, depth, mipmaps, image_format) -> int:
        return self._lib.vlImageComputeImageSize(
            width, height, depth, mipmaps, image_format)

    def flip_image(self, image_data, width=None, height=None, depth=1, mipmaps=-1):
        width = width or self.width()
        height = height or self.height()
        depth = depth or self.depth()
        mipmaps = mipmaps or self.mipmap_count()
        
        if self.image_format() != enums.ImageFormat.ImageFormatRGBA8888:
            logger.info('Converting to RGBA8888 for flipping')
            image_data = self.convert_to_rgba8888()
            
        image_data = cast(image_data, POINTER(c_byte))
        self._lib.vlImageFlipImage(image_data, width, height)
        size = self.compute_image_size(width, height, depth, mipmaps,
                                       enums.ImageFormat.ImageFormatRGBA8888)

        return pointer_to_array(image_data, size)

    def flip_image_external(self, image_data, width=None, height=None):
        width = width or self.width()
        height = height or self.height()
        image_data_p = cast(image_data, POINTER(c_byte))
        self._lib.vlImageFlipImage(image_data_p, width, height)
        size = width * height * 4

        return pointer_to_array(image_data, size)

    def mirror_image(self, image_data):
        if self.image_format() != enums.ImageFormat.ImageFormatRGBA8888:
            image_data = self.convert_to_rgba8888()
        image_data = cast(image_data, POINTER(c_byte))
        self._lib.vlImageMirrorImage(image_data, self.width(), self.height())
        size = self.compute_image_size(self.width(), self.height(), self.depth(), self.mipmap_count(),
                                       enums.ImageFormat.ImageFormatRGBA8888)

        return pointer_to_array(image_data, size)

    def convert_to_rgba8888(self):
        new_size = self.compute_image_size(self.width(), self.height(), self.depth(), self.mipmap_count(),
                                           enums.ImageFormat.ImageFormatRGBA8888)
        new_buffer = cast(create_string_buffer(init=new_size), POINTER(c_byte))
        
        # Note: vlImageConvertToRGBA8888 return type is void in C (usually) or boolean?
        # wrapper said it returns None (void).
        # Checking: vlImageConvertToRGBA8888(vlByte *lpSource, vlByte *lpDest, vlUInt uiWidth, vlUInt uiHeight, vlUInt uiSourceFormat);
        # It returns vlBool in C!
        # Original wrapper: restype = None.
        # If it returns bool, checking "if not self.ImageConvertToRGBA8888...".implies it expects a return value.
        # But `restype = None` means it returns python `None`.
        # `if not None:` is True. So it always entered the `if` block?
        # "if not self.ImageConvertToRGBA8888(...): return pointer..."
        # This means if it returns FALSE (fail), it returns pointer? That logic seems backwards or checking for success.
        # If C function returns True on success.
        # `if not True` -> False. It goes to else -> sys.stderr.write('CAN\'T CONVERT IMAGE\n')
        # So it expects True on success.
        # So `restype` SHOULD be `c_bool`.
        
        if self._lib.vlImageConvertToRGBA8888(self.get_image_data(0, 0, 0, 0), new_buffer, self.width(), self.height(),
                                           self.image_format().value):
             return pointer_to_array(new_buffer, new_size)
        else:
            logger.error('CAN\'T CONVERT IMAGE')
            return 0

    def convert(self, format_enum):
        logger.info(
            "Converting from {} to {}".format(
                self.image_format().name,
                enums.ImageFormat(format_enum).name))
        new_size = self.compute_image_size(
            self.width(),
            self.height(),
            self.depth(),
            self.mipmap_count(),
            format_enum)
        new_buffer = cast((c_byte * new_size)(), POINTER(c_byte))
        
        # Same logic for vlImageConvert: returns vlBool.
        if self._lib.vlImageConvert(self.get_image_data(0, 0, 0, 0), new_buffer, self.width(), self.height(),
                                 self.image_format().value, format_enum):
            return pointer_to_array(new_buffer, new_size)
        else:
            logger.error('CAN\'T CONVERT IMAGE')
            return 0

    def get_proc(self, proc: enums.Proc) -> int:
        try:
            return self._lib.vlGetProc(proc).contents.value
        except BaseException:
            logger.error("ERROR IN GetProc")
            return -1

    def set_proc(self, proc: enums.Proc, value) -> None:
        self._lib.vlSetProc(proc, value)
