import os
import sys
import re
import subprocess
from ctypes import cast, POINTER, c_byte

# --- Determine the base path for bundled assets and modules ---
if getattr(sys, 'frozen', False):
    # Running as a PyInstaller executable
    BASE_PATH = sys._MEIPASS # Path to the temporary bundle folder for assets
    # For CLI output, we want the directory of the actual .exe
    OUTPUT_ADDON_ROOT = os.path.dirname(sys.executable)
else:
    # Running as a script
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))
    OUTPUT_ADDON_ROOT = BASE_PATH

# --- Consolidate sys.path modification here ---
# Add the script's base path (for VTFLibWrapper)
if BASE_PATH not in sys.path:
    sys.path.insert(0, BASE_PATH)

# Add the libs path (for PIL/Pillow)
LIBS_PATH = os.path.join(BASE_PATH, 'libs')
if LIBS_PATH not in sys.path:
    sys.path.insert(0, LIBS_PATH)

# --- Dependency Management ---
try:
    from PIL import Image, ImageSequence
except ImportError:
    print("ERROR: Pillow (PIL) is not found in the 'libs' folder or Python path.")
    print("Please ensure the 'libs' folder with Pillow is in the same directory as this script.")
    input("\nPress Enter to exit.")
    sys.exit(1)

try:
    import VTFLibWrapper.VTFLib as VTFLib
    import VTFLibWrapper.VTFLibEnums as VTFLibEnums
except ImportError as e:
    print("ERROR: Could not import the VTFLib wrapper.")
    print("Please ensure the 'VTFLibWrapper' folder (containing VTFLib.py, etc.) is in the same directory as this script.")
    input("\nPress Enter to exit.")
    sys.exit(1)

# --- Main Application Logic ---

def remove_emojis(text):
    """Removes a wide range of emojis and symbols from a string."""
    if not text: return ""
    # A more comprehensive regex for emojis and symbols
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002700-\U000027BF"  # Dingbats
        "\U000024C2-\U0001F251" 
        "\U0001f926-\U0001f937"
        "\U00010000-\U0010ffff"
        "\u2640-\u2642"
        "\u2600-\u2B55"
        "\u200d"
        "\u23cf"
        "\u23e9"
        "\u231a"
        "\ufe0f"  # dingbats
        "\u3030"
        "]+", flags=re.UNICODE)
    return emoji_pattern.sub(r'', text)

def sanitize_for_filename(name):
    """Removes emojis, spaces, special characters, and converts to lowercase for filenames."""
    name_no_emoji = remove_emojis(name)
    return re.sub(r'[^a-zA-Z0-9]', '', name_no_emoji).lower()

def letterbox_image(img, max_size=512):
    """Resizes an image to fit within a square, power-of-two canvas, padding with transparency.
    If the image is square, it's scaled up to max_size to appear larger in-game.
    """
    # New logic: If image is square, scale it up to the max size for a larger sticker.
    if img.width == img.height:
        img = img.resize((max_size, max_size), Image.LANCZOS)
    # Existing logic for non-square or oversized images
    elif img.width > max_size or img.height > max_size:
        img.thumbnail((max_size, max_size), Image.LANCZOS)
    
    largest_dim = max(img.width, img.height)
    if largest_dim == 0: return None # Skip empty frames
    
    # Find the next power of two for the canvas
    canvas_size = 1
    while canvas_size < largest_dim:
        canvas_size *= 2
        
    canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    paste_x = (canvas_size - img.width) // 2
    paste_y = (canvas_size - img.height) // 2
    canvas.paste(img, (paste_x, paste_y))
    return canvas

def create_addon_structure(base_path, pack_name):
    """Create the necessary directory structure for the ARC9 addon."""
    os.makedirs(os.path.join(base_path, f"arc9_{pack_name}_stickers", "lua", "arc9", "common", "attachments_bulk"), exist_ok=True)
    os.makedirs(os.path.join(base_path, f"arc9_{pack_name}_stickers", "materials", "stickers", pack_name), exist_ok=True)

def create_vmt(vmt_path, pack_name, compact_name, is_animated, framerate):
    """Creates a .vmt file for either a static or animated sticker."""
    material_path = f"stickers/{pack_name}/{compact_name}".replace("\\", "/")

    if is_animated:
        vmt_content = f'''"VertexLitGeneric"
{{
    "$basetexture" "{material_path}"
    "$alphatest" "1"
    "$decal" "1"
    "$nocull" "1"
    "Proxies"
    {{
        "AnimatedTexture"
        {{
            "animatedTextureVar" "$basetexture"
            "animatedTextureFrameNumVar" "$frame"
            "animatedTextureFrameRate" "{framerate}"
        }}
    }}
}}'''
    else:
        vmt_content = f'''"VertexLitGeneric"
{{
    "$basetexture" "{material_path}"
    "$alphatest" "1"
    "$decal" "1"
    "$nocull" "1"
}}'''
    with open(vmt_path, "w", encoding="utf-8") as f:
        f.write(vmt_content)

