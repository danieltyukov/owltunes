"""Shared OwlTunes mechanical parameters, in millimetres.

Coordinates: the origin is the centre of the display's active area on the front surface of the
cover glass. X points to the owl's right as seen from the front, Y points up and Z points out of
the face towards the viewer, so a part that sits behind the glass has a negative Z. "Depth" in the
names below is a positive distance behind the glass front (z = -depth).

Every value that comes from a datasheet names its source. Values marked "test" are what the ring
test prints check; the measured results are recorded in docs/hardware/ring-test.md and copied
here before the main board is ordered. Licence: CERN-OHL-P-2.0 (LICENSE-HARDWARE).
"""

# MJF nylon (PA12) minimum wall, from JLC3DP's design guideline (jlc3dp.com/help/article/212): 1.0 mm,
# and up to 0.2 mm less only on non-critical features. Structural walls (bearing seat and lip, ring
# bodies, carrier rings and the wall around each magnet pocket, bezel lugs, jig floor and pocket
# walls, sleeve) use MJF_STRUCT_WALL; cosmetic rims and coupon steps may use MJF_MIN_WALL.
MJF_MIN_WALL = 0.8
MJF_STRUCT_WALL = 1.0

# Display: VIEWE ALL-UEOL018VG-RA31-A001A specification V1.1 (2026-07-30), pages 4 and 6, with the
# specification's 52.6 mm cover glass. VIEWE's reply of 14 October 2026: the 48.16 mm glass they had
# confirmed on 13 October is discontinued, and only the 52.6 mm glass is supplied.
GLASS_D = 52.6  # cover glass diameter ("Outline (assembly) 52.6", specification page 4)
GLASS_D_TOL = 0.15  # taken as +-0.15; the drawing's general tolerance is +-0.20
GLASS_T = 1.10  # cover glass thickness ("C.G 1.1")
GLASS_TAPE_T = 0.2  # double-sided tape under the glass border (docs/hardware/assembly.md step 9)
DISPLAY_STACK_T = 2.07  # glass, OCA, panel and foam ("Total 2.07")
VIEW_D = 44.16  # viewing area ("V.A 44.16")
PANEL_W = 45.93  # panel outline width
PANEL_H = 46.35  # panel outline height including the flex bonding ledge
FLEX_PARTS_H = 1.2  # component area on the folded main flex ("H=1.2mm")

# Bearing 6710ZZ: 50 x 62 x 6 thin-section deep-groove ball bearing.
BRG_ID = 50.0
BRG_OD = 62.0
BRG_W = 6.0
BRG_INNER_RACE_OD = 53.6  # estimate of the inner race shoulder; the glass edge stays inside it
BRG_OUTER_RACE_ID = 58.4  # estimate of the outer race shoulder; the ring contacts outside it

# Face bezel (stationary): carries the bearing inner race. The glass is wider than the bearing's
# bore, so it sits in front of the bearing on its tape, on the bezel's front face (the glass ledge),
# which is flush with the bearing's front face. The glass edge reaches 0.2 over the inner race face;
# nothing stationary surrounds it, so the tape alone holds the glass. The bearing has no lip in front
# of it: it is set flush on a flat plate at assembly and held by epoxy on its seat.
BRG_FRONT_DEPTH = GLASS_T + GLASS_TAPE_T  # 1.3: bearing or sleeve front face = bezel front face = glass ledge
LIP_T = 1.3  # the ring lip stands this far in front of the glass, flush with the body face
PANEL_POCKET_D = 47.2  # clears the 46.35 panel behind the glass; the ring left over (to the seat) is the glass ledge
FPC_NOTCH_W = 14.0  # room for the flex fold at the panel's top edge
FPC_NOTCH_R = 23.95  # notch reaches this radius, leaving a 1.0 wall under the bearing seat
FPC_NOTCH_END_DEPTH = 4.0  # the fold sits next to the panel edge; behind it the flex lies flat
BRG_SEAT_D = 49.90  # test: 0.10 clearance, bearing glued (coupon picks the final value)
TUBE_OD = 49.6  # bezel tube behind the seat; the bearing slides over it from the back
TUBE_END_DEPTH = 9.6
LUG_T = 2.0
LUG_R_IN = 15.0
LUG_W = 8.0
LUG_ANGLES_DEG = (0.0, 120.0, 270.0)  # keeps the top free for the flex and 9 o clock free for the sensor
LUG_HOLE_R = 20.0
M2_CLEAR_D = 2.4
# Enclosure screws (bought): ISO 7380-1 hexagon socket button head, M2, black; head dk 3.5 and
# k 1.3 (maximum values of the standard). M2 x 6 from the front through the bezel lugs and the board
# into the back-cover standoffs; M2 x 14 from the back through the cover and the board into the body.
SCREW_FRONT = "ISO 7380 M2 x 6, black"
SCREW_FRONT_L = 6.0
SCREW_BACK = "ISO 7380 M2 x 14, black"
SCREW_BACK_L = 14.0
M2_BUTTON_DK = 3.5
M2_BUTTON_K = 1.3
M2_INSERT_L = 3.0  # M2 x 3 heat-set insert
M2_NUT_AF = 4.0  # across flats of an M2 hex nut
M2_NUT_T = 1.6
M2_NUT_AF_CLEAR = 0.25  # extra across-flats width of the printed nut pocket
M2_NUT_DEPTH_CLEAR = 0.2  # extra depth of the printed nut pocket

