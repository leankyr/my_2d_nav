#!/usr/bin/env python
from __future__ import division

import rospy
import actionlib
import scipy
import time
import math
import tf
import numpy
import random
import bresenham

from utilities import OgmOperations
from utilities import RvizHandler
from utilities import Print
from utilities import Cffi

from geometry_msgs.msg import PoseStamped, Twist
from nav_msgs.msg import OccupancyGrid
from brushfires import Brushfires
from topology import Topology
from visualization_msgs.msg import Marker, MarkerArray

from timeit import default_timer as timer

import operator

class TargetSelect:

    def __init__(self):
        self.xLimitUp = 0
        self.xLimitDown = 0
        self.yLimitUp = 0
        self.yLimitDown = 0

        self.brush = Brushfires()
        self.topo = Topology()
        self.target = [-1, -1]
        self.previousTarget = [-1, -1]
        self.costs = []


    def targetSelection(self, initOgm, coverage, origin, resolution, robotPose, flag, other_goal, force_random):
        rospy.loginfo("-----------------------------------------")
        rospy.loginfo("[Target Select Node] Robot_Pose[x, y, th] = [%f, %f, %f]", 
                    robotPose['x'], robotPose['y'], robotPose['th'])
        rospy.loginfo("[Target Select Node] OGM_Origin = [%i, %i]", origin['x'], origin['y'])
        rospy.loginfo("[Target Select Node] OGM_Size = [%u, %u]", initOgm.shape[0], initOgm.shape[1])

        # willow params
#        ogm_limits = {}
#        ogm_limits['min_x'] = 350  # used to be 200
#        ogm_limits['max_x'] = 800  # used to be 800
#        ogm_limits['min_y'] = 200
#        ogm_limits['max_y'] = 800

#        # Big Map
        ogm_limits = {}
        ogm_limits['min_x'] = 200  # used to be 200
#        ogm_limits['max_x'] = 800  # used to be 800
        ogm_limits['max_x'] = 850
        ogm_limits['min_y'] = 300
        ogm_limits['max_y'] = 710


        # publisher

        marker_pub = rospy.Publisher("/robot1/vis_nodes", MarkerArray, queue_size = 1)
        # Find only the useful boundaries of OGM. Only there calculations have meaning
#        ogm_limits = OgmOperations.findUsefulBoundaries(initOgm, origin, resolution)
        print ogm_limits

        # Blur the OGM to erase discontinuities due to laser rays
        #ogm = OgmOperations.blurUnoccupiedOgm(initOgm, ogm_limits)
        ogm = initOgm
        # find brushfire field
        brush2 = self.brush.obstaclesBrushfireCffi(ogm, ogm_limits)

        # Calculate skeletonization
        skeleton = self.topo.skeletonizationCffi(ogm, origin, resolution, ogm_limits)

        # Find Topological Graph
        tinit = time.time()
        nodes = self.topo.topologicalNodes(ogm, skeleton, coverage, origin, \
                                    resolution, brush2, ogm_limits)
        # print took to calculate....
        rospy.loginfo("Calculation time: %s",str(time.time() - tinit))
        
        if len(nodes) == 0 and force_random: 
            brush = self.brush.coverageLimitsBrushfire(initOgm, 
                      coverage, robotPose, origin, resolution)
            throw = set()
            throw = self.filterGoal(brush, initOgm, resolution, origin)
            brush.difference_update(throw)
            goal = random.sample(brush, 1)
            
            rospy.loginfo("nodes are zero and random node chosen!!!!")
            th_rg = math.atan2(goal[0][1] - robotPose['y'], \
                    goal[0][0] - robotPose['x'])

            self.target = [goal[0][0], goal[0][1], th_rg]
            return self.target
        
        if len(nodes) == 0:
            brush = self.brush.coverageLimitsBrushfire(initOgm, 
                      coverage, robotPose, origin, resolution)
            throw = set()
            throw = self.filterGoal(brush, initOgm, resolution, origin)
            brush.difference_update(throw)
            distance_map = dict()
            distance_map = self.calcDist(robotPose, brush)
            self.target = min(distance_map, key = distance_map.get)
            
            th_rg = math.atan2(self.target[1] - robotPose['y'], \
                    self.target[0] - robotPose['x'])
            self.target = list(self.target)
            self.target.append(th_rg)
            return self.target
        
        

        if len(nodes) > 0:
            rospy.loginfo("[Main Node] Nodes ready! Elapsed time = %fsec", time.time() - tinit)
            rospy.loginfo("[Main Node] # of nodes = %u", len(nodes))

            # Remove previous targets from the list of nodes
            rospy.loginfo("[Main Node] Prev. target = [%u, %u]", self.previousTarget[0], 
                self.previousTarget[1])
            if len(nodes) > 1:
                nodes = [i for i in nodes if i != self.previousTarget]

            vis_nodes = []
            for n in nodes:
                vis_nodes.append([
                    n[0] * resolution + origin['x'],
                    n[1] * resolution + origin['y']
                ])
            RvizHandler.printMarker(\
                vis_nodes,\
                1, # Type: Arrow
                0, # Action: Add
                "map", # Frame
                "art_topological_nodes", # Namespace
                [0.3, 0.4, 0.7, 0.5], # Color RGBA
                0.1 # Scale
            )
            self.publish_markers(marker_pub, vis_nodes)

        
        # Check distance From Other goal

        for node in nodes:
            node_x = node[0] * resolution + origin['x']
            node_y = node[1] * resolution + origin['y']
            dist = math.hypot(node_x - other_goal['x'], node_y - other_goal['y']) 
            if dist < 1 and len(nodes) > 2:
                nodes.remove(node)

        # pick Random node!!
        if force_random:
            ind = random.randrange(0,len(nodes))
            rospy.loginfo('index is: %d', ind)
            rospy.loginfo('Random raw node is: [%u, %u]', nodes[ind][0], nodes[ind][1])
            tempX = nodes[ind][0] * resolution + origin['x']
            tempY = nodes[ind][1] * resolution + origin['y']
            th_rg = math.atan2(tempY - robotPose['y'], \
                    tempX - robotPose['x'])
            self.target = [tempX, tempY, th_rg]
            rospy.loginfo("[Main Node] Random target found at [%f, %f]", 
                            self.target[0], self.target[1])
            rospy.loginfo("-----------------------------------------")
            return self.target
 

        # Calculate distance cost
        wDist = []
        nodesX = []
        nodesY = []
        for i in range(0, len(nodes)):
            nodesX.append(nodes[i][0])
            nodesY.append(nodes[i][1])
        for i in range(0, len(nodes)):
            dist = math.sqrt((nodes[i][0] * resolution + origin['x_px'] - robotPose['x_px'])**2 + \
                        (nodes[i][1] * resolution + origin['y_px'] - robotPose['y_px'])**2)


