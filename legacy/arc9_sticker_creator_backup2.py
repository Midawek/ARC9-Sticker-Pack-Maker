import os                                                                                                                                                                                                                                                        #Made you look haha
import sys
import re
import subprocess
from ctypes import cast, POINTER, c_byte

# --- Dependency Management ---
# Add the bundled libraries to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'libs'))

try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow (PIL) is not found in the 'libs' folder.")
    print("Please make sure the 'libs' folder with Pillow is in the same directory as this script.")
    input("\nPress Enter to exit.")
    sys.exit(1)

# Add the wrapper to the Python path so we can import it
sys.path.insert(0, os.path.dirname(__file__))

try:
    import VTFLibWrapper.VTFLib as VTFLib
    import VTFLibWrapper.VTFLibEnums as VTFLibEnums
except ImportError as e:
    print("ERROR: Could not import the VTFLib wrapper.")
    print("Please ensure the 'VTFLibWrapper' folder (containing VTFLib.py, etc.) is in the same directory as this script.")
    input("\nPress Enter to exit.")
    sys.exit(1)

# --- Main Application Logic ---

def sanitize_for_filename(name):
    """Removes spaces, special characters, and converts to lowercase for filenames."""
    return re.sub(r'[^a-zA-Z0-9]', '', name).lower()

def letterbox_image(img, max_size=512):
    """Resizes an image to fit within a square, power-of-two canvas, padding with transparency."""
    if img.width > max_size or img.height > max_size:
        img.thumbnail((max_size, max_size), Image.LANCZOS)
    largest_dim = max(img.width, img.height)
    canvas_size = 1 << (largest_dim - 1).bit_length()
    canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    paste_x = (canvas_size - img.width) // 2
    paste_y = (canvas_size - img.height) // 2
    canvas.paste(img, (paste_x, paste_y))
    return canvas

def create_addon_structure(base_path, pack_name):
    """Create the necessary directory structure for the ARC9 addon."""
    os.makedirs(os.path.join(base_path, f"arc9_{pack_name}_stickers", "lua", "arc9", "common", "attachments_bulk"), exist_ok=True)
    os.makedirs(os.path.join(base_path, f"arc9_{pack_name}_stickers", "materials", "stickers", pack_name), exist_ok=True)

def create_vtf_and_vmt(base_path, image_obj, pack_name, compact_name):
    """Create a static DXT5 VTF and VMT file from a given PIL Image object."""
    addon_root = os.path.join(base_path, f"arc9_{pack_name}_stickers")
    vtf_path = os.path.join(addon_root, "materials", "stickers", pack_name, f"{compact_name}.vtf")
    vmt_path = os.path.join(addon_root, "materials", "stickers", pack_name, f"{compact_name}.vmt")
    vtf_lib = None
    try:
        vtf_lib = VTFLib.VTFLib()
        texture = letterbox_image(image_obj.convert("RGBA"))
        w, h = texture.size
        image_bytes = texture.tobytes()
        image_buffer_ptr = cast(image_bytes, POINTER(c_byte))

        options = vtf_lib.create_default_params_structure()
        options.ImageFormat = VTFLibEnums.ImageFormat.ImageFormatDXT5
        options.Flags |= VTFLibEnums.ImageFlag.ImageFlagEightBitAlpha
        options.Resize = False # We are handling resizing ourselves :3

        if not vtf_lib.image_create_single(w, h, image_buffer_ptr, options):
            raise Exception(f"image_create_single failed. Error: {vtf_lib.get_last_error()}")

        if not vtf_lib.image_save(vtf_path):
            raise Exception(f"image_save failed. Error: {vtf_lib.get_last_error()}")

        with open(vmt_path, "w") as f:
            f.write(f'''VertexLitGeneric
{{
    "$basetexture" "stickers/{pack_name}/{compact_name}"
    "$alphatest" 1
    "$decal" 1
    "$nocull" 1
}}''')
        return True
    except Exception as e:
        print(f"Error creating VTF/VMT for {compact_name}: {e}")
        return False
    finally:
        if vtf_lib:
            vtf_lib.image_destroy()
            vtf_lib.shutdown()

def create_lua_script(base_path, pack_name, processed_images):
    """Create the Lua script for the ARC9 addon from pre-processed info."""
    addon_root = os.path.join(base_path, f"arc9_{pack_name}_stickers")
    lua_path = os.path.join(addon_root, "lua", "arc9", "common", "attachments_bulk", f"a9sm_{pack_name}.lua")
    with open(lua_path, "w") as f:
        for info in processed_images:
            f.write(f'''ATT = {{}}
ATT.PrintName = "{info["print_name"]}"
ATT.CompactName = "{info["compact_name"].upper()}"
ATT.Description = [[{info["description"]}]]
ATT.Icon = Material("stickers/{pack_name}/{info["compact_name"]}")
ATT.Free = true
ATT.Category = "stickers"
ATT.Folder = "{pack_name}"
ATT.StickerMaterial = "stickers/{pack_name}/{info["compact_name"]}"
ARC9.LoadAttachment(ATT, "sticker_{pack_name}_{info["compact_name"]}")

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
    
    # Determine the base directory (for exe or script)
    if getattr(sys, 'frozen', False):
        # Running as a compiled exe
        script_dir = os.path.dirname(sys.executable)
    else:
        # Running as a .py script
        script_dir = os.path.dirname(os.path.abspath(__file__))

    image_folder_name = input("Enter the name of the folder with images: ")
    pack_name = input("Enter the name of the pack: ")

    # Use absolute paths based on the script's location
    image_folder_path = os.path.join(script_dir, image_folder_name)

    if not os.path.isdir(image_folder_path):
        print(f"Error: Folder '{image_folder_path}' not found.")
        input("\nPress Enter to exit.")
        return

    # 1. DISCOVERY PHASE: Find all images
    images_to_process = []
    print("\nScanning for images...")
    for filename in os.listdir(image_folder_path):
        file_path = os.path.join(image_folder_path, filename)
        original_name = os.path.splitext(filename)[0]
        if filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            images_to_process.append({"path": file_path, "original_name": original_name, "type": "static"})

    # 2. NAMING PHASE: Get all user input upfront
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
        
        # CompactName is now derived from the final PrintName
        compact_name = sanitize_for_filename(print_name)
        item["print_name"] = print_name
        item["description"] = description
        item["compact_name"] = compact_name
        processed_info.append(item)

    # 3. CREATION PHASE: Process all images with final names
    create_addon_structure(script_dir, pack_name)
    successful_images = []
    print("\nStarting image conversion...")
    for info in processed_info:
        print(f"Processing '{info['original_name']}' -> '{info['compact_name']}.vtf'...")
        image_obj = None
        try:
            if info["type"] == "static":
                image_obj = Image.open(info["path"])

            if image_obj and create_vtf_and_vmt(script_dir, image_obj, pack_name, info["compact_name"]):
                successful_images.append(info)
        finally:
            if image_obj:
                image_obj.close()

    # 4. FINALIZATION PHASE
    if successful_images:
        print("\nConversion complete. Now generating Lua script...")
        create_lua_script(script_dir, pack_name, successful_images)
        print(f"\nSuccessfully created the '{pack_name}' sticker pack!")
    else:
        print("\nNo images were successfully converted. Addon creation aborted.")

    input("\nPress Enter to exit.")

if __name__ == "__main__":
    main()
