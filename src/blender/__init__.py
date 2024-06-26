import os
import platform
import subprocess
import sys

import bpy
from bpy.utils import register_class, unregister_class

# Addon metadata
bl_info = {
    "name": "ReachyMarionette",
    "author": "Energinet",
    "version": (1, 0, 0),
    "blender": (4, 0, 1),
    "location": "Toolbar > ReachyMarionette",
    "description": "Connects to the Reachy robot from Pollen Robotics, to stream angles of joints in Reachy rig.",
    "category": "Animation",
}


# Non standard Python packages - "python import name": "pip install name"
packages = {
    "gtts": "gTTS",
    "openai": "openai",
    "pydub": "pydub",
    "reachy_sdk": "reachy-sdk",
    "requests": "requests",
    "scipy": "scipy",
    "sounddevice": "sounddevice",
    "whisper": "openai-whisper",
}


def install_package(package):

    if platform.system() == "win32":

        python_exe = os.path.join(sys.prefix, "bin", "python.exe")
        target = os.path.join(sys.prefix, "lib", "site-packages")

        subprocess.call([python_exe, "-m", "ensurepip"])
        subprocess.call([python_exe, "-m", "pip", "install", "--upgrade", "pip"])

        subprocess.call(
            [python_exe, "-m", "pip", "install", "--upgrade", package, "-t", target]
        )

    else:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])


for package_py, package_pip in packages.items():
    try:
        exec("import " + package_py)

    except ModuleNotFoundError:
        print(
            package_py
            + " module not found, installing '"
            + package_pip
            + "' with pip..."
        )

        install_package(package_pip)
        exec("import " + package_py)

        print(package_py + " successfully imported")

print("All packages installed")

# Load addon modules
from .reachy_marionette import ReachyMarionette
from .reachy_gpt import ReachyGPT
from .reachy_voice import ReachyVoice

# Global objects
reachy = ReachyMarionette()
reachy_gpt = ReachyGPT()
reachy_voice = ReachyVoice()

# Global constants
AUDIO_FILE_PATH = "//mic_input.wav"


# Classes


class SceneProperties(bpy.types.PropertyGroup):
    # Defining custom properties to be used by the addon panel

    def callback_kinematics(self, context):
        # Toggle IK constraint on bones that has thems

        for bone in bpy.context.active_object.pose.bones:

            if not "IK" in bone.constraints:
                continue

            if self.Kinematics == "FK":
                bone.constraints["IK"].enabled = False
            elif self.Kinematics == "IK":
                bone.constraints["IK"].enabled = True

    def callback_streaming(self, context):

        if self.Streaming:
            bpy.ops.reachy_marionette.stream_angles("INVOKE_DEFAULT")

            if reachy.reachy == None:
                self.Streaming = False

        return

    def callback_recording(self, context):

        if self.Recording:
            bpy.ops.reachy_marionette.record_audio("INVOKE_DEFAULT")

        return

    IPaddress: bpy.props.StringProperty(
        name="IP adress",
        description="Reachy's IP address (default = localhost).",
        default="localhost",
    )  # type: ignore (stops warning squiggles)

    Kinematics: bpy.props.EnumProperty(
        name="Kinematics",
        description="Choose if rig is controlled by forward kinematics (FK) or inverse kinematics (IK).",
        items=[("FK", "FK", ""), ("IK", "IK", "")],
        default="FK",
        update=callback_kinematics,
    )  # type: ignore (stops warning squiggles)

    Streaming: bpy.props.BoolProperty(
        description="If addon is currently streaming angles to Reachy.",
        default=False,
        update=callback_streaming,
    )  # type: ignore (stops warning squiggles)

    Speaker: bpy.props.BoolProperty(
        description="If responses from ChatGPT are played through speaker.",
        default=False,
    )  # type: ignore (stops warning squiggles)

    PromtType: bpy.props.EnumProperty(
        name="Promt Type",
        description="Choose if promt is provided as text or speech.",
        items=[("Text", "Text", ""), ("Speech", "Speech", "")],
        default="Text",
    )  # type: ignore (stops warning squiggles)

    Promt: bpy.props.StringProperty(
        name="Promt", description="Promt for ChatGPT", default=""
    )  # type: ignore (stops warning squiggles)

    Recording: bpy.props.BoolProperty(
        description="If addon is currently recording audio.",
        default=False,
        update=callback_recording,
    )  # type: ignore (stops warning squiggles)


class REACHYMARIONETTE_OT_ConnectReachy(bpy.types.Operator):
    # Handling connection to Reachy
    bl_idname = "reachy_marionette.connect_reachy"
    bl_label = "Connect to Reachy Robot via IP-adress"

    def execute(self, context):
        scene_properties = context.scene.scn_prop

        reachy.connect_reachy(self.report, scene_properties.IPaddress)

        return {"FINISHED"}


