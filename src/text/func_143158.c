/*
 * Ratchet & Clank Collection (PS3, USA BCUS98282)
 *
 * A function of the collection launcher that calls one other function and
 * returns nothing.
 *
 * Target   : PS3_GAME/USRDIR/EBOOT.BIN, rebuilt PPU ELF
 * Address  : 0x143158
 * Extent   : 0x143158 .. 0x14317C (36 bytes, 9 instructions)
 * Compiler : SCEI PPC GCC 4.1.1 (SDK400, $Rev: 3538 $), target ppu-lv2
 * Flags    : -O1 -mno-save-restore-tocbase
 *
 * Result   : **byte-exact**.  The 36 bytes at 0x143158 are reproduced.
 *
 * The proof
 * ---------
 *     python tools/try_body.py work/gate/func_143158.c 0x143158 \
 *         --elf work/decrypted/eboot.elf --symbol sub_14714=0x14714
 *     match: 36 bytes at 0x143158
 *
 * What the code does
 * ------------------
 * It calls one function and returns nothing.  The frame is the SDK's.
 *
 * What is still a hypothesis
 * --------------------------
 * * The name.  The address describes the place; the game's own name for it
 *   is unknown.
 * * The callee.  Its name here is an address.
 */

void sub_14714(void);

void func_143158(void)
{
    sub_14714();
}
