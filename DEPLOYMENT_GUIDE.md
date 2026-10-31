# plan_ws 部署与交接指南

本文描述当前仓库中 `px4_bridge bringup.launch.py` 的 EGO + PX4 SITL 启动链。它可以帮助另一台开发机复现实验，但当前默认配置是**本机 Gazebo SITL 和本 MID-360 模型专用**，不能直接用于真实飞机。

## 组件关系

`plan_ws` 不是独立完整系统。它提供 EGO、轨迹到 PX4 Offboard 的控制桥、FAST-LIO 到 PX4 EKF 的外部里程计桥。完整仿真另外需要：

- Ubuntu 与 ROS 2 Jazzy。
- PX4-Autopilot，包含成功构建的 `px4_sitl_default`。
- Gazebo Harmonic 和 `ros_gz_bridge`。
- `ws_livox`：`livox_ros_driver2` 的 `CustomMsg` 消息定义。
- `mid360_ws`：Gazebo MID-360 插件、X500+MID-360 模型及仿真 launch。
- `fastlio2_pgo_ws`：FAST-LIO2、PGO 和对应配置。
- `plan_ws`：EGO、`px4_msgs`、`quadrotor_msgs` 和两个 bridge。
- `factory_world_2026_9_22`：当前默认的工厂世界和模型资源。

本机当前路径写在仿真启动脚本默认值中：`~/PX4-Autopilot`、`~/GRA_1/factory_world_2026_9_22` 和当前工作区布局。交付时应把仓库和依赖克隆到接收方的机器，检查这些路径，或通过 `PX4_DIR`、`GRA_WORKSPACE` 和 launch 参数改为接收方路径。不能只拷贝 `plan_ws/install`：ROS overlay 与 PX4 二进制、Gazebo 插件、消息包版本必须相匹配。

## 首次安装与构建

在目标机器安装 ROS 2 Jazzy、Gazebo Harmonic、ROS-Gazebo bridge、colcon、Eigen/PCL 等 ROS 依赖，并按各依赖仓库说明构建 PX4 SITL。随后在每个工作区按依赖顺序构建；命令里的路径需按实际 checkout 修改：

```bash
source /opt/ros/jazzy/setup.bash

cd ~/GRA_1/ws_livox
colcon build --symlink-install

cd ~/GRA_1/mid360_ws
source ~/GRA_1/ws_livox/install/setup.bash
colcon build --symlink-install

cd ~/GRA_1/fastlio2_pgo_ws
source ~/GRA_1/ws_livox/install/setup.bash
colcon build --symlink-install

cd ~/GRA_1/plan_ws
source ~/GRA_1/ws_livox/install/setup.bash
colcon build --symlink-install
```

编译 `plan_ws` 后运行 `ros2 pkg list | grep -E '^(ego_planner|px4_bridge|fastlio2_px4_odom_bridge|px4_msgs|quadrotor_msgs)$'`，确认关键包已被找到。接收方如更新 PX4 `px4_msgs`，必须同步使用与固件兼容的消息定义并重新构建 `plan_ws`。

## 每次仿真启动

每条命令使用独立终端。先关闭上一次的 Gazebo、PX4、Micro XRCE-DDS Agent、FAST-LIO/PGO 和 ROS launch；UDP 端口 `8888` 只能有一个 Micro XRCE-DDS Agent。所有终端使用同一个 `ROS_DOMAIN_ID` 和 DDS 实现。

**终端 1：Gazebo、PX4 SITL、MID-360**

```bash
source /opt/ros/jazzy/setup.bash
source ~/GRA_1/ws_livox/install/setup.bash
source ~/GRA_1/mid360_ws/install/setup.bash
export GRA_WORKSPACE=~/GRA_1
export PX4_DIR=~/PX4-Autopilot
ros2 launch mid360_simulation_plugin_ros2 mid360_posix_sitl.launch.py gui:=true use_nvidia_gpu:=true
```

