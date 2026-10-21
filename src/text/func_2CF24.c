/*
 * Ratchet & Clank Collection (PS3, USA BCUS98282)
 *
 * A function of the collection launcher that calls one other function and
 * returns nothing.
 *
 * Target   : PS3_GAME/USRDIR/EBOOT.BIN, rebuilt PPU ELF
 * Address  : 0x2CF24
 * Extent   : 0x2CF24 .. 0x2CF44 (32 bytes, 8 instructions)
 * Compiler : SCEI PPC GCC 4.1.1 (SDK400, $Rev: 3538 $), target ppu-lv2
 * Flags    : -O1 -mno-save-restore-tocbase -mno-nop-after-bl
 *
 * Result   : **byte-exact**.  The 32 bytes at 0x2CF24 are reproduced.
 *
 * The proof
 * ---------
 *     python tools/try_body.py work/gate/func_2CF24.c 0x2CF24 \
 *         --elf work/decrypted/eboot.elf --symbol sub_2CE90=0x2CE90
 *     match: 32 bytes at 0x2CF24
 *
 * The flags
 * ---------
 * This function is compiled with -mno-nop-after-bl, and that is visible in
 * its code: the call is four bytes long, where the SCE backend would
 * otherwise emit the branch and a second word that restores the TOC.  The
 * launcher holds both shapes, so the game was built with the option on some
 * files and off on others.  See docs/TOOLCHAIN.md.
 *
 * What the code does
 * ------------------
 * It calls one function and returns nothing.  The frame is the SDK's: 0x70
 * bytes, the link register saved in the caller's frame at 0x80(r1), and the
 * stack pointer restored with an immediate add.
 *
 * What is still a hypothesis
 * --------------------------
 * * The name.  The address describes the place; the game's own name for it
 *   is unknown.
 * * The callee.  Its name here is an address.
 */

void sub_2CE90(void);

void func_2CF24(void)
{
    sub_2CE90();
}
