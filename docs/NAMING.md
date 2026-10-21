# The naming

A name is a hypothesis until the code proves it. This document records how
the names of this project are obtained, and why the obvious shortcuts do not
work.

## The rule

The sibling project puts it plainly: *the name is never the evidence*. A
function is named when **what the code at its address must do** agrees with
the name. A name that merely sounds right is a hypothesis, and a hypothesis
stays in the catalogue as such.

For this project the chain is short and it closes:

1. **The evidence.** The code says what the function touches: the strings, the
   functions it calls, the functions that call it, the data it reads.
2. **The proposal.** The evidence suggests a name. A function that touches the
   string `Ratchet` is a candidate for a name about Ratchet.
3. **The source.** The function is written in the form the original author
   would have used.
4. **The proof.** The source is compiled with the qualified profile, linked at
   the measured address, and compared with the retail bytes. **Only a body
   that reproduces the retail bytes carries a name.**

Step 4 is what makes the name a fact. Everything before it is a guess that
happens to be written down.

## Why the shortcuts do not work

The sibling project measured the obvious shortcut and it failed. A prototype
of the engine binds eleven engine symbols to fixed addresses in its linker
script; those addresses were tested against the retail build, and **one name
transfers and ten do not**.

The reason is measurable and not mysterious: the two builds **share a shape,
not a layout**.

| Section | The prototype | The retail build |
|---|---|---|
| CORE `.text` | `0x00115200`-`0x00133a50` | `0x00115200`-`0x00133b4f` |
| CORE `.data` | `0x00133a80`-`0x00139ec0` | `0x00133b80`-`0x0013a1bf` |
| FRONTEND `.text` | `0x001faf80`-`0x00260e10` | `0x0026ea00`-`0x00351fbf` |

The section *names* and the section *order* are the same; the addresses are
not. An address is therefore not a portable name, and a name cannot be
transferred by address — neither from a prototype to a retail build, nor from
the PlayStation 2 originals to the PlayStation 3 builds, nor from one retail
build to another.

The same measurement was made here, on the three titles of the release: the
standalone PlayStation Network titles and the collection's copies are **two
builds of the same programs**, with the same entry points, and their code
sizes differ by hundreds of bytes. The names still have to be proved on each
build.

## The evidence the code carries

The naming evidence of a function is what the analysis of the code finds:

| Evidence | What it gives |
|---|---|
| the strings it touches | the *subject* of the function: a name, a format string, a file name, a message |
| the functions it calls | its *role*: a getter, a setter, a parser, a dispatcher |
| the functions that call it | its *role* seen from the other side |
| the data it reads and writes | the *state* it works on |

The evidence is measured, and it is published: it is research metadata, and it
carries no game bytes.

## The vocabulary of the series

The three titles of the release share the engine with the other games of the
series, and the sibling projects have recovered a good part of that engine's
vocabulary. That vocabulary is a **hypothesis source**: it says what to look
for, and it makes a proposal cheap.

It is never the proof. A name that comes from another project has to be
proved here, on this build, by the body gate. A function that the sibling
project calls `weapon_get_name` and that this project's code also calls
`weapon_get_name` is one name with two pieces of evidence — the string, and
the bytes.

## The state of the names

| | Count |
|---|---|
| functions bounded | 50,877 |
| functions that touch a string | 2,679 — the subject of the function, measured |
| functions that carry an assert | 246 — the source file and the line, measured |
| functions with a call graph | 35,703 — the role of the function, measured |
| functions with a proved name | 6 — and those six carry the placeholder of their address, because nothing yet says what they do |
| functions with a proposed name | **299** — 236 from the assert messages, 63 from the sibling projects |

The six proved bodies are the first ones, and they are deliberately the
simplest: a frame, a call, an epilogue. They prove the toolchain and the
method, not the vocabulary.

The next names come from the evidence: a function that touches a string is
named after what the string says, written, and measured. The evidence is in
[config/evidence.tsv](../config/evidence.tsv), and the method is in
[EVIDENCE.md](EVIDENCE.md).

## How a name travels

The section above says a name cannot be transferred by address. That is true,
and it is not the end of the story: the *function* travels, and the
correspondence between the builds is measured.

The measurement is in [CORRESPONDENCE.md](CORRESPONDENCE.md): 99 % of the
functions of a game are matched with the function that plays the same role in
the other build of that game, every matched pair having exactly the same
size. Between the three games of the series, the engine's own code is matched
as well, and **more than half of those pairs are literally the same bytes**.

That gives three levels of travel:

| The counterpart | What travels | What the name is worth there |
|---|---|---|
| the other build of the same game | the address, the code, the subject | a **proposal**, to be proved by the body gate on that build |
| the other game, **same bytes** | the body itself | the **proof**: the body gate reproduces the same bytes at the other address |
| the other game, different bytes | the subject, the role | a **proposal**, to be proved on that game |

The second line is the one that changes the economics of the naming: for the
engine's own code, a name proved once is proved three times, and the work of
the second and the third proof is the address.

`tools/propose_name.py` carries a name over, and records the proposal in the
catalogue with the state `proposed` and the evidence that says where it comes
from:

