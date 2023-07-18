import numpy as np
from PIL import Image


def close_enough(data, orig_color: tuple[int, int, int], margin: int = 25):
    return np.abs(data - orig_color) < margin


def recolor(
    img: Image,
    orig_color: tuple[int, int, int],
    replacement_color: tuple[int, int, int],
):
    img = img.convert("RGB")
    data = np.array(img)
    data[(close_enough(data, orig_color)).all(axis=-1)] = replacement_color
    return Image.fromarray(data, mode="RGB")
