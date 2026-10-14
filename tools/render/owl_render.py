"""Product renders of the owl and the perch, built from the real enclosure and board files.

Run through tools/render.sh, which exports the meshes first. Blender runs this file headless:

    blender -b --factory-startup -P tools/render/owl_render.py -- SCENE OUT.jpg [--samples N] [--size WxH]

SCENE is one of: hero, desk, pocket, exploded. Meshes come from build/render/ (enclosure/render_export.py
and the KiCad GLB export), the screen image from docs/img/now_playing.png (the simulator's golden
screenshot). Units are metres; the meshes are in millimetres and are scaled on import. Everything
else in a scene (desk, denim, props) is built here. Licence: MIT (LICENSE).
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[2]
MESHES = ROOT / "build" / "render"
SCREEN = ROOT / "docs" / "img" / "now_playing.png"
MM = 0.001
VIEW_D = 44.16  # display viewing area, owl_params.VIEW_D
OWL_BACK_Z = -22.2  # back face of the back cover, owl_v1.BACK_Z
OWL_PARTS = ("back_cover", "body", "ring", "bezel", "glass_retainer", "beak_key", "ear_key_left", "ear_key_right")


# ---------------------------------------------------------------------------------------------
# Scene, lights and camera


def reset(size: tuple[int, int], samples: int) -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 8
    scene.render.resolution_x, scene.render.resolution_y = size
    scene.render.resolution_percentage = 100
    try:
        scene.view_settings.view_transform = "AgX"
        scene.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    scene.render.image_settings.file_format = "JPEG"
    scene.render.image_settings.quality = 90
    scene.world = bpy.data.worlds.new("world")


def world_color(rgb: tuple[float, float, float], strength: float) -> None:
    tree = bpy.context.scene.world.node_tree
    bg = next(n for n in tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (*rgb, 1.0)
    bg.inputs["Strength"].default_value = strength


def aim(obj: bpy.types.Object, target) -> None:
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def area_light(name: str, loc, target, size: float, power: float, rgb=(1.0, 1.0, 1.0), spread: float = 180.0) -> None:
    """A softbox; `spread` below 180 degrees narrows its beam like a grid on the box."""
    data = bpy.data.lights.new(name, "AREA")
    data.shape = "RECTANGLE"
    data.size = data.size_y = size
    data.energy = power
    data.color = rgb
    data.spread = math.radians(spread)
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = loc
    aim(obj, target)


def camera(loc, target, lens: float, fstop: float | None = None, focus=None) -> None:
    data = bpy.data.cameras.new("camera")
    data.lens = lens
    data.sensor_width = 36.0
    data.clip_start = 0.005
    obj = bpy.data.objects.new("camera", data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = loc
    aim(obj, target)
    if fstop is not None:
        data.dof.use_dof = True
        data.dof.aperture_fstop = fstop
        data.dof.focus_distance = (Vector(focus or target) - Vector(loc)).length
    bpy.context.scene.camera = obj


# ---------------------------------------------------------------------------------------------
# Materials


def material(name: str):
    mat = bpy.data.materials.new(name)
    if mat.node_tree is None:
        mat.use_nodes = True
    tree = mat.node_tree
    bsdf = next(n for n in tree.nodes if n.type == "BSDF_PRINCIPLED")
    return mat, tree, bsdf


def simple(name: str, rgb, rough: float, metal: float = 0.0, coat: float = 0.0, spec: float = 0.5) -> bpy.types.Material:
    mat, _, bsdf = material(name)
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    bsdf.inputs["Coat Weight"].default_value = coat
    bsdf.inputs["Specular IOR Level"].default_value = spec
    return mat


def mjf_black(name: str, rough: float = 0.42, tone: float = 0.006) -> bpy.types.Material:
    """Dyed MJF PA12: near black, satin, with the fine grain of the powder bed."""
    mat, tree, bsdf = material(name)
    bsdf.inputs["Base Color"].default_value = (tone, tone, tone * 1.08, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Specular IOR Level"].default_value = 0.45
    noise = tree.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 9000.0
    noise.inputs["Detail"].default_value = 2.0
    bump = tree.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.08
    bump.inputs["Distance"].default_value = 0.00002
    tree.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    tree.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def cover_glass() -> bpy.types.Material:
    mat, _, bsdf = material("cover_glass")
    bsdf.inputs["Roughness"].default_value = 0.0
    bsdf.inputs["Transmission Weight"].default_value = 1.0
    bsdf.inputs["IOR"].default_value = 1.52
    return mat


def screen(strength: float) -> bpy.types.Material:
    """The AMOLED: the simulator's frame as emission over a glossy black panel."""
    mat, tree, bsdf = material("screen")
    tex = tree.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(str(SCREEN))
    tex.interpolation = "Cubic"
    bsdf.inputs["Base Color"].default_value = (0.0, 0.0, 0.0, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.08
    bsdf.inputs["Emission Strength"].default_value = strength
    tree.links.new(tex.outputs["Color"], bsdf.inputs["Emission Color"])
    return mat


def oak() -> bpy.types.Material:
    """Light oak desk top: fine grain lines along X from distorted waves, with noise for figure."""
    mat, tree, bsdf = material("oak")
    n, links = tree.nodes, tree.links
    coord = n.new("ShaderNodeTexCoord")
    mapping = n.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (4.0, 90.0, 4.0)
    wave = n.new("ShaderNodeTexWave")
    wave.bands_direction = "Y"
    wave.inputs["Scale"].default_value = 1.0
    wave.inputs["Distortion"].default_value = 5.0
    wave.inputs["Detail"].default_value = 4.0
    noise = n.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 2.5
    noise.inputs["Detail"].default_value = 10.0
    mix = n.new("ShaderNodeMix")
    mix.data_type = "FLOAT"
    mix.inputs["Factor"].default_value = 0.4
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.26, 0.15, 0.07, 1.0)
    ramp.color_ramp.elements[1].color = (0.50, 0.33, 0.18, 1.0)
    links.new(coord.outputs["Object"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], wave.inputs["Vector"])
    links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
    links.new(wave.outputs["Fac"], mix.inputs["A"])
    links.new(noise.outputs["Fac"], mix.inputs["B"])
    links.new(mix.outputs["Result"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.38
    bsdf.inputs["Coat Weight"].default_value = 0.2
    bsdf.inputs["Coat Roughness"].default_value = 0.2
    return mat


def denim(name: str, stitch: bool = False) -> bpy.types.Material:
    """Indigo twill: diagonal bands for the weave and slub noise; with stitch=True a double row of
    gold topstitching along the left, right and bottom of the UV square."""
    mat, tree, bsdf = material(name)
    n, links = tree.nodes, tree.links
    coord = n.new("ShaderNodeTexCoord")
    mapping = n.new("ShaderNodeMapping")
    mapping.inputs["Rotation"].default_value = (0.0, 0.0, math.radians(63))
    twill = n.new("ShaderNodeTexWave")
    twill.inputs["Scale"].default_value = 420.0
    twill.inputs["Distortion"].default_value = 0.6
    twill.inputs["Detail"].default_value = 1.0
    slub = n.new("ShaderNodeTexNoise")
    slub.inputs["Scale"].default_value = 60.0
    slub.inputs["Detail"].default_value = 6.0
    fade = n.new("ShaderNodeTexNoise")
    fade.inputs["Scale"].default_value = 6.0
    weave = n.new("ShaderNodeMath")
    weave.operation = "MULTIPLY"
    tone = n.new("ShaderNodeMix")
    tone.data_type = "FLOAT"
    tone.inputs["Factor"].default_value = 0.35
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.012, 0.022, 0.055, 1.0)
    ramp.color_ramp.elements[1].color = (0.16, 0.22, 0.34, 1.0)
    bump = n.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.4
    bump.inputs["Distance"].default_value = 0.0002
    links.new(coord.outputs["Object"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], twill.inputs["Vector"])
    links.new(coord.outputs["Object"], slub.inputs["Vector"])
    links.new(coord.outputs["Object"], fade.inputs["Vector"])
    links.new(twill.outputs["Fac"], weave.inputs[0])
    links.new(slub.outputs["Fac"], weave.inputs[1])
    links.new(weave.outputs["Value"], tone.inputs["A"])
    links.new(fade.outputs["Fac"], tone.inputs["B"])
    links.new(tone.outputs["Result"], ramp.inputs["Fac"])
    links.new(twill.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    bsdf.inputs["Roughness"].default_value = 0.92
    bsdf.inputs["Sheen Weight"].default_value = 0.4
    color = topstitch(tree, ramp.outputs["Color"]) if stitch else ramp.outputs["Color"]
    links.new(color, bsdf.inputs["Base Color"])
    return mat


def topstitch(tree, base):
    """Gold thread over `base` near the UV square's left, right and bottom edges, dashed."""
    n, links = tree.nodes, tree.links
    uv = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    links.new(uv.outputs["UV"], sep.inputs["Vector"])

    def op(kind: str, a, b=None, value: float | None = None):
        m = n.new("ShaderNodeMath")
        m.operation = kind
        links.new(a, m.inputs[0])
        if b is not None:
            links.new(b, m.inputs[1])
        if value is not None:
            m.inputs[1].default_value = value
        return m.outputs[0]

    def band(axis, centre: float, half: float):
        return op("LESS_THAN", op("ABSOLUTE", op("SUBTRACT", axis, value=centre)), value=half)

    def dashes(axis, count: float):
        return op("LESS_THAN", op("FRACT", op("MULTIPLY", axis, value=count)), value=0.68)

    x, y = sep.outputs["X"], sep.outputs["Y"]
    mask = None
    for c in (0.035, 0.06, 0.94, 0.965):
        row = op("MULTIPLY", band(x, c, 0.0035), dashes(y, 70))
        mask = row if mask is None else op("MAXIMUM", mask, row)
    for c in (0.05, 0.08, 0.90):
        mask = op("MAXIMUM", mask, op("MULTIPLY", band(y, c, 0.0045), dashes(x, 90)))
    mix = n.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["B"].default_value = (0.62, 0.36, 0.09, 1.0)
    links.new(mask, mix.inputs["Factor"])
    links.new(base, mix.inputs["A"])
    return mix.outputs["Result"]


# ---------------------------------------------------------------------------------------------
# Geometry


def smooth(obj: bpy.types.Object, angle_deg: float = 30.0) -> None:
    with bpy.context.temp_override(object=obj, active_object=obj, selected_objects=[obj], selected_editable_objects=[obj]):
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(angle_deg))


def import_stl(path: Path, mat: bpy.types.Material, smooth_deg: float = 30.0) -> bpy.types.Object:
    bpy.ops.wm.stl_import(filepath=str(path), global_scale=MM)
    obj = bpy.context.selected_objects[0]
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    smooth(obj, smooth_deg)
    return obj


def owl(matrix: Matrix = Matrix.Identity(4), screen_strength: float = 2.4) -> dict[str, bpy.types.Object]:
    """The assembled owl in owl coordinates, then placed by `matrix` (world metres)."""
    shell = mjf_black("mjf_black")
    keys = mjf_black("mjf_black_keys", rough=0.36, tone=0.01)
    mats = {"ring": mjf_black("mjf_black_ring", rough=0.32, tone=0.009), "beak_key": keys,
            "ear_key_left": keys, "ear_key_right": keys}
    objs = {name: import_stl(MESHES / f"{name}.stl", mats.get(name, shell)) for name in OWL_PARTS}
    objs["glass"] = import_stl(MESHES / "glass.stl", cover_glass(), 45)
    z_back = min((objs["glass"].matrix_world @ Vector(c)).z for c in objs["glass"].bound_box)
    objs["screen"] = disc("screen", VIEW_D / 2 * MM, z_back - 0.03 * MM, screen(screen_strength))
    for obj in objs.values():
        obj.matrix_world = matrix @ obj.matrix_world
    return objs


def disc(name: str, r: float, z: float, mat: bpy.types.Material) -> bpy.types.Object:
    """A filled circle at height z whose UV square spans its diameter (for the round screen)."""
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, cap_ends=True, segments=128, radius=r)
    uv = bm.loops.layers.uv.new()
    for face in bm.faces:
        for loop in face.loops:
            loop[uv].uv = (loop.vert.co.x / (2 * r) + 0.5, loop.vert.co.y / (2 * r) + 0.5)
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.location.z = z
    return obj


