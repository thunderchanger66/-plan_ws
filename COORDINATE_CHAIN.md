# MID-360、FAST-LIO、EGO、PX4 坐标链

本文按当前源码和配置说明从 Gazebo 雷达模型到最终 PX4 仿真控制量的坐标关系。`frame_id` 只是消息标签；真正改变数值的是 SDF pose、插件 `output_yaw`、FAST-LIO `r_il/t_il` 和 bridge 矩阵。

## 当前链路

感知链是：Gazebo `mid360_link` -> MID-360 插件 -> `/livox/lidar` 和 `/livox/imu` -> FAST-LIO -> `/fastlio2/lio_odom`、`/fastlio2/world_cloud` -> EGO。

控制链是：EGO `PositionCommand`（`lidar` 坐标）-> `px4_bridge` -> `/fmu/in/trajectory_setpoint`（PX4 NED）。

当前关键值：MID-360 相对 `base_link` 安装 yaw 为 `pi`；插件 `output_yaw` 为 `pi`；FAST-LIO `world_frame` 为 `lidar`；FAST-LIO `r_il` 为单位阵；EGO `planning_frame` 为 `lidar`；bridge `planner_frame` 为 `lidar`。

## 1. Gazebo 模型

文件：`mid360_ws/src/mid360_gazebo_harmonic/packages/mid360_simulation_plugin_ros2/models/x500_gimbal_mid360/model.sdf`。

其中 `mid360_link` 的安装是：

```xml
<pose relative_to="base_link">0 0 0.08 0 0 3.141592653589793</pose>
```

这表示传感器相对机体平移 `[0,0,0.08]`，绕 Z 旋转 `pi`。它改变 Gazebo 中 link 的物理姿态和射线方向。工厂 world 中的 `<pose>0 7 0 0 0 0</pose>` 是整架无人机的初始世界 pose，属于另一层。

## 2. MID-360 插件

文件：`mid360_ws/src/mid360_gazebo_harmonic/packages/mid360_simulation_plugin_ros2/models/mid360/model.sdf` 和 `src/mid360_system.cpp`。

插件绑定 `mid360_link`，发布 `/livox/lidar`、`/livox/imu`，消息标签是 `livox_frame`，输出类型 3 是 `livox_ros_driver2/msg/CustomMsg`。

插件先用 `gz::sim::worldPose(rayEntity, ecm)` 得到物理 link 位姿，再用 RMagine 做射线检测。`output_yaw` 不改变碰撞模型或射线 link。

点云发布前执行 `x=cos(yaw)*result.x-sin(yaw)*result.y`、`y=sin(yaw)*result.x+cos(yaw)*result.y`，即 `p_out=Rz(output_yaw)*p_sensor`。当前 `output_yaw=pi`，所以输出点的 XY 数值都取反，Z 不变；header 仍是 `livox_frame`。

插件还对 IMU 的加速度、角速度和姿态做对应输出帧修正。不能只旋转点云而不旋转 IMU。

因此当前有两层 yaw：物理安装 `pi` 和输出数值 `pi`。它们不是同一个参数，不能再无条件叠加第三次补偿。

## 3. FAST-LIO

文件：`fastlio2_pgo_ws/src/FASTLIO2_ROS2_PGO/fastlio2/config/lio.yaml` 和 `fastlio2/src/lio_node.cpp`。

当前输入是 `/livox/imu`、`/livox/lidar`，`body_frame=body`，`world_frame=lidar`。`pgo_launch.py` 默认加载 `lio.yaml`，不是 `lio_sim.yaml`；两者 `t_il` 不同，修改错文件不会生效。

FAST-LIO 直接使用 `CustomMsg` 的点坐标，不根据 `livox_frame` 查询 TF。点变换源码为：

```cpp
point_world = state.r_wi * (state.r_il * point + state.t_il) + state.t_wi;
```

当前 `r_il=I`，表示插件输出的 LiDAR 数值轴必须已经和 body/IMU 数值轴一致。当前默认 `lio.yaml` 的平移外参是 `t_il=[-0.011,-0.02329,0.04412]`。

FAST-LIO 发布 `/fastlio2/lio_odom`（header `lidar`、child `body`）、`/fastlio2/body_cloud`（`body`）和 `/fastlio2/world_cloud`（`lidar`）。`lidar` 是 FAST-LIO 局部估计世界的标签，不自动等于 Gazebo world 或 PX4 NED。

## 4. PGO

PGO 订阅 `/fastlio2/body_cloud` 和 `/fastlio2/lio_odom`，发布 `map -> lidar` 优化 TF、路径和回环标记。当前 EGO 使用 `/fastlio2/lio_odom` 与 `/fastlio2/world_cloud`，没有使用 PGO map 坐标，所以 PGO 当前不直接改变 EGO 局部规划坐标。

## 5. EGO

文件：`plan_ws/src/ego/ego_planner/launch/single_uav_gazebo.launch.py`、`advanced_param.launch.py`、`plan_env/src/library/grid_map.cpp`。

当前 `planning_frame=lidar`，`odom_topic=/fastlio2/lio_odom`，`cloud_topic=/fastlio2/world_cloud`。EGO 将它们分别重映射到 `odom_world`、`grid_map/odom` 和 `grid_map/cloud`。