class REACHYMARIONETTE_OT_DisconnectReachy(bpy.types.Operator):
    # Handling connection to Reachy
    bl_idname = "reachy_marionette.disconnect_reachy"
    bl_label = "Disconnect current connection to Reachy"

    def execute(self, context):

        reachy.disconnect_reachy(self.report)

        return {"FINISHED"}


class REACHYMARIONETTE_OT_SendPose(bpy.types.Operator):
    # Get angles from Blender rig, and send to Reachy

    bl_idname = "reachy_marionette.send_pose"
    bl_label = "Send current pose once"

    def execute(self, context):

        reachy.send_angles(self.report)

        return {"FINISHED"}


class REACHYMARIONETTE_OT_StreamPose(bpy.types.Operator):
    # Continously get angles from Blender rig, and stream to Reachy

    bl_idname = "reachy_marionette.stream_angles"
    bl_label = "Live streaming of bone angles"

    def __init__(self):
        print("Stream starting...")

    def __del__(self):
        reachy.set_state_idle()

        print("Stream ended")

    def modal(self, context, event):
        scene_properties = context.scene.scn_prop

        if not scene_properties.Streaming:
            self.report({"INFO"}, "Stopping stream")
            return {"FINISHED"}

        if event.type == "ESC":
            self.report({"INFO"}, "ESC key pressed, stopping stream")
            return {"FINISHED"}

        return {"PASS_THROUGH"}

    def invoke(self, context, event):
        context.window_manager.modal_handler_add(self)

        reachy.stream_angles_enable(self.report)

        return {"RUNNING_MODAL"}


class REACHYMARIONETTE_OT_AnimatePose(bpy.types.Operator):
    # Go through animation timeline and get angles from Blender rig, and send to Reachy

    bl_idname = "reachy_marionette.animate_pose"
    bl_label = "Go through animation timeline and send poses"

    def __init__(self):
        print("Animation starting...")

    def __del__(self):
        print("Animation ended")

    def modal(self, context, event):
        if event.type == "ESC":
            reachy.set_state_idle()

            self.report({"INFO"}, "ESC key pressed, stopping animation")
            return {"FINISHED"}

        return {"PASS_THROUGH"}

    def invoke(self, context, event):
        context.window_manager.modal_handler_add(self)

        reachy.animate_angles(self.report)

        return {"RUNNING_MODAL"}


class REACHYMARIONETTE_OT_ActivateGPT(bpy.types.Operator):

    bl_idname = "reachy_marionette.activate_gpt"
    bl_label = "Start ChatGPT client"

    def execute(self, context):
        scene_properties = context.scene.scn_prop

        if not reachy_gpt.activate(self.report):
            return {"CANCELLED"}

        return {"FINISHED"}


class REACHYMARIONETTE_OT_SendRequest(bpy.types.Operator):
    # Select action

    bl_idname = "reachy_marionette.action_selection"
    bl_label = "Select action"

    def execute(self, context):
        scene_properties = context.scene.scn_prop

        response = reachy_gpt.send_request(scene_properties.Promt, reachy, self.report)

        if scene_properties.Speaker:
            reachy_voice.speak_audio(response["answer"], language="da")

        return {"FINISHED"}


class REACHYMARIONETTE_OT_RecordAudio(bpy.types.Operator):
    # Continously get angles from Blender rig, and stream to Reachy

    bl_idname = "reachy_marionette.record_audio"
    bl_label = "Record audio from microphone."

    def __init__(self):
        print("Recording started")

    def __del__(self):
        print("Recording processed")

    def process_recording(self, scene_properties):

        reachy_voice.stop_recording()
        print("Recording ended")

        audio_file_path = bpy.path.abspath(AUDIO_FILE_PATH)

        # Convert to text
        transcription = reachy_voice.transcribe_audio(
            audio_file_path, self.report, language="da"
        )

        # Send promt to ChatGPT
        response = reachy_gpt.send_request(transcription, reachy, self.report)

        if scene_properties.Speaker:
            reachy_voice.speak_audio(response["answer"], language="da")

    def modal(self, context, event):
        scene_properties = context.scene.scn_prop

        # Sync settings
        if not reachy_voice.recording:
            scene_properties.Recording = False
            self.process_recording(scene_properties)
            return {"FINISHED"}

        if not scene_properties.Recording:
            self.report({"INFO"}, "Stopping recording")
            self.process_recording(scene_properties)
            return {"FINISHED"}

        if event.type == "ESC":
            self.report({"INFO"}, "ESC key pressed, stopping recording and processing")
            return {"FINISHED"}

        return {"PASS_THROUGH"}

    def invoke(self, context, event):
        context.window_manager.modal_handler_add(self)

        audio_file_path = bpy.path.abspath(AUDIO_FILE_PATH)

        # Record audio sample
        reachy_voice.start_recording(
            self.report, file_path=audio_file_path, duration_max=10.0
        )

        return {"RUNNING_MODAL"}


