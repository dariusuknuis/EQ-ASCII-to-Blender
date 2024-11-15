import math
import mathutils

# Function to convert Euler angles to quaternion
def euler_to_quaternion(x, y, z):
    x_normalized = (x / 512) * 2 * math.pi
    y_normalized = ((512 - y) / 512) * 2 * math.pi
    z_normalized = (z / 512) * 2 * math.pi
    
    cx = math.cos(x_normalized / 2)
    cy = math.cos(y_normalized / 2)
    cz = math.cos(z_normalized / 2)
    
    sx = math.sin(x_normalized / 2)
    sy = math.sin(y_normalized / 2)
    sz = math.sin(z_normalized / 2)
    
    qw = cx * cy * cz + sx * sy * sz
    qx = sx * cy * cz - cx * sy * sz
    qy = cx * sy * cz + sx * cy * sz
    qz = cx * cy * sz - sx * sy * cz
    
    return [qw, qx, qy, qz]