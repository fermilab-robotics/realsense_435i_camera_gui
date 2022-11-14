#This is the file that gives functionality to the GUI. 
#The actual GUI is the GUI.py file

#Functions:
#GUI that connects to the designer file. 
#Buttons for starting and stopping color and video depth streams, as well as taking pictures of either. 
#Drop down menu options with icons that work to display things. (Yay!!!!) A bit jenky, but works, unless we 
#   change any sizing ratios, then we are going to have some issues. 
#The depth_frame.getDistance(x,y) has been checked to be fairly accurate on center (320, 240). (within 2 inches)
#The single point distance menu is now fully working, although points aside from the center may not be accurate. 


#Issues:
#This is using threading, but I may not be terminating things correctly? Especially the camera. (See note 3, definitely a thing)
#Right now some of this is static and not variable, for the sake of getting results. Should fix later though. 
#If you exit out of the GUI without stopping the video streams first you cause a segmentation fault. I need to fix that..
#This main file should definitely get broken up into a few smaller files

from contextlib import nullcontext
from tkinter import Frame
from PyQt5 import QtGui
from PyQt5.QtGui import QPixmap, QIcon
import sys
import cv2
from PyQt5.QtCore import pyqtSignal, pyqtSlot, Qt, QThread
import numpy as np
import pyrealsense2 as rs

from datetime import datetime
import time

from GUI import *

#This class is what allows us to actually get a video stream from the camera
class DepthCamera:
    def __init__(self):
        # Configure depth and color streams
        self.pipeline = rs.pipeline()
        config = rs.config()

        # Get device product line for setting a supporting resolution 
        pipeline_wrapper = rs.pipeline_wrapper(self.pipeline)
        pipeline_profile = config.resolve(pipeline_wrapper)
        device = pipeline_profile.get_device()
        device_product_line = str(device.get_info(rs.camera_info.product_line))

        config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
        config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)

        # Start streaming
        self.pipeline.start(config)

    def get_frame(self):
        frames = self.pipeline.wait_for_frames()
        depth_frame = frames.get_depth_frame()
        color_frame = frames.get_color_frame()
        #print(depth_frame)

        depth = round(depth_frame.get_distance(320, 240),3)

        depth_image = np.asanyarray(depth_frame.get_data())
        color_image = np.asanyarray(color_frame.get_data())

        #This line is necessary to apply color to the depth frame. (This may need to be reworked to get acurate color mapping) 
        depth_colormap = cv2.applyColorMap(cv2.convertScaleAbs(depth_image, alpha=0.10), cv2.COLORMAP_JET)
        
        if not depth_frame or not color_frame: #setting this to depth_colormap throws errors...
            return False, None, None, None
        return True, color_image, depth_colormap, depth_frame #depth_image #Need to export depth_frame too. 

    def release(self):
        self.pipeline.stop()

#This is the class that allows us to create a thread specifically to run the video feed so that the QT
#program can still do other functional things. 
class VideoThread(QThread):
    change_pixmap_signal = pyqtSignal(np.ndarray)
    change_pixmap_signal2 = pyqtSignal(np.ndarray)
    change_depth_signal = pyqtSignal(object) #What type is it??

    def __init__(self):
        super().__init__()
        self._run_flag = True

    dc = DepthCamera() #This has to be declared outside of run() to prevent multiple pipelines from being opened
    def run(self):
        # Get the actual images from the camera to then be processed below
        while self._run_flag:
            ret, cv_img, dv_img, depth_data = self.dc.get_frame()
            if ret:
                self.change_pixmap_signal.emit(cv_img)
                self.change_pixmap_signal2.emit(dv_img)
                self.change_depth_signal.emit(depth_data)
        # shut down capture system
        #cap.release()


    def stop(self):
        #Sets run flag to False and waits for thread to finish
        self._run_flag = False
        self.wait()
        self.quit()

