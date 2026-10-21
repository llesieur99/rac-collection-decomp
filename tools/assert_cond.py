"""The condition and the free text of every assert of RC3, site by site.

The retail RC3 build does not pass the whole assert in one call.  A single
assert of the lobby is made of **three** calls to the same handler:

    r3 = "\\n\\nAssertion failure: %s:%d"   r4 = the file   r5 = the line
    r3 = "\\n\\texpression '%s'\\n\\n"       r4 = the condition
    r3 = the free text of the assert

Only the first call carries the line, so only that one is an assert for
``tools/assert_xref.py``.  The two others are the **condition** and the
**message** of the assert, and they are the best naming evidence the lobby
carries: they name the class, the member, and the method.

This tool re-reads the calls of the program, with the rule the strings tool
uses (a register keeps the address it holds until an instruction writes it),
and attaches the condition and the message to the assert they belong to.

The output is metadata: the address of the call, and the text of the strings.
No game byte is copied.
"""

from __future__ import annotations

import argparse
import csv
import os
import struct
import sys
from typing import Sequence

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ppu_elf import PpuElf  # noqa: E402
from strings_xref import StringTable, segments, read_pointer  # noqa: E402

BRANCH = 18
ADDIS = 15
ADDI = 14
ADDIC = 12
ADDICD = 13
ORI = 24
ORIS = 25
WRITES_RD = frozenset({7, 8, 12, 13, 14, 15, 24, 25, 26, 27, 28, 29, 31, 58})
MEMORY = frozenset({
    32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45,
    46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 58, 62,
})
ARGUMENT_REGISTERS = (3, 4, 5, 6, 7, 8, 9, 10)
EXPRESSION_FORMAT = "\n\texpression '%s'\n\n"


def branch_target(word: int, address: int) -> int:
    displacement = word & 0x03FFFFFC
    if displacement & 0x02000000:
        displacement -= 0x04000000
    return (address + displacement) & 0xFFFFFFFF


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--elf", required=True)
    parser.add_argument("--asserts", required=True)
    parser.add_argument("--program", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    with open(args.elf, "rb") as handle:
        elf = PpuElf(handle.read(), args.elf)
    code, data = segments(elf)
    strings = StringTable(data)

    def resolve(address: int) -> str | None:
        text = strings.at(address)
        if text is not None:
            return text
        for width in (8, 4):
            pointer = read_pointer(data, address, width)
            if pointer is None:
                continue
            text = strings.at(pointer)
            if text is not None:
                return text
        return None

    handlers = set()
    sites = {}
    with open(args.asserts, encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            if row["program"] != args.program:
                continue
            handlers.add(int(row["handler"], 0))
            sites.setdefault(row["site"], []).append(row)

    base, blob = code
    high: dict[int, int] = {}
    calls = []                                  # (address, target, [strings])
    for offset in range(0, len(blob) - 3, 4):
        word = struct.unpack_from(">I", blob, offset)[0]
        address = base + offset
        opcode = word >> 26
        rD = (word >> 21) & 0x1F
        rA = (word >> 16) & 0x1F
        held = high.get(rA)

        if opcode == BRANCH and word & 1:
            target = branch_target(word, address)
            if target in handlers:
                arguments = []
                for register in ARGUMENT_REGISTERS:
                    value = high.get(register)
                    if value is None:
                        continue
                    text = resolve(value)
                    if text is not None:
                        arguments.append((register, text))
                calls.append((address, target, arguments))
            if opcode in WRITES_RD:
                high.pop(rD, None)
            continue

        if opcode in WRITES_RD:
            high.pop(rD, None)
        if opcode == ADDIS and rA == 0:
            high[rD] = (word & 0xFFFF) << 16
            continue
        if opcode == ORIS:
            if held is not None:
                high[rD] = held | ((word & 0xFFFF) << 16)
            continue
        if held is None:
            continue
        if opcode in (ADDI, ADDIC, ADDICD):
            low = word & 0xFFFF
            if low & 0x8000:
                low -= 0x10000
            high[rD] = (held + low) & 0xFFFFFFFF
            continue
        if opcode == ORI:
            high[rD] = held | (word & 0xFFFF)
            continue
        if opcode in MEMORY:
            low = word & 0xFFFF
            if low & 0x8000:
                low -= 0x10000
            high[rD] = (held + low) & 0xFFFFFFFF

    # The calls, in address order: the condition and the message of an assert
    # are the calls that follow the header of the assert.
    by_address = {address: (target, arguments)
                  for address, target, arguments in calls}
    order = [address for address, _t, _a in calls]

    rows = []
    for site, records in sites.items():
        address = int(site, 0)
        if address not in by_address:
            continue
        _target, arguments = by_address[address]
        condition = ""
        message = ""
        texts = [text for _register, text in arguments]
        if not any("%s:%d" in text for text in texts):
            # the shape of a single literal that already carries the file and
            # the line: the condition and the message are in the literal.
            for text in texts:
                if "Assertion failure" in text:
                    continue
                if not condition and ("\n" not in text) and len(text) < 120:
                    condition = text
                elif not message and len(text) < 200:
                    message = text
            rows.append((site, condition, message, " | ".join(texts)))
            continue
        # the calls that follow, in the same function, are the condition and
        # the message.
        index = order.index(address)
        for follower in order[index + 1:index + 6]:
            if follower - address > 0x40:
                break
            target, follower_arguments = by_address[follower]
            follower_texts = [text for _r, text in follower_arguments]
            if not condition:
                for position, text in enumerate(follower_texts):
                    if text == EXPRESSION_FORMAT:
                        if position + 1 < len(follower_texts):
                            condition = follower_texts[position + 1]
                        break
            if not message and condition:
                if EXPRESSION_FORMAT in follower_texts:
                    continue            # the call of the condition
                if not follower_texts:
                    continue
                text = follower_texts[0]
                if "%" in text or text.endswith(".cpp") or text.endswith(".h"):
                    continue
                message = text
            if condition and message:
                break
        rows.append((site, condition, message, " | ".join(texts)))

    rows.sort(key=lambda row: row[0])
    with open(args.out, "w", encoding="utf-8", newline="\n") as out:
        out.write("site\tcondition\tmessage\targuments\n")
        for site, condition, message, arguments in rows:
            out.write("%s\t%s\t%s\t%s\n" % (
                site,
                condition.replace("\t", " ").replace("\n", "\\n"),
                message.replace("\t", " ").replace("\n", "\\n"),
                arguments.replace("\t", " ").replace("\n", "\\n")))
    print(f"wrote {args.out}: {len(rows)} asserts, "
          f"{sum(1 for r in rows if r[1])} with a condition, "
          f"{sum(1 for r in rows if r[2])} with a message")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