#        for i in range(len(nodes)):
#            rospy.logwarn("Distance Cost is: %f ",wDist[i])
            gaussCoeff = 1               
            wDist.append(dist * gaussCoeff)

        #return self.target


        # Normalize costs
#        wTopoNorm = []
        wDistNorm = []
#        wCoveNorm = []
#        wRotNorm = []
        for i in range(0, len(nodes)):
#            if max(wTopo) - min(wTopo) == 0:
#                normTopo = 0
#            else:
#                normTopo = 1 - (wTopo[i] - min(wTopo)) / (max(wTopo) - min(wTopo))
#            if wDist[i] == max(wDist):
#                nodes.remove(nodes[i])
#                continue
            if max(wDist) - min(wDist) == 0:
                normDist = 0
            else:
                normDist = 1 - (wDist[i] - min(wDist)) / (max(wDist) - min(wDist))
#            if max(wCove) - min(wCove) == 0:
#                normCove = 0
#            else:
#                normCove = 1 - (wCove[i] - min(wCove)) / (max(wCove) - min(wCove))
#            if max(wRot) - min(wRot) == 0:
#                normRot = 0
#            else:
#                normRot = 1 - (wRot[i] - min(wRot)) / (max(wRot) - min(wRot))
#            wTopoNorm.append(normTopo)
            wDistNorm.append(normDist)
