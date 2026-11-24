"""Blender render of the case for the README.

blender -b -P tools/render_readme.py -- <bottom.stl> <top.stl> <out.png>
"""
import bpy, sys, math
from mathutils import Vector, Matrix

bot_p, top_p, out = sys.argv[sys.argv.index("--") + 1:]
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene

def load(p):
    bpy.ops.wm.stl_import(filepath=p)
    o = bpy.context.selected_objects[0]
    o.scale = (0.01,) * 3                       # mm -> 1 unit = 10 cm, keeps lights sane
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.transform_apply(scale=True)
    bpy.ops.object.shade_auto_smooth(angle=math.radians(30))
    return o

bot, top = load(bot_p), load(top_p)
# print orientation -> assembly: bottom as-is; top is lid-down, flip it and explode upward
top.matrix_world = Matrix.Rotation(math.pi, 4, "X") @ top.matrix_world
bpy.context.view_layer.update()
bz = max((bot.matrix_world @ Vector(c)).z for c in bot.bound_box)
tz = min((top.matrix_world @ Vector(c)).z for c in top.bound_box)
top.location.z += bz - tz + 0.17 - 0.06         # top shell overlaps the lip by ~6 mm when closed; show 17 mm gap

def mat(name, rgb, rough=0.45):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1); b.inputs["Roughness"].default_value = rough
    return m
bot.data.materials.append(mat("bot", (0.06, 0.065, 0.075)))     # dark grey PLA
top.data.materials.append(mat("top", (0.32, 0.33, 0.35)))      # light grey PLA

# shadow-catcher floor
bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, min((bot.matrix_world @ Vector(c)).z for c in bot.bound_box)))
bpy.context.object.is_shadow_catcher = True

# camera: 3/4 view from the front-right, a bit above
cx = sum((bot.matrix_world @ Vector(c) for c in bot.bound_box), Vector()) / 8
mid = Vector((cx.x, cx.y, (cx.z + top.location.z) / 2 - 0.08))
bpy.ops.object.camera_add(location=mid + 1.95 * Vector((1.15, -1.55, 1.05)))
cam = bpy.context.object; sc.camera = cam
cam.data.lens = 85
cam.rotation_euler = (mid - cam.location).to_track_quat("-Z", "Y").to_euler()

def area(name, loc, energy, size):
    bpy.ops.object.light_add(type="AREA", location=loc)
    l = bpy.context.object; l.data.energy = energy; l.data.size = size
    l.rotation_euler = (mid - l.location).to_track_quat("-Z", "Y").to_euler()
area("key", mid + Vector((1.2, -1.0, 1.6)), 60, 1.5)
area("fill", mid + Vector((-1.6, -0.8, 0.6)), 20, 2.0)
area("rim", mid + Vector((-0.4, 1.6, 1.2)), 45, 1.0)
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs["Color"].default_value = (1, 1, 1, 1)
w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.35

sc.render.engine = "CYCLES"; sc.cycles.samples = 128; sc.cycles.use_denoising = True
sc.render.film_transparent = True
try: sc.view_settings.view_transform = "AgX"
except TypeError: pass   # distro Blender may lack a loadable OCIO config
sc.render.resolution_x, sc.render.resolution_y = 1600, 1000
sc.render.filepath = out
sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGBA"
bpy.ops.render.render(write_still=True)
