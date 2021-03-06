#!/usr/bin/env python


import rospy
import actionlib
import scipy
import time
import math
import tf
import numpy
import random
from bresenham import bresenham

from utilities import OgmOperations
from geometry_msgs.msg import PoseStamped, Twist
from nav_msgs.msg import OccupancyGrid
from brushfires import Brushfires
from topology import Topology
from visualization_msgs.msg import Marker

import operator
class TargetSelect:

    def __init__(self):
        self.xLimitUp = 0
        self.xLimitDown = 0
        self.yLimitUp = 0
        self.yLimitDown = 0

        self.brush = Brushfires()
        self.topo = Topology()
        self.target1 = [-1, -1]
        self.target2 = [-1, -1]
        self.previousTarget = [-1, -1]
        self.costs = []


    def targetSelection(self, initOgm, coverage, origin, resolution, robotPose1, robotPose2):
        rospy.loginfo("-----------------------------------------")
        rospy.loginfo("[Target Select Node] Robot_Pose1[x, y, th] = [%f, %f, %f]", \
                    robotPose1['x'], robotPose1['y'], robotPose1['th'])
        rospy.loginfo("[Target Select Node] Robot_Pose2[x, y, th] = [%f, %f, %f]", \
                    robotPose2['x'], robotPose2['y'], robotPose2['th'])
        rospy.loginfo("[Target Select Node] OGM_Origin = [%i, %i]", origin['x'], origin['y'])
        rospy.loginfo("[Target Select Node] OGM_Size = [%u, %u]", initOgm.shape[0], initOgm.shape[1])

        # Blur the OGM to erase discontinuities due to laser rays
        #ogm = OgmOperations.blurUnoccupiedOgm(initOgm, ogmLimits)
        ogm = initOgm

        rospy.loginfo("Calculating brushfire of first robot...")
        brush1 = self.brush.coverageLimitsBrushfire(initOgm, coverage, robotPose1, origin, resolution )
        rospy.loginfo("Calculating brushfire of second robot...")
        brush2 = self.brush.coverageLimitsBrushfire(initOgm, coverage, robotPose2, origin, resolution )
        
        print 'size of brush1:'
        print len(brush1)
        print 'size of brush2:'
        print len(brush2)


        min_dist = 10**24
        store_goal1 = ()
        throw1 = set()
        store_goal2 = ()
        throw2 = set()


        throw1 = self.filterGoal(brush1, ogm, resolution, origin)
        throw2 = self.filterGoal(brush2, ogm, resolution, origin)

        print 'size of throw1:'
        print len(throw1)
        print 'size of throw2:'
        print len(throw2)


        brush1.difference_update(throw1)
        brush2.difference_update(throw2)

        print 'size of brush1 after update:'
        print len(brush1)
        print 'size of brush2 after update:'
        print len(brush2)
        
        ## Sample randomly the sets ????
#        brush1 = random.sample(brush1, int(len(brush1)/5))
#        brush2 = random.sample(brush2, int(len(brush2)/5))

#        print 'size of brush 1 after sampling... '
#        print len(brush1)
#        print 'size of brush 2 after sampling... '
#        print len(brush2)