若直接使用 source tree 的 launch 文件，也可按仓库现有做法从 `~/PX4-Autopilot/launch` 執行。安裝後透過 package launch 可避免手動複製 launch 檔，但交接前要在接收端確認此 launch 可由 ament 找到。啟動腳本會檢查 PX4 SITL binary、rootfs、world 和 MID-360 model；缺任一項都不能繼續。

**终端 2：FAST-LIO2/PGO**

```bash
source /opt/ros/jazzy/setup.bash
source ~/GRA_1/ws_livox/install/setup.bash
source ~/GRA_1/fastlio2_pgo_ws/install/setup.bash
ros2 launch pgo pgo_launch.py
```

`pgo_launch.py` 同时启动 FAST-LIO2、PGO 和 RViz。当前 EGO 使用 FAST-LIO 的 `/fastlio2/lio_odom`、`/fastlio2/world_cloud`，不使用 PGO map 坐标；只做 EGO 飞行时 PGO 算法不是规划必需项，但现有 launch 把它们一起启动。

**终端 3：EGO 和 PX4 bridge**

```bash
source /opt/ros/jazzy/setup.bash
source ~/GRA_1/ws_livox/install/setup.bash
source ~/GRA_1/plan_ws/install/setup.bash
ros2 launch px4_bridge bringup.launch.py start_rviz:=true
```

该 bringup 默认启动 EGO、Micro XRCE-DDS Agent（UDP `8888`）、PX4 Offboard bridge、FAST-LIO 外部里程计 bridge 和 RViz。**不要另外启动第二个 Agent、第二个 px4_bridge 或第二个规划器**，也不要在 bringup 后再启动另一个同话题的 VehicleVisualOdometry publisher。

**终端 4：发送目标**

```bash
source /opt/ros/jazzy/setup.bash
source ~/GRA_1/ws_livox/install/setup.bash
source ~/GRA_1/plan_ws/install/setup.bash
ros2 run px4_bridge manual_goal 4.0 -4.0 0.5 90
```

`manual_goal` 会等到 goal/yaw 订阅者出现、bridge 确认 yaw 模式并报告启动起飞稳定后才发目标；坐标是 `lidar` 局部坐标，单位米，最后的 `90` 是该局部坐标中的 yaw 角度。自动朝向可以用 `--auto-yaw`，但不能同时传 yaw 数值。

## 启动前检查

目标发送前先确认：

```bash
ros2 topic hz /livox/lidar
ros2 topic hz /livox/imu
ros2 topic echo /fastlio2/lio_odom --once
ros2 topic echo /fastlio2/world_cloud --once
ros2 topic echo /px4_bridge/status --once
ros2 topic echo /fmu/out/vehicle_local_position_v1 --once
ros2 topic info -v /fmu/in/vehicle_visual_odometry
ros2 topic info -v /drone_0_planning/pos_cmd
```

期望：LiDAR、IMU、FAST-LIO odometry/cloud 持续更新；odometry 和 cloud 的 `frame_id` 都是 `lidar`；PX4 `xy_valid/z_valid` 为真；命令话题只有一个 planner publisher；外部里程计话题只有一个 publisher；bridge 报告起飞完成。若启动画面显示 `EMERGENCY_STOP`、`ODOM_STALE`、frame mismatch、FAST-LIO suppressing odometry 或 `px4_position_hold_latched`，不要再发送目标，先处理原因。

## PX4 参数

**当前 SITL**：Gazebo launch 在 PX4 进程启动时通过 `PX4_PARAM_*` 环境变量注入一组仿真参数，不要求操作员每次手动进入 PX4 shell 执行 `param set`。当前默认值为：

| PX4 参数 | 当前 launch 值 | 用途 |
|---|---:|---|
| `EKF2_EV_CTRL` | `7` | 融合外部视觉  水平/垂直位置及速度 |
| `EKF2_GPS_CTRL` | `0` | 当前无 GNSS aiding |
| `EKF2_HGT_REF` | `3` | 使用 external vision 高度参考 |
| `NAV_DLL_ACT` | `0` | 当前无 GCS 的 SITL 行为 |
| `COM_RCL_EXCEPT`、`COM_DLL_EXCEPT` | `4` | 当前 SITL Offboard 测试对 RC/GCS loss 的例外位 |
| `COM_LOW_BAT_ACT`、`SIM_BAT_DRAIN` | `0` | 关闭确定性仿真中的低电量动作/电量消耗 |