# Ring (rotating). The outer diameter is the owl's width.
RING_OD = 66.0
RING_LIP_ID = 53.6  # 0.425 radial to the largest glass (GLASS_D + GLASS_D_TOL), 0.40 at the drawing's +-0.20
RING_CONTACT_R = 30.0  # the ring touches the outer race only outside this radius
LIP_RELIEF = 0.3  # gap between the ring lip and the inner race or shields
RING_A_BORE_D = 62.10  # test: bearing variant, 0.10 clearance, bearing glued
RING_B_BORE_D = 62.00  # test: bushing variant, 0.10 radial clearance on the sleeve
RING_REAR_DEPTH = 8.5  # ring body ends here, 1.0 behind the carrier front (the floor in front of the pockets)
INDEX_NOTCH_W = 1.0
INDEX_NOTCH_D = 0.6
INDEX_NOTCH_L = 2.0

# Bushing sleeve (variant B): replaces the bearing in the same 50 x 62 x 6 envelope.
SLEEVE_ID = 50.10
SLEEVE_OD = 61.80
ORING_CS = 1.5  # O-ring 59 x 1.5 mm NBR 70 (the one bought: ID 59, cross-section 1.5, OD 62)
ORING_ID = 59.0
ORING_GROOVE_W = 2.0
# Groove bottom diameter = SLEEVE_OD - 2 * depth = 59.5: the ring stretches 0.8 percent and is squeezed
# 1.5 mm to 1.25 mm (16.7 percent) between the groove bottom and the 62.00 bore.
ORING_GROOVE_DEPTH = 1.15

# Magnets: D3 x 1 mm N52 discs, axially magnetised, alternating polarity.
MAG_D = 3.0
MAG_H = 1.0
MAG_POCKET_D = 3.10  # test: coupon checks 2.95 to 3.25; magnets are glued
MAG_POCKET_DEPTH = 1.0  # equal to MAG_H: a seated magnet is flush with the carrier's rear face
R_TRACK = 28.0  # magnet centre radius
MAGNET_COUNTS = (24, 32)
CARRIER_ID = 50.9  # 0.65 radial clearance to the bezel tube; leaves a 1.0 wall inside the magnet pockets
CARRIER_FIT_CLEARANCE = 0.2  # diametral MJF clearance between the carrier body and the smaller ring bore
CARRIER_OD = min(RING_A_BORE_D, RING_B_BORE_D) - CARRIER_FIT_CLEARANCE  # fits both rings; glued
CARRIER_FRONT_DEPTH = BRG_FRONT_DEPTH + BRG_W + 0.2  # 7.5: 0.2 behind the bearing; leaves a 1.0 floor in front of the pockets
CARRIER_FLANGE_T = 1.0
CARRIER_REAR_DEPTH = RING_REAR_DEPTH + CARRIER_FLANGE_T  # 9.5: the flange sits beside the pockets, behind the ring body
CARRIER_FLANGE_R_IN = 29.8  # 1.1 overlap with the body, 0.25 clear of the pocket mouths
POLARITY_BUMP_D = 1.0  # raised bump on the carrier's rear face beside every other pocket
POLARITY_BUMP_H = 0.3
POLARITY_BUMP_R = 31.75

