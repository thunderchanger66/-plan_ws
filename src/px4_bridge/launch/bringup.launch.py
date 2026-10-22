import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    mid360_share = get_package_share_directory("mid360_simulation_plugin_ros2")
    px4_launch_default = os.path.join(
        mid360_share, "launch", "mid360_posix_sitl.launch.py")
    bridge_share = get_package_share_directory("px4_bridge")
    pgo_share = get_package_share_directory("pgo")
    ego_share = get_package_share_directory("ego_planner")

    px4_launch_file = LaunchConfiguration("px4_launch_file")
    px4_gui = LaunchConfiguration("px4_gui")
    bridge_params = LaunchConfiguration("bridge_params")

    return LaunchDescription([
        DeclareLaunchArgument(
            "px4_launch_file", default_value=px4_launch_default,
            description="Path to mid360_posix_sitl.launch.py"),
        DeclareLaunchArgument("px4_gui", default_value="true"),
        DeclareLaunchArgument(
            "bridge_params",
            default_value=os.path.join(bridge_share, "config", "sitl_control.yaml"),
            description="Bridge parameter file; defaults to the checked-in SITL control profile"),
        ExecuteProcess(
            cmd=["MicroXRCEAgent", "udp4", "-p", "8888"],
            name="micro_xrce_agent",
            output="screen",
            respawn=True,
            respawn_delay=2.0,
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(px4_launch_file),
            launch_arguments={"gui": px4_gui}.items(),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(os.path.join(pgo_share, "launch", "pgo_launch.py")),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(ego_share, "launch", "single_uav_gazebo.launch.py")),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(os.path.join(ego_share, "launch", "rviz.launch.py")),
        ),
        Node(
            package="px4_bridge",
            executable="px4_bridge_node",
            name="px4_bridge",
            output="screen",
            parameters=[bridge_params],
        ),
    ])
