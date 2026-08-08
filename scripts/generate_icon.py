"""Generate ProTube app icon."""
from PIL import Image, ImageDraw

size = 256
img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Background circle
margin = 20
draw.ellipse(
    [margin, margin, size - margin, size - margin],
    fill="#1a73e8",
)

# Inner circle (darker)
inner_margin = 55
draw.ellipse(
    [inner_margin, inner_margin, size - inner_margin, size - inner_margin],
    fill="#1557b0",
)

# White play triangle in center
cx, cy = size // 2, size // 2
tri_size = 35
draw.polygon(
    [
        (cx - tri_size, cy - tri_size),
        (cx - tri_size, cy + tri_size),
        (cx + tri_size, cy),
    ],
    fill="white",
)

# Bottom download bar with arrow
bar_h = 22
bar_y = size - 65
bar_x1, bar_x2 = 55, size - 55
draw.rounded_rectangle(
    [bar_x1, bar_y, bar_x2, bar_y + bar_h],
    radius=11,
    fill="white",
)

# Down arrow inside bar
arrow_x = size // 2
arrow_y = bar_y + 4
draw.polygon(
    [
        (arrow_x - 16, arrow_y),
        (arrow_x + 16, arrow_y),
        (arrow_x, arrow_y + 14),
    ],
    fill="#1557b0",
)

# Save PNG
img.save("D:/AI/pro-tube/assets/icon.png")

# Save ICO with multiple sizes
ico_sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
ico_images = []
for s in ico_sizes:
    ico_images.append(img.resize(s, Image.Resampling.LANCZOS))

ico_images[0].save(
    "D:/AI/pro-tube/assets/icon.ico",
    format="ICO",
    sizes=[(w, h) for w, h in ico_sizes],
    append_images=ico_images[1:],
)

print("Icon created: assets/icon.png + assets/icon.ico")
