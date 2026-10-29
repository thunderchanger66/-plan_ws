import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.conditions import IfCondition
from launch.actions import DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    bridge_share = get_package_share_directory("px4_bridge")
    ego_share = get_package_share_directory("ego_planner")
    odom_bridge_share = get_package_share_directory("fastlio2_px4_odom_bridge")

    bridge_params = LaunchConfiguration("bridge_params")
    odom_bridge_params = LaunchConfiguration("odom_bridge_params")
    start_odom_bridge = LaunchConfiguration("start_odom_bridge")
    start_rviz = LaunchConfiguration("start_rviz")
    start_agent = LaunchConfiguration("start_agent")

    return LaunchDescription([
        DeclareLaunchArgument(
            "bridge_params",
            default_value=os.path.join(bridge_share, "config", "sitl_control.yaml"),
            description="Bridge parameter file; defaults to the checked-in SITL control profile"),
        DeclareLaunchArgument(
            "start_agent", default_value="true",
            description="Start Micro XRCE-DDS Agent on UDP 8888"),
        DeclareLaunchArgument(
            "start_odom_bridge",
            default_value="true",
            description="Start FAST-LIO2 to PX4 external-odometry bridge"),
        DeclareLaunchArgument(
            "start_rviz", default_value="true",
            description="Start the EGO RViz visualization"),
        DeclareLaunchArgument(
            "odom_bridge_params",
            default_value=os.path.join(
                odom_bridge_share, "config", "fastlio2_px4_odom_bridge.yaml"),
            description="FAST-LIO2 to PX4 odometry bridge parameter file"),
        ExecuteProcess(
            cmd=["MicroXRCEAgent", "udp4", "-p", "8888"],
            name="micro_xrce_agent",
            output="screen",
            respawn=True,
            respawn_delay=2.0,
            condition=IfCondition(start_agent),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(ego_share, "launch", "single_uav_gazebo.launch.py")),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(os.path.join(ego_share, "launch", "rviz.launch.py")),
            condition=IfCondition(start_rviz),
        ),
        Node(
            package="px4_bridge",
            executable="px4_bridge_node",
            name="px4_bridge",
            output="screen",
            parameters=[bridge_params],
        ),
        Node(
            package="fastlio2_px4_odom_bridge",
            executable="fastlio2_px4_odom_bridge_node",
            name="fastlio2_px4_odom_bridge",
            output="screen",
            parameters=[odom_bridge_params],
            condition=IfCondition(start_odom_bridge),
        ),
    ])