def process_image_to_vtf(base_path, image_info, pack_name, compact_name):
    """Processes a given image (static or animated) and creates VTF and VMT files."""
    addon_root = os.path.join(base_path, f"arc9_{pack_name}_stickers")
    vtf_path = os.path.join(addon_root, "materials", "stickers", pack_name, f"{compact_name}.vtf")
    vmt_path = os.path.join(addon_root, "materials", "stickers", pack_name, f"{compact_name}.vmt")
    
    vtf_lib = VTFLib.VTFLib()
    try:
        with Image.open(image_info["path"]) as img:
            is_animated = image_info["type"] == 'animated' and getattr(img, 'is_animated', False)

            options = vtf_lib.create_default_params_structure()
            options.ImageFormat = VTFLibEnums.ImageFormat.ImageFormatDXT5
            options.Flags |= VTFLibEnums.ImageFlag.ImageFlagEightBitAlpha
            options.Resize = False

            if is_animated:
                # --- CORRECT ANIMATED VTF CREATION USING THE WRAPPER ---
                frames = []
                durations = []
                for frame in ImageSequence.Iterator(img):
                    letterboxed_frame = letterbox_image(frame.convert("RGBA"))
                    if letterboxed_frame:
                        frames.append(letterboxed_frame)
                        durations.append(frame.info.get('duration', 100))

                if not frames: raise Exception("Could not extract frames from animated image.")

                w, h = frames[0].size
                avg_duration_ms = sum(durations) / len(durations)
                framerate = round(1000 / avg_duration_ms) if avg_duration_ms > 0 else 15
                if framerate == 0: framerate = 15

                # 1. Create an empty multi-frame image with all required arguments
                if not vtf_lib.image_create(w, h, len(frames), 1, 1, options.ImageFormat, False, False, True):
                     raise Exception(f"image_create failed for animated VTF: {vtf_lib.get_last_error()}")

                # 2. Add each frame's data using the correct set_image_data method
                for i, frame in enumerate(frames):
                    frame_bytes = frame.tobytes()
                    frame_buffer_ptr = cast(frame_bytes, POINTER(c_byte))
                    # Use the correct method name: set_image_data
                    vtf_lib.set_image_data(i, 0, 0, 0, frame_buffer_ptr)

                create_vmt(vmt_path, pack_name, compact_name, True, framerate)
            else:
                # --- Static Image Processing ---
                texture = letterbox_image(img.convert("RGBA"))
                w, h = texture.size
                image_bytes = texture.tobytes()
                image_buffer_ptr = cast(image_bytes, POINTER(c_byte))

                if not vtf_lib.image_create_single(w, h, image_buffer_ptr, options):
                    raise Exception(f"image_create_single failed: {vtf_lib.get_last_error()}")
                
                create_vmt(vmt_path, pack_name, compact_name, False, 0)

            # 3. Save the final VTF file
            if not vtf_lib.image_save(vtf_path):
                raise Exception(f"image_save failed: {vtf_lib.get_last_error()}")
            
            return True

    except Exception as e:
        print(f"Error processing {image_info['original_name']}: {e}")
        return False
    finally:
        if vtf_lib:
            vtf_lib.shutdown()

def create_lua_script(base_path, pack_name, processed_images):
    """Create or append to the Lua script for the ARC9 addon from pre-processed info."""
    addon_root = os.path.join(base_path, f"arc9_{pack_name}_stickers")
    lua_path = os.path.join(addon_root, "lua", "arc9", "common", "attachments_bulk", f"a9sm_{pack_name}.lua")

    file_existed = os.path.exists(lua_path) and os.path.getsize(lua_path) > 0

    with open(lua_path, "a", encoding="utf-8") as f:
        if file_existed:
            f.write("\n")

        for info in processed_images:
            print_name = remove_emojis(info["print_name"]).replace('"', '\"')
            description = remove_emojis(info["description"]).replace(']]', '] ]') # Avoid breaking multiline string

            f.write(f'''SPM = {{}}
SPM.PrintName = "{print_name}"
SPM.CompactName = "{info["compact_name"].upper()}"
SPM.Description = [[{description}]]

SPM.Icon = Material("stickers/{pack_name}/{info["compact_name"]}")

SPM.Free = true

SPM.Category = "stickers"
SPM.Folder = "{pack_name}"

SPM.StickerMaterial = "stickers/{pack_name}/{info["compact_name"]}"

ARC9.LoadAttachment(SPM, "sticker_{pack_name}_{info["compact_name"]}")

''')

