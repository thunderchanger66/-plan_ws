import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    bridge_share = get_package_share_directory("px4_bridge")
    ego_share = get_package_share_directory("ego_planner")

    bridge_params = LaunchConfiguration("bridge_params")

    return LaunchDescription([
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
