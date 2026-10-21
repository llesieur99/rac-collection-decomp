"""A minimal disassembler for the PPU, enough to read a function.

The PPU is a 64-bit PowerPC, big-endian.  The tool prints the instructions
of a range of the code segment, with the register names, so that a boundary
can be checked by reading it.

    python tools/ppu_disasm.py <eboot.elf> --start 0x10200 --count 24
    python tools/ppu_disasm.py <eboot.elf> --at 0x10638

Only the instructions that matter for a boundary are decoded: the branches,
the stack frame, the moves.  The others are printed with their opcode and
their operands, so nothing is hidden.
"""

from __future__ import annotations

import argparse
import os
import struct
import sys
from typing import Sequence

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ppu_elf import ElfError, PpuElf  # noqa: E402

# The name of the registers.
REGS = ["r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7",
        "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15",
        "r16", "r17", "r18", "r19", "r20", "r21", "r22", "r23",
        "r24", "r25", "r26", "r27", "r28", "r29", "r30", "r31"]


def signed(value: int, bits: int) -> int:
    """The signed value of a field."""
    if value & (1 << (bits - 1)):
        return value - (1 << bits)
    return value


def reg(index: int) -> str:
    return REGS[index] if index < len(REGS) else f"r{index}"


def decode(word: int, address: int) -> str:
    """The text of one instruction.

    Only the shapes that matter for a boundary are named; the others are
    printed as their word, so nothing is hidden.

    The field layout of the 64-bit PowerPC is used: the destination or the
    source sits in the bits 6-10, the first operand in the bits 16-20, and
    the second one, for the three-operand forms, in the bits 11-15.
    """
    opcode = word >> 26
    rD = (word >> 21) & 0x1F
    rA = (word >> 16) & 0x1F
    rB = (word >> 11) & 0x1F
    rS = rD
    uimm = word & 0xFFFF
    simm = signed(uimm, 16)

    if word == 0x4E800020:
        return "blr"
    if word == 0x4E800420:
        return "bctr"
    if word == 0x4E800421:
        return "bctrl"
    if word == 0x60000000:
        return "nop"

    if opcode == 18:
        # b / bl
        link = "bl" if word & 1 else "b"
        absolute = "a" if word & 2 else ""
        displacement = word & 0x03FFFFFC
        if displacement & 0x02000000:
            displacement -= 0x04000000
        target = (address + displacement) & 0xFFFFFFFF
        return f"{link}{absolute} 0x{target:08X}"

    if opcode == 19:
        return f"bcx 0x{word:08X}"

    if opcode == 16:
        displacement = signed(word & 0xFFFC, 16)
        target = (address + displacement) & 0xFFFFFFFF
        return f"bc 0x{target:08X}"

    # the stores of the SDK, and the frame of the SDK
    if opcode == 62:
        extended = (word >> 1) & 0x1F
        if extended == 8:
            return f"stdu {reg(rS)},{simm}({reg(rA)})"
        return f"stw {reg(rS)},{simm}({reg(rA)})"
    if opcode == 36:
        return f"stw {reg(rS)},{simm}({reg(rA)})"
    if opcode == 32:
        return f"lwz {reg(rD)},{simm}({reg(rA)})"
    if opcode == 34:
        return f"lbz {reg(rD)},{simm}({reg(rA)})"
    if opcode == 40:
        return f"lhz {reg(rD)},{simm}({reg(rA)})"
    if opcode == 42:
        return f"sth {reg(rS)},{simm}({reg(rA)})"
    if opcode == 14:
        if rA == 0:
            return f"li {reg(rD)},{simm}"
        return f"addi {reg(rD)},{reg(rA)},{simm}"
    if opcode == 15:
        return f"addis {reg(rD)},{reg(rA)},{simm << 16}"
    if opcode == 24:
        return f"ori {reg(rA)},{reg(rA)},{uimm}"
    if opcode == 25:
        return f"oris {reg(rA)},{reg(rA)},{uimm << 16}"
    if opcode == 28:
        return f"andi. {reg(rA)},{reg(rA)},{uimm}"
    if opcode == 29:
        return f"andis. {reg(rA)},{reg(rA)},{uimm << 16}"
    if opcode == 11:
        return f"cmpwi cr0,{reg(rA)},{simm}"
    if opcode == 10:
        return f"cmpli cr0,{reg(rA)},{uimm}"

    if opcode == 31:
        # the move of the link register, and the specials of the SDK
        if word & 0xFF1FFCFF == 0x7C0800A6:
            # the PPU places the destination of the link-register moves in
            # the bits 8-12, with an offset of two
            return f"mflr r{((word >> 8) & 0x1F) - 2}"
        if word & 0xFF1FFCFF == 0x7C0003A6:
            return f"mtlr {reg(rS)}"
        return f"op31 xo=0x{(word >> 1) & 0x3FF:03X} {reg(rD)},{reg(rA)},{reg(rB)}"

    return f".long 0x{word:08X}"


def text_range(elf: PpuElf) -> tuple[int, int]:
    best = None
    for ph in elf.program_headers():
        if not ph.is_load or (ph.flags & 0x4) == 0:
            continue
        if best is None or ph.filesz > best.filesz:
            best = ph
    if best is None:
        raise ElfError("no executable segment found")
    return best.vaddr, best.filesz


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # pragma: no cover
            pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("elf", help="path to the rebuilt PPU ELF")
    parser.add_argument("--start", help="first address")
    parser.add_argument("--at", help="first address")
    parser.add_argument("--count", type=int, default=16, help="number of instructions")
    args = parser.parse_args(argv)

    start = args.start or args.at
    if start is None:
        parser.error("--start or --at is required")
    address = int(start, 0)

    try:
        with open(args.elf, "rb") as handle:
            elf = PpuElf(handle.read(), args.elf)
    except (OSError, ElfError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    vaddr, size = text_range(elf)
    if not vaddr <= address < vaddr + size:
        print(f"error: 0x{address:X} is not in the code segment", file=sys.stderr)
        return 1
    data = elf.read_vaddr(address, args.count * 4)
    for index in range(args.count):
        offset = index * 4
        if offset + 4 > len(data):
            break
        word = struct.unpack_from(">I", data, offset)[0]
        here = address + offset
        print(f"0x{here:08X}:  {word:08X}  {decode(word, here)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
