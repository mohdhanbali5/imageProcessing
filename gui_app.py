import base64
import json
import os
import subprocess
import sys
import time
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import cv2
from object_detection_dip import detect_all, draw_result, imread_color

APP_DIR = Path(__file__).parent
IMAGE_DIR = APP_DIR / "images"
OUTPUT_DIR = APP_DIR / "results"
OUTPUT_DIR.mkdir(exist_ok=True)

# ===== NEW PALETTE: Midnight Teal Modern Vibe =====
PALETTE = {
    "paper": "#121317",      # main background
    "paper2": "#1A1D24",     # secondary background
    "card": "#1E222A",       # card background
    "card2": "#252A35",      # card alt background
    "input": "#101216",      # input fields background
    "blue": "#2A9D8F",       # primary accent (teal)
    "blue2": "#238276",      # primary hover
    "blue3": "#174E46",      # primary light bg
    "cyan": "#4ECDC4",       # secondary accent (cyan)
    "cyan2": "#36B8AF",      # secondary hover
    "cyan3": "#1E5F59",      # secondary light bg
    "orange": "#F4A261",     # warning/accent (warm)
    "orange2": "#E88D47",    # warning hover
    "orange3": "#48321E",    # warning light bg
    "purple": "#9B5DE5",     # extra accent
    "purple2": "#7B3FCC",    # extra hover
    "purple3": "#2D1A42",    # extra light bg
    "green": "#2EC4B6",      # success
    "green2": "#219E8A",     # success hover
    "green3": "#163832",     # success light bg
    "red": "#E76F51",        # danger
    "red2": "#D55D3F",       # danger hover
    "red3": "#4C2C1E",       # danger light bg
    "ink": "#E5E9F0",        # primary text
    "muted": "#8D94A6",      # secondary text
    "muted2": "#5C6474",     # tertiary text
    "line": "#2D323E",       # borders
    "line2": "#424958",      # borders light
    "success": "#2EC4B6",    # success
    "warning": "#F4A261",    # warning
    "danger": "#E76F51",     # danger
}
# =================================================

METHOD_DISPLAY = {
    "template": "Template Matching",
    "edge": "Edge Detection",
    "histogram": "Color Histogram",
    "hybrid": "Hybrid Fusion"
}

def cv_to_photo(img_bgr, max_w=900, max_h=520):
    h, w = img_bgr.shape[:2]
    scale = min(max_w / max(w, 1), max_h / max(h, 1), 1.0)
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))
    resized = cv2.resize(img_bgr, (new_w, new_h), interpolation=cv2.INTER_AREA)
    ok, buffer = cv2.imencode(".png", resized)
    if not ok:
        raise RuntimeError("Could not encode preview image.")
    encoded = base64.b64encode(buffer.tobytes()).decode("ascii")
    return tk.PhotoImage(data=encoded)

class PillButton(tk.Button):
    def __init__(self, master, **kwargs):
        bg = kwargs.pop("bg", PALETTE["blue"])
        fg = kwargs.pop("fg", "#FFFFFF")
        hover_bg = kwargs.pop("hover_bg", PALETTE["blue2"])
        hover_fg = kwargs.pop("hover_fg", "#FFFFFF")
        super().__init__(master, bg=bg, fg=fg, activebackground=hover_bg,
                         activeforeground=hover_fg, bd=0, relief="flat",
                         padx=16, pady=10, cursor="hand2",
                         font=("Segoe UI", 10, "bold"), **kwargs)
        self.default_bg = bg
        self.default_fg = fg
        self.hover_bg = hover_bg
        self.hover_fg = hover_fg
        self.bind("<Enter>", self._hover_in)
        self.bind("<Leave>", self._hover_out)

    def _hover_in(self, _event):
        self.configure(bg=self.hover_bg, fg=self.hover_fg)

    def _hover_out(self, _event):
        self.configure(bg=self.default_bg, fg=self.default_fg)

