# my_2d_nav

My thesis repository.

how to execute:

As long as you have the willow garage world on the gazebo resource path and GAZEBO simulator and gazebo_ros_pkgs,


1.0) clone master repo

2.0) open one terminal

2.1) type: `roslaunch my_2d_nav amcl_one_to_rule_them_all.launch`

3.0) open another terminal(second different from the one above)

3.1) type: `roslaunch my_2d_nav target_select.launch`

you will se the turtlebot trying to cover the whole map and setting goals on its own.
Soon more features to come.