# Ring sensor (TMAG5273) position on the main PCB: under the magnet track at 9 o'clock, mounted
# on the PCB's back side so the board's flat front can sit just behind the magnet carrier. The
# field passes through the 1.0 mm FR4 unchanged.
SENSOR_ANGLE_DEG = 180.0
PCB_T = 1.0  # main board thickness (4-layer)
HALL_ELEMENT_H = 0.70  # Hall element height above its seating plane, TMAG5273 figure 6-2 (estimate)
# Product gap (provisional until the Task 9 measurements): 2.7 mm, so the board front sits 1.0 mm
# behind the carrier's rear face, where the magnets are flush and the flange sits beside them (the
# product carrier has no polarity bumps). Nothing that turns stands behind the magnet faces, and the
# 1.0 mm covers the 0.5 mm clearance Task 9 may ask for. Every 0.1 mm of gap adds 0.1 mm of depth;
# pressing the ring cannot push it back towards the board: its front lip rests on the bearing or
# sleeve front face (the carrier lets it move 0.2 mm forward only).
HALL_GAP_NOMINAL = 2.7  # test: magnet face to Hall element; the board front then sits 1.0 mm behind the carrier
HALL_GAP_STEPS = (4.7, 3.7, 2.7, 1.7)  # gaps the jig gives with spacers of 0, 1, 2 and 3 mm; the 2 mm spacer gives the product gap


def magnet_face_depth() -> float:
    """Depth of the magnets' rear faces. A magnet rests on the pocket floor, so its rear face sits
    MAG_POCKET_DEPTH - MAG_H (0 today) in front of the carrier's rear face."""
    return CARRIER_REAR_DEPTH - (MAG_POCKET_DEPTH - MAG_H)


def pcb_front_depth(hall_gap: float = HALL_GAP_NOMINAL) -> float:
    """Depth of the main PCB's front surface for a given magnet-to-Hall-element gap, with the
    TMAG5273 on the back side (the element sits HALL_ELEMENT_H behind the back surface)."""
    return magnet_face_depth() + hall_gap - HALL_ELEMENT_H - PCB_T


# Display adapter FPC: VIEWE's standard adapter from the panel's 31-pin connector to J301 (VIEWE
# drawings and reply of 13 October 2026). The panel connector's reference point on VIEWE's
# connector-position drawing (a back view) is its centre, 13.04 right of the display centre on the
# drawing (a back view, so towards 9 o clock seen from the front) and 4.22 above it; panel pin 1 is
# at the band's bottom edge. The adapter leaves the connector towards 9 o clock
# and reaches J301 with one U-turn and an S-bend (enclosure/tests/test_pcb_contract.py).
PANEL_CONN_X = -13.04
PANEL_CONN_Y = 4.22
PANEL_CONN_H = 1.0  # connector height
PANEL_CONN_FACE = 1.60  # front face beyond the centre, +-0.15: measured on VIEWE's STEP model of the connector (reply of 17 October 2026)
ADAPTER_L = 24.148  # +-0.5 (VIEWE's reply of 14 October 2026), from the panel connector's front face to the end of the fingers
ADAPTER_W = 9.60  # +-0.1 (Hirose asks +-0.05 for J301's FH26W: measure a few)
ADAPTER_T = 0.20  # +-0.03
ADAPTER_STIFFENER_L = 5.00  # PI stiffener at each end, positioning line 2.50 from the finger ends
ADAPTER_INSERT = 2.50  # into each connector, up to the positioning line
ADAPTER_BEND_R = 2.0  # 10 times the thickness
ADAPTER_PANEL_DEPTH = 2.8  # +-0.2, flex mid-plane at the panel connector: stack 2.07, stiffener, slot 0.5 above the connector base
J301_FPC_DEPTH = pcb_front_depth() - 0.5  # flex mid-plane at J301: FPC plane 0.4 above the board (Hirose EDC3-323714-05) plus half the flex


