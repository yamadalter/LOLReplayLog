import json


def get_keys(dict, key, v):
    keys = [k for k, v in dict.items() if v[key] == v]
    if keys:
        return keys[0]
    return None