#            wCoveNorm.append(normCove)
#            wRotNorm.append(normRot)

        # Calculate Priority Weight
        priorWeight = []
        for i in range(0, len(nodes)):
            pre = wDistNorm[i] / 0.5
            #pre = 1
            priorWeight.append(pre)

        # Calculate smoothing factor
        smoothFactor = []
        for i in range(0, len(nodes)):
            coeff = 1 - wDistNorm[i]

            smoothFactor.append(coeff)

        # Calculate costs
        self.costs = []
        for i in range(0, len(nodes)):
            self.costs.append(smoothFactor[i] * priorWeight[i])

        print 'len nodes is:'
        print len(nodes) 
    
        goals_and_costs = zip(nodes, self.costs)
        #print goals_and_costs

        goals_and_costs.sort(key = lambda t: t[1], reverse = False)
        #sorted(goals_and_costs, key=operator.itemgetter(1))
        #print goals_and_costs 
        rospy.loginfo("[Main Node] Raw node = [%u, %u]", goals_and_costs[0][0][0], goals_and_costs[0][0][1])
        tempX = goals_and_costs[0][0][0] * resolution + origin['x']
        tempY = goals_and_costs[0][0][1] * resolution + origin['y']
        th_rg = math.atan2(tempY - robotPose['y'], \
                    tempX - robotPose['x'])
        self.target = [tempX, tempY, th_rg]
        rospy.loginfo("[Main Node] Eligible node found at [%f, %f]", 
                        self.target[0], self.target[1])
        rospy.loginfo("[Main Node] Node Index: %u", i)
        rospy.loginfo("[Main Node] Node Cost = %f", goals_and_costs[0][1])
        rospy.loginfo("-----------------------------------------")
        self.previousTarget = [goals_and_costs[0][0][0], goals_and_costs[0][0][1]]
        
               

        return self.target

    def rotateRobot(self):
        velocityMsg = Twist()
        angularSpeed = 0.3
        relativeAngle = 2*math.pi
        currentAngle = 0

        rospy.loginfo("Roatating robot...")
        velocityMsg.linear.x = 0
        velocityMsg.linear.y = 0
        velocityMsg.linear.z = 0
        velocityMsg.angular.x = 0
        velocityMsg.angular.y = 0
        velocityMsg.angular.z = angularSpeed

        t0 = rospy.Time.now().to_sec()
        rospy.logwarn(rospy.get_caller_id() + ": Rotate Robot! Please wait...")
        while currentAngle < relativeAngle:
            self.velocityPub.publish(velocityMsg)
            t1 = rospy.Time.now().to_sec()
            currentAngle = angularSpeed * (t1 - t0)

        velocityMsg.angular.z = 0
        self.velocityPub.publish(velocityMsg)
        rospy.logwarn(rospy.get_caller_id() + ": Robot Rotation OVER!")
        return



    def publish_markers(self, marker_pub, vis_nodes):
        markers = MarkerArray()
        c = 0
        for n in vis_nodes:
            c += 1
            msg = Marker()
            msg.header.frame_id = "map"
            msg.ns = "lines"
            msg.action = msg.ADD
            msg.type = msg.CUBE
            msg.id = c
            #msg.scale.x = 1.0
            #msg.scale.y = 1.0
            #msg.scale.z = 1.0
            # I guess I have to take into consideration resolution too
            msg.pose.position.x = n[0]
            msg.pose.position.y = n[1]
            msg.pose.position.z = 0
            msg.pose.orientation.x = 0.0
            msg.pose.orientation.y = 0.0
            msg.pose.orientation.z = 0.05
            msg.pose.orientation.w = 0.05
            msg.scale.x = 0.2
            msg.scale.y = 0.2
            msg.scale.z = 0.2
            msg.color.a = 1.0 # Don't forget to set the alpha!
            msg.color.r = 0.0
            msg.color.g = 1.0
            msg.color.b = 0.0
    #        print 'I publish msg now!!!'
            markers.markers.append(msg)
            
        marker_pub.publish(markers)
#
        return

    def calcDist(self, robotPose, brush):
        distance_map = dict()
        for goal in brush:
            dist = math.hypot(goal[0] - robotPose['x'], goal[1] - robotPose['y'])
            distance_map[goal] = dist
        return distance_map

    def filterGoal(self, brush2, ogm, resolution, origin):
        throw = set()
        for goal in brush2:
            goal = list(goal)
            for i in range(-9,10):
                if int(goal[0]/resolution - origin['x']/resolution) + i >= len(ogm):
                    break
                if ogm[int(goal[0]/resolution - origin['x']/resolution) + i]\
                [int(goal[1]/resolution - origin['y']/resolution)] > 49 \
                or ogm[int(goal[0]/resolution - origin['x']/resolution) + i]\
                [int(goal[1]/resolution - origin['y']/resolution)] == -1:
                    goal = tuple(goal)
                    throw.add(goal)
                    break

        for goal in brush2:
            goal = list(goal)
            for j in range(-9,10):
                if int(goal[1]/resolution - origin['y']/resolution) + j >= len(ogm[0]):
                    break
                if ogm[int(goal[0]/resolution - origin['x']/resolution)]\
                [int(goal[1]/resolution - origin['y']/resolution) + j] > 49 \
                or ogm[int(goal[0]/resolution - origin['x']/resolution) + i]\
                [int(goal[1]/resolution - origin['y']/resolution)] == -1:
                    goal = tuple(goal)
                    throw.add(goal)
                    break

        for goal in brush2:
            goal = list(goal)
            for i in range(-9,10):
                if int(goal[0]/resolution - origin['x']/resolution) + i >= len(ogm) or \
                    int(goal[1]/resolution - origin['y']/resolution) + i >= len(ogm[0]):
                    break
                if ogm[int(goal[0]/resolution - origin['x']/resolution) + i]\
                [int(goal[1]/resolution - origin['y']/resolution) + i] > 49 \
                or ogm[int(goal[0]/resolution - origin['x']/resolution) + i]\
                [int(goal[1]/resolution - origin['y']/resolution) + i] == -1:
                    goal = tuple(goal)
                    throw.add(goal)
                    break


        for goal in brush2:
            goal = list(goal)
            for i in range(-9, 10):
                if int(goal[0]/resolution - origin['x']/resolution) + i >= len(ogm) or \
                    int(goal[1]/resolution - origin['y']/resolution) + i >= len(ogm[0]):
                    break
                if ogm[int(goal[0]/resolution - origin['x']/resolution) + i]\
                [int(goal[1]/resolution - origin['y']/resolution) - i] > 49 \
                or ogm[int(goal[0]/resolution - origin['x']/resolution) + i]\
                [int(goal[1]/resolution - origin['y']/resolution) - i] == -1:
                    goal = tuple(goal)
                    throw.add(goal)
                    break

        return throw