class PlumMintStudio:
    def __init__(self, root):
        self.root = root
      
        self.root.geometry("1480x880")
        self.root.minsize(1060, 680)
        self.root.configure(bg=PALETTE["paper"])
        self.scene_var = tk.StringVar(value="")
        self.object_var = tk.StringVar(value="")
        self.output_var = tk.StringVar(value=str(OUTPUT_DIR))
        self.method_var = tk.StringVar(value="hybrid")
        self.auto_crop_var = tk.BooleanVar(value=True)
        self.scene_path = None
        self.object_path = None
        self.results = []
        self.scene_photo = None
        self.object_photo = None
        self.output_photo = None
        self.status_var = tk.StringVar(value="Ready to start.")
        self.stage_var = tk.StringVar(value="01  Select Images")
        self.selected_method_var = tk.StringVar(value="Hybrid Fusion")
        self.best_method_var = tk.StringVar(value="—")
        self.confidence_var = tk.StringVar(value="—")
        self.runtime_var = tk.StringVar(value="—")
        self.coordinates_var = tk.StringVar(value="No coordinates yet.")
        self.running_animation = False
        self.animation_index = 0
        self.setup_style()
        self.build_ui()

    def setup_style(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview",
                        background=PALETTE["input"],
                        foreground=PALETTE["ink"],
                        fieldbackground=PALETTE["input"],
                        borderwidth=0,
                        rowheight=32,
                        font=("Segoe UI", 9))
        style.configure("Treeview.Heading",
                        background=PALETTE["blue3"],
                        foreground=PALETTE["ink"],
                        relief="flat",
                        font=("Segoe UI", 9, "bold"))
        style.map("Treeview",
                  background=[("selected", PALETTE["blue"])],
                  foreground=[("selected", "#FFFFFF")])
        style.configure("TCombobox",
                        fieldbackground=PALETTE["input"],
                        background=PALETTE["input"],
                        foreground=PALETTE["ink"],
                        arrowcolor=PALETTE["cyan"],
                        bordercolor=PALETTE["line2"],
                        lightcolor=PALETTE["line2"],
                        darkcolor=PALETTE["line2"])
        style.configure("Studio.Horizontal.TProgressbar",
                        troughcolor=PALETTE["paper2"],
                        background=PALETTE["success"],
                        bordercolor=PALETTE["line"],
                        lightcolor=PALETTE["success"],
                        darkcolor=PALETTE["success"])

    def card(self, master, title=None, subtitle=None, accent=PALETTE["blue"]):
        outer = tk.Frame(master, bg=PALETTE["card"],
                         highlightbackground=PALETTE["line"],
                         highlightthickness=1, bd=0)
        if title:
            header = tk.Frame(outer, bg=PALETTE["card"])
            header.pack(fill="x", padx=16, pady=(14, 4))
            tk.Label(header, text=title, bg=PALETTE["card"],
                     fg=accent, font=("Segoe UI", 12, "bold")).pack(anchor="w")
            if subtitle:
                tk.Label(header, text=subtitle, bg=PALETTE["card"],
                         fg=PALETTE["muted"], font=("Segoe UI", 8)).pack(anchor="w", pady=(2, 0))
        content = tk.Frame(outer, bg=PALETTE["card"])
        content.pack(fill="both", expand=True, padx=16, pady=(8, 16))
        return outer, content

    def path_label(self, master, text):
        return tk.Label(master, text=text, bg=PALETTE["input"], fg=PALETTE["muted"],
                        anchor="w", justify="left", padx=10, pady=8,
                        font=("Consolas", 8),
                        highlightbackground=PALETTE["line"], highlightthickness=1)

    def small_caption(self, master, text):
        return tk.Label(master, text=text, bg=master["bg"], fg=PALETTE["muted"],
                        font=("Segoe UI", 9))

    def shorten_path(self, path, max_len=48):
        path = str(path)
        if len(path) <= max_len:
            return path
        return "..." + path[-max_len:]

    def cv_to_widget_photo(self, img_bgr, widget, fallback_w=760, fallback_h=420, padding=20):
        widget.update_idletasks()
        available_w = widget.winfo_width() - padding
        available_h = widget.winfo_height() - padding
        if available_w < 140:
            available_w = fallback_w
        if available_h < 90:
            available_h = fallback_h
        return cv_to_photo(img_bgr, max_w=max(140, available_w), max_h=max(90, available_h))

    def build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        container = tk.Frame(self.root, bg=PALETTE["paper"])
        container.grid(row=0, column=0, sticky="nsew")
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(container, bg=PALETTE["paper"], highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.scroll_frame = tk.Frame(self.canvas, bg=PALETTE["paper"])
        self.scroll_window = self.canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.scroll_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.scroll_window, width=e.width))
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.scroll_frame.columnconfigure(0, weight=1)
        self.build_header()
        body = tk.Frame(self.scroll_frame, bg=PALETTE["paper"], padx=18, pady=12)
        body.grid(row=1, column=0, sticky="nsew")
        # Two columns: workflow (left) and preview (right) — inspector removed
        body.columnconfigure(0, weight=1, minsize=320)
        body.columnconfigure(1, weight=3, minsize=700)
        body.rowconfigure(0, weight=1)
        self.build_workflow_panel(body)
        self.build_preview_panel(body)
        # Inspector panel (right) completely removed

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def build_header(self):
        header = tk.Frame(self.scroll_frame, bg=PALETTE["paper"], padx=24, pady=18)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        left = tk.Frame(header, bg=PALETTE["paper"])
        left.grid(row=0, column=0, sticky="w")
        
        

    def build_workflow_panel(self, parent):
        left = tk.Frame(parent, bg=PALETTE["paper"])
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left.columnconfigure(0, weight=1)
        workflow_card, workflow = self.card(left, title="Workflow", subtitle="Select images, choose method, and run.",
                                            accent=PALETTE["cyan"])
        workflow_card.grid(row=0, column=0, sticky="nsew")
        workflow.columnconfigure(0, weight=1)
        self.small_caption(workflow, "Scene image").grid(row=0, column=0, sticky="w")
        self.scene_path_label = self.path_label(workflow, "No scene selected")
        self.scene_path_label.grid(row=1, column=0, sticky="ew", pady=(5, 9))
        PillButton(workflow, text="1. Choose Scene", command=self.browse_scene,
                   bg=PALETTE["blue"], hover_bg=PALETTE["blue2"]).grid(row=2, column=0, sticky="ew", pady=(0, 14))
        self.small_caption(workflow, "Query object").grid(row=3, column=0, sticky="w")
        self.object_path_label = self.path_label(workflow, "No object selected")
        self.object_path_label.grid(row=4, column=0, sticky="ew", pady=(5, 9))
        PillButton(workflow, text="2. Choose Object", command=self.browse_object,
                   bg=PALETTE["cyan"], hover_bg=PALETTE["cyan2"]).grid(row=5, column=0, sticky="ew", pady=(0, 14))
        self.small_caption(workflow, "Output folder").grid(row=6, column=0, sticky="w")
        self.output_path_label = self.path_label(workflow, str(OUTPUT_DIR))
        self.output_path_label.grid(row=7, column=0, sticky="ew", pady=(5, 9))
        PillButton(workflow, text="3. Choose Output", command=self.browse_output,
                   bg=PALETTE["orange"], fg="#FFFFFF", hover_bg=PALETTE["orange2"], hover_fg="#FFFFFF").grid(row=8, column=0, sticky="ew", pady=(0, 14))
        controls = tk.Frame(workflow, bg=PALETTE["card"])
        controls.grid(row=9, column=0, sticky="ew", pady=(0, 14))
        controls.columnconfigure(0, weight=1)
        controls.columnconfigure(1, weight=1)
        tk.Checkbutton(controls, text="Auto crop", variable=self.auto_crop_var,
                       bg=PALETTE["card"], fg=PALETTE["ink"], selectcolor=PALETTE["input"],
                       activebackground=PALETTE["card"], activeforeground=PALETTE["blue"],
                       font=("Segoe UI", 9), bd=0).grid(row=0, column=0, sticky="w")
        self.method_combo = ttk.Combobox(controls, textvariable=self.method_var,
                                         values=["template", "edge", "histogram", "hybrid"],
                                         state="readonly", width=12)
        self.method_combo.grid(row=0, column=1, sticky="e")
        self.method_combo.bind("<<ComboboxSelected>>", self.on_method_change)
        PillButton(workflow, text="Run Detection", command=self.detect_object,
                   bg=PALETTE["red"], hover_bg=PALETTE["red2"]).grid(row=10, column=0, sticky="ew", pady=(0, 10))
        action_row = tk.Frame(workflow, bg=PALETTE["card"])
        action_row.grid(row=11, column=0, sticky="ew")
        action_row.columnconfigure(0, weight=1)
        action_row.columnconfigure(1, weight=1)
        PillButton(action_row, text="Clear", command=self.clear_inputs,
                   bg=PALETTE["purple3"], fg=PALETTE["purple"],
                   hover_bg=PALETTE["purple2"], hover_fg="#FFFFFF").grid(row=0, column=0, sticky="ew", padx=(0, 5))
        PillButton(action_row, text="Results", command=self.open_output_folder,
                   bg=PALETTE["green3"], fg=PALETTE["green"],
                   hover_bg=PALETTE["green"], hover_fg="#FFFFFF").grid(row=0, column=1, sticky="ew", padx=(5, 0))
        left.rowconfigure(0, weight=1)

    def build_preview_panel(self, parent):
        center = tk.Frame(parent, bg=PALETTE["paper"])
        center.grid(row=0, column=1, sticky="nsew")
        center.columnconfigure(0, weight=1)
        center.rowconfigure(0, weight=5)
        center.rowconfigure(1, weight=2)
        preview_card, preview = self.card(center, title="Detection Canvas",
                                          subtitle="The selected method is rendered here.",
                                          accent=PALETTE["red"])
        preview_card.grid(row=0, column=0, sticky="nsew", pady=(0, 12))
        preview.columnconfigure(0, weight=1)
        preview.rowconfigure(0, weight=1)
        self.output_label = tk.Label(preview, bg=PALETTE["input"], fg=PALETTE["muted"],
                                     text="No detection yet\n\nChoose images and click Run Detection.",
                                     font=("Segoe UI", 14), justify="center",
                                     highlightbackground=PALETTE["line"], highlightthickness=1)
        self.output_label.grid(row=0, column=0, sticky="nsew")
        bottom_card, bottom = self.card(center, title="Method Scores",
                                        subtitle="Click any row to display that method.",
                                        accent=PALETTE["cyan"])
        bottom_card.grid(row=1, column=0, sticky="nsew")
        bottom.columnconfigure(0, weight=1)
        bottom.rowconfigure(0, weight=1)
        columns = ("method", "score", "x", "y", "w", "h", "time")
        self.table = ttk.Treeview(bottom, columns=columns, show="headings", height=7)
        headers = {"method": "Method", "score": "Confidence", "x": "X", "y": "Y", "w": "W", "h": "H", "time": "Runtime"}
        widths = {"method": 120, "score": 90, "x": 55, "y": 55, "w": 55, "h": 55, "time": 80}
        for col in columns:
            self.table.heading(col, text=headers[col])
            self.table.column(col, width=widths[col], anchor="center", stretch=True)
        self.table.grid(row=0, column=0, sticky="nsew")
        self.table.bind("<<TreeviewSelect>>", self.on_table_select)

    # build_inspector_panel completely removed

    def browse_scene(self):
        path = filedialog.askopenfilename(title="Select Scene Image",
                                          filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.webp"),
                                                     ("All files", "*.*")],
                                          initialdir=str(IMAGE_DIR))
        if path:
            self.scene_var.set(path)
            self.scene_path_label.configure(text=self.shorten_path(path), fg=PALETTE["cyan"])
            self.stage_var.set("02  Select Object")

    def browse_object(self):
        path = filedialog.askopenfilename(title="Select Object Image",
                                          filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.webp"),
                                                     ("All files", "*.*")],
                                          initialdir=str(IMAGE_DIR))
        if path:
            self.object_var.set(path)
            self.object_path_label.configure(text=self.shorten_path(path), fg=PALETTE["cyan"])
            self.stage_var.set("03  Run Detection")

    def browse_output(self):
        path = filedialog.askdirectory(title="Select Output Folder", initialdir=str(OUTPUT_DIR))
        if path:
            self.output_var.set(path)
            self.output_path_label.configure(text=self.shorten_path(path), fg=PALETTE["orange"])

    def open_output_folder(self):
        folder = Path(self.output_var.get().strip() or OUTPUT_DIR)
        folder.mkdir(exist_ok=True)
        if sys.platform.startswith("win"):
            os.startfile(str(folder))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(folder)])
        else:
            subprocess.Popen(["xdg-open", str(folder)])

    def clear_inputs(self):
        self.scene_var.set("")
        self.object_var.set("")
        self.method_var.set("hybrid")
        self.scene_path = None
        self.object_path = None
        self.results = []
        self.scene_photo = None
        self.object_photo = None
        self.output_photo = None
        self.scene_path_label.configure(text="No scene selected", fg=PALETTE["muted"])
        self.object_path_label.configure(text="No object selected", fg=PALETTE["muted"])
        self.output_path_label.configure(text=str(OUTPUT_DIR), fg=PALETTE["muted"])
        self.output_label.configure(image="", text="No detection yet\n\nChoose images and click Run Detection.")
        self.stage_var.set("01  Select Images")
        self.selected_method_var.set("Hybrid Fusion")
        self.best_method_var.set("—")
        self.confidence_var.set("—")
        self.runtime_var.set("—")
        self.coordinates_var.set("No coordinates yet.")
        self.status_var.set("Cleared.")
        for item in self.table.get_children():
            self.table.delete(item)

    # load_preview method removed (no preview widgets exist anymore)

    def start_animation(self):
        self.running_animation = True
        self.animation_index = 0
        self.animate_status()

    def stop_animation(self, text="Done"):
        self.running_animation = False
        self.status_var.set(text)

    def animate_status(self):
        if not self.running_animation:
            return
        frames = ["Processing", "Processing.", "Processing..", "Processing..."]
        self.status_var.set(frames[self.animation_index % len(frames)])
        self.animation_index += 1
        self.root.after(240, self.animate_status)

    def detect_object(self):
        try:
            scene_path = Path(self.scene_var.get().strip())
            object_path = Path(self.object_var.get().strip())
            output_folder = Path(self.output_var.get().strip() or OUTPUT_DIR)
            output_folder.mkdir(exist_ok=True)
            if not str(scene_path):
                raise FileNotFoundError("Please select a scene image first.")
            if not str(object_path):
                raise FileNotFoundError("Please select an object/query image first.")
            if not scene_path.exists():
                raise FileNotFoundError(f"Scene image not found:\n{scene_path}")
            if not object_path.exists():
                raise FileNotFoundError(f"Object image not found:\n{object_path}")
            self.scene_path = str(scene_path)
            self.object_path = str(object_path)
            timestamp = int(time.time())
            out_path = output_folder / f"hybrid_result_{timestamp}.png"
            json_path = output_folder / f"detection_summary_{timestamp}.json"
            self.stage_var.set("04  Processing")
            self.start_animation()
            self.root.update_idletasks()
            self.results = detect_all(self.scene_path, self.object_path,
                                      output_path=str(out_path), json_path=str(json_path),
                                      auto_crop=self.auto_crop_var.get())
            self.fill_metrics_table()
            self.write_summary(json_path)
            self.update_summary_cards()
            self.update_output_by_method(save_name=f"preview_{self.method_var.get()}_{timestamp}.png")
            self.stage_var.set("05  Completed")
            self.stop_animation("Detection complete.")
        except Exception as exc:
            self.stage_var.set("Error")
            self.stop_animation("Detection failed.")
            messagebox.showerror("Detection Error", str(exc))

    def fill_metrics_table(self):
        for item in self.table.get_children():
            self.table.delete(item)
        sorted_results = sorted(self.results, key=lambda r: r.score, reverse=True)
        for result in sorted_results:
            short = self.short_method_name(result.method)
            x, y, w, h = result.bbox
            self.table.insert("", "end", iid=short,
                              values=(short, f"{result.score*100:.1f}%",
                                      int(x), int(y), int(w), int(h),
                                      f"{result.elapsed_ms/1000.0:.3f}s"))

    def write_summary(self, json_path):
        data = {"scene_image": self.scene_path,
                "object_image": self.object_path,
                "selected_method": self.method_var.get(),
                "auto_crop_query": self.auto_crop_var.get(),
                "methods": []}
        for result in self.results:
            x, y, w, h = result.bbox
            data["methods"].append({
                "method": self.short_method_name(result.method),
                "confidence": round(result.score * 100, 2),
                "coordinates": {"x": int(x), "y": int(y), "width": int(w), "height": int(h)},
                "runtime_seconds": round(result.elapsed_ms / 1000.0, 3),
                "extra": result.extra
            })
        # No JSON text widget anymore – summary is still saved to file
        try:
            with open(json_path, "w", encoding="utf-8") as file:
                json.dump(data, file, indent=2)
        except Exception:
            pass

    def update_summary_cards(self):
        if not self.results:
            return
        best = max(self.results, key=lambda r: r.score)
        total_runtime = sum(result.elapsed_ms for result in self.results) / 1000.0
        self.best_method_var.set(self.short_method_name(best.method).capitalize())
        self.runtime_var.set(f"{total_runtime:.3f}s")
        selected = self.get_result_by_short_name(self.method_var.get())
        if selected:
            self.confidence_var.set(f"{selected.score*100:.1f}%")

    def update_output_by_method(self, save_name=None):
        if not self.results or not self.scene_path:
            return
        method = self.method_var.get()
        result = self.get_result_by_short_name(method)
        if result is None:
            return
        self.selected_method_var.set(METHOD_DISPLAY.get(method, method))
        scene = imread_color(self.scene_path)
        output_folder = Path(self.output_var.get().strip() or OUTPUT_DIR)
        output_folder.mkdir(exist_ok=True)
        out_path = output_folder / (save_name or f"preview_{method}.png")
        image = draw_result(scene, result, str(out_path))
        self.output_photo = self.cv_to_widget_photo(image, self.output_label, fallback_w=780, fallback_h=440)
        self.output_label.configure(image=self.output_photo, text="")
        x, y, w, h = result.bbox
        self.coordinates_var.set(f"Method: {method}\nConfidence: {result.score*100:.1f}%\n\nx = {int(x)}\ny = {int(y)}\nw = {int(w)}\nh = {int(h)}")
        self.confidence_var.set(f"{result.score*100:.1f}%")
        self.status_var.set(f"Showing {method} result.")

    def on_method_change(self, _event=None):
        self.update_output_by_method()

    def on_table_select(self, _event=None):
        selected = self.table.selection()
        if selected:
            self.method_var.set(selected[0])
            self.update_output_by_method()

    def short_method_name(self, method):
        low = method.lower()
        if "template" in low:
            return "template"
        if "edge" in low:
            return "edge"
        if "histogram" in low or "color" in low:
            return "histogram"
        if "hybrid" in low:
            return "hybrid"
        return low.replace(" ", "_")

    def get_result_by_short_name(self, short_name):
        for result in self.results:
            if self.short_method_name(result.method) == short_name:
                return result
        return None

def main():
    root = tk.Tk()
    PlumMintStudio(root)
    root.mainloop()

if __name__ == "__main__":
    main()