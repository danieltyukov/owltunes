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

# Display: VIEWE ALL-UEOL018WV-RA31-A001A specification V1.0 (2024-09-04), pages 4 and 6.
GLASS_D = 48.16  # cover glass diameter ("C.G 48.16")
GLASS_T = 1.10  # cover glass thickness ("C.G 1.1")
DISPLAY_STACK_T = 2.07  # glass, OCA, panel and foam ("Total 2.07")
VIEW_D = 44.16  # viewing area ("V.A 44.16")
PANEL_W = 45.93  # panel outline width
PANEL_H = 46.35  # panel outline height including the flex bonding ledge
FLEX_PARTS_H = 1.2  # component area on the folded main flex ("H=1.2mm")

# Bearing 6710ZZ: 50 x 62 x 6 thin-section deep-groove ball bearing.
BRG_ID = 50.0
BRG_OD = 62.0
BRG_W = 6.0
BRG_INNER_RACE_OD = 53.6  # estimate of the inner race shoulder; the bezel lip stays inside it
BRG_OUTER_RACE_ID = 58.4  # estimate of the outer race shoulder; the ring contacts outside it

# Face bezel (stationary): holds the glass and carries the bearing inner race.
LIP_T = 1.3  # front lips of bezel and ring stand this far in front of the glass (ring lip is LIP_T - LIP_RELIEF = 1.0 thick)
BEZEL_LIP_ID = 48.30  # front opening: the glass is inserted from the front, so it must pass here
BEZEL_LIP_OD = 52.0  # contacts only the inner race front face (inside 53.6)
GLASS_POCKET_D = 48.30  # glass seat, 0.07 radial clearance; drops in from the front, glue it; wall to the 49.9 seat is 0.8
GLASS_POCKET_DEPTH = 1.3  # glass rests on the ledge, 0.2 below the rim plane (glue layer)
PANEL_POCKET_D = 47.2  # clears the 46.35 panel behind the glass; the ring left over is the glass ledge
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
RING_LIP_ID = 52.8  # 0.4 radial gap to the bezel lip
RING_CONTACT_R = 30.0  # the ring touches the outer race only outside this radius
LIP_RELIEF = 0.3  # gap between the ring lip and the inner race or shields
RING_A_BORE_D = 62.10  # test: bearing variant, 0.10 clearance, bearing glued
RING_B_BORE_D = 62.00  # test: bushing variant, 0.10 radial clearance on the sleeve
RING_REAR_DEPTH = 9.2  # ring body ends here; leaves a 1.0 floor under the magnet pockets
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

# Magnets: D3 x 2 mm N52 discs, axially magnetised, alternating polarity.
MAG_D = 3.0
MAG_H = 2.0
MAG_POCKET_D = 3.10  # test: coupon checks 2.95 to 3.25; magnets are glued
MAG_POCKET_DEPTH = 2.00  # equal to MAG_H: a seated magnet is flush with the carrier's rear face
R_TRACK = 28.0  # magnet centre radius
MAGNET_COUNTS = (24, 32)
CARRIER_ID = 50.9  # 0.65 radial clearance to the bezel tube; leaves a 1.0 wall inside the magnet pockets
CARRIER_FIT_CLEARANCE = 0.2  # diametral MJF clearance between the carrier body and the smaller ring bore
CARRIER_OD = min(RING_A_BORE_D, RING_B_BORE_D) - CARRIER_FIT_CLEARANCE  # fits both rings; glued
CARRIER_FRONT_DEPTH = 6.2  # 0.2 behind the bearing rear face; leaves a 1.0 floor in front of the pockets
CARRIER_FLANGE_T = 1.0
CARRIER_FLANGE_R_IN = 29.8  # 1.1 overlap with the body, 0.25 clear of the pocket mouths
POLARITY_BUMP_D = 1.0  # raised bump on the flange behind every other pocket
POLARITY_BUMP_H = 0.3
POLARITY_BUMP_R = 31.75

# Ring sensor (TMAG5273) position on the main PCB: under the magnet track at 9 o'clock, mounted
# on the PCB's back side so the board's flat front can sit just behind the magnet carrier. The
# field passes through the 1.0 mm FR4 unchanged.
SENSOR_ANGLE_DEG = 180.0
PCB_T = 1.0  # main board thickness (4-layer)
HALL_ELEMENT_H = 0.70  # Hall element height above its seating plane, TMAG5273 figure 6-2 (estimate)
# Product gap (Task 7, provisional until the Task 9 measurements): 3.0 mm, so the board front sits
# 0.3 mm behind the rotating carrier flange (the product carrier has no polarity bumps). Kept at
# 3.0 rather than 3.2 (0.5 mm) because enclosure v1 is already 23.5 mm deep, every 0.1 mm of gap
# adds 0.1 mm of depth, and pressing the ring cannot push it back towards the board: its front lip
# rests on the bearing or sleeve front face (the carrier lets it move 0.2 mm forward only). Task 9
# measures the real flange-to-board clearance on the prints and may move this to 3.2 (23.7 mm deep).
HALL_GAP_NOMINAL = 3.0  # test: magnet face to Hall element; the board front then sits 0.3 mm behind the flange
HALL_GAP_STEPS = (4.5, 3.5, 2.5, 1.5)  # gaps the jig gives with spacers of 0, 1, 2 and 3 mm


def magnet_face_depth() -> float:
    """Depth of the magnets' rear faces. A magnet rests on the pocket floor, so its rear face sits
    MAG_POCKET_DEPTH - MAG_H (0.1) in front of the carrier's rear face."""
    return RING_REAR_DEPTH - (MAG_POCKET_DEPTH - MAG_H)


def pcb_front_depth(hall_gap: float = HALL_GAP_NOMINAL) -> float:
    """Depth of the main PCB's front surface for a given magnet-to-Hall-element gap, with the
    TMAG5273 on the back side (the element sits HALL_ELEMENT_H behind the back surface)."""
    return magnet_face_depth() + hall_gap - HALL_ELEMENT_H - PCB_T


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
JIG_CENTRE_HOLE_D = 28.0
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
