from ctypes import ArgumentError
from pathlib import Path

def get_hash(path: Path, type: str = "sha256") -> str | int:
        
    from hashlib import sha1, sha256, sha512
    from murmurhash2 import murmurhash2 as murmur2

    with open(path, "rb") as file:
        data = file.read()

    match(type):

        case "sha1": hash = sha1(data).hexdigest()
        case "sha256": hash = sha256(data).hexdigest()
        case "sha512": hash = sha512(data).hexdigest()

        case "murmur2": 
            data = bytes([b for b in data if b not in (9, 10, 13, 32)])
            hash = murmur2(data, seed=1)

        case _: raise(ArgumentError("Incorrect hash type!"))

    return hash