# SparkFun Linear 3D Hall-Effect Sensor TMAG5273 (Qwiic), SEN-23880, 1 x 1 inch board.
# Source: github.com/sparkfun/SparkFun_Qwiic_Hall_Effect_Sensor_TMAG5273, Hardware/1x1/
# Qwiic_Hall_Effect_Sensor_TMAG5273.brd (Eagle) and Production/ordering_instructions.txt.
# Board frame: u to the right, v up, origin at the lower left corner, top side (parts) up.
SF_BOARD = 25.4  # outline 0 to 25.4 in both axes
SF_BOARD_T = 1.6  # "PCB thickness, 1.6mm" in ordering_instructions.txt
SF_U1 = (12.8778, 13.0302)  # TMAG5273 (SOT23-6) centre
SF_HOLE_D = 3.302  # four stand-off holes
SF_HOLE_INSET = 2.54  # hole centres 2.54 from each edge
SF_J1 = (5.08, 12.7)  # Qwiic connector, opening faces -u (board edge), rotated R270
SF_J2 = (20.32, 12.7)  # Qwiic connector, opening faces +u (board edge), rotated R90
SF_CONN_W = 6.0  # connector body width along the edge (footprint silkscreen +-3.0)
SF_CONN_L = 4.6  # body length from the pad row towards the board edge (footprint silkscreen)
SF_CONN_H = 4.25  # height above the board: JST SH side entry, not in the board files (estimate, generous)
SF_CABLE_SLOT_W = 8.0  # cable slot width through the jig, centred on the connector row

# Sensor jig (test fixture).
JIG_D = 92.0
JIG_FRONT_DEPTH = TUBE_END_DEPTH + LUG_T  # 11.6
JIG_T = 6.2
JIG_POCKET_CLEAR = 0.4
JIG_CENTRE_HOLE_D = 27.8  # leaves a 1.0 wall to the sensor pocket at 9 o clock
SPACER_T = (1.0, 2.0, 3.0)
TICK_R_IN = 36.0
TICK_R_OUT = 39.0
TICK_R_OUT_LONG = 40.5
TICK_W = 0.6
TICK_DEPTH = 0.4
TICK_SKIP_DEG = 32.0  # no ticks within this angle of the sensor pocket and cable slot
TICK_SKIP_TOP_DEG = 12.0  # no ticks across the antenna marker at 90 degrees

# Module antenna region used for the RSSI check. ESP32-S3-WROOM-1 is 18 x 25.5 mm; its PCB
# antenna is the top 6.5 mm. The module top edge sits 0.3 mm inside the 1.6 mm head top wall.
OWL_TOP_Y = 45.0
OWL_BOTTOM_Y = -39.0
MODULE_W = 18.0
MODULE_L = 25.5
ANTENNA_L = 6.5
ANT_Y_TOP = OWL_TOP_Y - 1.9  # 43.1
ANT_Y_BOTTOM = ANT_Y_TOP - ANTENNA_L  # 36.6
ANT_TAB_W = 32.0
ANT_TAB_TOP = 50.0
MODULE_SIDE = "back"  # the WROOM-1 sits on the PCB back side; its antenna overhangs the top edge

# Dock contacts on the owl's back cover (dock-pad board) and the perch's pogo pins. Owl
# coordinates; nets from left to right as seen from the front, x = -4.5, 0, +4.5.
DOCK_PAD_PITCH = 4.5
DOCK_PAD_Y = -31.0
DOCK_PAD_ORDER = ("PAD_DET", "PAD_GND", "PAD_VBUS")
# The dock-pad board (the perch board's snap-off section, with J2 beyond PAD_VBUS) is keyed: a notch with
# a round end in its DET end, centred across the board, takes a tongue standing in the back cover's
# recess, so the board seats only with J2 towards J303. Turned round, the VBUS pad would meet the perch's
# DET pin and put the perch's 5 V on GPIO1.
DOCK_PAD_BOARD = (28.0, 8.0, 1.6)
DOCK_KEY_R = 1.5  # half the notch width, and the radius of its end
DOCK_KEY_DEPTH = 2.5  # from the board's DET end to the bottom of the notch
DOCK_KEY_CLEAR = 0.2  # per side between the tongue and the notch, as between the board and its recess