def main():
    """Main script execution flow."""
    logo = """
┏━ ┏━┓┏━┓┏━╸┏━┓ ━┓   ┏━┓╺┳╸╻┏━╸╻┏ ┏━╸┏━┓   ┏━┓┏━┓┏━╸╻┏    ┏┳┓┏━┓╻┏ ┏━╸┏━┓ ╻  ╻ 
┃  ┣━┫┣┳┛┃  ┗━┫  ┃   ┗━┓ ┃ ┃┃  ┣┻┓┣╸ ┣┳┛   ┣━┛┣━┫┃  ┣┻┓   ┃┃┃┣━┫┣┻┓┣╸ ┣┳┛╺╋╸╺╋╸
┗━ ╹ ╹╹┗╸┗━╸┗━┛ ━┛   ┗━┛ ╹ ╹┗━╸╹ ╹┗━╸╹┗╸   ╹  ╹ ╹┗━╸╹ ╹   ╹ ╹╹ ╹╹ ╹┗━╸╹┗╸ ╹  ╹ 
        ♡ by Midawek ♡ Made with love for ARC9 Community ♡
      """
                                                                                                                                                                                 
    print(f"\033[95m{logo}\033[0m")
    
    # Determine the base directory for output
    if getattr(sys, 'frozen', False):
        output_base_path = os.path.dirname(sys.executable)
    else:
        output_base_path = os.path.dirname(os.path.abspath(__file__))

    image_folder_name = input("Enter the name of the folder with images: ")
    pack_name_input = input("Enter the name of the pack: ")
    pack_name = remove_emojis(pack_name_input)

    # Resolve image folder path relative to current working directory if not absolute
    if os.path.isabs(image_folder_name):
        image_folder_path = image_folder_name
    else:
        image_folder_path = os.path.join(os.getcwd(), image_folder_name)

    if not os.path.isdir(image_folder_path):
        print(f"Error: Folder '{image_folder_path}' not found.")
        input("\nPress Enter to exit.")
        return

    # 1. DISCOVERY PHASE: Try to open all files with Pillow
    images_to_process = []
    print("\nScanning for images...")
    for filename in sorted(os.listdir(image_folder_path)):
        file_path = os.path.join(image_folder_path, filename)
        if os.path.isdir(file_path): continue
        try:
            with Image.open(file_path) as img:
                original_name = os.path.splitext(filename)[0]
                is_animated = getattr(img, 'is_animated', False) and img.n_frames > 1
                images_to_process.append({
                    "path": file_path, 
                    "original_name": original_name, 
                    "type": "animated" if is_animated else "static"
                })
                print(f"Found {'animated' if is_animated else 'static'} image: {filename}")
        except (IOError, SyntaxError):
            continue # Skip files that are not images

    # 2. NAMING PHASE
    processed_info = []
    manual_naming = input("\nManually name each sticker and add a description? (y/n): ").lower().strip() == 'y'
    for item in images_to_process:
        default_print_name = item["original_name"].replace('_', ' ').title()
        print_name = default_print_name
        description = ""

        if manual_naming:
            print("\n----------------------------------------")
            print(f"Processing: {item['original_name']}")
            user_print_name = input(f"Enter display name (or press Enter for default: '{default_print_name}'): ")
            if user_print_name:
                print_name = user_print_name
            description = input("Enter description (optional): ")
        
        compact_name = sanitize_for_filename(print_name)
        item["print_name"] = print_name
        item["description"] = description
        item["compact_name"] = compact_name
        processed_info.append(item)

    # 3. CREATION PHASE
    create_addon_structure(output_base_path, pack_name)
    successful_images = []
    print("\nStarting image conversion...")
    for info in processed_info:
        print(f"Processing '{info['original_name']}' -> '{info['compact_name']}.vtf'...")
        if process_image_to_vtf(output_base_path, info, pack_name, info["compact_name"]):
            successful_images.append(info)

    # 4. FINALIZATION PHASE
    if successful_images:
        print("\nConversion complete. Now generating Lua script...")
        create_lua_script(output_base_path, pack_name, successful_images)
        print(f"\nSuccessfully created the '{pack_name}' sticker pack!")
    else:
        print("\nNo images were successfully converted. Addon creation aborted.")

    input("\nPress Enter to exit.")

if __name__ == "__main__":
    main()
