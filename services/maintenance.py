from config import MAINTENANCE_MODE

def set_maintenance(value: bool):
    global MAINTENANCE_MODE
    MAINTENANCE_MODE = value

def get_maintenance():
    return MAINTENANCE_MODE
