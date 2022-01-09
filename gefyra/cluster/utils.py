import base64
import collections


def decode_secret(u):
    n = {}
    for k, v in u.items():
        if isinstance(v, collections.abc.Mapping):
            n[k] = decode_secret(v)
        else:
            n[k] = (base64.b64decode(v.encode("utf-8"))).decode("utf-8")
    return n
