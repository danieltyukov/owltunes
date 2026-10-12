# Assembling an owl (rev A)

Tools: a soldering iron (for the inserts at 220 C, with a heat-set insert tip or a clean conical
tip, and for the LRA leads), solder and 1.5 mm heat-shrink tubing, a multimeter, a 1.3 mm hex key
for the ISO 7380 M2 button heads, cyanoacrylate glue, 0.2 mm double-sided tape, 1 mm double-sided
foam tape (battery end stop, step 8), and a glue that does not fog glass (two-part epoxy or
UV-curing glue) for the glass retainer. No crimp tool: the LRA gets a pre-crimped pigtail. Keep
cyanoacrylate away from the cover glass: its vapour leaves a white film. Also a piece of soft
silicone thermal gap pad, about 5 x 5 mm and 1.5 mm thick, 1 to 3 W/mK, electrically insulating
(see step 8).

The ring variant (A with the 6710 bearing, B with the printed bushing) and the magnet count come
from the ring test; see [ring-test.md](ring-test.md).

1. **Inserts.** Press M2 x 3 mm heat-set inserts into the four body bosses (behind the head
   corners and the belly) and the four back-cover standoffs.
2. **Magnets.** Ring carrier: alternate the polarity (see `ring-test.md`), a drop of glue each.
   The product carrier has no polarity bumps, so check each magnet against its neighbour with a
   reference magnet before the glue sets. Back cover: two D6 x 2 mm magnets in the cups at
   (+-20, -22), north facing out; the perch magnets face south out so they attract.
3. **Ring.** Slide the bearing (or the bushing sleeve) onto the bezel tube from the back until it
   stops on the lip, press the ring on from the front, push the carrier into the ring from the
   back.
4. **Keys.** Beak key into the face slot from inside; ear keys into the top slots from inside.
5. **LRA.** The motor's two leads (red and blue, about 27 mm, AWG 32) are spliced to a pre-crimped
   JST SH 1.0 mm 2-pin pigtail whose housing plugs into J302. Trim the pigtail to about 20 mm from
   its housing, slide a 10 mm piece of 1.5 mm heat-shrink tubing over each of its wires, strip
   about 3 mm of each wire and each motor lead, twist and solder red to the wire in housing pin 1
   and blue to pin 2, then shrink the tubing over the joints. The LRA has no polarity; the order
   only keeps every owl the same. Glue the motor into the back cover cup with its lead tab in the
   slot of the cup wall; the splices lie between the cup and J302.
6. **Battery.** The pack is a 2-wire 1S LiPo of the 803030 class (8 x 30 x 30 mm) with a protection
   circuit and a JST PH 2.0 2-pin plug: efaso 803030 740 mAh, or EEMB 803030 700 mAh if its plug is
   confirmed as PH 2.0 (2.0 mm pitch, not PH 1.25 or SH 1.0). The cavity is drawn for an 803040
   (8 x 30 x 40 mm), so the shorter cell is held by a foam end stop (step 8). The pack needs no NTC
   wire: the charger reads RT101, an NTC on the board under the cell. A 3-wire pack (with its own
   NTC) works too: move its positive and negative contacts into a 2-pin JST PHR-2 housing and
   insulate the NTC wire, which is unused. J101 has no reverse-polarity protection, and many packs
   are wired the other way round. Before plugging in, hold the plug the way it mates with J101 and
   check with a multimeter that the contact facing the `+` mark (pin 1, with the dot) is positive
   and the one facing `-` is negative; the red wire should be on `+`. If the order differs, lift
   each contact's latch with a needle and swap the two wires. No soldering. Do this for every pack,
   the spare too: J101 pin 1 is VBAT and pin 2 is GND.
7. **Dock pads.** Snap the dock-pad section off the perch board at the mouse bites, file the
   neck flush, glue it into the back cover recess with the gold pads facing out. Plug a straight
   4-pin JST SH cable (pin 1 to pin 1) into its J2; the other end goes to J303 on the main board.
   Snap at the bite row with pliers on the tab and file the nub flat after snapping; the owl recess
   and the perch pocket have a 0.8 mm relief at the neck, but a nub over 0.4 mm reaches the battery margin.
8. **Stack.** Put the main board into the body from the back, then the bezel and ring into the face
   opening so the bezel lugs rest on the board. Press the thermal gap pad onto the back of the
   board, centred on RT101's copper patch (the 4.5 x 3 mm rectangle under the mask, 4.5 mm below
   the centre of U303, with RT101 just past its right-hand end seen from the back; see
   [rev-a.md](rev-a.md), Off-board parts), so the cell rests on it. The battery space runs between
   the four cover standoffs, from the top edge of the dock-pad recess in the cover up to just below
   J101's plug. Lay the cell in lead end up, with its leads leaving the right half of its top edge
   for J101, and check that it covers the gap pad. It is about 8 to 10 mm shorter than the space:
   stick an end stop of 1 mm double-sided foam tape to the inside of the back cover, just above the
   dock-pad recess, about 25 mm wide and three to five layers high, cut deep enough that it holds
   the cell's top edge just below J101's plug. Keep tape and foam off the cell's two large faces:
   the battery layer is 9.2 mm deep and the board's back-side parts under the cell stand up to
   1.1 mm, so an 8 mm cell has only 0.1 to 0.2 mm to spare. The gap pad presses the cell against
   the cover once it is closed. Fold the spare battery lead into the space right of the cell,
   between the two right-hand cover standoffs and clear of the LRA cup. Put the battery, motor plug
   and dock cable in place (J101, J302, J303) and close the back cover. Screw four ISO 7380 M2 x 6
   from the front through the bezel lugs and the board into the cover standoffs, and four ISO 7380
   M2 x 14 from the back through the cover spacers and the board into the body bosses. The back
   screw heads sit just below the cover's back face.
9. **Display.** The cover glass is laminated to the panel. Insert the panel's adapter FPC into
   J301 contacts down (the connector is bottom contact) and close the latch; check that the FPC's
   pin 1 marking is at the J301 `31` end (connector pin k = panel pin 32 - k). Fold the flex
   through the notch at the top of the bezel and lower the display into the bezel from the
   front: the panel goes into its pocket and the glass border rests on a ring of the 0.2 mm tape
   on the ledge. Then glue the 1.3 mm retainer ring into the lip opening over the glass border,
   keeping glue off the viewing area.
