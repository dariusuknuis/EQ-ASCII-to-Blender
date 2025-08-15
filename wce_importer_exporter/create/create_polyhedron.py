import bpy
from .create_mesh_and_bounding_shapes import create_bounding_sphere

def create_polyhedron(polyhedron_data):
    name = polyhedron_data['name']
    vertices = polyhedron_data['vertices']
    faces = [face['vertex_list'] for face in polyhedron_data['faces']]

    # Create the mesh and object
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)

    # Set the location of the object
    obj.location = bpy.context.scene.cursor.location
    bpy.context.collection.objects.link(obj)

    # Create the mesh from given vertices and faces
    mesh.from_pydata(vertices, [], faces)
    mesh.update()

    # Apply the scale factor to the object
    scale_factor = polyhedron_data['scale_factor']
    obj.scale = (scale_factor, scale_factor, scale_factor)

    # Create a simple pinkish-red transparent material
    material = bpy.data.materials.new(name="PinkishRedMaterial")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()

    # Add a Principled BSDF shader node
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (1.0, 0.0, 0.5, 1.0)  # Pinkish-red
    bsdf.inputs['Alpha'].default_value = 0.5  # 50% transparent

    # Add a Material Output node and link it to the BSDF shader
    output = nodes.new(type='ShaderNodeOutputMaterial')
    material.node_tree.links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    # Enable transparency in the material settings
    material.blend_method = 'BLEND'
    material.shadow_method = 'HASHED'

    # Assign the material to the object
    if obj.data.materials:
        obj.data.materials[0] = material
    else:
        obj.data.materials.append(material)
    
    obj["HEXONEFLAG"] = bool(polyhedron_data.get("hexoneflag", 0))

    bounding_radius = polyhedron_data.get('bounding_radius', 1.0)

    if bounding_radius > 0:
        bounding_sphere = create_bounding_sphere(obj, bounding_radius)
        bounding_sphere.hide_set(True)
    
    return obj