def perch() -> Matrix:
    """Import the perch body; return the owl's docked placement in world metres."""
    info = json.loads((MESHES / "perch.json").read_text())
    import_stl(MESHES / info["perch"], mjf_black("mjf_black_perch", rough=0.6, tone=0.007))
    m = Matrix(info["owl_docked"])
    m.translation *= MM
    return m


def board() -> list[bpy.types.Object]:
    """Top-level objects of the main board from KiCad's GLB export, moved to the board's owl Z."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(MESHES / "pcb.glb"))
    roots = [o for o in bpy.data.objects if o not in before and o.parent is None]
    z = json.loads((MESHES / "perch.json").read_text())["pcb_back_z"] * MM
    for obj in roots:
        obj.location.z += z
    return roots


def cyclorama(mat: bpy.types.Material, back_y: float, radius: float, width: float = 3.0, height: float = 1.5) -> None:
    """A photo sweep: a floor that curves up into the back wall, so there is no horizon line."""
    profile = [(-2.0, 0.0), (back_y - radius, 0.0)]
    for i in range(1, 17):
        a = math.radians(90 * i / 16)
        profile.append((back_y - radius + radius * math.sin(a), radius - radius * math.cos(a)))
    profile.append((back_y, height))
    mesh = bpy.data.meshes.new("sweep")
    bm = bmesh.new()
    rows = [[bm.verts.new((x, y, z)) for y, z in profile] for x in (-width / 2, width / 2)]
    for i in range(len(profile) - 1):
        bm.faces.new((rows[0][i], rows[1][i], rows[1][i + 1], rows[0][i + 1]))
    bm.to_mesh(mesh)
    bm.free()
    for poly in mesh.polygons:
        poly.use_smooth = True
    mesh.materials.append(mat)
    bpy.context.scene.collection.objects.link(bpy.data.objects.new("sweep", mesh))


def plane(mat: bpy.types.Material, size: float, loc=(0, 0, 0), rot=(0, 0, 0)) -> bpy.types.Object:
    bpy.ops.mesh.primitive_plane_add(size=size, location=loc, rotation=rot)
    obj = bpy.context.active_object
    obj.data.materials.append(mat)
    return obj


def rounded_box(mat: bpy.types.Material, size, loc, rot_z: float = 0.0, bevel: float = 0.002) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc, rotation=(0, 0, rot_z))
    obj = bpy.context.active_object
    obj.scale = size
    bpy.ops.object.transform_apply(scale=True)
    mod = obj.modifiers.new("bevel", "BEVEL")
    mod.width = bevel
    mod.segments = 5
    obj.data.materials.append(mat)
    return obj


def mug(x: float, y: float) -> None:
    """An open ceramic mug with a handle and coffee in it."""
    ceramic = simple("ceramic", (0.80, 0.78, 0.74), 0.25, coat=0.5)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.041, depth=0.092, vertices=96, location=(x, y, 0.046))
    cup = bpy.context.active_object
    bm = bmesh.new()
    bm.from_mesh(cup.data)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.normal.z > 0.9], context="FACES")
    bm.to_mesh(cup.data)
    bm.free()
    cup.modifiers.new("shell", "SOLIDIFY").thickness = 0.004
    cup.data.materials.append(ceramic)
    smooth(cup, 40)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.022, minor_radius=0.0055, location=(x + 0.043, y, 0.05),
                                     rotation=(math.radians(90), 0, 0))
    handle = bpy.context.active_object
    handle.data.materials.append(ceramic)
    smooth(handle, 60)
    plane(simple("coffee", (0.05, 0.025, 0.012), 0.08), 0.077, (x, y, 0.076))


# ---------------------------------------------------------------------------------------------
# Scenes


def scene_hero() -> None:
    """Launch shot on a graphite sweep: the docked owl, near frontal, screen on, rim lit."""
    owl(perch())
    cyclorama(simple("graphite", (0.012, 0.012, 0.014), 0.95, spec=0.15), back_y=0.9, radius=0.35)
    world_color((0.002, 0.002, 0.0025), 1.0)
    area_light("key", (-0.45, -0.10, 0.30), (0, 0, 0.05), 0.25, 1.4, (1.0, 0.95, 0.9), spread=50)
    area_light("rim_l", (-0.30, 0.22, 0.16), (0, 0, 0.06), 0.18, 3.0, (0.75, 0.85, 1.0), spread=30)
    area_light("rim_r", (0.30, 0.22, 0.16), (0, 0, 0.06), 0.18, 3.0, (1.0, 0.85, 0.7), spread=30)
    area_light("top", (0, 0.05, 0.5), (0, 0, 0.04), 0.4, 0.2, spread=40)
    area_light("halo", (0, 0.45, 0.45), (0, 0.9, 0.12), 0.5, 0.15, (0.8, 0.85, 1.0), spread=60)
    camera((0.07, -0.56, 0.13), (0.0, 0.0, 0.052), 85, fstop=5.6)


def scene_desk() -> None:
    """Docked on a light oak desk by a window, a mug, a phone and a notebook out of focus."""
    owl(perch())
    plane(oak(), 3.0)
    plane(simple("wall", (0.62, 0.58, 0.52), 0.95), 3.0, (0, 0.45, 1.0), (math.radians(90), 0, 0))
    mug(0.20, 0.20)
    rounded_box(simple("phone", (0.012, 0.012, 0.014), 0.25, coat=0.8), (0.072, 0.152, 0.008), (-0.20, 0.06, 0.004),
                rot_z=math.radians(-18), bevel=0.008)
    rounded_box(simple("notebook", (0.46, 0.40, 0.31), 0.85), (0.15, 0.21, 0.012), (-0.24, 0.30, 0.006),
                rot_z=math.radians(12), bevel=0.001)
    world_color((0.95, 0.92, 0.88), 0.04)
    area_light("window", (-0.7, -0.15, 0.45), (0, 0.02, 0.05), 1.0, 26, (1.0, 0.88, 0.74))
    area_light("fill", (0.6, -0.5, 0.25), (0, 0, 0.05), 0.8, 5, (0.85, 0.9, 1.0))
    area_light("rim", (0.25, 0.35, 0.30), (0, 0, 0.06), 0.3, 6)
    camera((0.19, -0.47, 0.16), (0.025, 0.03, 0.045), 60, fstop=2.4, focus=(0.0, 0.0, 0.05))


def pocket_drape(w: float, h: float, top: float, lift: float, spin: float, mat: bpy.types.Material) -> bpy.types.Object:
    """A patch pocket of size w x h whose open top edge is at y = top, draped over the owl.

    Instead of a cloth simulation the drape is shaped directly: flat on the owl's face inside its
    outline, then a smooth fall to the denim over a band around it, with a few soft wrinkles on
    the slope. The owl's outline is its body (66 x 84 mm, 8 mm corners) turned by `spin`."""
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=240, y_subdivisions=140, size=1.0, location=(0, top - h / 2, 0))
    obj = bpy.context.active_object
    obj.scale = (w, h, 1.0)
    bpy.ops.object.transform_apply(location=True, scale=True)  # vertices in world coordinates
    half_w, half_h, corner, centre_y, fall = 0.033, 0.042, 0.008, 0.003, 0.016
    c, s_ = math.cos(-spin), math.sin(-spin)
    for v in obj.data.vertices:
        wx, wy = v.co.x, v.co.y
        ox, oy = c * wx - s_ * wy, s_ * wx + c * wy - centre_y  # into the owl's frame
        qx, qy = abs(ox) - (half_w - corner), abs(oy) - (half_h - corner)
        d = math.hypot(max(qx, 0.0), max(qy, 0.0)) + min(max(qx, qy), 0.0) - corner  # rounded box
        t = min(max(d / fall, 0.0), 1.0)
        z = lift * (1.0 - t * t * (3.0 - 2.0 * t))
        wrinkle = (math.sin(ox * 260.0 + oy * 90.0) + 0.6 * math.sin(oy * 410.0 - ox * 150.0)) * math.sin(math.pi * t) * 0.0006
        v.co.z = z + wrinkle + 0.0004
    obj.data.materials.append(mat)
    obj.modifiers.new("thickness", "SOLIDIFY").thickness = 0.0007
    sub = obj.modifiers.new("smooth", "SUBSURF")
    sub.levels = sub.render_levels = 1
    for poly in obj.data.polygons:
        poly.use_smooth = True
    return obj


