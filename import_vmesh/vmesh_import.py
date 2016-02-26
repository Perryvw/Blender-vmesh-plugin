from mathutils import *

from . import pyVRF

import importlib

import bpy

def import_file(path):
    importlib.reload(pyVRF)
    print('Reloading pyVRF...')

    blocks = pyVRF.readBlocks( path )

    #Add geometry
    newObj = addGeometry( blocks['VBIB'] )

    #Add
    skeleton = addSkeleton( blocks['DATA'] )

#Add geometry to the scene, returns the added object
def addGeometry( data ):
    #Skeleton
    return 0

#Add a skeleton to the scene, returns the created skeleton
def addSkeleton( data ):

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

    bones = {}
    for bone in data['m_skeleton']['m_bones']:
        newBone = armature.edit_bones.new( bone['m_boneName'] )

        if len(bone['m_parentName']) > 0:
            newBone.parent = bones[bone['m_parentName']]
            newBone.use_connect = True

        #Set position
        m = bone['m_invBindPose']
        inverseBindPose = Matrix([[m[0],m[1],m[2],m[3]],
                                 [m[4],m[5],m[6],m[7]],
                                 [m[8],m[9],m[10],m[11]],
                                 [0, 0, 0, 1]])

        inverseBindPose.invert()
        parentMat = Matrix()
        if newBone.parent:
            newBone.head = newBone.parent.tail
        newBone.tail = inverseBindPose.to_translation()

        newBone.tail_radius = bone['m_flSphereRadius']

        bones[bone['m_boneName']] = newBone

    return armature