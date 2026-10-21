"""Reader for the PlayStation 3 ``SCE\\0`` SELF container.

The retail executables of a PS3 disc are SELF containers whose payload is
NPDRM-encrypted.  The format is documented in ``docs/SELF-FORMAT.md``.

The tool reads the header, the program information, the segment table and the
NPDRM control information, and it can rebuild the PPU ELF that the container
holds.  It needs nothing but the Python standard library.

    python tools/self_header.py info     <file.self>
    python tools/self_header.py segments <file.self>
    python tools/self_header.py control  <file.self>
    python tools/self_header.py extract  <file.self> --out <file.elf>

``extract`` rebuilds the ELF from a container whose payload is already in the
clear.  It does **not** decrypt anything: the NPDRM decryption needs console
key material and is not published here (see ``docs/SELF-FORMAT.md``).
"""

from __future__ import annotations

import argparse
import hashlib
import os
import struct
import sys
from dataclasses import dataclass
from typing import Sequence

MAGIC = b"SCE\x00"

# Header field offsets.  Every multi-byte field of the SELF header is
# big-endian, like the PPU ELF it carries.
OFF_MAGIC = 0x00
OFF_VERSION = 0x04
OFF_KEY_REVISION = 0x08
OFF_HEADER_TYPE = 0x0A
OFF_METADATA_OFFSET = 0x0C
OFF_HEADER_SIZE = 0x10
OFF_ELF_SIZE = 0x18
OFF_EXTENSION_VERSION = 0x20
OFF_PROGRAM_INFO = 0x28
OFF_ELF_HEADER = 0x30
OFF_PROGRAM_HEADER = 0x38
OFF_SECTION_HEADER = 0x40
OFF_SEGMENT_TABLE = 0x48
OFF_VERSION_HEADER = 0x50
OFF_CONTROL_HEADER = 0x58
OFF_CONTROL_SIZE = 0x60

# Header types.
TYPE_SELF = 0x0001
TYPE_RSX = 0x0002
TYPE_SPRX = 0x0003

TYPE_NAMES = {TYPE_SELF: "SELF", TYPE_RSX: "RSX", TYPE_SPRX: "SPRX"}

# NPDRM licence types, as they appear in the control information.
LICENSE_LOCAL = 2
LICENSE_NETWORK = 3

SEGMENT_ENTRY_SIZE = 32
SEGMENT_ENTRY_WORDS = 8


class SelfError(Exception):
    """The file is not a readable SELF container."""


@dataclass(frozen=True)
class Segment:
    """One entry of the segment table."""

    index: int
    encryption_state: int
    file_offset: int
    unknown: int
    size: int
    compression: int
    reserved_a: int
    reserved_b: int
    flags: int

    @property
    def end(self) -> int:
        return self.file_offset + self.size


