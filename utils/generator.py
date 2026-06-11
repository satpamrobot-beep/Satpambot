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

    if photo > 0:
        parts.append(f"{photo}p")
    if video > 0:
        parts.append(f"{video}v")
    if doc > 0:
        parts.append(f"{doc}d")

    return "_".join(parts)


# =========================
# ANTI DUPLICATE CODE GENERATOR
# =========================
def generate_upload_code(
    check_func,
    photo: int = 0,
    video: int = 0,
    doc: int = 0,
    prefix: str = "Earnfilebot",
    max_retry: int = 10
) -> str:

    for _ in range(max_retry):

        base = random_id(14)
        media_part = build_media_part(photo, video, doc)

        if media_part:
            code = f"{prefix}_{base}_{media_part}"
        else:
            code = f"{prefix}_{base}"

        # CEK DUPLIKAT
        try:
            if not check_func(code):
                return code
        except Exception:
            # kalau DB error, tetap generate ulang
            continue

    raise Exception("Failed to generate unique upload code after max retry")
