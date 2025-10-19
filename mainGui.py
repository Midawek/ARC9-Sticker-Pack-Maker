import tkinter as tk
from tkinter import filedialog, messagebox
import os
import sys
import ctypes

# --- Determine the base path for bundled assets and modules ---
if getattr(sys, 'frozen', False):
    # Running as a PyInstaller executable
    BASE_PATH = sys._MEIPASS # Path to the temporary bundle folder for assets
    OUTPUT_BASE_PATH = os.path.dirname(sys.executable) # Path to the actual .exe location for output
else:
    # Running as a script
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))
    OUTPUT_BASE_PATH = BASE_PATH

# --- Consolidate sys.path modification here ---
# Add the script's base path (for arc9_sticker_creator.py and VTFLibWrapper)
if BASE_PATH not in sys.path:
    sys.path.insert(0, BASE_PATH)

# Add the libs path (for PIL/Pillow)
LIBS_PATH = os.path.join(BASE_PATH, 'libs')
if LIBS_PATH not in sys.path:
    sys.path.insert(0, LIBS_PATH)

# --- Now import modules ---
try:
    from PIL import Image, ImageTk
except ImportError:
    messagebox.showerror("Import Error", "Pillow (PIL) is not found. Please ensure the 'libs' folder with Pillow is in the same directory as this script.")
    sys.exit(1)

try:
    import arc9_sticker_creator as core
except ImportError as e:
    messagebox.showerror("Import Error", f"Could not import core script 'arc9_sticker_creator.py'.\nError: {e}\nPlease make sure it's in the same directory.")
    sys.exit(1)

class StickerCreatorGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ARC9 Sticker Pack Maker++")
        self.geometry("600x750")
        self.resizable(False, False)

        # --- Get script directory (now BASE_PATH) ---
        self.script_dir = BASE_PATH # For assets
        self.output_dir = OUTPUT_BASE_PATH # For output folders

        # --- Load Custom Font ---
        try:
            font_path = os.path.join(self.script_dir, 'venryn-sans.regular.otf')
            if ctypes.windll.gdi32.AddFontResourceW(font_path) > 0:
                self.FONT_FAMILY = "Venryn Sans"
            else:
                raise Exception("Failed to load font resource via GDI32.")
        except Exception as e:
            print(f"Could not load custom font, falling back to Segoe UI. Error: {e}")
            self.FONT_FAMILY = "Segoe UI"

        # --- Style Data ---
        self.BG_COLOR = "#2d2d2d"
        self.FG_COLOR = "#e0e0e0"
        self.ENTRY_BG = "#222222"
        self.BTN_PRIMARY_BG = "#4c005f"
        self.BTN_PRIMARY_ACTIVE_BG = "#bf00be"
        self.BTN_SECONDARY_BG = "#4a4a4a"
        self.FONT_NORMAL = (self.FONT_FAMILY, 11)
        self.FONT_BOLD = (self.FONT_FAMILY, 11, "bold")
        self.FONT_HEADER = (self.FONT_FAMILY, 14, "bold")
        
        self.configure(background=self.BG_COLOR)

        # --- Set Icon ---
        try:
            logo_path = os.path.join(self.script_dir, 'logo.png')
            self.icon_image = ImageTk.PhotoImage(file=logo_path)
            self.iconphoto(True, self.icon_image)
        except Exception as e:
            print(f"Could not load logo.png: {e}")

        # --- Main Container ---
        container = tk.Frame(self, bg=self.BG_COLOR)
        container.pack(side="top", fill="both", expand=True, padx=10, pady=10)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        self.processing_data = {}

        for F in (SetupFrame, ProcessingFrame):
            frame = F(container, self)
            self.frames[F] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_frame(SetupFrame)

    def show_frame(self, cont):
        frame = self.frames[cont]
        frame.tkraise()

    def start_processing(self, image_folder, pack_name):
        images_to_process = []
        for filename in sorted(os.listdir(image_folder)):
            file_path = os.path.join(image_folder, filename)
            if os.path.isdir(file_path): continue
            try:
                with Image.open(file_path) as img:
                    original_name = os.path.splitext(filename)[0]
                    is_animated = getattr(img, 'is_animated', False) and img.n_frames > 1
                    images_to_process.append({"path": file_path, "original_name": original_name, "type": "animated" if is_animated else "static"})
            except (IOError, SyntaxError):
                continue

        if not images_to_process:
            messagebox.showinfo("Info", "No images found in the selected folder.")
            return
            
        self.processing_data = {
            "pack_name": pack_name,
            "images": images_to_process,
            "processed_info": []
        }
        
        processing_frame = self.frames[ProcessingFrame]
        processing_frame.start()
        self.show_frame(ProcessingFrame)