```sh
python tools/propose_name.py --program collection-RC1 --address 0x000128B8 --name rt_udp_send --write
```

A proposal is still a hypothesis. Only the body gate makes a name a fact —
but a hypothesis with a measured counterpart is a much cheaper hypothesis.

## The first proposals

Two sources of proposals, both measured, both hypotheses until the body gate
proves them.

**The PlayStation 2 decompilation.** The message a function prints is the
proof that the PlayStation 2 function and the PlayStation 3 one are the same
function: a pair of functions picked at random shares a message 0,18 % of the
time.

| Program | Address | Proposed name | The message that proves it |
|---|---|---|---|
| `RC1` | `0x000716B0` | `do_space_transition` | `unloaded sound bank %#010x\n` |
| `RC1` | `0x000F3370` | `copy_text_to_shared_buffer` | `(Message too long)` |
| `RC1` | `0x00179E40` | `draw_prompt_box` | `(error)` |
| `RC1` | `0x001971B8` | `draw_ties_2` | `tie draw`, `tie texs` |
| `RC1` | `0x0019C300` | `set_scrolling_status_message` | `%s` |
| `RC2` | `0x00096C60` | `memcard_get_data_size` | `ERROR: could not init memcard lib\n` |
| `RC2` | `0x00BE79F8` | `draw_prompt_box` | `(error)` |
| `RC3` | `0x001F2504` | `memcard_get_data_size` | `ERROR: could not init memcard lib\n` |

Two of them land on **the same function in two different games** —
`draw_prompt_box` in `RC1` and in `RC2` — which is the control the method
needs: the key is not a coincidence of one program.

**The assert messages of the lobby.** `RC3` carries the code of the
multiplayer, and 682 live assertions in 47 source files. An assertion names
the class, the member and often the method itself:

| Program | Address | Proposed name | The assert that names it |
|---|---|---|---|
| `RC3` | `0x00A8616C` | `lobby_gui_item_set_scale` | `"%s() not defined for this objectType (%d)."` with `"SetScale"` |
| `RC3` | `0x008EE05C` | `lobby_net_main_alloc_location_list` | `"LobbyNet::AllocLocationList() - Need more memory!"` |
| `RC3` | `0x008D6194` | `lobby_net_account_login_request` | `"LobbyNet::AccountMgr::LoginRequest()"` |
| `RC3` | `0x008D8C60` | `lobby_net_clan_clan_mgr_ctor` | `"LobbyNet::ClanMgr() - Wrong class size"` |
| `RC3` | `0x008E21FC` | `lobby_net_clan_update` | `"LobbyNet::ClanMgr::Update() - … Refresh Timed Out"` |
| `RC3` | `0x008F525C` | `lobby_net_room_refresh_player_list` | `"LobbyNet::RoomMgr::RefreshPlayerList() Error (MEDIUS: %d)"` |
| `RC3` | `0x00905DF4` | `lobby_gui_item_create_graphics` | `"CreateGraphics"` |
| `RC3` | `0x00906350` | `lobby_gui_item_push_layer` | `"You are out of widget layers."` |
| `RC3` | `0x00900D34` | `lobby_shared_pool_alloc_destroy_pool` | `"PoolAllocator::DestroyPool() - Pool not empty!"` |

**222 of the 230 functions of the lot** carry a name, and the eight that do
not are published as such: six of them have nothing but a header file, one is
indistinguishable from its neighbour, and one is *contradicted* by its own
code — it is engine code, and the assert that names it belongs to another
file. The read of the disassembly corrected one proposal in the process.

Every proposal is checked: the literal it rests on is searched in the
measured code of the function and of its callers, and a proposal whose
literal is nowhere near the function is a proposal that contradicts the
code. None does.

**The vocabulary of the sibling projects.** The six projects that
decompiled the PlayStation 2 games of the series carry **16,049 distinct
names**, 4,824 of them names of functions, and the tool that extracts them
is [`tools/extract_vocab.py`](../tools/extract_vocab.py). The largest
source of them was never exploited: the table of symbols of `rac2`, which
holds **1,958 names the engine itself carries** — `OnDmacBusError`,
`OnTertiaryVoiceStarted`, `StopFileLoad` — and which were established
independently on the three titles.

That lot named **63 functions** of the PlayStation 3 builds, against 18
before it. The gain came almost entirely from one key — the **message**
the two versions print — and the others were measured to be worth nothing
on their own: the profile of the strings (+0), the reach in the call graph
(0), the name of the file (0). The control is measured too: a pair of
functions picked at random shares a message 0,005 % to 0,225 % of the time,
and the proposals share one by construction. Three of them are
demonstrably false positives, and they are marked as such.

**Four of the 63 proposals carry an ambiguous name** — the name of a group
of functions rather than of one — and none of the 299 is a fact: the
compiled body still has to reproduce the retail bytes.

The table is in [config/proposals.tsv](../config/proposals.tsv).

## What a name is worth

A name is worth what it saves. The engine's vocabulary is large and shared
across the three titles: a name recovered once on one title is a hypothesis
for the other two, and the same *shape* of code appears in all three. A name
that is proved on one title and merely proposed on the other two is already
worth a lot of work.

That is the reason the names are worth the effort, and the reason they are
not transferred by address.