def scene_pocket() -> None:
    """Flat lay on indigo denim, the owl half in a patch pocket stitched to the jeans."""
    spin = math.radians(-6)
    height = -OWL_BACK_Z * MM
    owl(Matrix.Rotation(spin, 4, "Z") @ Matrix.Translation((0, 0, height)), 2.6)
    plane(denim("denim"), 1.2)
    pocket_drape(0.15, 0.085, -0.016, height + 0.0023, spin, denim("denim_pocket", stitch=True))  # 1 mm over the ring lip
    world_color((0.9, 0.92, 1.0), 0.03)
    area_light("key", (-0.45, 0.10, 0.22), (0, -0.02, 0.01), 0.25, 5.5, (1.0, 0.93, 0.84))
    area_light("fill", (0.4, -0.35, 0.35), (0, 0, 0), 0.8, 1.2, (0.85, 0.9, 1.0))
    camera((0.07, -0.29, 0.24), (0.0, -0.025, 0.012), 60, fstop=4.0, focus=(0, -0.02, 0.02))


def scene_exploded() -> None:
    """Exploded along the owl's axis, every part in its place, on a light grey sweep."""
    objs = owl(screen_strength=2.0)
    objs["battery"] = import_stl(MESHES / "battery.stl", simple("pouch", (0.62, 0.63, 0.66), 0.32, metal=0.7))
    pcb = board()
    lift = {"back_cover": -0.066, "battery": -0.046, "ring": 0.022, "bezel": 0.040, "screen": 0.056,
            "glass": 0.068, "glass_retainer": 0.080, "beak_key": 0.022, "ear_key_left": 0.022, "ear_key_right": 0.022}
    for name, obj in objs.items():
        obj.location.z += lift.get(name, 0.0)
    for obj in pcb:
        obj.location.z -= 0.024
    bpy.context.view_layer.update()
    # Face towards the camera's left and a little up, so the stack fans out across the frame.
    tilt = (Matrix.Translation((0.0, 0.0, 0.085)) @ Matrix.Rotation(math.radians(-62), 4, "Z")
            @ Matrix.Rotation(math.radians(78), 4, "X"))
    for obj in list(objs.values()) + pcb:
        obj.matrix_world = tilt @ obj.matrix_world
    cyclorama(simple("paper", (0.80, 0.80, 0.81), 0.85), back_y=0.4, radius=0.3)
    world_color((0.9, 0.9, 0.92), 0.25)
    area_light("key", (-0.45, -0.45, 0.55), (0, 0, 0.085), 0.9, 30)
    area_light("rim", (0.45, 0.25, 0.35), (0, 0, 0.085), 0.4, 14, (0.9, 0.95, 1.0))
    area_light("fill", (0.5, -0.5, 0.2), (0, 0, 0.085), 0.6, 6)
    camera((0.04, -0.50, 0.14), (0.0, 0.0, 0.085), 60)


SCENES = {"hero": scene_hero, "desk": scene_desk, "pocket": scene_pocket, "exploded": scene_exploded}


def main(argv: list[str]) -> int:
    name, out = argv[0], Path(argv[1]).resolve()
    samples = int(argv[argv.index("--samples") + 1]) if "--samples" in argv else 256
    size = tuple(int(v) for v in argv[argv.index("--size") + 1].split("x")) if "--size" in argv else (1600, 1000)
    reset(size, samples)
    SCENES[name]()
    bpy.context.scene.render.filepath = str(out)
    bpy.ops.render.render(write_still=True)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[sys.argv.index("--") + 1:]))
