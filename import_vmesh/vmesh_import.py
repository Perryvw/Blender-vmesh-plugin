from mathutils import *

from . import pyVRF

import importlib

import bpy
global bonesdata
bonesdata = []
def import_file(path):
    importlib.reload(pyVRF)
    print('Reloading pyVRF...')

    #Get the data
    blocks = pyVRF.readBlocks( path )
    vbib = blocks['VBIB']

    #Go to object mode before doing anything
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)

    #Add geometry
    newObj = addGeometry( vbib )
    #Add
    skeleton = addSkeleton( blocks['DATA'], newObj )

    #add rigging
    addRig(newObj, skeleton, vbib)

#Add geometry to the scene, returns the added object
def addGeometry( data ):
    # Create mesh and object
    me = bpy.data.meshes.new('Mesh')
    ob = bpy.data.objects.new('MeshObject', me)
    ob.location = (0,0,0)
    # Link object to scene
    scn = bpy.context.scene
    scn.objects.link(ob)
    scn.objects.active = ob
    scn.update()
 
    # Create mesh from given verts, edges, faces. Either edges or
    # faces should be [], or you ask for problems
    vertices = data["vertexdata"][0]["vertex"]
    indices = data["indexdata"][0]
    #print(indices)
    me.from_pydata(vertices, [], indices)
 
    # Update mesh with new data
    me.update(calc_edges=False)
    scn.update()
    #uv texcoords
    me.uv_textures.new()
    uv_data = me.uv_layers[0].data
    for i in range(len(uv_data)):
        uv_data[i].uv = data["vertexdata"][0]["texcoords"][me.loops[i].vertex_index]
    scn.update()
    return ob

#Add a skeleton to the scene, returns the created skeleton
def addSkeleton( data, mesh ):

    #Fetch scene
    scn = bpy.context.scene

    #Make armature
    armature = bpy.data.armatures.new('Armature')
    obj = bpy.data.objects.new('Armature', armature)
    
    #Link the armature object in the scene and select it
    scn.objects.link(obj)
    scn.objects.active = obj
    obj.select = True
        
    bpy.ops.object.mode_set(mode='EDIT', toggle=False)

    #Create skeleton bone by bone
    matrices = {}
    bones = {}
    for bone in data['m_skeleton']['m_bones']:
        newBone = armature.edit_bones.new( bone['m_boneName'] )

        #Set parent
        if len(bone['m_parentName']) > 0:
            newBone.parent = bones[bone['m_parentName']]
            newBone.use_connect = False

        #Set position
        m = bone['m_invBindPose']
        inverseBindPose = Matrix([[m[0],m[1],m[2],m[3]],
                                 [m[4],m[5],m[6],m[7]],
                                 [m[8],m[9],m[10],m[11]],
                                 [0, 0, 0, 1]])

        inverseBindPose.invert()

        #Set head and tail
        newBone.head = inverseBindPose.to_translation()
        if newBone.parent:
            #Calculate the average position of siblings to set the parent tail to
            avgPos = Vector()
            num = 0
            for pc in newBone.parent.children:
                avgPos = avgPos + pc.head
                num = num + 1
            avgPos = avgPos / num
            newBone.parent.tail = avgPos

        #Set tail radius - doesn't seem to do anything?
        newBone.tail_radius = bone['m_flSphereRadius']

        #Save the bone to parent later
        bones[bone['m_boneName']] = newBone

        #Also keep track fo the matrix for later
        matrices[newBone] = inverseBindPose

        #global bonesdata array. Fix/Change?
        mesh.vertex_groups.new(bone['m_boneName'])
        bonesdata.append(bone['m_boneName'])

    #Show extreme bones - i.e. bones without children to set the tail position to
    for bone in matrices:
        if len(bone.children) == 0:
            #Show extreme bones as extensions of their parent
            bone.tail = bone.head + (bone.parent.tail - bone.parent.head).normalized() * 4
    
    #Merge heads/tails where a parent has only 1 child
    for bone in matrices:
        if len(bone.children) == 1:
            #Connect bones that have no siblings to their parents
            bone.children[0].use_connect = True


    return obj

def addRig(mesh, skeleton, vbib):
    for index in range(len(vbib["vertexdata"][0]["blendindices"])):
        #print(index)
        weight = vbib["vertexdata"][0]["blendweights"][index]
        #print(index, weight)
        for q in range(len(weight)):
            vg = mesh.vertex_groups.get(bonesdata[vbib["vertexdata"][0]["blendindices"][index][q]])
            #not sure if this actually works correctly --v
            vg.add([index],  float( weight[q] ) /255.0, "REPLACE")
    mod = mesh.modifiers.new('Armature', 'ARMATURE')
    mod.object = skeleton
    mod.use_bone_envelopes = False
    mod.use_vertex_groups = True