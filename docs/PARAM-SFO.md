# The PARAM.SFO metadata file

`PS3_GAME/PARAM.SFO` is the metadata file of the release. It is a flat table
of typed values with a separate string table for the keys. The format is
little-endian.

## The structure

| Offset | Size | Field |
|---|---|---|
| `0x00` | 4 | magic `0x46535000` (`"\0PSF"`) |
| `0x04` | 4 | version, `0x00000101` |
| `0x08` | 4 | offset of the key table |
| `0x0C` | 4 | offset of the data table |
| `0x10` | 4 | number of index entries |
| `0x14` | 16 × n | the index table |

Each index entry is 16 bytes:

| Offset | Size | Field |
|---|---|---|
| `0x00` | 2 | offset of the key, relative to the key table |
| `0x02` | 2 | data format |
| `0x04` | 4 | length of the value |
| `0x08` | 4 | maximum length of the value |
| `0x0C` | 4 | offset of the value, relative to the data table |

The data formats are:

| Format | Meaning |
|---|---|
| `0x0004` | UTF-8 string, null terminated |
| `0x0204` | UTF-8 string, null terminated (special characters allowed) |
| `0x0404` | 32-bit signed integer |

## The measured table

| # | Key | Format | Length | Value |
|---|---|---|---|---|
| 0 | `APP_VER` | utf8 | 6 | `01.00` |
| 1 | `ATTRIBUTE` | int32 | 4 | 135,168 (`0x21000`) |
| 2 | `BOOTABLE` | int32 | 4 | 1 |
| 3 | `CATEGORY` | utf8 | 3 | `DG` |
| 4 | `LICENSE` | utf8 | 401 | the Sony licence text |
| 5 | `PARENTAL_LEVEL` | int32 | 4 | 4 |
| 6 | `PS3_SYSTEM_VER` | utf8 | 8 | `04.2100` |
| 7 | `RESOLUTION` | int32 | 4 | 63 |
| 8 | `SOUND_FORMAT` | int32 | 4 | 1 |
| 9 | `TITLE` | utf8 | 27 | `Ratchet & Clank Collection` |
| 10 | `TITLE_ID` | utf8 | 10 | `BCUS98282` |
| 11 | `VERSION` | utf8 | 6 | `02.00` |

The file is 1,040 bytes and hashes to
`95d46880b05a87a614a01d3a07f4222e92aac0ab92405b646a9182cd204bce83`.

## Reading it

```sh
python tools/param_sfo.py info   "path/to/PS3_GAME/PARAM.SFO"
python tools/param_sfo.py list   "path/to/PS3_GAME/PARAM.SFO"
python tools/param_sfo.py get    "path/to/PS3_GAME/PARAM.SFO" TITLE_ID
python tools/param_sfo.py to-json "path/to/PS3_GAME/PARAM.SFO"
```

## What it does not tell

The `PARAM.SFO` holds no content id. The content id of the release lives in the
encrypted NPDRM metadata of the executables, which needs console key material
to read; see [SELF-FORMAT.md](SELF-FORMAT.md). The value that
`config/target.json` carries is a **derivation** from the title, and it is
flagged as such.
