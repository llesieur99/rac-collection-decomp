"""Reader for the PS2 executable (the little-endian MIPS ELF of a game).

The PlayStation 2's Emotion Engine runs a MIPS III core.  The retail
executables of the games are ELF32, little-endian, ``EM_MIPS``, and they are
stripped: the names of the functions are gone, and only the code says what
the program does.

The reader reports the structure of the file — the program headers, the
section headers, the symbol table when there is one — and gives the bytes of
a section or of a virtual address.  It needs nothing but the Python standard
library.

    python tools/mips_elf.py info     <boot_elf.elf>
    python tools/mips_elf.py sections <overlay.elf>
    python tools/mips_elf.py symbols  <overlay.elf> [--limit N]

MIPS specifics worth knowing:

* The ELF is ELF32, little-endian, and its ``e_machine`` is ``EM_MIPS`` (8).
* The section flags carry the processor-specific bits in the high nibble
  (``SHF_MASKPROC``): the flags must be masked before they are read, or the
  sections of the overlays look like they have no permission at all.
* The Emotion Engine is a MIPS III core with the R5900's extensions, so the
  64-bit loads and stores (``lq``, ``sq``, ``ld``, ``sd``) are part of the
  instruction set, and the game uses them.
* A game is not one file: the *core* executable holds the shared code, and
  every level ships its own **overlay**, an ELF of its own that the core
  loads at run time.  The same function therefore sits at a different
  address in the core and in each overlay.
"""

from __future__ import annotations

import argparse
import struct
import sys
from dataclasses import dataclass
from typing import Sequence

SHT_SYMTAB = 2
SHT_STRTAB = 3
SHT_NOBITS = 8
SHT_DYNSYM = 11

SHF_WRITE = 0x1
SHF_ALLOC = 0x2
SHF_EXECINSTR = 0x4

# The processor-specific bits of the section flags; they must be masked out
# before the permissions are read.
SHF_MASKPROC = 0xF0000000

STT_FUNC = 2

PT_LOAD = 1

EM_MIPS = 8


class ElfError(Exception):
    """The file is not a readable MIPS ELF."""


@dataclass(frozen=True)
class ProgramHeader:
    index: int
    type: int
    offset: int
    vaddr: int
    paddr: int
    filesz: int
    memsz: int
    flags: int
    align: int

    @property
    def is_load(self) -> bool:
        return self.type == PT_LOAD


@dataclass(frozen=True)
class SectionHeader:
    index: int
    name_offset: int
    type: int
    flags: int
    addr: int
    offset: int
    size: int
    link: int
    info: int
    addralign: int
    entsize: int
    name: str = ""

    @property
    def allocated(self) -> bool:
        """The section is in the memory of the program.

        The processor-specific bits of the flags live in the high nibble and
        do not overlap the permissions, so the mask is only a reminder.
        """
        return bool(self.flags & SHF_ALLOC)

    @property
    def executable(self) -> bool:
        return bool(self.flags & SHF_EXECINSTR)


@dataclass(frozen=True)
class Symbol:
    index: int
    name: str
    value: int
    size: int
    info: int
    other: int
    shndx: int

    @property
    def type(self) -> int:
        return self.info & 0xF

    @property
    def is_function(self) -> bool:
        return self.type == STT_FUNC


