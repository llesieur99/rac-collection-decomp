/*
 * Ratchet & Clank Collection (PS3, USA BCUS98282)
 *
 * A function of the collection launcher that calls one other function and
 * returns nothing.
 *
 * Target   : PS3_GAME/USRDIR/EBOOT.BIN, rebuilt PPU ELF
 * Address  : 0x512F4
 * Extent   : 0x512F4 .. 0x51318 (36 bytes, 9 instructions)
 * Compiler : SCEI PPC GCC 4.1.1 (SDK400, $Rev: 3538 $), target ppu-lv2
 * Flags    : -O1 -mno-save-restore-tocbase
 *
 * Result   : **byte-exact**.  The 36 bytes at 0x512F4 are reproduced.
 *
 * The proof
 * ---------
 *     python tools/try_body.py work/gate/func_512F4.c 0x512F4 \
 *         --elf work/decrypted/eboot.elf --symbol sub_8954C=0x8954C
 *     match: 36 bytes at 0x512F4
 *
 * What the code does
 * ------------------
 * It calls one function and returns nothing.  The frame is the SDK's: 0x70
 * bytes, the link register saved in the caller's frame at 0x10(r1), and the
 * stack pointer restored with an immediate add.
 *
 * What is still a hypothesis
 * --------------------------
 * * The name. "func_512F4" describes the place: the address of the
 *   function.  The game's own name for it is unknown.
 * * The callee.  Its name here is an address; what it does is still to be
 *   read.
 */

void sub_8954C(void);

void func_512F4(void)
{
    sub_8954C();
}