#        topo_gain1 = dict()
#        topo_gain1 = self.topoGain(brush1, resolution, origin, ogm)
#
#        topo_gain2 = dict()
#        topo_gain2 = self.topoGain(brush2, resolution, origin, ogm)
        
        ## Sort Topo Gain goal ##

        #sorted_topo_gain = sorted(topo_gain.items(), key=operator.itemgetter(1), reverse = True)
        #rospy.loginfo('the length of sorted_topo_gain is %d !!', len(sorted_topo_gain))


        distance_map1 = dict()
        distance_map1 = self.calcDist(robotPose1, brush1)
        rospy.loginfo('the length of distance map1 is %d !!', len(distance_map1))

        distance_map2 = dict()
        distance_map2 = self.calcDist(robotPose2, brush2)
        rospy.loginfo('the length of distance map2 is %d !!', len(distance_map2))

        self.target1 = min(distance_map1, key = distance_map1.get)
        self.target2 = min(distance_map2, key = distance_map2.get)

        #self.target1 = self.findGoal(brush1, distance_map1, topo_gain1)
        #self.target2 = self.findGoal(brush2, distance_map2, topo_gain2)
        
        
        return self.target1, self.target2

    
    def filterGoal(self, brush2, ogm, resolution, origin):
        throw = set()
        for goal in brush2:
            goal = list(goal)
            for i in range(-3,4):
                if int(goal[0]/resolution - origin['x']/resolution) + i >= len(ogm):
                    break
                if ogm[int(goal[0]/resolution - origin['x']/resolution) + i]\
                [int(goal[1]/resolution - origin['y']/resolution) ] > 49 \
                or ogm[int(goal[0]/resolution - origin['x']/resolution) + i]\
                [int(goal[1]/resolution - origin['y']/resolution) ] == -1:
                    goal = tuple(goal)
                    throw.add(goal)
                    break

        for goal in brush2:
            goal = list(goal)
            for j in range(-3,4):
                if int(goal[1]/resolution - origin['y']/resolution) + j >= len(ogm[0]):
                    break
                if ogm[int(goal[0]/resolution - origin['x']/resolution)]\
                [int(goal[1]/resolution - origin['y']/resolution) + j] > 49 \
                or ogm[int(goal[0]/resolution - origin['x']/resolution) + i]\
                [int(goal[1]/resolution - origin['y']/resolution) ] == -1:
                    goal = tuple(goal)
                    throw.add(goal)
                    break

        for goal in brush2:
            goal = list(goal)
            for i in range(-3,4):
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

#        for goal in brush2:
#            goal = list(goal)
#            for i in range(-3,4):
#                if int(goal[0]/resolution - origin['x']/resolution) + i >= len(ogm) or \
#                    int(goal[1]/resolution - origin['y']/resolution) + i >= len(ogm[0]):
#                    break
#                if ogm[int(goal[0]/resolution - origin['x']/resolution) - i]\
#                [int(goal[1]/resolution - origin['y']/resolution) - i] > 49 \
#                or ogm[int(goal[0]/resolution - origin['x']/resolution) - i]\
#                [int(goal[1]/resolution - origin['y']/resolution) - i] == -1:
#                    goal = tuple(goal)
#                    throw.add(goal)
#                    break

        for goal in brush2:
            goal = list(goal)
            for i in range(-3,4):
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