class Self:
    """A SELF container opened for reading."""

    def __init__(self, data: bytes, name: str = "<memory>"):
        self.data = data
        self.name = name
        if len(data) < 0x70:
            raise SelfError("the file is too small to be a SELF")
        if data[OFF_MAGIC:OFF_MAGIC + 4] != MAGIC:
            raise SelfError("bad magic: this is not a SCE container")

    # -- header ------------------------------------------------------------
    @property
    def version(self) -> int:
        return struct.unpack_from(">I", self.data, OFF_VERSION)[0]

    @property
    def key_revision(self) -> int:
        return struct.unpack_from(">H", self.data, OFF_KEY_REVISION)[0]

    @property
    def header_type(self) -> int:
        return struct.unpack_from(">H", self.data, OFF_HEADER_TYPE)[0]

    @property
    def metadata_offset(self) -> int:
        return struct.unpack_from(">I", self.data, OFF_METADATA_OFFSET)[0]

    @property
    def header_size(self) -> int:
        return struct.unpack_from(">Q", self.data, OFF_HEADER_SIZE)[0]

    @property
    def elf_size(self) -> int:
        return struct.unpack_from(">Q", self.data, OFF_ELF_SIZE)[0]

    @property
    def extension_version(self) -> int:
        return struct.unpack_from(">Q", self.data, OFF_EXTENSION_VERSION)[0]

    @property
    def program_info_offset(self) -> int:
        return struct.unpack_from(">Q", self.data, OFF_PROGRAM_INFO)[0]

    @property
    def elf_header_offset(self) -> int:
        return struct.unpack_from(">Q", self.data, OFF_ELF_HEADER)[0]

    @property
    def program_header_offset(self) -> int:
        return struct.unpack_from(">Q", self.data, OFF_PROGRAM_HEADER)[0]

    @property
    def section_header_offset(self) -> int:
        return struct.unpack_from(">Q", self.data, OFF_SECTION_HEADER)[0]

    @property
    def segment_table_offset(self) -> int:
        return struct.unpack_from(">Q", self.data, OFF_SEGMENT_TABLE)[0]

    @property
    def version_header_offset(self) -> int:
        return struct.unpack_from(">Q", self.data, OFF_VERSION_HEADER)[0]

    @property
    def control_header_offset(self) -> int:
        return struct.unpack_from(">Q", self.data, OFF_CONTROL_HEADER)[0]

    @property
    def control_header_size(self) -> int:
        return struct.unpack_from(">Q", self.data, OFF_CONTROL_SIZE)[0]

    # -- program information ------------------------------------------------
    def program_info(self) -> list[int]:
        """The four 32-bit words of the program information block."""
        off = self.program_info_offset
        return list(struct.unpack_from(">4I", self.data, off))

    # -- segments -----------------------------------------------------------
    def segments(self) -> list[Segment]:
        """The segment table, in file order."""
        off = self.segment_table_offset
        count = self.program_header_count()
        out = []
        for i in range(count):
            base = off + i * SEGMENT_ENTRY_SIZE
            words = struct.unpack_from(f">{SEGMENT_ENTRY_WORDS}I", self.data, base)
            out.append(Segment(i, words[0], words[1], words[2], words[3],
                               words[4], words[5], words[6], words[7]))
        return out

    # -- NPDRM control information -----------------------------------------
    def license_type(self) -> int | None:
        """The NPDRM licence type, when the control information is readable."""
        off = self.control_header_offset + 0x30
        if off + 4 > len(self.data):
            return None
        value = struct.unpack_from(">I", self.data, off)[0]
        if value in (LICENSE_LOCAL, LICENSE_NETWORK):
            return value
        return None

    def control_information(self) -> bytes:
        """The raw control information block."""
        off = self.control_header_offset
        size = self.control_header_size
        return self.data[off:off + size]

    def encrypted_metadata(self) -> bytes:
        """The 16 encrypted bytes that name the content id and the key."""
        off = self.metadata_offset
        return self.data[off:off + 16]

    def encrypted_metadata_block(self) -> bytes:
        """The encrypted NPDRM metadata block of the control information.

        The block holds the encrypted content id and the key material.  It
        stays encrypted on the retail disc and needs console key material to
        be read, which this project does not publish.
        """
        off = self.control_header_offset + 0x40
        size = struct.unpack_from(">I", self.data, self.control_header_offset + 0x34)[0]
        return self.data[off:off + size]

    # -- the embedded ELF ---------------------------------------------------
    def elf_header(self) -> bytes:
        off = self.elf_header_offset
        return self.data[off:off + 64]

    def program_header_count(self) -> int:
        """The number of program headers, read from the embedded ELF."""
        off = self.elf_header_offset
        if off + 0x38 > len(self.data):
            return 0
        return struct.unpack_from(">H", self.data, off + 0x38)[0]

    def rebuild_elf(self) -> bytes:
        """Rebuild the PPU ELF the container holds.

        The layout of a retail SELF is: a header block, the ELF header and the
        program headers, then the segment payloads and the section header
        table.  The payload area starts at ``header_size`` and the rebuilt ELF
        is that area, with the ELF header and the program headers copied over
        the first bytes of the text segment.
        """
        payload_start = self.header_size
        rebuilt = bytearray(self.data[payload_start:])
        src_start = self.elf_header_offset
        src_end = self.program_header_offset + self.program_header_count() * 56
        rebuilt[0:src_end - src_start] = self.data[src_start:src_end]
        return bytes(rebuilt)

    def digest(self) -> str:
        return hashlib.sha256(self.data).hexdigest()


