import bpy

def create_bounding_sphere(mesh_obj, bounding_radius):
    name = f"{mesh_obj.name}_BR"
    sphere = bpy.data.objects.new(name, None)
    sphere.empty_display_type = 'SPHERE'
    sphere.empty_display_size = bounding_radius
    bpy.context.collection.objects.link(sphere)
    sphere.parent = mesh_obj

    return sphere