class SetupFrame(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=controller.BG_COLOR)
        self.controller = controller
        
        # --- Banner ---
        self.banner_image = None
        try:
            banner_path = os.path.join(self.controller.script_dir, 'banner.png')
            img = Image.open(banner_path).convert("RGBA")
            img.thumbnail((500, 150), Image.LANCZOS)
            self.banner_image = ImageTk.PhotoImage(img)
            banner_label = tk.Label(self, image=self.banner_image, bg=controller.BG_COLOR)
            banner_label.pack(pady=(10, 25))
        except FileNotFoundError:
            print("INFO: 'banner.png' not found, skipping banner display.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load banner.png: {e}")

        # --- Widgets ---
        frame = tk.LabelFrame(self, text="1. Setup Pack", 
                              bg=controller.BG_COLOR, fg=controller.FG_COLOR, 
                              font=controller.FONT_BOLD, relief='flat', borderwidth=2)
        frame.pack(padx=10, pady=10, fill="x", ipady=5)
        frame.columnconfigure(1, weight=1)

        tk.Label(frame, text="Image Folder", bg=controller.BG_COLOR, fg=controller.FG_COLOR, font=controller.FONT_NORMAL).grid(row=0, column=0, padx=15, pady=10, sticky="w")
        
        self.folder_path_var = tk.StringVar()
        folder_entry = tk.Entry(frame, textvariable=self.folder_path_var, 
                                bg=controller.ENTRY_BG, fg=controller.FG_COLOR,
                                relief='flat', state='readonly', readonlybackground=controller.ENTRY_BG,
                                font=controller.FONT_NORMAL)
        folder_entry.grid(row=0, column=1, padx=5, pady=10, sticky="ew", ipady=4)

        browse_button = tk.Button(frame, text="Browse...", 
                                  bg=controller.BTN_SECONDARY_BG, fg='white', 
                                  activebackground='#777777', activeforeground='white',
                                  command=self.browse_folder, relief='flat', borderwidth=0,
                                  font=controller.FONT_BOLD)
        browse_button.grid(row=0, column=2, padx=(5,15), pady=10, ipady=2, ipadx=5)

        tk.Label(frame, text="Pack Name", bg=controller.BG_COLOR, fg=controller.FG_COLOR, font=controller.FONT_NORMAL).grid(row=1, column=0, padx=15, pady=10, sticky="w")
        
        self.pack_name_var = tk.StringVar()
        self.pack_name_entry = tk.Entry(frame, textvariable=self.pack_name_var,
                                   bg=controller.ENTRY_BG, fg=controller.FG_COLOR, relief='flat',
                                   font=controller.FONT_NORMAL)
        self.pack_name_entry.grid(row=1, column=1, columnspan=1, padx=5, pady=10, sticky="ew", ipady=4)
        self.pack_name_entry.bind("<KeyRelease>", lambda e: self.hide_caution())

        # --- Caution Icon ---
        try:
            caution_path = os.path.join(self.controller.script_dir, 'Caution.png')
            img = Image.open(caution_path).resize((20, 20), Image.LANCZOS)
            self.caution_image = ImageTk.PhotoImage(img)
            self.caution_label = tk.Label(frame, image=self.caution_image, bg=controller.BG_COLOR)
        except Exception as e:
            print(f"Could not load Caution.png: {e}")
            self.caution_label = tk.Label(frame, text="!", fg="yellow", bg=controller.BG_COLOR, font=controller.FONT_BOLD)

        start_button = tk.Button(self, text="Start Processing",
                                 bg=controller.BTN_PRIMARY_BG, fg='white',
                                 activebackground=controller.BTN_PRIMARY_ACTIVE_BG, activeforeground='white',
                                 command=self.on_start, relief='flat', borderwidth=0, font=controller.FONT_BOLD,
                                 padx=10, pady=8)
        start_button.pack(pady=25)

    def browse_folder(self):
        folder_selected = filedialog.askdirectory(initialdir=self.controller.script_dir)
        if folder_selected:
            self.folder_path_var.set(folder_selected)

    def validate(self):
        pack_name_ok = bool(self.pack_name_var.get().strip())
        folder_ok = bool(self.folder_path_var.get().strip())

        if not pack_name_ok:
            self.caution_label.grid(row=1, column=2, padx=(0, 15), sticky='w')
        
        if not folder_ok:
            messagebox.showwarning("Validation Error", "Image Folder cannot be empty.")

        return pack_name_ok and folder_ok

    def hide_caution(self):
        self.caution_label.grid_remove()
            
    def on_start(self):
        self.hide_caution()
        if self.validate():
            pack_name = core.remove_emojis(self.pack_name_var.get())
            self.controller.start_processing(self.folder_path_var.get(), pack_name)