#        for goal in brush2:
#            goal = list(goal)
#            for i in range(-3,4):
#                if int(goal[0]/resolution - origin['x']/resolution) + i >= len(ogm) or \
#                    int(goal[1]/resolution - origin['y']/resolution) + i >= len(ogm[0]):
#                    break
#                if ogm[int(goal[0]/resolution - origin['x']/resolution) - i]\
#                [int(goal[1]/resolution - origin['y']/resolution) + i] > 49 \
#                or ogm[int(goal[0]/resolution - origin['x']/resolution) - i]\
#                [int(goal[1]/resolution - origin['y']/resolution) + i] == -1:
#                    goal = tuple(goal)
#                    throw.add(goal)
#                    break
        return throw

    def topoGain(self, brush, resolution, origin, ogm):
        topo_gain = dict()
        half_side = rospy.get_param('radius')
        for goal in brush:
            xx = goal[0]/resolution
            yy = goal[1]/resolution
            rays_len = numpy.full([8], rospy.get_param('radius'))

            line = list(bresenham(int(xx), int(yy), int(xx), int(yy + half_side/resolution)))
            for idx,coord in enumerate(line):
                if ogm[coord[0] - origin['x_px']][coord[1] - origin['y_px']] > 80:
                    rays_len[0] = len(line[0: idx]) * resolution
                    break

            line = list(bresenham(int(xx),int(yy),int(xx),int(yy - half_side/resolution)))
            for idx,coord in enumerate(line):
                if ogm[coord[0] - origin['x_px']][coord[1] - origin['y_px']] > 80:
                    rays_len[1] = len(line[0: idx]) * resolution
                    break

            line = list(bresenham(int(xx),int(yy),int(xx + half_side/resolution),int(yy)))
            for idx,coord in enumerate(line):
                if ogm[coord[0] - origin['x_px']][coord[1] - origin['y_px']] > 80:
                    rays_len[2] = len(line[0: idx]) * resolution
                    break

            line = list(bresenham(int(xx),int(yy),int(xx - half_side/resolution),int(yy)))
            for idx,coord in enumerate(line):
                if ogm[coord[0] - origin['x_px']][coord[1] - origin['y_px']] > 80:
                    rays_len[3] = len(line[0: idx]) * resolution
                    break

            line = list(bresenham(int(xx),int(yy),int(xx + half_side/resolution),int(yy + half_side/resolution)))
            for idx,coord in enumerate(line):
                if ogm[coord[0] - origin['x_px']][coord[1] - origin['y_px']] > 80:
                    rays_len[4] = len(line[0: idx]) * resolution
                    break

            line = list(bresenham(int(xx),int(yy),int(xx + half_side/resolution),int(yy - half_side/resolution)))
            for idx,coord in enumerate(line):
                if ogm[coord[0] - origin['x_px']][coord[1] - origin['y_px']] > 80:
                    rays_len[5] = len(line[0: idx]) * resolution
                    break

            line = list(bresenham(int(xx),int(yy),int(xx - half_side/resolution),int(yy + half_side/resolution)))
            for idx,coord in enumerate(line):
                if ogm[coord[0] - origin['x_px']][coord[1] - origin['y_px']] > 80:
                    rays_len[6] = len(line[0: idx]) * resolution
                    break

            line = list(bresenham(int(xx),int(yy),int(xx - half_side/resolution),int(yy - half_side/resolution)))
            for idx,coord in enumerate(line):
                if ogm[coord[0] - origin['x_px']][coord[1] - origin['y_px']] > 80:
                    rays_len[7] = len(line[0: idx]) * resolution
                    break

            #topo_gain[goal] = sum(rays_len)/len(rays_len)
            topo_gain[goal] = sum(rays_len) #/len(rays_len)
            #rospy.loginfo('The topo gain for goal = [%f,%f] is %f', xx, yy, topo_gain[goal])
        return topo_gain

    def calcDist(self, robotPose, brush):
        distance_map = dict()
        for goal in brush:
            dist = math.hypot(goal[0] - robotPose['x'], goal[1] - robotPose['y'])
            distance_map[goal] = dist
        return distance_map
    
    def findGoal(self, brush, distance_map, topo_gain):
        ######################################################################################
        ##################### Here I calculate the gain of my Goals ##########################
        ######################################################################################
        normTopo = dict()
        normDist = dict()
        for goal in brush:
            if max(topo_gain.values()) - min(topo_gain.values()) == 0:
                normTopo[(0,0)] = 0
            else:
                # 1 - ...
                normTopo[goal] = (topo_gain[goal] - min(topo_gain.values())) \
                            / (max(topo_gain.values()) - min(topo_gain.values()))
            if max(distance_map.values()) - min(distance_map.values()) == 0:
                normDist[(0,0)] = 0
            else:
                normDist[goal] = 1 - (distance_map[goal] - min(distance_map.values())) \
                            / (max(distance_map.values()) - min(distance_map.values()))

        # Calculate Priority Weight
        priorWeight = dict()
        for goal in brush:
            pre = 2 * round((normTopo[goal] / 0.5), 0) + \
                    1 * round((normDist[goal] / 0.5), 0)
            priorWeight[goal] = pre

        # Calculate smoothing factor
        smoothFactor = dict()
        for goal in brush:
            coeff = (2 * ( normTopo[goal]) + 1 * (1 - normDist[goal]))  / (2**2 - 1)
            # coeff = (4 * (1 - wDistNorm[i]) + 2 * (1 - wCoveNorm[i]) + \
            #             (1 - wRotNorm[i])) / (2**3 - 1)
            smoothFactor[goal] = coeff

        # Calculate costs
        goalGains = dict()
        for goal in brush:
            goalGains[goal] = priorWeight[goal] * smoothFactor[goal]

        # Choose goal with max gain 
        store_goal1 = set()
        for goal in brush:
            if goalGains[goal] == max(goalGains.values()):
                store_goal = goal
                rospy.loginfo("[Main Node] Goal1 at = [%u, %u]!!!", goal[0], goal[1])
                rospy.loginfo("The Gain1 is = %f!!", goalGains[goal])
            else:
                pass
                #rospy.logwarn("[Main Node] Did not find any goals :( ...")
                #self.target = self.selectRandomTarget(ogm, coverage, brush2, \
                #                        origin, ogm_limits, resolution)
#
#        goal = list(goal)
        goal = list(store_goal)
        print 'the ogm value is'
        #print ogm[int(goal1[0] - origin['x_px'])][int(goal1[1] - origin['y_px'])]
        print goal
        return goal