class REACHYMARIONETTE_PT_PanelConnection(bpy.types.Panel):
    # Addon panel displaying options

    bl_label = "Connection"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ReachyMarionette"
    bl_options = {"HEADER_LAYOUT_EXPAND"}

    def draw(self, context):
        layout = self.layout
        scene_properties = context.scene.scn_prop

        layout.prop(scene_properties, "IPaddress")

        if reachy.reachy == None:
            layout.row().operator(
                REACHYMARIONETTE_OT_ConnectReachy.bl_idname,
                text="Connect to Reachy",
                icon="PLUGIN",
            )

        else:
            layout.row().operator(
                REACHYMARIONETTE_OT_DisconnectReachy.bl_idname,
                text="Disconnect Reachy",
                icon="UNLINKED",
            )


class REACHYMARIONETTE_PT_PanelManual(bpy.types.Panel):
    # Addon panel displaying options

    bl_label = "Manual Control"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ReachyMarionette"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        scene_properties = context.scene.scn_prop

        layout.prop(scene_properties, "Kinematics", expand=True)

        layout.row().operator(
            REACHYMARIONETTE_OT_SendPose.bl_idname,
            text="Send Pose",
            icon="ARMATURE_DATA",
        )

        label = "Streaming..." if scene_properties.Streaming else "Stream Pose"
        icon = "RADIOBUT_ON" if scene_properties.Streaming else "RADIOBUT_OFF"
        layout.prop(scene_properties, "Streaming", text=label, icon=icon, toggle=True)

        layout.row().operator(
            REACHYMARIONETTE_OT_AnimatePose.bl_idname,
            text="Animate Pose",
            icon="PLAY",
        )


class REACHYMARIONETTE_PT_PanelAI(bpy.types.Panel):
    # Addon panel displaying options

    bl_label = "AI Control"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ReachyMarionette"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        scene_properties = context.scene.scn_prop

        if reachy_gpt.client == None:

            layout.row().operator(
                REACHYMARIONETTE_OT_ActivateGPT.bl_idname,
                text="Activate API key",
                icon="RADIOBUT_OFF",
            )

        else:
            layout.row().operator(
                REACHYMARIONETTE_OT_ActivateGPT.bl_idname,
                text="API key is active",
                icon="RADIOBUT_ON",
            )

        label = "Sound ON" if scene_properties.Speaker else "Sound OFF"
        icon = "MUTE_IPO_ON" if scene_properties.Speaker else "MUTE_IPO_OFF"
        layout.prop(scene_properties, "Speaker", text=label, icon=icon, toggle=True)

        layout.prop(scene_properties, "PromtType", expand=True)

        if scene_properties.PromtType == "Text":

            layout.prop(scene_properties, "Promt")

            layout.row().operator(
                REACHYMARIONETTE_OT_SendRequest.bl_idname,
                text="Send Request",
                icon="URL",
            )

        elif scene_properties.PromtType == "Speech":

            # layout.row().operator(
            #     REACHYMARIONETTE_OT_RecordAudio.bl_idname,
            #     text="Record Audio",
            #     icon="SPEAKER",
            # )

            label = "Recording..." if scene_properties.Recording else "Record Audio"
            icon = "RADIOBUT_ON" if scene_properties.Recording else "RADIOBUT_OFF"
            layout.prop(
                scene_properties, "Recording", text=label, icon=icon, toggle=True
            )


classes = (
    SceneProperties,
    REACHYMARIONETTE_OT_ConnectReachy,
    REACHYMARIONETTE_OT_DisconnectReachy,
    REACHYMARIONETTE_OT_SendPose,
    REACHYMARIONETTE_OT_StreamPose,
    REACHYMARIONETTE_OT_AnimatePose,
    REACHYMARIONETTE_OT_ActivateGPT,
    REACHYMARIONETTE_OT_SendRequest,
    REACHYMARIONETTE_OT_RecordAudio,
    REACHYMARIONETTE_PT_PanelConnection,
    REACHYMARIONETTE_PT_PanelManual,
    REACHYMARIONETTE_PT_PanelAI,
)


def register():
    for cls in classes:
        register_class(cls)

    bpy.types.Scene.scn_prop = bpy.props.PointerProperty(type=SceneProperties)


def unregister():
    for cls in classes:
        unregister_class(cls)

    del bpy.types.Scene.scn_prop

    def temp(_x, _y): ...

    reachy.disconnect_reachy(temp)


if __name__ == "__main__":

    register()