class MipsElf:
    """A PS2 executable: the core, or one of the overlays."""

    def __init__(self, data: bytes, name: str = "<memory>"):
        self.data = data
        self.name = name
        if data[:4] != b"\x7fELF":
            raise ElfError("not an ELF file")
        if data[4] != 1:
            raise ElfError("not a 32-bit ELF")
        if data[5] != 1:
            raise ElfError("not a little-endian ELF")
        self.machine = struct.unpack_from("<H", data, 18)[0]
        if self.machine != EM_MIPS:
            raise ElfError(f"not a MIPS ELF (e_machine={self.machine})")
        self.entry = struct.unpack_from("<I", data, 24)[0]
        self.phoff = struct.unpack_from("<I", data, 28)[0]
        self.shoff = struct.unpack_from("<I", data, 32)[0]
        (self.phentsize, self.phnum, self.shentsize,
         self.shnum, self.shstrndx) = struct.unpack_from("<5H", data, 42)
        self._sections: list[SectionHeader] | None = None

    # -- program headers ---------------------------------------------------

    def program_headers(self) -> list[ProgramHeader]:
        out = []
        for i in range(self.phnum):
            off = self.phoff + i * self.phentsize
            if off + 32 > len(self.data):
                break
            p_type, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_flags, p_align = \
                struct.unpack_from("<8I", self.data, off)
            out.append(ProgramHeader(i, p_type, p_offset, p_vaddr, p_paddr,
                                     p_filesz, p_memsz, p_flags, p_align))
        return out

    # -- section headers ---------------------------------------------------

    def sections(self) -> list[SectionHeader]:
        if self._sections is not None:
            return self._sections
        raw = []
        for i in range(self.shnum):
            off = self.shoff + i * self.shentsize
            if off + 40 > len(self.data):
                break
            name_offset, sh_type, sh_flags, sh_addr, sh_offset, sh_size = \
                struct.unpack_from("<6I", self.data, off)
            sh_link, sh_info, sh_addralign, sh_entsize = \
                struct.unpack_from("<4I", self.data, off + 24)
            raw.append(SectionHeader(i, name_offset, sh_type, sh_flags, sh_addr,
                                     sh_offset, sh_size, sh_link, sh_info,
                                     sh_addralign, sh_entsize))
        if raw and self.shstrndx < len(raw):
            strtab = raw[self.shstrndx]
            names = []
            for sec in raw:
                start = strtab.offset + sec.name_offset
                end = self.data.find(b"\x00", start)
                names.append(self.data[start:end].decode("ascii", "replace")
                             if 0 <= start < len(self.data) else "")
            raw = [SectionHeader(s.index, s.name_offset, s.type, s.flags, s.addr,
                                 s.offset, s.size, s.link, s.info, s.addralign,
                                 s.entsize, names[i]) for i, s in enumerate(raw)]
        self._sections = raw
        return raw

    def section(self, name: str) -> SectionHeader | None:
        for sec in self.sections():
            if sec.name == name:
                return sec
        return None

    def section_data(self, section: SectionHeader) -> bytes:
        if section.type == SHT_NOBITS:
            return b""
        return self.data[section.offset:section.offset + section.size]

    # -- the code and the data --------------------------------------------

    def code_sections(self) -> list[SectionHeader]:
        """The sections that hold instructions.

        A section that is allocated and executable holds code; one that is
        allocated and not executable holds data.  The processor-specific bits
        of the flags are masked out by the properties of the section.
        """
        return [sec for sec in self.sections()
                if sec.size and sec.executable and sec.allocated and sec.addr]

    def data_sections(self) -> list[SectionHeader]:
        """The sections that hold the data the code reads."""
        return [sec for sec in self.sections()
                if sec.size and sec.type != SHT_NOBITS
                and sec.allocated and not sec.executable and sec.addr]

    # -- symbols -----------------------------------------------------------

    def symbols(self) -> list[Symbol]:
        out: list[Symbol] = []
        for sec in self.sections():
            if sec.type not in (SHT_SYMTAB, SHT_DYNSYM) or not sec.size:
                continue
            if sec.link >= len(self.sections()):
                continue
            strtab = self.sections()[sec.link]
            count = sec.size // (sec.entsize or 16)
            for i in range(count):
                off = sec.offset + i * (sec.entsize or 16)
                if off + 16 > len(self.data):
                    break
                st_name, st_value, st_size, st_info, st_other, st_shndx = \
                    struct.unpack_from("<IIIBBH", self.data, off)
                start = strtab.offset + st_name
                end = self.data.find(b"\x00", start)
                name = self.data[start:end].decode("ascii", "replace") \
                    if 0 <= start < len(self.data) else ""
                out.append(Symbol(i, name, st_value, st_size, st_info, st_other, st_shndx))
        return out

    def functions(self) -> list[Symbol]:
        """The named functions of the executable, sorted by address."""
        funcs = [s for s in self.symbols() if s.is_function and s.name and s.value]
        funcs.sort(key=lambda s: s.value)
        return funcs

    # -- helpers -----------------------------------------------------------

    def segment_for(self, vaddr: int) -> ProgramHeader | None:
        for ph in self.program_headers():
            if not ph.is_load:
                continue
            if ph.vaddr <= vaddr < ph.vaddr + ph.memsz:
                return ph
        return None

    def read_vaddr(self, vaddr: int, length: int) -> bytes:
        """The bytes at a virtual address.

        The program is linked in one segment that starts at a fixed address
        and the file holds it at another one, so the address has to be
        translated through the program headers.
        """
        ph = self.segment_for(vaddr)
        if ph is None:
            raise ElfError(f"no segment holds 0x{vaddr:X}")
        start = ph.offset + (vaddr - ph.vaddr)
        return self.data[start:start + length]