class ProcessingFrame(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=controller.BG_COLOR)
        self.controller = controller
        self.current_index = 0
        self.image_photo = None

        # --- Widgets ---
        self.header_label = tk.Label(self, text="Processing Image 1 of N", 
                                     bg=controller.BG_COLOR, fg=controller.FG_COLOR,
                                     font=controller.FONT_HEADER)
        self.header_label.pack(pady=(5, 15))

        self.image_label = tk.Label(self, bg=controller.ENTRY_BG, anchor='center')
        self.image_label.pack(pady=10, padx=10, fill="both", expand=True)

        details_frame = tk.LabelFrame(self, text="2. Enter Details", 
                                      bg=controller.BG_COLOR, fg=controller.FG_COLOR,
                                      font=controller.FONT_BOLD, relief='flat', borderwidth=2)
        details_frame.pack(padx=10, pady=10, fill="x", ipady=5)
        details_frame.columnconfigure(1, weight=1)

        tk.Label(details_frame, text="Display Name", bg=controller.BG_COLOR, fg=controller.FG_COLOR, font=controller.FONT_NORMAL).grid(row=0, column=0, padx=15, pady=10, sticky="w")
        self.print_name_var = tk.StringVar()
        tk.Entry(details_frame, textvariable=self.print_name_var,
                 bg=controller.ENTRY_BG, fg=controller.FG_COLOR, relief='flat', font=controller.FONT_NORMAL).grid(row=0, column=1, padx=(5,15), pady=10, sticky="ew", ipady=4)

        tk.Label(details_frame, text="Description", bg=controller.BG_COLOR, fg=controller.FG_COLOR, font=controller.FONT_NORMAL).grid(row=1, column=0, padx=15, pady=10, sticky="w")
        self.desc_var = tk.StringVar()
        tk.Entry(details_frame, textvariable=self.desc_var,
                 bg=controller.ENTRY_BG, fg=controller.FG_COLOR, relief='flat', font=controller.FONT_NORMAL).grid(row=1, column=1, padx=(5,15), pady=10, sticky="ew", ipady=4)

        # --- Buttons ---
        button_frame = tk.Frame(self, bg=controller.BG_COLOR)
        button_frame.pack(pady=20, padx=10, fill="x")
        
        back_button = tk.Button(button_frame, text="< Back to Setup", 
                                bg=controller.BTN_SECONDARY_BG, fg='white',
                                activebackground='#777777', activeforeground='white',
                                command=lambda: controller.show_frame(SetupFrame),
                                relief='flat', borderwidth=0, font=controller.FONT_BOLD, padx=10, pady=8)
        back_button.pack(side="left")

        self.next_button = tk.Button(button_frame, text="Next Image >", 
                                     bg=controller.BTN_PRIMARY_BG, fg='white',
                                     activebackground=controller.BTN_PRIMARY_ACTIVE_BG, activeforeground='white',
                                     command=self.next_image, relief='flat', borderwidth=0, font=controller.FONT_BOLD, padx=10, pady=8)
        self.next_button.pack(side="right")

    def start(self):
        self.current_index = 0
        self.show_image()

    def show_image(self):
        data = self.controller.processing_data
        num_images = len(data["images"])
        self.header_label.config(text=f"Processing Image {self.current_index + 1} of {num_images}")

        image_info = data["images"][self.current_index]
        
        try:
            self.image_label.after(50, lambda: self.load_image_preview(image_info["path"]))
        except Exception as e:
            error_text = "Error preparing image preview:\n" + str(e)
            self.image_label.config(text=error_text, image='')
            print(error_text)

        self.print_name_var.set(core.remove_emojis(image_info["original_name"].replace('_', ' ').title()))
        self.desc_var.set("")

        if self.current_index == num_images - 1:
            self.next_button.config(text="Finish & Create Pack")
        else:
            self.next_button.config(text="Next Image >")

    def load_image_preview(self, path):
        try:
            w, h = self.image_label.winfo_width(), self.image_label.winfo_height()
            if w <= 1 or h <= 1: # Widget not drawn yet
                self.image_label.after(100, lambda: self.load_image_preview(path))
                return
            img = Image.open(path).convert("RGBA")
            img.thumbnail((w - 20, h - 20), Image.LANCZOS)
            self.image_photo = ImageTk.PhotoImage(img)
            self.image_label.config(image=self.image_photo, text="")
        except Exception as e:
            error_text = "Error loading image:\n" + str(e)
            self.image_label.config(text=error_text, image='')
            print(error_text)

    def next_image(self):
        current_image_info = self.controller.processing_data["images"][self.current_index]
        print_name = self.print_name_var.get()
        if not print_name.strip():
            messagebox.showwarning("Validation Error", "Display Name cannot be empty.")
            return

        compact_name = core.sanitize_for_filename(print_name)
        
        self.controller.processing_data["processed_info"].append({
            **current_image_info,
            "print_name": print_name,
            "description": core.remove_emojis(self.desc_var.get()),
            "compact_name": compact_name
        })

        self.current_index += 1
        if self.current_index < len(self.controller.processing_data["images"]):
            self.show_image()
        else:
            self.finish_creation()

    def finish_creation(self):
        data = self.controller.processing_data
        pack_name = data["pack_name"]
        processed_info = data["processed_info"]
        
        if not processed_info:
            messagebox.showwarning("Warning", "No images were processed.")
            self.controller.destroy()
            return

        try:
            core.create_addon_structure(self.controller.output_dir, pack_name)

            successful_images = []
            for info in processed_info:
                if core.process_image_to_vtf(self.controller.output_dir, info, pack_name, info["compact_name"]):
                    successful_images.append(info)
            
            if successful_images:
                core.create_lua_script(self.controller.output_dir, pack_name, successful_images)
                messagebox.showinfo("Success", f"Successfully created/updated the '{pack_name}' sticker pack!\n\nThank you for using the ARC9 Sticker Pack Maker! ♡")
            else:
                messagebox.showwarning("Warning", "No images were successfully converted.\n\nThank you for using the creator.")
        except Exception as e:
            messagebox.showerror("An Error Occurred", f"An unexpected error occurred:\n{e}")
            import traceback
            traceback.print_exc()
        finally:
            self.controller.destroy()

if __name__ == "__main__":
    app = StickerCreatorGUI()
    app.mainloop()