# LRA: Leader LD0832AA-0099F specification REV.00 (LCSC C2682305), page 13: body 8 +-0.1 x 3.25 +-0.1
# (plus 0.3 foam on top and 0.15 tape under it), leads 27 +-2 long. At the mounting face the lead tab
# reaches 5.75 +-0.1 from the motor centre; it and its UV glue are up to 3.5 wide and 2.5 high. The
# back cover's LRA cup (owl_v1 LRA_*) has a slot through its wall for the tab. The slot points
# along the leads' way to J302's plug (J302 opens to -x at x 21.4, y -20, so the plug's rear is near
# x 19.4) as far as the dock magnet boss at (20, -22) allows: at 185 degrees the tab and its glue stay
# 1.0 from that boss and 1.6 from the board-mount boss at (19, -9); pointed at the plug (220 degrees)
# or at J302 (250) the tab would sit on the magnet boss.
LRA_D = 8.0
LRA_T = 3.25
LRA_TAB_R = 5.75 + 0.1
LRA_TAB_W = 3.5
LRA_TAB_H = 2.5
LRA_SLOT_W = 4.0  # tab width plus 0.25 per side
LRA_SLOT_ANGLE_DEG = 185.0  # slot centre line from the motor centre, counter-clockwise from +X (owl coordinates)

# J303 cable relief: the dock link's JST SH 4-pin plug (SHR-04V-S-B, 7.0 wide with its protrusions,
# 5.0 without, 2.8 high: JST SH catalogue eSH) mates side-on in J303 with its rear close to the body's
# bottom wall, which leaves the wires little room to turn. Behind J303 the wall's inner face is set
# back until J303_RELIEF_WALL is left (0.6 deeper in the 1.6 wall), centred on J303's x, as wide as the
# plug plus 1.0 and from the board's back face J303_RELIEF_H down (J303 is 2.95 high). The relief
# depends on J303's x only: its y may move along the board.
J303_RELIEF_W = 7.0 + 1.0
J303_RELIEF_H = 4.0
J303_RELIEF_WALL = MJF_STRUCT_WALL  # the owl stands on this wall on the perch seat

# USB-C opening in the body's bottom wall for J201 (HRO TYPE-C-31-M-12, LCSC C165948 drawing: 7.35 long,
# 3.26 high, plug axis 1.63 behind the board's back face). The receptacle's mouth is 0.075 outside the wall's
# inner face, so a plug overmold that stopped on the wall's outer face would leave the plug about 1 mm short
# of full mating. The wall is cut through to the Type-C specification's largest plug overmold with the
# perch's clearance (R48), so a plug's overmold can come to within USB_MATE_GAP of the mouth.
USB_PLUG_CENTRE_H = 1.63
USB_OVERMOLD = (12.35, 6.5)  # width by height
USB_OPENING = (13.0, 7.0)  # width by height, centred on the plug axis
USB_MATE_GAP = 0.3

# Owner mark, debossed into the owl back cover's outer face and the perch's underside. MJF PA12 detail
# limits (JLC3DP): 0.5 mm deep, strokes and the gaps between them at least 0.6 mm, cap height at least
# 4 mm. Font: Inter Bold 4.0 from the fonts-inter package (SIL Open Font Licence); its capitals are 1490
# of its 2048 units per em high. At a 5 mm cap height Inter Bold has 0.33 mm notches where the arches of
# n and u meet their stems, which MARK_ROUND fills (the arches are then 0.64 mm at their thinnest), and
# T, y and u stand 0.53 mm apart as set, so MARK_TRACK spreads the letters.
MARK_TEXT = "Tyukov Inc"
MARK_FONT = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"
MARK_FONT_CAP = 1490 / 2048
MARK_CAP_H = 5.0
MARK_DEPTH = 0.5
MARK_MIN_DETAIL = 0.6
MARK_ROUND = MARK_MIN_DETAIL / 2  # every glyph is closed by this radius: inside corners rounded, notches under 0.6 filled
MARK_TRACK = 0.15  # extra space between neighbouring letters