def _load(path: str) -> Self:
    with open(path, "rb") as handle:
        return Self(handle.read(), path)


def _human(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{int(value)} B" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TiB"


def cmd_info(container: Self, args: argparse.Namespace) -> int:
    print(f"file            : {container.name}")
    print(f"size            : {len(container.data)} ({_human(len(container.data))})")
    print(f"sha256          : {container.digest()}")
    print(f"version         : {container.version}")
    print(f"key revision    : 0x{container.key_revision:04X}")
    print(f"header type     : 0x{container.header_type:04X} "
          f"({TYPE_NAMES.get(container.header_type, 'unknown')})")
    print(f"header size     : 0x{container.header_size:X}")
    print(f"metadata offset : 0x{container.metadata_offset:X}")
    print(f"extension ver.  : {container.extension_version}")
    print(f"ELF size        : {container.elf_size} (0x{container.elf_size:X})")
    print(f"ELF header      : 0x{container.elf_header_offset:X}")
    print(f"program headers : 0x{container.program_header_offset:X} "
          f"({container.program_header_count()})")
    print(f"section headers : 0x{container.section_header_offset:X}")
    print(f"segment table   : 0x{container.segment_table_offset:X}")
    print(f"version header  : 0x{container.version_header_offset:X}")
    print(f"control header  : 0x{container.control_header_offset:X} "
          f"(size 0x{container.control_header_size:X})")
    print(f"program info    : {' '.join(f'0x{v:08X}' for v in container.program_info())}")
    licence = container.license_type()
    if licence is None:
        print("licence type    : unreadable (the control information is encrypted)")
    else:
        kind = "local" if licence == LICENSE_LOCAL else "network"
        print(f"licence type    : {licence} ({kind})")
    return 0


def cmd_segments(container: Self, args: argparse.Namespace) -> int:
    print(f"{'#':>3}  {'file offset':>12}  {'size':>12}  {'end':>12}  "
          f"{'compress':>8}  {'state':>6}")
    for seg in container.segments():
        print(f"{seg.index:>3}  0x{seg.file_offset:010X}  0x{seg.size:010X}  "
              f"0x{seg.end:010X}  {seg.compression:>8}  {seg.encryption_state:>6}")
    return 0


def cmd_control(container: Self, args: argparse.Namespace) -> int:
    raw = container.control_information()
    print(f"control information ({len(raw)} bytes):")
    for i in range(0, len(raw), 16):
        chunk = raw[i:i + 16]
        print(f"  0x{container.control_header_offset + i:04X}  " +
              " ".join(f"{b:02x}" for b in chunk))
    licence = container.license_type()
    print(f"licence type    : {licence if licence is not None else 'unreadable'}")
    print(f"encrypted metadata at 0x{container.metadata_offset:X}: "
          + container.encrypted_metadata().hex())
    return 0


def cmd_extract(container: Self, args: argparse.Namespace) -> int:
    elf = container.rebuild_elf()
    if elf[:4] != b"\x7fELF":
        print("error: the rebuilt image is not an ELF", file=sys.stderr)
        return 1
    with open(args.out, "wb") as out:
        out.write(elf)
    print(f"wrote {args.out}: {len(elf)} bytes, "
          f"sha256 {hashlib.sha256(elf).hexdigest()}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # pragma: no cover
            pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name: str, help_text: str) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("self_file", help="path to the SELF container")
        return p

    add("info", "print the SELF header").set_defaults(func=cmd_info)
    add("segments", "print the segment table").set_defaults(func=cmd_segments)
    add("control", "print the NPDRM control information").set_defaults(func=cmd_control)

    p_extract = add("extract", "rebuild the PPU ELF the container holds")
    p_extract.add_argument("--out", required=True, help="output file")
    p_extract.set_defaults(func=cmd_extract)

    args = parser.parse_args(argv)
    try:
        container = _load(args.self_file)
    except (OSError, SelfError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return args.func(container, args)


if __name__ == "__main__":
    raise SystemExit(main())
