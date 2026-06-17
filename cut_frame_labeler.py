import re
import yaml
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk


class CutFrameLabelerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Python Frame Labeler")
        self.root.geometry("1100x850")

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # State
        self.frames_path = None
        self.output_path = None
        self.characters = []
        self.frame_files = []
        self.current_index = 0
        self.current_frame = None
        self.checkbox_vars = []
        self.checkbox_widgets = []
        self.photo = None

        # Top row: YAML selector
        top_frame = tk.Frame(root)
        top_frame.pack(fill="x", padx=10, pady=10)

        self.select_btn = tk.Button(top_frame, text="Select YAML", command=self.select_yaml)
        self.select_btn.pack(side="left")

        self.yaml_entry = tk.Entry(top_frame, width=90)
        self.yaml_entry.pack(side="left", padx=10, fill="x", expand=True)

        # Main area
        main_frame = tk.Frame(root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Left: image viewer
        left_frame = tk.Frame(main_frame)
        left_frame.pack(side="left", fill="both", expand=True)

        self.canvas = tk.Canvas(left_frame, width=700, height=500, bg="black")
        self.canvas.pack(fill="both", expand=True)

        self.status_label = tk.Label(left_frame, text="", font=("Arial", 16, "bold"))
        self.status_label.pack(pady=10)

        nav_frame = tk.Frame(left_frame)
        nav_frame.pack(pady=10)

        self.prev_btn = tk.Button(nav_frame, text="Prev", width=12, command=self.prev_frame)
        self.prev_btn.pack(side="left", padx=5)

        self.next_btn = tk.Button(nav_frame, text="Next", width=12, command=self.next_frame)
        self.next_btn.pack(side="left", padx=5)

        # Right: checkbox panel with scrollbar
        right_frame = tk.Frame(main_frame, width=280)
        right_frame.pack(side="right", fill="y", padx=10)

        tk.Label(right_frame, text="Characters", font=("Arial", 14, "bold")).pack(anchor="w")

        self.checkbox_canvas = tk.Canvas(right_frame, width=260, height=650)
        self.checkbox_canvas.pack(side="left", fill="y", expand=False)

        scrollbar = tk.Scrollbar(right_frame, orient="vertical", command=self.checkbox_canvas.yview)
        scrollbar.pack(side="right", fill="y")

        self.checkbox_canvas.configure(yscrollcommand=scrollbar.set)

        self.checkbox_frame = tk.Frame(self.checkbox_canvas)
        self.checkbox_canvas.create_window((0, 0), window=self.checkbox_frame, anchor="nw")

        self.checkbox_frame.bind(
            "<Configure>",
            lambda e: self.checkbox_canvas.configure(scrollregion=self.checkbox_canvas.bbox("all"))
        )

    def select_yaml(self):
        yaml_file = filedialog.askopenfilename(
            title="Select YAML file",
            filetypes=[("YAML files", "*.yml *.yaml"), ("All files", "*.*")]
        )
        if not yaml_file:
            return

        self.yaml_entry.delete(0, tk.END)
        self.yaml_entry.insert(0, yaml_file)

        try:
            with open(yaml_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except Exception as e:
            messagebox.showerror("YAML error", f"Could not read YAML file:\n{e}")
            return

        # Required keys
        try:
            self.frames_path = Path(data["frames_path"])
            self.output_path = Path(data["output_path"])
            self.characters = list(data["characters"])
        except Exception as e:
            messagebox.showerror("YAML format error", f"Missing or invalid YAML fields:\n{e}")
            return

        self.output_path.mkdir(parents=True, exist_ok=True)

        # Load and sort frames
        self.frame_files = self.get_sorted_jpg_files(self.frames_path)
        if not self.frame_files:
            messagebox.showerror("No frames found", f"No .jpg files found in:\n{self.frames_path}")
            return

        # Create checkboxes
        self.build_checkboxes()

        # Show first frame
        self.current_index = 0
        self.load_current_frame()

    def get_sorted_jpg_files(self, folder: Path):
        jpgs = list(folder.glob("*.jpg"))

        def extract_number(p: Path):
            digits = re.sub(r"\D", "", p.stem)
            return int(digits) if digits else -1

        return sorted(jpgs, key=extract_number)

    def build_checkboxes(self):
        # Clear old checkboxes
        for widget in self.checkbox_frame.winfo_children():
            widget.destroy()

        self.checkbox_vars = []
        self.checkbox_widgets = []

        for char in self.characters:
            var = tk.BooleanVar(value=False)
            cb = tk.Checkbutton(self.checkbox_frame, text=char, variable=var)
            cb.pack(anchor="w", pady=2)
            self.checkbox_vars.append(var)
            self.checkbox_widgets.append(cb)

    def get_checked_labels(self):
        return [
            self.characters[i]
            for i, var in enumerate(self.checkbox_vars)
            if var.get()
        ]

    def save_char_to_text(self, txt_fp: Path, checked_labels):
        txt_fp.parent.mkdir(parents=True, exist_ok=True)
        with open(txt_fp, "w", encoding="utf-8") as f:
            for label in checked_labels:
                f.write(f"- {label}\n")

    def load_text_labels(self, txt_fp: Path):
        labels = []
        with open(txt_fp, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("- "):
                    labels.append(line[2:].strip())
                elif line:
                    labels.append(line)
        return labels

    def check_labels(self, file_labels):
        file_set = set(file_labels)
        for i, char in enumerate(self.characters):
            self.checkbox_vars[i].set(char in file_set)

    def set_all_checks_to_false(self):
        for var in self.checkbox_vars:
            var.set(False)

    def current_txt_path(self):
        if self.current_frame is None:
            return None
        return self.output_path / self.current_frame.with_suffix(".txt").name

    def load_current_frame(self):
        if not self.frame_files:
            return

        self.current_frame = self.frame_files[self.current_index]
        try:
            img = Image.open(self.current_frame)
        except Exception as e:
            messagebox.showerror("Image error", f"Could not open image:\n{self.current_frame}\n\n{e}")
            return

        # Fit image to canvas while preserving aspect ratio
        canvas_w = max(self.canvas.winfo_width(), 1)
        canvas_h = max(self.canvas.winfo_height(), 1)

        # In case window has not fully rendered yet, use fallback size
        if canvas_w < 10 or canvas_h < 10:
            canvas_w, canvas_h = 700, 500

        img_ratio = img.width / img.height
        canvas_ratio = canvas_w / canvas_h

        if img_ratio > canvas_ratio:
            new_w = canvas_w
            new_h = int(canvas_w / img_ratio)
        else:
            new_h = canvas_h
            new_w = int(canvas_h * img_ratio)

        resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(resized)

        self.canvas.delete("all")
        self.canvas.create_image(canvas_w // 2, canvas_h // 2, image=self.photo, anchor="center")
        self.canvas.create_text(
            10, 10, anchor="nw",
            text=self.current_frame.name,
            fill="white",
            font=("Arial", 14, "bold")
        )

        total = len(self.frame_files)
        percent = round(100 * (self.current_index + 1) / total, 1)
        self.status_label.config(text=f"{self.current_index + 1}/{total}: {percent}%")

        txt_fp = self.current_txt_path()
        if txt_fp.exists():
            try:
                file_labels = self.load_text_labels(txt_fp)
                self.check_labels(file_labels)
            except Exception as e:
                messagebox.showwarning("Label file error", f"Could not read:\n{txt_fp}\n\n{e}")
                self.set_all_checks_to_false()
        else:
            self.set_all_checks_to_false()

    def save_current_labels(self):
        if self.current_frame is None:
            return
        txt_fp = self.current_txt_path()
        labels = self.get_checked_labels()
        self.save_char_to_text(txt_fp, labels)

    def next_frame(self):
        if not self.frame_files:
            return

        self.save_current_labels()

        if self.current_index >= len(self.frame_files) - 1:
            messagebox.showinfo("End", "Can't go further forward, this is the last frame.")
            return

        self.current_index += 1
        self.load_current_frame()

    def prev_frame(self):
        if not self.frame_files:
            return

        self.save_current_labels()

        if self.current_index <= 0:
            messagebox.showinfo("Start", "Can't go further back, this is the first frame.")
            return

        self.current_index -= 1
        self.load_current_frame()


    def on_close(self):
        self.save_current_labels()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = CutFrameLabelerApp(root)
    root.mainloop()
