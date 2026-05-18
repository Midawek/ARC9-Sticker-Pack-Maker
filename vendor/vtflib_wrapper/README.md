# VTFLib Wrapper

A Python wrapper for Nem's VTFLib, designed to provide a Pythonic interface for manipulating VTF (Valve Texture Format) files.

## Installation

You can install this package via pip:

```bash
pip install .
```

(Once published to PyPI, you can install it using `pip install vtflib-wrapper`)

## Requirements

- **Windows**: The package includes the necessary DLLs (`VTFLib.x86.dll` and `VTFLib.x64.dll`).
- **Linux**: You may need to install VTFLib and `libtxc_dxtn` manually or ensure `libVTFLib.so` is in your library path.

## Usage

### Basic Example

The library supports usage as a context manager, which handles initialization and shutdown automatically.

```python
from vtflib import VTFLib, ImageFormat

# Initialize the library
with VTFLib() as vtf:
    print(f"VTFLib Version: {vtf.get_str_version()}")

    # Create a new image
    width, height = 512, 512
    vtf.image_create(
        width, height, 
        frames=1, faces=1, slices=1, 
        image_format=ImageFormat.ImageFormatRGBA8888, 
        thumbnail=False, mipmaps=False, nulldata=False
    )
    
    if vtf.image_is_loaded():
        print(f"Image created: {vtf.width()}x{vtf.height()}")

    # Save the image
    # vtf.image_save("output.vtf")
```

### Manual Initialization

You can also manually initialize and shutdown the library.

```python
from vtflib import VTFLib

vtf = VTFLib()
# Library is initialized in __init__
# ... operations ...
vtf.shutdown()
```

## Structure

- `vtflib.core`: Main `VTFLib` class.
- `vtflib.enums`: Enumerations for formats, flags, etc.
- `vtflib.structures`: ctypes structures used by the library.
