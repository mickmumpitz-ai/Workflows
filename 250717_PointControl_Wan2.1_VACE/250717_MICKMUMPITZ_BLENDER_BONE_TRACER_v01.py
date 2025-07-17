bl_info = {
    "name": "Bone Tracer for ComfyUI",
    "author": "Mickmumpitz",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > Bone Tracer",
    "description": "Export selected bones and empty objects as pixel coordinates for ComfyUI",
    "category": "Animation",
}

import bpy
import bmesh
import json
import os
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
from bpy.props import StringProperty, IntProperty, BoolProperty, EnumProperty
from bpy.types import Panel, Operator, PropertyGroup

class BoneTracerProperties(PropertyGroup):
    output_path: StringProperty(
        name="Output Path",
        description="Path to save the text file with coordinate data",
        default="//coordinates_output.txt",
        subtype='FILE_PATH'
    )
    
    resolution_x: IntProperty(
        name="Resolution X",
        description="Output resolution width",
        default=1024,
        min=1
    )
    
    resolution_y: IntProperty(
        name="Resolution Y", 
        description="Output resolution height",
        default=1024,
        min=1
    )
    
    use_render_resolution: BoolProperty(
        name="Use Render Resolution",
        description="Use the scene's render resolution instead of custom values",
        default=True
    )
    
    bone_point: EnumProperty(
        name="Bone Point",
        description="Which part of the bone to trace",
        items=[
            ('HEAD', 'Head', 'Trace bone head position'),
            ('TAIL', 'Tail', 'Trace bone tail position'),
            ('CENTER', 'Center', 'Trace bone center position'),
        ],
        default='HEAD'
    )
    
    frame_start: IntProperty(
        name="Start Frame",
        description="First frame to trace",
        default=1,
        min=1
    )
    
    frame_end: IntProperty(
        name="End Frame", 
        description="Last frame to trace",
        default=250,
        min=1
    )
    
    use_scene_frame_range: BoolProperty(
        name="Use Scene Frame Range",
        description="Use the scene's frame range instead of custom values",
        default=True
    )

class BONE_TRACER_OT_export(Operator):
    """Export selected bones and empty objects to text file for ComfyUI"""
    bl_idname = "bone_tracer.export"
    bl_label = "Export Bone Traces"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        props = context.scene.bone_tracer_props
        
        # Get active camera
        camera = context.scene.camera
        if not camera:
            self.report({'ERROR'}, "No active camera found")
            return {'CANCELLED'}
        
        # Get resolution
        if props.use_render_resolution:
            res_x = context.scene.render.resolution_x
            res_y = context.scene.render.resolution_y
        else:
            res_x = props.resolution_x
            res_y = props.resolution_y
        
        # Get frame range
        if props.use_scene_frame_range:
            frame_start = context.scene.frame_start
            frame_end = context.scene.frame_end
        else:
            frame_start = props.frame_start
            frame_end = props.frame_end
        
        # Get selected bones from all selected armatures
        selected_bones_with_armature = []
        selected_armatures = [obj for obj in context.selected_objects if obj.type == 'ARMATURE']
        
        # Get selected empty objects
        selected_empties = [obj for obj in context.selected_objects if obj.type == 'EMPTY']
        
        if not selected_armatures and not selected_empties:
            self.report({'ERROR'}, "No armature or empty objects selected. Please select armature and/or empty objects.")
            return {'CANCELLED'}
        
        # Switch to pose mode to get bone transforms
        original_mode = context.mode
        original_active = context.active_object
        
        for armature in selected_armatures:
            # Make this armature active and switch to pose mode
            context.view_layer.objects.active = armature
            if context.mode != 'POSE':
                bpy.ops.object.mode_set(mode='POSE')
            
            # Get selected pose bones from this armature
            for bone in armature.pose.bones:
                if bone.bone.select:
                    selected_bones_with_armature.append((bone, armature))
        
        if not selected_bones_with_armature and not selected_empties:
            self.report({'ERROR'}, "No bones selected and no empty objects selected. Please select bones in pose mode on armatures or select empty objects.")
            return {'CANCELLED'}
        
        # Store current frame
        current_frame = context.scene.frame_current
        
        # Trace each bone over time
        bone_traces = []
        
        try:
            # Process bones from armatures
            for bone, armature in selected_bones_with_armature:
                bone_trace = []
                
                # Go through each frame
                for frame in range(frame_start, frame_end + 1):
                    context.scene.frame_set(frame)
                    
                    # Get bone position based on selected point
                    if props.bone_point == 'HEAD':
                        bone_pos = bone.head
                    elif props.bone_point == 'TAIL':
                        bone_pos = bone.tail
                    else:  # CENTER
                        bone_pos = (bone.head + bone.tail) / 2
                    
                    # Convert to world space using this armature's matrix
                    world_pos = armature.matrix_world @ bone_pos
                    
                    # Convert to camera space (0-1 normalized)
                    cam_pos = world_to_camera_view(context.scene, camera, world_pos)
                    
                    # Convert to pixel coordinates with top-left origin (0,0)
                    pixel_pos = {
                        "x": int(cam_pos.x * res_x),
                        "y": int((1.0 - cam_pos.y) * res_y)
                    }
                    
                    bone_trace.append(pixel_pos)
                
                bone_traces.append(bone_trace)
            
            # Process empty objects
            for empty in selected_empties:
                empty_trace = []
                
                # Go through each frame
                for frame in range(frame_start, frame_end + 1):
                    context.scene.frame_set(frame)
                    
                    # Get empty object's world position
                    world_pos = empty.matrix_world.translation
                    
                    # Convert to camera space (0-1 normalized)
                    cam_pos = world_to_camera_view(context.scene, camera, world_pos)
                    
                    # Convert to pixel coordinates with top-left origin (0,0)
                    pixel_pos = {
                        "x": int(cam_pos.x * res_x),
                        "y": int((1.0 - cam_pos.y) * res_y)
                    }
                    
                    empty_trace.append(pixel_pos)
                
                bone_traces.append(empty_trace)
            
        finally:
            # Restore original frame and active object
            context.scene.frame_set(current_frame)
            context.view_layer.objects.active = original_active
        
        # Save to text file
        output_path = bpy.path.abspath(props.output_path)
        try:
            with open(output_path, 'w') as f:
                json.dump(bone_traces, f, indent=2)
            
            total_objects = len(selected_armatures) + len(selected_empties)
            self.report({'INFO'}, f"Exported {len(bone_traces)} traces from {total_objects} object(s) ({frame_end - frame_start + 1} frames each) to {output_path}")
            self.report({'INFO'}, "Open the text file and copy the content to use in ComfyUI")
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to save file: {str(e)}")
            return {'CANCELLED'}
        
        return {'FINISHED'}
    
    def get_bone_chains(self, selected_bones):
        """Group connected bones into chains"""
        chains = []
        processed = set()
        
        for bone in selected_bones:
            if bone.name in processed:
                continue
                
            # Start a new chain
            chain = []
            current = bone
            
            # Go to the root of this chain
            while current.parent and current.parent in selected_bones:
                current = current.parent
            
            # Build chain from root to tip
            while current and current in selected_bones:
                chain.append(current)
                processed.add(current.name)
                
                # Find child in selected bones
                next_bone = None
                for child in current.children:
                    if child in selected_bones:
                        next_bone = child
                        break
                current = next_bone
            
            if chain:
                chains.append(chain)
        
        return chains

