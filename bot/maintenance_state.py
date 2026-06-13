MAINTENANCE = False


def is_maintenance() -> bool:
    return MAINTENANCE


def set_maintenance(state: bool):
    global MAINTENANCE
    MAINTENANCE = state
