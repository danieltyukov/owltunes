# Assembling an owl (rev A)

Tools: a soldering iron with a heat-set insert tip (for the inserts only, 220 C), a JST SH crimp
tool (Engineer PA-09 or similar), a multimeter, a 1.3 mm hex key for the ISO 7380 M2 button
heads, cyanoacrylate glue, 0.2 mm double-sided tape, and a glue that does not fog glass (two-part
epoxy or UV-curing glue) for the glass retainer. Keep cyanoacrylate away from the cover glass: its
vapour leaves a white film. Also a piece of soft silicone thermal gap pad, about 5 x 5 mm and
1.5 mm thick, 1 to 3 W/mK, electrically insulating (see step 8).

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
5. **LRA.** Crimp SSH-003T-P0.2-H contacts on the motor's two leads, push them into an
   SHR-02V-S-B housing (red lead in pin 1), glue the motor into the back cover cup.
6. **Battery.** The pack is a 1S LiPo 803040 (8 x 30 x 40 mm, about 1000 mAh) with a protection
   circuit and a 2-wire lead on a JST PH 2.0 2-pin plug. It needs no NTC wire: the charger reads
   RT101, an NTC on the board under the cell. A 3-wire pack (with its own NTC) works too: move
   its positive and negative contacts into a 2-pin JST PHR-2 housing and insulate the NTC wire,
   which is unused. J101 has no reverse-polarity protection, and many packs are wired the other
   way round. Before plugging in, hold the plug the way it mates with J101 and check with a
   multimeter that the contact facing the `+` mark (pin 1, with the dot) is positive and the one
   facing `-` is negative; the red wire should be on `+`. If the order differs, lift each
   contact's latch with a needle and swap the two wires. No soldering.
7. **Dock pads.** Snap the dock-pad section off the perch board at the mouse bites, file the
   neck flush, glue it into the back cover recess with the gold pads facing out. Plug a straight
   4-pin JST SH cable (pin 1 to pin 1) into its J2; the other end goes to J303 on the main board.
   Snap at the bite row with pliers on the tab and file the nub flat after snapping; the owl recess
   and the perch pocket have a 0.8 mm relief at the neck, but a nub over 0.4 mm reaches the battery margin.
8. **Stack.** Put the main board into the body from the back, then the bezel and ring into the
   face opening so the bezel lugs rest on the board. Press the thermal gap pad onto the back of
   the board, centred on RT101's copper patch (the 4.5 x 3 mm rectangle under the mask, 4.5 mm
   below the centre of U303, with RT101 just past its right-hand end seen from the back; see
   [rev-a.md](rev-a.md), Off-board parts), so the cell rests on it. Put the battery, motor plug
   and dock cable in place (J101, J302, J303) and close the back cover. Screw four ISO 7380
   M2 x 6 from the front through the bezel lugs and the board into the cover standoffs, and four
   ISO 7380 M2 x 14 from the back through the cover spacers and the board into the body bosses.
   The back screw heads sit just below the cover's back face.
9. **Display.** The cover glass is laminated to the panel. Insert the panel's adapter FPC into
   J301 contacts down (the connector is bottom contact) and close the latch; check that the FPC's
   pin 1 marking is at the J301 `31` end (connector pin k = panel pin 32 - k). Fold the flex
   through the notch at the top of the bezel and lower the display into the bezel from the
   front: the panel goes into its pocket and the glass border rests on a ring of the 0.2 mm tape
   on the ledge. Then glue the 1.3 mm retainer ring into the lip opening over the glass border,
   keeping glue off the viewing area.