# Owl v0: the low-cost owl around the Waveshare ESP32-S3-Touch-AMOLED-1.75 kit (SKU 31261,
# enclosure/owl_kit.py). From Waveshare's dimension drawing and labelled photos
# (docs.waveshare.com/ESP32-S3-Touch-AMOLED-1.75, fetched 20 October 2026); values marked "est."
# are read off the photos (about 0.3 mm) and carry margin. Owl coordinates as above, with the kit's
# glass front at z = 0. Seen from the front with the screen upright: the USB-C port is on the left
# edge, PWR, BOOT and the TF slot on the right edge, the 8-pin header at the bottom and the battery
# and speaker sockets at the top, all on the board's back.
KIT_GLASS_D = 48.96  # cover glass outline
KIT_GLASS_D_TOL = 0.15  # assumed: the drawing gives no tolerance
KIT_STACK_T = 2.05  # cover glass and panel
KIT_BODY_R = 23.3  # est.: panel frame and the 46.0 mm board behind the glass, with margin
KIT_PCB_BACK_DEPTH = 6.90  # glass front to the board's back face
KIT_PCB_T = 1.2  # est.
KIT_STANDOFF_DEPTH = 10.40  # ends of the three M2 threaded standoffs ("M2.00-H3.5")
KIT_STANDOFFS = ((0.0, 20.5), (-13.75, -14.7), (13.75, -14.7))
KIT_STANDOFF_OD = 3.5  # est.
KIT_USB_MOUTH_X = -23.8  # Type-C receptacle mouth ("23.80"), centred on y = 0, on the board's back
KIT_USB = (7.35, 8.94, 3.26)  # receptacle length (into the board), width (y) and height (z)
KIT_HEADER_Y = -18.7  # 8-pin 2.54 mm female header, centred on x = 0
KIT_HEADER = (21.0, 2.6, 6.2)  # est.: body x, y and height above the board's back (the photo gives 5.9)
KIT_SOCKETS_X = ((-8.7, -2.9), (3.5, 9.3))  # est.: BAT and SPK MX1.25 sockets
KIT_SOCKETS_Y = (12.8, 18.0)  # est.
KIT_SOCKET_H = 5.2  # est.: socket height above the board's back
KIT_BACK_PARTS_H = 1.7  # est.: every other part on the board's back
KIT_SIDE_BUTTONS_DEG = (30.0, -33.0)  # est.: PWR and BOOT, pressed outwards at the right edge

# TMAG5273 module (AliExpress, MJKDZ "3D Hall Sensor", 15 x 20 mm, 1.6 mm FR4): the sensor sits
# 2.4 mm below one short edge, centred across the board; a 2.7 mm hole 9.5 mm from the sensor;
# five pads (GND, INT, SCL, SDA, VCC) 0.9 mm from the other short edge. Parts up to 1.25 mm tall
# on the sensor side. Measured on the seller's dimensioned photo (20 October 2026).
TMAG_MODULE = (20.0, 15.0, 1.6)  # length (sensor end to pad end), width, thickness
TMAG_SENSOR_INSET = 2.4  # sensor centre from the sensor end
TMAG_HOLE_FROM_SENSOR = 9.5
TMAG_HOLE_D = 2.7
TMAG_PARTS_H = 1.25

# Tact switch 3 x 6 x 2.5 mm, two SMD legs: body 6.0 x 3.0 (legs to 7.6 long), 2.5 tall with the
# plunger, which is 1.5 x 1.2 at the centre and travels 0.25 mm.
SWITCH_3X6 = (6.0, 3.0, 2.5)
SWITCH_3X6_LEGS = 7.6
SWITCH_3X6_TRAVEL = 0.25

# LiPo 602040: 6 x 20 x 40 mm; the protection board end makes it up to 43 mm long.
KIT_BATTERY = (43.0, 20.5, 6.0)  # x, y, z with the protection board end
