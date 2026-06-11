import random
import string


# =========================
# CORE RANDOM STRING
# =========================
def random_id(length: int = 12) -> str:
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


# =========================
# FORMAT MEDIA PART (p/v/d)
# =========================
def build_media_part(photo: int = 0, video: int = 0, doc: int = 0) -> str:
    parts = []

    if photo:
        parts.append(f"{photo}p")
    if video:
        parts.append(f"{video}v")
    if doc:
        parts.append(f"{doc}d")

    return "_".join(parts)


# =========================
# MAIN CODE GENERATOR
# =========================
def generate_upload_code(
    photo: int = 0,
    video: int = 0,
    doc: int = 0,
    prefix: str = "Earnfilebot"
) -> str:

    base = random_id(14)
    media_part = build_media_part(photo, video, doc)

    return f"{prefix}_{base}_{media_part}" if media_part else f"{prefix}_{base}"