class BONE_TRACER_PT_panel(Panel):
    """Creates a Panel in the 3D Viewport N-Panel"""
    bl_label = "Bone Tracer"
    bl_idname = "BONE_TRACER_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Bone Tracer"
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.bone_tracer_props
        
        # Camera info
        camera = context.scene.camera
        if camera:
            layout.label(text=f"Active Camera: {camera.name}", icon='CAMERA_DATA')
        else:
            layout.label(text="No Active Camera!", icon='ERROR')
        
        # Resolution settings
        layout.prop(props, "use_render_resolution")
        
        if props.use_render_resolution:
            render = context.scene.render
            layout.label(text=f"Resolution: {render.resolution_x} x {render.resolution_y}")
        else:
            layout.prop(props, "resolution_x")
            layout.prop(props, "resolution_y")
        
        # Frame range settings
        layout.separator()
        layout.label(text="Frame Range:", icon='TIME')
        layout.prop(props, "use_scene_frame_range")
        
        if props.use_scene_frame_range:
            scene = context.scene
            layout.label(text=f"Frames: {scene.frame_start} - {scene.frame_end} ({scene.frame_end - scene.frame_start + 1} frames)")
        else:
            layout.prop(props, "frame_start")
            layout.prop(props, "frame_end")
            frame_count = max(0, props.frame_end - props.frame_start + 1)
            layout.label(text=f"Total Frames: {frame_count}")
        
        # Bone point selection
        layout.separator()
        layout.prop(props, "bone_point")
        
        # Output settings
        layout.separator()
        layout.prop(props, "output_path")
        
        # Export button
        layout.separator()
        
        # Selection info
        selected_armatures = [obj for obj in context.selected_objects if obj.type == 'ARMATURE']
        selected_empties = [obj for obj in context.selected_objects if obj.type == 'EMPTY']
        total_selected_bones = 0
        
        if selected_armatures:
            layout.label(text=f"Selected Armatures: {len(selected_armatures)}")
            
            for armature in selected_armatures:
                selected_count = sum(1 for bone in armature.pose.bones if bone.bone.select)
                total_selected_bones += selected_count
                if selected_count > 0:
                    layout.label(text=f"  {armature.name}: {selected_count} bones")
        
        if selected_empties:
            layout.label(text=f"Selected Empty Objects: {len(selected_empties)}")
            for empty in selected_empties:
                layout.label(text=f"  {empty.name}")
        
        total_traces = total_selected_bones + len(selected_empties)
        if total_traces > 0:
            layout.label(text=f"Total Traces: {total_traces}")
            
            if props.use_scene_frame_range:
                frame_count = context.scene.frame_end - context.scene.frame_start + 1
            else:
                frame_count = max(0, props.frame_end - props.frame_start + 1)
            total_points = total_traces * frame_count
            layout.label(text=f"Total Points: {total_points}")
        
        if not selected_armatures and not selected_empties:
            layout.label(text="Select Armature and/or Empty Objects", icon='INFO')
        
        # Instructions
        box = layout.box()
        box.label(text="Instructions:", icon='INFO')
        box.label(text="1. Select armature and/or empty objects")
        box.label(text="2. Enter Pose mode (for armatures)")
        box.label(text="3. Select bones to trace (if using armatures)")
        box.label(text="4. Active camera is used for tracing bones/ empties")
        box.label(text="5. Reduce resolution to 720p or below for faster ComfyUI processing")
        box.label(text="6. Click Export")
        box.label(text="7. Open .txt file and copy content")
        
        layout.operator("bone_tracer.export", icon='EXPORT')

# Registration
classes = (
    BoneTracerProperties,
    BONE_TRACER_OT_export,
    BONE_TRACER_PT_panel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    bpy.types.Scene.bone_tracer_props = bpy.props.PointerProperty(type=BoneTracerProperties)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    del bpy.types.Scene.bone_tracer_props

if __name__ == "__main__":
    register()