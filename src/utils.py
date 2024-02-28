import json


def get_keys(d, key, value):
    keys = [k for k, v in d.items() if v[key] == value]
    if keys:
        return keys[0]
    return None
