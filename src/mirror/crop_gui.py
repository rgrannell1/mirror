"""Show a desktop selector for a movable, fixed-ratio image crop."""

import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from PIL import Image, ImageEnhance, ImageTk

from mirror.crop import CropBounds, export_crop, make_output_path

CANVAS_MAX_WIDTH = 1200
CANVAS_MAX_HEIGHT = 800
INITIAL_CROP_SCALE = 0.8
MINIMUM_CROP_SCALE = 0.1
SCALE_STEP = 0.05
SCROLL_UP_BUTTON = 4
OUTSIDE_BRIGHTNESS = 0.2


class CropSelector:
    """Own the crop window and its selection state."""

    def __init__(self, source: Path) -> None:
        self.source = source
        self.image = load_image(source)
        self.preview = self.image.copy()
        self.preview.thumbnail((CANVAS_MAX_WIDTH, CANVAS_MAX_HEIGHT), Image.Resampling.LANCZOS)
        self.root = tk.Tk()
        self.root.title(f"Mirror crop: {source.name}")
        self.preview_image = ImageTk.PhotoImage(self.preview)
        self.canvas = self.make_canvas()
        self.set_initial_crop()
        self.add_controls()
        self.bind_events()
        self.draw()

    def set_initial_crop(self) -> None:
        """Set the initial centred crop state."""

        self.scale = INITIAL_CROP_SCALE
        self.centre_x = self.preview.width / 2
        self.centre_y = self.preview.height / 2
        self.drag_x = 0.0
        self.drag_y = 0.0
        self.crop_rectangle = self.canvas.create_rectangle(0, 0, 0, 0, outline="white", width=3)
        self.status = tk.StringVar()

    def make_canvas(self) -> tk.Canvas:
        """Create the preview canvas."""

        self.canvas = tk.Canvas(
            self.root,
            width=self.preview.width,
            height=self.preview.height,
            highlightthickness=0,
        )
        self.canvas.pack()
        self.canvas_image = self.canvas.create_image(
            0, 0, anchor=tk.NW, image=self.preview_image
        )
        return self.canvas

    def add_controls(self) -> None:
        """Add dimensions, help text, and the crop button."""

        tk.Label(self.root, textvariable=self.status).pack(pady=6)
        help_text = "Drag to move. Scroll to resize. Enter to crop. Esc to cancel."
        tk.Label(self.root, text=help_text).pack()
        tk.Button(self.root, text="Crop", command=self.crop).pack(pady=8)

    def bind_events(self) -> None:
        """Bind pointer and keyboard controls."""

        self.canvas.bind("<ButtonPress-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.drag)
        self.canvas.bind("<MouseWheel>", self.resize)
        self.canvas.bind("<Button-4>", self.resize)
        self.canvas.bind("<Button-5>", self.resize)
        self.root.bind("<Return>", self.crop)
        self.root.bind("<Escape>", self.cancel)

    def get_preview_bounds(self) -> tuple[float, float, float, float]:
        """Return the crop rectangle in preview pixels."""

        width = self.preview.width * self.scale
        height = self.preview.height * self.scale
        return (
            self.centre_x - width / 2,
            self.centre_y - height / 2,
            self.centre_x + width / 2,
            self.centre_y + height / 2,
        )

    def get_source_bounds(self) -> CropBounds:
        """Map the preview rectangle to exact source pixels."""

        left, top, right, bottom = self.get_preview_bounds()
        factor = self.image.width / self.preview.width
        return CropBounds(
            x=round(left * factor),
            y=round(top * factor),
            width=round((right - left) * factor),
            height=round((bottom - top) * factor),
        )

    def draw(self) -> None:
        """Draw the crop rectangle and its source dimensions."""

        bounds = self.get_preview_bounds()
        masked_preview = make_masked_preview(self.preview, bounds)
        self.preview_image = ImageTk.PhotoImage(masked_preview)
        self.canvas.itemconfigure(self.canvas_image, image=self.preview_image)
        self.canvas.coords(self.crop_rectangle, *bounds)
        source_bounds = self.get_source_bounds()
        self.status.set(
            f"{source_bounds.width} x {source_bounds.height} px  "
            f"at {source_bounds.x}, {source_bounds.y}"
        )

    def start_drag(self, event: tk.Event) -> None:
        """Record the pointer offset for a crop move."""

        self.drag_x = event.x - self.centre_x
        self.drag_y = event.y - self.centre_y

    def drag(self, event: tk.Event) -> None:
        """Move the crop rectangle within the image."""

        crop_width = self.preview.width * self.scale
        crop_height = self.preview.height * self.scale
        self.centre_x = clamp_centre(event.x - self.drag_x, crop_width, self.preview.width)
        self.centre_y = clamp_centre(event.y - self.drag_y, crop_height, self.preview.height)
        self.draw()

    def resize(self, event: tk.Event) -> None:
        """Resize the crop rectangle while its ratio stays fixed."""

        grows = (
            getattr(event, "delta", 0) > 0
            or getattr(event, "num", 0) == SCROLL_UP_BUTTON
        )
        change = SCALE_STEP if grows else -SCALE_STEP
        self.scale = min(1.0, max(MINIMUM_CROP_SCALE, self.scale + change))
        crop_width = self.preview.width * self.scale
        crop_height = self.preview.height * self.scale
        self.centre_x = clamp_centre(self.centre_x, crop_width, self.preview.width)
        self.centre_y = clamp_centre(self.centre_y, crop_height, self.preview.height)
        self.draw()

    def crop(self, _event: tk.Event | None = None) -> None:
        """Confirm replacement when needed, then export through GIMP."""

        output = make_output_path(self.source)
        if output.exists() and not messagebox.askyesno("Replace crop?", f"Replace {output.name}?"):
            return
        try:
            export_crop(self.source, output, self.get_source_bounds())
        except Exception as err:  # noqa: BLE001
            messagebox.showerror("Crop failed", str(err))
            return
        messagebox.showinfo("Crop saved", str(output))
        self.root.destroy()

    def cancel(self, _event: tk.Event | None = None) -> None:
        """Close without exporting a crop."""

        self.root.destroy()


def select_crop(source: Path) -> None:
    """Open and run the crop selector."""

    selector = CropSelector(source)
    selector.root.mainloop()


def clamp_centre(centre: float, crop_size: float, image_size: int) -> float:
    """Keep one crop axis within its image axis."""

    half_size = crop_size / 2
    return min(max(centre, half_size), image_size - half_size)


def load_image(source: Path) -> Image.Image:
    """Load an image fully and close its source file."""

    with Image.open(source) as image:
        return image.copy()


def make_masked_preview(
    preview: Image.Image, bounds: tuple[float, float, float, float]
) -> Image.Image:
    """Dim the preview by 80% outside the crop bounds."""

    left, top, right, bottom = (round(value) for value in bounds)
    masked = ImageEnhance.Brightness(preview).enhance(OUTSIDE_BRIGHTNESS)
    crop = preview.crop((left, top, right, bottom))
    masked.paste(crop, (left, top))
    return masked