#This is the class that is actually connecting to the GUI and adding functionality
class App(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self, window):
        #Set up the initial window
        super().__init__()
        ui = Ui_MainWindow()
        ui.setupUi(self)
        self.setupUi(window)

        #Connect all of the buttons to their functions
        self.StartColorVideo.clicked.connect(lambda state: self.colorStartThread())
        self.StopColorVideo.clicked.connect(lambda state: self.colorCloseEvent())

        self.StartDepthVideo.clicked.connect(lambda state: self.depthStartThread())
        self.StopDepthVideo.clicked.connect(lambda state: self.depthCloseEvent())

        self.SaveColorPic.clicked.connect(lambda state: self.colorPic())
        self.SaveDepthPic.clicked.connect(lambda state: self.depthPic())

        #Add in the icons because the UIC file doesn't know where the images are actually stored
        self.ExpandPoint.setIcon(QIcon("Icons/ExpandArrow.png"))
        self.ExpandLine.setIcon(QIcon("Icons/ExpandArrow.png"))
        self.ExpandMultiple.setIcon(QIcon("Icons/ExpandArrow.png"))
        self.ExpandRadius.setIcon(QIcon("Icons/ExpandArrow.png"))

        self.ExpandPoint.clicked.connect(lambda state: self.expandPointButton())
        self.ExpandLine.clicked.connect(lambda state: self.expandLineButton())
        self.ExpandMultiple.clicked.connect(lambda state: self.expandMultipleButton())
        self.ExpandRadius.clicked.connect(lambda state: self.expandRadiusButton())

        self.CalculatePointDistance.clicked.connect(lambda state: self.calculatePointDepth())
        self.ClearPointDistance.clicked.connect(lambda state: self.clearPointDepth())

    #All the expand functions are for handling expanding/collapsing the menu for that particular function.
    #It's technically all static, which isn't the best, but the videos are static, so okay??
    def expandPointButton(self):
        if(self.PointDistanceFrame.height() >= 255):
            self.ExpandPoint.setIcon(QIcon("Icons/ExpandArrow.png"))
            self.PointDistanceFrame.setMinimumSize(QtCore.QSize(603,44))
            self.PointDistanceFrame.setMaximumSize(QtCore.QSize(603,44))

        else:
            self.ExpandPoint.setIcon(QIcon("Icons/CollapseArrow.png"))
            self.ExpandLine.setIcon(QIcon("Icons/ExpandArrow.png"))
            self.ExpandMultiple.setIcon(QIcon("Icons/ExpandArrow.png"))
            self.ExpandRadius.setIcon(QIcon("Icons/ExpandArrow.png"))
            self.PointDistanceFrame.setMinimumSize(QtCore.QSize(603,255))
            self.PointDistanceFrame.setMaximumSize(QtCore.QSize(603,255))
            self.LineDistanceFrame.setMinimumSize(QtCore.QSize(603,44))
            self.LineDistanceFrame.setMaximumSize(QtCore.QSize(603,44))
            self.MultiplePointsFrame.setMinimumSize(QtCore.QSize(603,44))
            self.MultiplePointsFrame.setMaximumSize(QtCore.QSize(603,44))
            self.RadiusFrame.setMinimumSize(QtCore.QSize(603,44))
            self.RadiusFrame.setMaximumSize(QtCore.QSize(603,44))


    def expandLineButton(self):
        if(self.LineDistanceFrame.height() >= 255):
            self.ExpandLine.setIcon(QIcon("Icons/ExpandArrow.png"))
            self.LineDistanceFrame.setMinimumSize(QtCore.QSize(603,44))
            self.LineDistanceFrame.setMaximumSize(QtCore.QSize(603,44))

        else:
            self.ExpandLine.setIcon(QIcon("Icons/CollapseArrow.png"))
            self.ExpandPoint.setIcon(QIcon("Icons/ExpandArrow.png"))
            self.ExpandMultiple.setIcon(QIcon("Icons/ExpandArrow.png"))
            self.ExpandRadius.setIcon(QIcon("Icons/ExpandArrow.png"))
            self.PointDistanceFrame.setMinimumSize(QtCore.QSize(603,44))
            self.PointDistanceFrame.setMaximumSize(QtCore.QSize(603,44))
            self.LineDistanceFrame.setMinimumSize(QtCore.QSize(603,255))
            self.LineDistanceFrame.setMaximumSize(QtCore.QSize(603,255))
            self.MultiplePointsFrame.setMinimumSize(QtCore.QSize(603,44))
            self.MultiplePointsFrame.setMaximumSize(QtCore.QSize(603,44))
            self.RadiusFrame.setMinimumSize(QtCore.QSize(603,44))
            self.RadiusFrame.setMaximumSize(QtCore.QSize(603,44))

    def expandMultipleButton(self):
        if(self.MultiplePointsFrame.height() >= 255):
            self.ExpandMultiple.setIcon(QIcon("Icons/ExpandArrow.png"))
            self.MultiplePointsFrame.setMinimumSize(QtCore.QSize(603,44))
            self.MultiplePointsFrame.setMaximumSize(QtCore.QSize(603,44))
        
        else:
            self.ExpandMultiple.setIcon(QIcon("Icons/CollapseArrow.png"))
            self.ExpandPoint.setIcon(QIcon("Icons/ExpandArrow.png"))
            self.ExpandLine.setIcon(QIcon("Icons/ExpandArrow.png"))
            self.ExpandRadius.setIcon(QIcon("Icons/ExpandArrow.png"))
            self.PointDistanceFrame.setMinimumSize(QtCore.QSize(603,44))
            self.PointDistanceFrame.setMaximumSize(QtCore.QSize(603,44))
            self.LineDistanceFrame.setMinimumSize(QtCore.QSize(603,44))
            self.LineDistanceFrame.setMaximumSize(QtCore.QSize(603,44))
            self.MultiplePointsFrame.setMinimumSize(QtCore.QSize(603,255))
            self.MultiplePointsFrame.setMaximumSize(QtCore.QSize(603,255))
            self.RadiusFrame.setMinimumSize(QtCore.QSize(603,44))
            self.RadiusFrame.setMaximumSize(QtCore.QSize(603,44))

    def expandRadiusButton(self):
        if(self.RadiusFrame.height() >= 255):
            self.ExpandRadius.setIcon(QIcon("Icons/ExpandArrow.png"))
            self.RadiusFrame.setMinimumSize(QtCore.QSize(603,44))
            self.RadiusFrame.setMaximumSize(QtCore.QSize(603,44))

        else:
            self.ExpandRadius.setIcon(QIcon("Icons/CollapseArrow.png"))
            self.ExpandPoint.setIcon(QIcon("Icons/ExpandArrow.png"))
            self.ExpandLine.setIcon(QIcon("Icons/ExpandArrow.png"))
            self.ExpandMultiple.setIcon(QIcon("Icons/ExpandArrow.png"))
            self.PointDistanceFrame.setMinimumSize(QtCore.QSize(603,44))
            self.PointDistanceFrame.setMaximumSize(QtCore.QSize(603,44))
            self.LineDistanceFrame.setMinimumSize(QtCore.QSize(603,44))
            self.LineDistanceFrame.setMaximumSize(QtCore.QSize(603,44))
            self.MultiplePointsFrame.setMinimumSize(QtCore.QSize(603,44))
            self.MultiplePointsFrame.setMaximumSize(QtCore.QSize(603,44))
            self.RadiusFrame.setMinimumSize(QtCore.QSize(603,255))
            self.RadiusFrame.setMaximumSize(QtCore.QSize(603,255))

    #Variables to make sure all threads are terminated at end of program run. 
    T1 = False #T1/thread1 = color video thread
    T2 = False #T2/thread2 = depth video thread
    T3 = False #T3/thread3 = depth image thread for depth calculations. 

    #Again with the static variables, the stops could definitely be combined, starts could maybe as well. 
    def colorCloseEvent(self):
        self.thread1.stop()
        self.T1 = False
        if (not self.T2 ): 
            self.thread3.stop() 
            self.T3 = False
        #event.accept()

    def depthCloseEvent(self):
        self.thread2.stop()
        self.T2 = False
        if (not self.T1): 
            self.thread3.stop()
            self.T3 = False
        #event.accept()

    def colorStartThread(self):
        self.thread1 = VideoThread() #Create a thread to get the video image
        self.thread1.change_pixmap_signal.connect(self.update_color_image) #Connect its signal to the update_image slot
        self.thread1.start() #Start the thread
        self.T1 = True
        if (not self.T3): self.depthDataStart() #Also start the data thread

    def depthStartThread(self):
        self.thread2 = VideoThread() #Create a thread to get the depth image
        self.thread2.change_pixmap_signal2.connect(self.update_depth_image) #Connect its signal to the update_image slot
        self.thread2.start() #Start the thread
        self.T2 = True
        if (not self.T3): self.depthDataStart() #Also start the data thread

    def depthDataStart(self):
        self.thread3 = VideoThread() #Create a thread to get the depth data stream
        self.thread3.change_depth_signal.connect(self.update_Depth)
        self.thread3.start()
        self.T3 = True

    #Capture and save a picture from color or depth feeds. These work if the video is live streaming or not. 
    def colorPic(self):
        ret, color_image, depth_image, unused = self.thread1.dc.get_frame()
        now = datetime.now()
        dtstring = now.strftime("%d:%m:%Y %H:%M:%S")
        picName = "Color Image " + dtstring + ".jpeg"
        cv2.imwrite("../../Desktop/" + picName, color_image)

    def depthPic(self):
        ret, color_image, depth_image, unused = self.thread2.dc.get_frame()
        now = datetime.now()
        dtstring = now.strftime("%d:%m:%Y %H:%M:%S")
        picName = "Depth Image " + dtstring + ".jpeg"
        cv2.imwrite("../../Desktop/" + picName, depth_image) #Home/Documents/Realsense 435i Project/

    depth = 0.00 #Varable for point depth. 
    gPointX = 0
    gPointY = 0
    showPoint = False #Show dot on depth video
    showPointDistance = False #Bool for updating PointDistance display

    #Function to get the point coords entered by user & display depth. 
    def calculatePointDepth(self):
        self.gPointX = int(self.PointX.toPlainText()) #Get the entered point coords from the GUI
        self.gPointY = int(self.PointY.toPlainText())
        self.showPoint = True #Show the distance and circle on the depth video stream
        self.showPointDistance = True

    #Function to clear the point depth coords, point distance. 
    def clearPointDepth(self):
        self.gPointX = 0 
        self.gPointY = 0
        self.PointX.clear()
        self.PointY.clear()
        self.PointDistance.clear()
        self.showPoint = False


    #Connecting the actual Qt slots to the video feeds so they can be displayed
    @pyqtSlot(np.ndarray) #This line can be optional 
    def update_color_image(self, cv_img):
        #Updates the image_label with a new opencv image
        qt_img = self.convert_cv_qt(cv_img)
        self.ColorVideo.setPixmap(qt_img) #self.image_label.setPixmap(qt_img)

    def update_depth_image(self, dv_img):
        #Updates the image_label with a new opencv image
        circleImg = dv_img
        if (self.showPoint): #Display the circle on the depth feed. 
            point = (self.gPointX, self.gPointY)
            circleImg = cv2.circle(dv_img, point, 10, (57, 255, 20), -1)
        qt_img = self.convert_cv_qt(circleImg)
        self.DepthVideo.setPixmap(qt_img) #self.image_label.setPixmap(qt_img)
    
    def convert_cv_qt(self, cv_img):
        #Convert from an opencv image to QPixmap
        rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        convert_to_Qt_format = QtGui.QImage(rgb_image.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
        p = convert_to_Qt_format.scaled(640, 480, Qt.KeepAspectRatio) #static setting right now, make variable at some point?
        return QPixmap.fromImage(p)

    @pyqtSlot(object)
    #Slot dedicated to depth measurements given an incoming stream of depth images. 
    def update_Depth(self, depth_frame):
        #x, y = 320, 240
        self.depth = depth_frame.get_distance(self.gPointX, self.gPointY)
        if (self.showPointDistance): #The bool allows the point distance to be set instantly and accurately. 
            self.PointDistance.setText(str(round(self.depth, 5)))
            self.showPointDistance = False #If not reset, then can have a running display of the point distance. Maybe useful?
        
        #depth = depth_frame[y,x] #object type not subscriptable. Sigh. 
        #print("distance: " + str(round(self.depth, 5)))


#The stuff necessary to actually show the window
if __name__=="__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = QtWidgets.QMainWindow()
    a = App(w)
    w.show() #a.show()
    sys.exit(app.exec_())