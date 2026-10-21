"""Remove the encryption of a retail PlayStation 3 SELF container.

A retail SELF protects itself in two steps:

* the **metadata** — the block that names the sections and the keys — is
  encrypted with AES-256-CBC, under the ``erk`` and ``riv`` of the revision of
  the container;
* the **sections** are encrypted with AES-128-CTR, under the data keys that
  the metadata carries.

The ``erk`` and ``riv`` are the SCE constants of the revision, the same for
every console of that SDK.  They are not key material of a console, and they
are not published here: the tool reads them from a local key file, whose
format is described below and whose source is public.

When the container also carries an **NPDRM licence** — a control
information of type 3 — the payload needs the licence file of the title
(``.rap``) and the key of the console.  That case is reported, and the tool
stops: the key of a console never enters this repository.

    python tools/self_decrypt.py <file.self> --keys <keys.json> [--out <file.elf>]

The key file is a JSON object, keyed by the type of the program and the
revision of the container:

```json
{
  "APP:0x001C": {
    "erk": "<64 hexadecimal characters>",
    "riv": "<32 hexadecimal characters>"
  }
}
```

The types are the ones of the SCE header: ``LV0``, ``LV1``, ``LV2``, ``APP``,
``ISO``, ``LDR``, ``UNK7`` and ``NPDRM``.  The values are the constants of
``rpcs3/Crypto/key_vault.cpp`` of the RPCS3 sources, which are public.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import sys
from dataclasses import dataclass
from typing import Sequence

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from self_crypto import cbc_decrypt, ctr_apply, ecb_decrypt  # noqa: E402

MAGIC = b"SCE\x00"

# The SCE header, as the RPCS3 reader reads it.
OFF_VERSION = 0x04
OFF_FLAGS = 0x08
OFF_TYPE = 0x0A
OFF_METADATA = 0x0C
OFF_HEADER_SIZE = 0x10
OFF_ELF_SIZE = 0x18
SCE_HEADER_SIZE = 0x20

# The SELF header, right after the SCE header.
OFF_PROGRAM_INFO = 0x28
OFF_ELF_HEADER = 0x30
OFF_PROGRAM_HEADER = 0x38
OFF_SECTION_HEADER = 0x40
OFF_SEGMENT_TABLE = 0x48
OFF_VERSION_HEADER = 0x50
OFF_CONTROL_HEADER = 0x58
OFF_CONTROL_SIZE = 0x60

# The program identification header.
OFF_PROGRAM_AUTHORITY = 0x00
OFF_PROGRAM_VENDOR = 0x08
OFF_PROGRAM_TYPE = 0x0C
OFF_PROGRAM_VERSION = 0x10

# The types of the program, as the SCE key tables name them.
PROGRAM_TYPES = {
    1: "LV0", 2: "LV1", 3: "LV2", 4: "APP",
    5: "ISO", 6: "LDR", 7: "UNK7", 8: "NPDRM",
}

META_INFO_SIZE = 0x40
META_HEADER_SIZE = 0x20
META_SECTION_SIZE = 0x30


class DecryptError(Exception):
    """The container cannot be decrypted."""


def rap_to_rif(rap: bytes, constants: dict) -> bytes:
    """Derive the rif key of a licence file.

    The chain is the one RPCS3 implements: the licence file is decrypted
    with ``RAP_KEY``, then five rounds of the ``rap2rifkey`` substitution
    turn it into the rif key.
    """
    if len(rap) != 16:
        raise DecryptError("a licence file is 16 bytes")
    key = bytearray(cbc_decrypt(constants["RAP_KEY"], b"\x00" * 16, rap))
    pbox = constants["RAP_PBOX"]
    e1 = constants["RAP_E1"]
    e2 = constants["RAP_E2"]
    for _ in range(5):
        for i in range(16):
            key[pbox[i]] ^= e1[pbox[i]]
        for i in range(15, 0, -1):
            key[pbox[i]] ^= key[pbox[i - 1]]
        carry = 0
        for i in range(16):
            p = pbox[i]
            kc = (key[p] - carry) & 0xFF
            ec2 = e2[p]
            if carry != 1 or kc != 0xFF:
                carry = 1 if kc < ec2 else 0
                key[p] = (kc - ec2) & 0xFF
            elif kc == 0xFF:
                key[p] = (kc - ec2) & 0xFF
            else:
                key[p] = kc
    return bytes(key)


def npdrm_key_from_rap(rap: bytes, constants: dict) -> bytes:
    """Derive the NPDRM key of a licence file."""
    rif = rap_to_rif(rap, constants)
    return ecb_decrypt(constants["NP_KLIC_KEY"], rif)


@dataclass(frozen=True)
class MetaSection:
    """One entry of the decrypted metadata section table."""

    index: int
    data_offset: int
    data_size: int
    type: int
    program_index: int
    hashed: int
    sha1_index: int
    encrypted: int
    key_index: int
    iv_index: int
    compressed: int


class SelfDecryptor:
    """The decryption of one retail SELF container."""

    def __init__(self, data: bytes, name: str = "<memory>"):
        self.data = data
        self.name = name
        if len(data) < SCE_HEADER_SIZE + 0x50:
            raise DecryptError("the file is too small to be a SELF")
        if data[0:4] != MAGIC:
            raise DecryptError("bad magic: this is not a SCE container")
        self.version, self.flags, self.type = struct.unpack_from(">IHH", data, OFF_VERSION)
        self.metadata_offset = struct.unpack_from(">I", data, OFF_METADATA)[0]
        self.header_size = struct.unpack_from(">Q", data, OFF_HEADER_SIZE)[0]
        self.elf_size = struct.unpack_from(">Q", data, OFF_ELF_SIZE)[0]
        (ext_version, self.program_info_offset, self.elf_header_offset,
         self.program_header_offset, self.section_header_offset,
         self.segment_table_offset, self.version_header_offset,
         self.control_header_offset, self.control_header_size) = \
            struct.unpack_from(">9Q", data, 0x20)
        self.extension_version = ext_version
        self.program_type = struct.unpack_from(">I", data, 0x70 + OFF_PROGRAM_TYPE)[0]
        self.program_version = struct.unpack_from(">Q", data, 0x70 + OFF_PROGRAM_VERSION)[0]
        self.control_information = self._read_control_information()
        self.sections: list[MetaSection] = []
        self.data_keys: bytes = b""

    # -- control information ------------------------------------------------
    def _read_control_information(self) -> list[dict]:
        """Read the chain of the supplemental headers of the container."""
        out: list[dict] = []
        offset = self.control_header_offset
        end = offset + self.control_header_size
        while offset + 16 <= end:
            ctype, size, nxt = struct.unpack_from(">IIQ", self.data, offset)
            if ctype == 0:
                # the chain ends with an empty header
                break
            entry = {"type": ctype, "size": size, "offset": offset}
            if ctype == 3:
                (magic, version, licence, kind) = struct.unpack_from(">4I", self.data, offset + 16)
                entry["magic"] = magic
                entry["version"] = version
                entry["licence"] = licence
                entry["npdrm_type"] = kind
                entry["content_id"] = self.data[offset + 32:offset + 80].split(b"\x00")[0].decode("ascii", "replace")
            out.append(entry)
            if size == 0:
                break
            offset += size
        return out

    @property
    def npdrm_licence(self) -> int | None:
        """The licence of the container, when it has an NPDRM header."""
        for entry in self.control_information:
            if entry["type"] == 3:
                return entry.get("licence")
        return None

    @property
    def content_id(self) -> str | None:
        """The content id, when the container carries an NPDRM header."""
        for entry in self.control_information:
            if entry["type"] == 3:
                return entry.get("content_id")
        return None

    # -- keys ---------------------------------------------------------------
    def key_name(self) -> str:
        """The name of the key entry this container needs."""
        name = PROGRAM_TYPES.get(self.program_type, f"TYPE{self.program_type}")
        return f"{name}:0x{self.flags:04X}"

    def load_keys(self, path: str) -> tuple[bytes, bytes]:
        """Read the ``erk`` and the ``riv`` of this container from a key file."""
        with open(path, "r", encoding="utf-8") as handle:
            table = json.load(handle)
        wanted = self.key_name()
        entry = table.get(wanted)
        if entry is None:
            raise DecryptError(f"the key file has no entry for {wanted}")
        erk = bytes.fromhex(entry["erk"])
        riv = bytes.fromhex(entry["riv"])
        if len(erk) != 32 or len(riv) != 16:
            raise DecryptError(f"the entry {wanted} is not a valid key pair")
        return erk, riv

    def npdrm_constants(self, path: str) -> dict:
        """Read the constants of the NPDRM chain from the key file."""
        with open(path, "r", encoding="utf-8") as handle:
            table = json.load(handle)
        entry = table.get("npdrm")
        if entry is None:
            raise DecryptError("the key file has no 'npdrm' entry")
        out = {}
        for name in ("NP_KLIC_KEY", "RAP_KEY", "RAP_PBOX", "RAP_E1", "RAP_E2"):
            if name not in entry:
                raise DecryptError(f"the 'npdrm' entry misses {name}")
            out[name] = bytes.fromhex(entry[name])
        return out

    # -- metadata -----------------------------------------------------------
    def load_metadata(self, erk: bytes, riv: bytes, npdrm_key: bytes | None = None) -> None:
        """Decrypt the metadata of the container and read its section table."""
        if self.flags & 0x8000:
            raise DecryptError("this is a debug SELF: its payload is not encrypted")

        info_offset = self.metadata_offset + SCE_HEADER_SIZE
        metadata_info = self.data[info_offset:info_offset + META_INFO_SIZE]
        if len(metadata_info) < META_INFO_SIZE:
            raise DecryptError("the metadata info is outside the file")

        # The NPDRM layer, when the container has one, comes first.
        if self.npdrm_licence is not None:
            if npdrm_key is None:
                raise DecryptError(
                    "this container carries an NPDRM licence: the payload needs "
                    "the licence file of the title, which stays private")
            metadata_info = cbc_decrypt(npdrm_key, b"\x00" * 16, metadata_info)

        metadata_info = cbc_decrypt(erk, riv, metadata_info)

        # The padding of the key and of the iv must be zero, or the
        # metadata was not decrypted.
        if metadata_info[0x10] != 0x00 or metadata_info[0x30] != 0x00:
            raise DecryptError("the metadata info was not decrypted: wrong key")
        meta_key = metadata_info[0x00:0x10]
        meta_iv = metadata_info[0x20:0x30]

        headers_offset = META_INFO_SIZE + SCE_HEADER_SIZE + self.metadata_offset
        length = self.header_size - headers_offset
        if length < META_HEADER_SIZE:
            raise DecryptError("the metadata headers are outside the container")
        metadata_headers = self.data[headers_offset:headers_offset + length]
        metadata_headers = ctr_apply(meta_key, meta_iv, metadata_headers)

        (_signature_input_length, _unknown1, section_count, key_count,
         _opt_header_size, _unknown2, _unknown3) = \
            struct.unpack_from(">QIIIIII", metadata_headers, 0)

        sections: list[MetaSection] = []
        for i in range(section_count):
            base = META_HEADER_SIZE + META_SECTION_SIZE * i
            if base + META_SECTION_SIZE > len(metadata_headers):
                raise DecryptError("the metadata section table is truncated")
            (data_offset, data_size, stype, program_index, hashed, sha1_index,
             encrypted, key_index, iv_index, compressed) = \
                struct.unpack_from(">QQIIIIIIII", metadata_headers, base)
            sections.append(MetaSection(i, data_offset, data_size, stype,
                                        program_index, hashed, sha1_index,
                                        encrypted, key_index, iv_index,
                                        compressed))
        self.sections = sections

        keys_offset = META_HEADER_SIZE + META_SECTION_SIZE * section_count
        self.data_keys = metadata_headers[keys_offset:keys_offset + key_count * 16]

    # -- data ---------------------------------------------------------------
    def decrypt_data(self) -> bytes:
        """Return the container with its encrypted sections in the clear."""
        out = bytearray(self.data)
        for section in self.sections:
            if section.encrypted != 3:
                continue
            if section.key_index * 16 + 16 > len(self.data_keys) or \
               section.iv_index * 16 + 16 > len(self.data_keys):
                raise DecryptError(f"section {section.index} names a key that is absent")
            key = self.data_keys[section.key_index * 16:section.key_index * 16 + 16]
            iv = self.data_keys[section.iv_index * 16:section.iv_index * 16 + 16]
            start = section.data_offset
            end = start + section.data_size
            if end > len(self.data):
                raise DecryptError(f"section {section.index} is outside the file")
            out[start:end] = ctr_apply(key, iv, bytes(out[start:end]))
        return bytes(out)

    def rebuild_elf(self, plain: bytes) -> bytes:
        """Rebuild the PPU ELF from the decrypted container."""
        payload_start = self.header_size
        rebuilt = bytearray(plain[payload_start:payload_start + self.elf_size])
        src_start = self.elf_header_offset
        src_end = self.program_header_offset + \
            struct.unpack_from(">H", plain, src_start + 0x38)[0] * 56
        rebuilt[0:src_end - src_start] = plain[src_start:src_end]
        return bytes(rebuilt)


def load_keys(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # pragma: no cover
            pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("self_file", help="path to the SELF container")
    parser.add_argument("--keys", required=True, help="path to the local key file")
    parser.add_argument("--rap", help="path to the licence file, for a NPDRM container")
    parser.add_argument("--out", help="write the decrypted ELF here")
    parser.add_argument("--info", action="store_true",
                        help="report the container and stop")
    args = parser.parse_args(argv)

    try:
        with open(args.self_file, "rb") as handle:
            raw = handle.read()
        container = SelfDecryptor(raw, args.self_file)
    except (OSError, DecryptError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"file            : {container.name}")
    print(f"size            : {len(raw)}")
    print(f"flags           : 0x{container.flags:04X}")
    print(f"type            : {container.type}")
    print(f"program type    : {PROGRAM_TYPES.get(container.program_type, container.program_type)}")
    print(f"key entry       : {container.key_name()}")
    print(f"metadata offset : 0x{container.metadata_offset:X}")
    print(f"header size     : 0x{container.header_size:X}")
    print(f"elf size        : {container.elf_size}")
    for entry in container.control_information:
        print(f"control info    : type {entry['type']} size 0x{entry['size']:X}")
        if entry["type"] == 3:
            print(f"  licence       : {entry['licence']}")
            print(f"  content id    : {entry['content_id']}")

    if args.info:
        return 0

    try:
        erk, riv = container.load_keys(args.keys)
        npdrm_key = None
        if container.npdrm_licence is not None:
            if not args.rap:
                raise DecryptError(
                    "this container carries an NPDRM licence: the licence file "
                    "of the title is needed, with --rap")
            with open(args.rap, "rb") as handle:
                rap = handle.read(16)
            constants = container.npdrm_constants(args.keys)
            npdrm_key = npdrm_key_from_rap(rap, constants)
        container.load_metadata(erk, riv, npdrm_key)
    except (OSError, KeyError, DecryptError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"metadata        : {len(container.sections)} section(s), "
          f"{len(container.data_keys) // 16} data key(s)")
    for section in container.sections:
        print(f"  section {section.index}: offset 0x{section.data_offset:X} "
              f"size 0x{section.data_size:X} encrypted={section.encrypted} "
              f"key={section.key_index} iv={section.iv_index}")

    try:
        plain = container.decrypt_data()
    except DecryptError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    elf = container.rebuild_elf(plain)
    print(f"decrypted ELF   : {len(elf)} bytes, sha256 {hashlib.sha256(elf).hexdigest()}")
    if args.out:
        with open(args.out, "wb") as handle:
            handle.write(elf)
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