这些值描述本仓库的 SITL 流程，不应照搬到真实飞机。尤其 RC/GCS、低电量 failsafe 例外不能为了“让实验继续”而直接用于实机。launch 中还保留 `ekf2_ev_ctrl`、`ekf2_gps_ctrl`、`ekf2_hgt_ref` 等参数覆盖入口。

**真实 PX4**：必须先按接收方飞控固件版本核对 PX4 官方 external-vision/ROS 2 文档、参数元数据和 airframe 配置。再通过 QGroundControl 或受控参数流程设置 EKF2 external-vision 融合、测量延迟、传感器安装平移/方向、高度参考和必要的质量/噪声参数，并确认 EKF status/innovation 显示对应 EV 融合有效。不能只把 `EKF2_EV_CTRL` 写成固定值就认为配置完成。当前 bridge 使用 PX4 的 `vehicle_local_position` 时间戳给外部里程计打时间戳，仍要求测量坐标、时间、原点和传感器朝向经过实机标定。

**PX4 控制器**：启动不要求先改 PX4 位置控制增益。当前 EGO 限制为 `0.6 m/s`、`0.8 m/s^2`，bridge 以 `20 Hz` 持续发送位置 Offboard setpoint 和 `OffboardControlMode`，并在目标发送前执行约 `0.5 m` 的启动起飞段。实机必须先确认 PX4 固件、机型、执行器、geofence、手动接管和 failsafe；只有在记录真实 setpoint/position 误差且确认估计器稳定后，才调整 PX4 位置控制器参数。

## 必须重新标定的实机项目

- FAST-LIO `r_il/t_il`：LiDAR 到 IMU/body 的外参，使用实物标定值，不能沿用仿真默认。
- `fastlio2_px4_odom_bridge`：`world_rotation_row_major`、`body_to_frd_row_major`、位置平移、方差和时间戳映射。
- `px4_bridge`：`transform_rotation_row_major`、`transform_translation`、位置边界、速度/加速度上限和 yaw 方向。
- FAST-LIO 局部原点与 PX4 EKF local NED 原点对齐；核验三轴小位移方向和高度正负。
- EGO 地图范围、LiDAR 覆盖、障碍膨胀、安全净空、规划速度/加速度、机体尺寸与制动距离。
- PX4 地理围栏、低电量/RC/GCS/Offboard 丢失动作、kill switch、遥控器人工接管和实机试验场地。

当前坐标矩阵假设为 `PX4_NED = [lidar_y, lidar_x, -lidar_z]`，仅适用于当前 MID-360/Gazebo 模型链。实机需要做 observe-only/不解锁的变换核验，再以低速、限高和人工接管条件下验证；不能仅凭 frame 名称或仿真通过就飞行。

## 可交接状态与缺项

可以交给另一位开发者做**同版本 SITL 复现与 EGO 二次开发**，前提是把依赖仓库、PX4 固件版本/commit、ROS 和 Gazebo 版本、地图资源与本 `plan_ws` 一起交付。建议再附上每个仓库 commit、`git status`、PX4 参数输出和一个完整 rosbag。

当前不应宣称“开箱即用实机部署”。交付前仍需补齐：锁定所有仓库版本和依赖安装清单；给 PX4 固件与 `px4_msgs` 建立明确兼容版本；提供真实传感器标定参数文件；给 bridge 配置拆分 SITL 与 hardware profile；接入并记录实际碰撞/机体接触数据；在接收方机器执行完整构建和 B0/B1 冒烟测试。当前 `sitl_control.yaml` 明确是仿真 profile，且 FAST-LIO 的 PGO launch 会写入其 maps 目录，交接时应给每台设备独立数据目录或检查文件写权限。
