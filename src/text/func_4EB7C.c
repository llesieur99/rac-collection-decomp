/*
 * Ratchet & Clank Collection (PS3, USA BCUS98282)
 *
 * A function of the collection launcher that calls one other function and
 * returns nothing.
 *
 * Target   : PS3_GAME/USRDIR/EBOOT.BIN, rebuilt PPU ELF
 * Address  : 0x4EB7C
 * Extent   : 0x4EB7C .. 0x4EB9C (32 bytes, 8 instructions)
 * Compiler : SCEI PPC GCC 4.1.1 (SDK400, $Rev: 3538 $), target ppu-lv2
 * Flags    : -O1 -mno-save-restore-tocbase -mno-nop-after-bl
 *
 * Result   : **byte-exact**.  The 32 bytes at 0x4EB7C are reproduced.
 *
 * The proof
 * ---------
 *     python tools/try_body.py work/gate/func_4EB7C.c 0x4EB7C \
 *         --elf work/decrypted/eboot.elf --symbol sub_4D600=0x4D600
 *     match: 32 bytes at 0x4EB7C
 *
 * The call is four bytes long here, which is the trace of the
 * -mno-nop-after-bl option.  See docs/TOOLCHAIN.md.
 *
 * What is still a hypothesis
 * --------------------------
 * * The name.  The address describes the place.
 * * The callee.  Its name here is an address.
 */

void sub_4D600(void);

void func_4EB7C(void)
{
    sub_4D600();
}