EGO 和 GridMap 都严格要求消息 `header.frame_id` 等于 `lidar`；不一致就丢弃，不会自动 TF 转换。GridMap 直接使用点云的 `pt.x/y/z` 建图，因此 world_cloud 的数值必须已经是 FAST-LIO 的 `lidar` 局部世界坐标。

EGO 发出的 position、velocity、acceleration 和 yaw 都是 `lidar` 局部坐标语义，`PositionCommand.header.frame_id` 是 `lidar`。

## 6. Launch 中的其他旋转

`single_uav_gazebo.launch.py` 还创建 `body -> base_link` 的 yaw=`pi`、`body -> livox_frame` 的单位 TF，并给 `traj_server/initial_yaw` 设为 `pi`。

前两个是 ROS TF；`initial_yaw` 只影响轨迹 yaw 初值。FAST-LIO 当前数值外参来自 `lio.yaml` 的 `r_il/t_il`，不会自动使用这些 TF 修正 PCL。不要用多个层同时补偿同一个 yaw。

## 7. bridge 到 PX4

文件：`plan_ws/src/px4_bridge/src/px4_bridge_node.cpp` 和 `config/sitl_control.yaml`。

bridge 订阅 `/drone_0_planning/pos_cmd`，要求 frame 是 `lidar`。它对 position、velocity、acceleration 使用同一个 row-major 矩阵，并对 yaw 使用同一矩阵旋转 heading。

当前矩阵是：

```text
R = [ 0  1  0 ]
    [ 1  0  0 ]
    [ 0  0 -1 ]
```

因此实际是 `PX4_X=lidar_Y`、`PX4_Y=lidar_X`、`PX4_Z=-lidar_Z`。输出 `/fmu/in/trajectory_setpoint` 使用 PX4 NED。

bridge 不把 PX4 反馈位置反向转换到 `lidar`，当前 `transform_translation` 为零，所以 EGO 和 PX4 局部原点必须对齐。

## 8. 完整公式

插件输出：`p_livox = Rz(output_yaw) * p_sensor`。

FAST-LIO 输出：`p_lidar_world = R_wi * (R_il * p_livox + t_il) + t_wi`。

当前 `R_il=I`，所以 FAST-LIO 假设插件输出轴已经与 body/IMU 轴一致。

控制转换：`p_px4_ned = R_bridge * p_lidar = [lidar_y, lidar_x, -lidar_z]`。

如果修改 `output_yaw`、物理安装 yaw、`r_il` 或世界起始方向，就必须重新推导并实测验证 `R_bridge`。

## 9. 为什么会方向反

常见原因是：修改 `output_yaw` 但 bridge 仍用旧矩阵；把安装 yaw 和 output yaw 当成同一层；只旋转点云没旋转 IMU；以为静态 TF 会自动修改 FAST-LIO PCL 数值；修改 `lio_sim.yaml` 但启动实际加载 `lio.yaml`；或 EGO 与 PX4 局部原点不一致。

## 10. 验证顺序

先确认插件：

```bash
ros2 topic type /livox/lidar
ros2 topic type /livox/imu
ros2 topic hz /livox/lidar
ros2 topic hz /livox/imu
```

应分别是 `livox_ros_driver2/msg/CustomMsg` 和 `sensor_msgs/msg/Imu`，日志应显示 `output_yaw=3.141592653589793 rad`。

再确认 FAST-LIO：

```bash
ros2 topic echo /fastlio2/lio_odom --field header.frame_id --once
ros2 topic echo /fastlio2/lio_odom --field child_frame_id --once
ros2 topic echo /fastlio2/world_cloud --field header.frame_id --once
```

预期为 `lidar`、`body`、`lidar`。

再确认 EGO 地图：将 RViz Fixed Frame 设为 `lidar`，显示 `/drone_0_grid/grid_map/occupancy_inflate`。若出现 `frame differs from grid map frame lidar`，先修 frame/话题，不要调规划权重。

最后验证 bridge 单位方向。当前矩阵应满足 `[1,0,0] lidar -> [0,1,0] PX4`、`[0,1,0] lidar -> [1,0,0] PX4`、`[0,0,1] lidar -> [0,0,-1] PX4`。

先将 `sitl_control.yaml` 的 `observe_only` 设为 `true`，发送很小的单轴目标，比较 EGO 命令、`/px4_bridge/status` 的 PX4 position 和 `/fmu/out/vehicle_local_position_v1` 的实际变化；确认后再恢复 `false`。

## 11. 最终闭合标准

点云和 IMU 使用同一输出轴；FAST-LIO `r_il/t_il` 与插件输出轴一致；odom/world_cloud 的 frame 都是 `lidar`；EGO 和 GridMap frame 都是 `lidar`；三条单位方向经 bridge 后符合 PX4 NED 实测；EGO 与 PX4 局部原点一致；RViz 中点云、地图、轨迹和机体在同一个 Fixed Frame 下重合。

源码可以确定各程序的计算方式，但不能仅凭 frame 名称确定 PX4 模型在当前 world 起始 yaw 下的最终机头方向。因此 bridge 矩阵最终必须通过 `observe_only` 小位移测试确认。