def _load(path: str) -> MipsElf:
    with open(path, "rb") as handle:
        return MipsElf(handle.read(), path)


def cmd_info(elf: MipsElf, args: argparse.Namespace) -> int:
    print(f"file         : {elf.name}")
    print(f"size         : {len(elf.data)}")
    print(f"entry        : 0x{elf.entry:X}")
    print(f"program hdrs : {elf.phnum}")
    print(f"section hdrs : {elf.shnum}")
    print("program headers:")
    for ph in elf.program_headers():
        print(f"  [{ph.index}] type=0x{ph.type:X} off=0x{ph.offset:X} "
              f"vaddr=0x{ph.vaddr:X} filesz=0x{ph.filesz:X} memsz=0x{ph.memsz:X} "
              f"flags=0x{ph.flags:X}")
    print("code sections:")
    for sec in elf.code_sections():
        print(f"  {sec.name:24s} addr=0x{sec.addr:08X} size=0x{sec.size:X}")
    print("data sections:")
    for sec in elf.data_sections():
        print(f"  {sec.name:24s} addr=0x{sec.addr:08X} size=0x{sec.size:X}")
    return 0


def cmd_sections(elf: MipsElf, args: argparse.Namespace) -> int:
    for sec in elf.sections():
        print(f"[{sec.index:2d}] {sec.name:26s} type={sec.type:10d} "
              f"flags=0x{sec.flags:08X} addr=0x{sec.addr:08X} "
              f"off=0x{sec.offset:08X} size=0x{sec.size:X}")
    return 0


def cmd_symbols(elf: MipsElf, args: argparse.Namespace) -> int:
    symbols = elf.symbols()
    print(f"{len(symbols)} symbols")
    for sym in symbols[:args.limit] if args.limit else symbols:
        print(f"  0x{sym.value:08X} size={sym.size:6d} type={sym.type} "
              f"shndx={sym.shndx:3d} {sym.name}")
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
        p.add_argument("elf", help="path to the MIPS ELF")
        return p

    add("info", "print the ELF header, the program headers and the sections").set_defaults(func=cmd_info)
    add("sections", "list the section headers").set_defaults(func=cmd_sections)

    p_symbols = add("symbols", "dump the symbol table")
    p_symbols.add_argument("--limit", type=int, default=0, help="stop after N symbols")
    p_symbols.set_defaults(func=cmd_symbols)

    args = parser.parse_args(argv)
    try:
        elf = _load(args.elf)
    except (OSError, ElfError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return args.func(elf, args)


if __name__ == "__main__":
    raise SystemExit(main())
