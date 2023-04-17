#This is the file that gives functionality to the GUI. 
#The actual GUI is the GUI.py file

#Functions:
#GUI that connects to the designer file. 
#Buttons for starting and stopping color and video depth streams, as well as taking pictures of either. 
#Drop down menu options with icons that work to display things. (Yay!!!!) A bit jenky, but works, unless we 
#   change any sizing ratios, then we are going to have some issues. 
#The depth_frame.getDistance(x,y) has been checked to be fairly accurate on center (320, 240). (within 2 inches)
#The single point distance menu is now fully working, although points aside from the center may not be accurate.
# You can click on a point in either color or depth video feeds to get the coordinates for distance calculations.  
# The line distance menu is complete. You can click or type in points, edit them afterwards typed, draw line, and
#  get the distance between the two points. I think the distance is decently accurate too, the depth feed isn't
#  perfect and shadows can wreak havoc (Points in shadows become (null, null) which kills distance calculations.) 
#You can record a .bag file (the length is currently set only in the code)
#You can then load a .bag file from the GUI and it will play on a loop. You can also take measurements from it, although
#  right now everything is moving, so I really need a pause function for this to be truly useful. 


#Issues:
#Right now some of this is static and not variable, for the sake of getting results. Should fix later though. 
#This main file should definitely get broken up into a few smaller files
#Right now the recorded video just plays in an endless loop, I need a pause button, and a fastforward or reverse would be realy nice. 
#Right now you can only load .bag files stored in the program folder, I'm not sure why. 
#When you pause a video, take a measurement, and then hit clear, it still displays the circles/lines on the screen. 
#Pause is kind of working, but it's still a little weird. I had to add in a delay between sending back the saved frame,
#   and I still don't understand why it's hitting in the order it is. 
#When paused, frames aren't arriving quite like they should be, and the clear button doesn't work. It's like they're all 
#   being saved on the original saved image. Everything fixes as soon as you start playing again. 


#TODO
#I need to do more testing on the distance between two points. I think if you mark it on the depth video where you can make sure 
#  the depth feed is actually seeing it it's actually almost dead on. Within 2cm, and that's with me trying to be conservative on clicking. 
#Rework the video and depth feeds to have a single overlay instead of manually applying it both times. Will require reworking code
# as well as reworking the GUI layout. (PyQt5 doesn't like overlays) 
#Add in pause and play buttons, fast forward and rewind would be nice.  

#Future Features
#1. Fix the clear issue for taking measurements on paused videos
#2. Allow the user to pick what the saved dataset is named
#3. Fix the loading dataset issue from any folder other than the programs current one
#4. A 1 minute .bag file is 2.9GB long. Holy cow. That's not sustanable. 
#5. Stopping recording is throwing a pipeline error, same as when pausing, frame requests are getting sent after pipeline closed.  

from PyQt5 import QtGui
from PyQt5.QtGui import QPixmap, QIcon, QCursor, QPainter, QPen
from PyQt5.QtWidgets import QFileDialog
import sys
import cv2
import math
from PyQt5.QtCore import pyqtSignal, pyqtSlot, Qt, QThread, QTimer 
import numpy as np
import pyrealsense2 as rs
import time



from datetime import datetime, timedelta

from GUI import *

#This class is what allows us to actually get a video stream from the camera
class DepthCamera:
    depth_scale = 0
    color_intrin = []
    #global pipeline 
    pipelineStarted = False
    recordingPipelineStarted = False
    replayPipelineStarted = False
    paused = False
    i = 0

    svar = None
    scolor_image = None
    sdepth_colormap = None
    sdepth_frame = None

    def startPipeline(self): #def __init__(self):#This is called as soon as the GUI starts. I wonder if I broke it out into a different class if it might not be?
        # Configure depth and color streams
        self.pipeline = rs.pipeline()
        config = rs.config()

        # Get device product line for setting a supporting resolution 
        pipeline_wrapper = rs.pipeline_wrapper(self.pipeline)
        pipeline_profile = config.resolve(pipeline_wrapper)
        device = pipeline_profile.get_device()
        device_product_line = str(device.get_info(rs.camera_info.product_line))
        self.depth_scale = device.first_depth_sensor().get_depth_scale() #get the depth scale. Not sure if this is the right place to declare this or not. 

        config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
        config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)

        # Start streaming
        self.pipeline.start(config)
        print("pipeline started\n")
        self.pipelineStarted = True

    def startRecordingPipeline(self):
        self.pipeline = rs.pipeline()
        config = rs.config()
        config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
        config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)

        config.enable_record_to_file("BagFileTest.bag")
        self.pipeline.start(config)
        self.recordingPipelineStarted = True
        print("Recording pipeline started")

    def startReplayPipeline(self): #Need to be able to pass in the file name. 
        self.pipeline = rs.pipeline()
        config = rs.config()
        fileName = FileName.fName
        print(fileName)
        rs.config.enable_device_from_file(config, fileName)
        config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
        config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
        profile = self.pipeline.start(config)
        self.playback = profile.get_device().as_playback()
        self.playback.pause()
        FileName.videoLength = self.playback.get_duration() #This gets the length of the .bag in seconds. 
        #print(str(t.seconds))
        self.playback.resume()
        #self.playback.set_real_time(False) #This makes it play back at a fast speed. 
        
        self.replayPipelineStarted = True
        print("Pre-Recorded Pipeline Started")

    firstFrame = False

    def get_frame(self):
        #If the datastream is paused, just keep sending the last data received. So simple in theory. 
        if(self.firstFrame and self.paused): #This is never getting called because of the VideoThread Run function. 
            print("We should be hitting here, but I bet we aren't")
            return self.svar, self.scolor_image, self.sdepth_colormap, self.sdepth_frame 
        
        if (not self.paused):

            frame_present, frames = self.pipeline.try_wait_for_frames() #This returns a bool if there aren't any frames
            
            #This step is necessary so that the depth and video feeds are showing the same thing. Otherwise they are offset. 
            #I'm combining from color to depth because depth to color compromises the color video feed dramatically. 
            align = rs.align(rs.stream.color)
            if (not frame_present): 
                print ("Frame not present")
                return self.svar, self.scolor_image, self.sdepth_colormap, self.sdepth_frame
            
            frames = align.process(frames) 

            depth_frame = frames.get_depth_frame()
            color_frame = frames.get_color_frame()

            self.color_intrin = color_frame.profile.as_video_stream_profile().intrinsics #This is another set value, at least for when we'll be using it. 

            depth_image = np.asanyarray(depth_frame.get_data())
            color_image = np.asanyarray(color_frame.get_data())

            #This line is necessary to apply color to the depth frame. (This may need to be reworked to get acurate color mapping) 
            depth_colormap = cv2.applyColorMap(cv2.convertScaleAbs(depth_image, alpha=0.10), cv2.COLORMAP_JET)

            self.firstFrame = True
            
            #print("Normal acknowledge") 
            if(self.paused): #This is getting hit sometimes, which is interesting. 
                print("Are we ever hitting this??")
                return self.svar, self.scolor_image, self.sdepth_colormap, self.sdepth_frame       
            
            elif (not depth_frame or not color_frame and not self.paused): #setting this to depth_colormap throws errors...
                self.saveFrames(False, None, None, None)
                return False, None, None, None
            else: 
                self.saveFrames(True, color_image, depth_colormap, depth_frame)
                return True, color_image, depth_colormap, depth_frame #depth_image #Need to export depth_frame too. 
            
        else:
            return self.svar, self.scolor_image, self.sdepth_colormap, self.sdepth_frame
        
        #return self.svar, self.scolor_image, self.sdepth_colormap, self.sdepth_frame
    
    def saveFrames(self, var, color_image, depth_colormap, depth_frame):
        self.svar = var
        self.scolor_image = color_image
        self.sdepth_colormap = depth_colormap
        self.sdepth_frame = depth_frame

    def returnSavedFrame(self):
        time.sleep(0.03) #This has to be included otherwise it just spams frames and freezes out. 
        #print("Returning saved frame...")
        return self.svar, self.scolor_image, self.sdepth_colormap, self.sdepth_frame #self.sdepth_colormap


    #I don't think this is valid, pipeline is declared in init, so it's not global. 
    def stopPipeline(self):
        self.pipeline.stop()
        print("Pipeline stopped\n")
        self.pipelineStarted = False
        self.recordingPipelineStarted = False
        self.replayPipelineStarted = False
        self.firstFrame = False

    def pausePipeline(self):
        #print("Actual pause called")
        self.paused = True #Order may matter here, need to save frame before actually stopping the pipeline.
        #self.playback.pause()
        #self.paused = True
    
    def finalPause(self):
        #print("actual final pause called")
        self.paused = True
        self.playback.pause()
        

    def playPipeline(self):
        self.paused = False
        self.playback.resume()
        #self.paused = False
        

#This is the class that allows us to create a thread specifically to run the video feed so that the QT
#program can still do other functional things. 
class VideoThread(QThread):

    dc = DepthCamera() #This has to be declared outside of run() to prevent multiple pipelines from being opened   
    
    #Test variable to allow us to get depth_frame more easily. 
    depth_frame_holder = None #This works!!! Or at least it stores something, TODO: Make sure this is updating! (I think it is)
    change_pixmap_signal = pyqtSignal(np.ndarray)
    change_pixmap_signal2 = pyqtSignal(np.ndarray)
    change_depth_signal = pyqtSignal(object) #What type is it?? - any or None. Basically doesn't have a type. 

    def __init__(self, pipeline):
        super().__init__()
        self._run_flag = True
        if(self.dc.pipelineStarted == False and pipeline == "live"): self.dc.startPipeline() 
        if(self.dc.recordingPipelineStarted == False and pipeline == "record"): self.dc.startRecordingPipeline() 
        if(self.dc.replayPipelineStarted == False and pipeline == "replay"): self.dc.startReplayPipeline()
    
    def run(self):
        # Get the actual images from the camera to then be processed below
        while self._run_flag:
            
            if(self.dc.paused):
                print("Refreshing via saved data")
                ret, cv_img, dv_img, depth_data = self.dc.returnSavedFrame()
            
            else: ret, cv_img, dv_img, depth_data = self.dc.get_frame()
            
            if ret:
                    self.change_pixmap_signal.emit(cv_img)
                    self.change_pixmap_signal2.emit(dv_img)
                    self.change_depth_signal.emit(depth_data)
                    self.depth_frame_holder = depth_data

        # shut down capture system
        #cap.release()

    def lastStop(self):
        self.dc.stopPipeline() #Apparently this causes a whole slew of confusion. 
        self._run_flag = False
        self.wait()
        self.quit()

    def stop(self):
        #Sets run flag to False and waits for thread to finish
        self._run_flag = False
        self.wait()
        self.quit()

    def pause(self):
        #print("one of first two pause's called ex")
        self.dc.pausePipeline()
        print(self.dc.paused)

    def finalPause(self):
        #print("Final pause called ex")
        self.dc.finalPause()        

    def play(self):
        print("Play called")
        self.dc.playPipeline()

#Class used sheerly to move a variable from one class to the other. I suspect this is very bad practice. 
class FileName:
    fName = "test"#/home/susanna/Documents/realsense_435i_camera_gui/BagFileTest.bag" #The issue is probably getting from the original location to the code base location.
    videoLength = 0

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

        #self.StartDepthVideo.clicked.connect(lambda state: self.depthStartThread())
        #self.StopDepthVideo.clicked.connect(lambda state: self.depthCloseEvent())

        self.SaveColorPic.clicked.connect(lambda state: self.colorPic(None))
        self.SaveDepthPic.clicked.connect(lambda state: self.depthPic(None))

        #Add in the icons because the UIC file doesn't know where the images are actually stored
        self.ExpandPoint.setIcon(QIcon("Icons/ExpandArrow.png"))
        self.ExpandLine.setIcon(QIcon("Icons/ExpandArrow.png"))
        self.ExpandMultiple.setIcon(QIcon("Icons/ExpandArrow.png"))
        self.ExpandRadius.setIcon(QIcon("Icons/ExpandArrow.png"))
        self.LiveVideoExpand.setIcon(QIcon("Icons/ExpandArrow.png"))
        self.SavedDataExpand.setIcon(QIcon("Icons/ExpandArrow.png"))
        self.SavePicExpand.setIcon(QIcon("Icons/ExpandArrow.png"))
        self.DatasetExpand.setIcon(QIcon("Icons/ExpandArrow.png"))
        self.Pause.setIcon(QIcon("Icons/Pause.png"))
        self.Play.setIcon(QIcon("Icons/Play.png"))

        #self.ColorOverlay.setWindowTitle("Test Run")
        #self.ColorOverlay.setWindowOpacity(0.5)
        #self.DepthOverlay.setWindowOpacity(0)

        self.ExpandPoint.clicked.connect(lambda state: self.expandPointButton())
        self.ExpandLine.clicked.connect(lambda state: self.expandLineButton())
        self.ExpandMultiple.clicked.connect(lambda state: self.expandMultipleButton())
        self.ExpandRadius.clicked.connect(lambda state: self.expandRadiusButton())

        self.LiveVideoExpand.clicked.connect(lambda state: self.expandLiveVideo())
        self.SavedDataExpand.clicked.connect(lambda state: self.expandSavedData())
        self.SavePicExpand.clicked.connect(lambda state: self.expandPicSave())
        self.DatasetExpand.clicked.connect(lambda state: self.expandDataSave())

        self.PointSelect.clicked.connect(lambda state: self.enterPoint())
        self.CalculatePointDistance.clicked.connect(lambda state: self.calculatePointDepth())
        self.ClearPointDistance.clicked.connect(lambda state: self.clearPointDepth())

        self.LinePoint1.clicked.connect(lambda state: self.enterLinePoint1())
        self.LinePoint2.clicked.connect(lambda state: self.enterLinePoint2())
        self.ClearLineDistance.clicked.connect(lambda state: self.clearLineDistance())
        self.CalculateLineDistance.clicked.connect(lambda state: self.calculateLineDistance())
        self.DrawLine.clicked.connect(lambda state: self.showLineFunction())
        
        #Get the coordinates from either color or depth video stream mouse clicks. 
        self.ColorVideo.mousePressEvent = self.getPosition 
        self.DepthVideo.mousePressEvent = self.getPosition

        self.LoadDataButton.clicked.connect(lambda state: self.loadDataset())
        #self.SaveDatasetButton.clicked.connect(lambda state: self.saveDataset()) #Need to update this function...
        self.StartRecording.clicked.connect(lambda state: self.saveDataset()) 
        self.StopRecording.clicked.connect(lambda state: self.stopSaveDataset())

        self.Play.clicked.connect(lambda state: self.playDataset())
        self.Pause.clicked.connect(lambda state: self.pauseDataset())

        #if(time.time() - self.start > 5): self.colorCloseEvent()


    #Bools to tell when to register clicks on the video streams for distance measurements. Flipped in expand functions.     
    pointCoordinate = False
    lineCoordinate = False

    #All the expand functions are for handling expanding/collapsing the menu for that particular function.
    #It's technically all static, which isn't the best, but the videos are static, so okay??
    def expandPointButton(self):
        if(self.PointDistanceFrame.height() >= 255):
            self.ExpandPoint.setIcon(QIcon("Icons/ExpandArrow.png"))
            self.PointDistanceFrame.setMinimumSize(QtCore.QSize(603,44))
            self.PointDistanceFrame.setMaximumSize(QtCore.QSize(603,44))
            self.pointCoordinate = False
            self.showPoint = False
            self.ColorVideo.setCursor(QCursor(QtCore.Qt.ArrowCursor))
            self.DepthVideo.setCursor(QCursor(QtCore.Qt.ArrowCursor))

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
            self.pointCoordinate = True
            self.lineCoordinate = False
            self.showLinePoint1 = False
            self.showLinePoint2 = False


    def expandLineButton(self):
        if(self.LineDistanceFrame.height() >= 255):
            self.ExpandLine.setIcon(QIcon("Icons/ExpandArrow.png"))
            self.LineDistanceFrame.setMinimumSize(QtCore.QSize(603,44))
            self.LineDistanceFrame.setMaximumSize(QtCore.QSize(603,44))
            self.lineCoordinate = False
            self.showLinePoint1 = False
            self.showLinePoint2 = False
            self.showLine = False
            self.ColorVideo.setCursor(QCursor(QtCore.Qt.ArrowCursor))
            self.DepthVideo.setCursor(QCursor(QtCore.Qt.ArrowCursor))

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
            self.lineCoordinate = True
            self.pointCoordinate = False
            self.showPoint = False

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

    def expandLiveVideo(self):
        if(self.VideoControlsFrame.height() >= 170):
            self.LiveVideoExpand.setIcon(QIcon("Icons/ExpandArrow.png"))
            self.VideoControlsFrame.setMinimumSize(QtCore.QSize(603, 44))
            self.VideoControlsFrame.setMaximumSize(QtCore.QSize(603, 44))

        else:
            self.VideoControlsFrame.setMinimumSize(QtCore.QSize(603, 170))
            self.VideoControlsFrame.setMaximumSize(QtCore.QSize(603, 170))
            self.LiveVideoExpand.setIcon(QIcon("Icons/CollapseArrow.png"))
            self.SavedDataExpand.setIcon(QIcon("Icons/ExpandArrow.png"))
            self.SavePicExpand.setIcon(QIcon("Icons/ExpandArrow.png"))
            self.DatasetExpand.setIcon(QIcon("Icons/ExpandArrow.png"))
            self.SavedDataFrame.setMinimumSize(QtCore.QSize(603, 44))
            self.SavedDataFrame.setMaximumSize(QtCore.QSize(603, 44))
            self.SavePicFrame.setMinimumSize(QtCore.QSize(603, 44))
            self.SavePicFrame.setMaximumSize(QtCore.QSize(603, 44))
            self.SaveDatasetFrame.setMinimumSize(QtCore.QSize(603, 44))
            self.SaveDatasetFrame.setMaximumSize(QtCore.QSize(603, 44))


    def expandSavedData(self):
        if(self.SavedDataFrame.height() >= 170):
            self.SavedDataExpand.setIcon(QIcon("Icons/ExpandArrow.png"))
            self.SavedDataFrame.setMinimumSize(QtCore.QSize(603, 44))
            self.SavedDataFrame.setMaximumSize(QtCore.QSize(603, 44))

        else:
            self.SavedDataFrame.setMinimumSize(QtCore.QSize(603, 200))
            self.SavedDataFrame.setMaximumSize(QtCore.QSize(603, 200))
            self.SavedDataExpand.setIcon(QIcon("Icons/CollapseArrow.png"))
            self.LiveVideoExpand.setIcon(QIcon("Icons/ExpandArrow.png"))
            self.SavePicExpand.setIcon(QIcon("Icons/ExpandArrow.png"))
            self.DatasetExpand.setIcon(QIcon("Icons/ExpandArrow.png"))
            self.VideoControlsFrame.setMinimumSize(QtCore.QSize(603, 44))
            self.VideoControlsFrame.setMaximumSize(QtCore.QSize(603, 44))
            self.SavePicFrame.setMinimumSize(QtCore.QSize(603, 44))
            self.SavePicFrame.setMaximumSize(QtCore.QSize(603, 44))
            self.SaveDatasetFrame.setMinimumSize(QtCore.QSize(603, 44))
            self.SaveDatasetFrame.setMaximumSize(QtCore.QSize(603, 44))

 
    def expandPicSave(self):
        if(self.SavePicFrame.height() >= 200):
            self.SavePicExpand.setIcon(QIcon("Icons/ExpandArrow.png"))
            self.SavePicFrame.setMinimumSize(QtCore.QSize(603, 44))
            self.SavePicFrame.setMaximumSize(QtCore.QSize(603, 44))

        else:
            self.SavePicFrame.setMinimumSize(QtCore.QSize(603, 200))
            self.SavePicFrame.setMaximumSize(QtCore.QSize(603, 200))
            self.SavePicExpand.setIcon(QIcon("Icons/CollapseArrow.png"))
            self.SavedDataExpand.setIcon(QIcon("Icons/ExpandArrow.png"))
            self.LiveVideoExpand.setIcon(QIcon("Icons/ExpandArrow.png"))
            self.DatasetExpand.setIcon(QIcon("Icons/ExpandArrow.png"))
            self.SavedDataFrame.setMinimumSize(QtCore.QSize(603, 44))
            self.SavedDataFrame.setMaximumSize(QtCore.QSize(603, 44))
            self.VideoControlsFrame.setMinimumSize(QtCore.QSize(603, 44))
            self.VideoControlsFrame.setMaximumSize(QtCore.QSize(603, 44))
            self.SaveDatasetFrame.setMinimumSize(QtCore.QSize(603, 44))
            self.SaveDatasetFrame.setMaximumSize(QtCore.QSize(603, 44))

    def expandDataSave(self):
        if(self.SaveDatasetFrame.height() >= 200):
            self.DatasetExpand.setIcon(QIcon("Icons/ExpandArrow.png"))
            self.SaveDatasetFrame.setMinimumSize(QtCore.QSize(603, 44))
            self.SaveDatasetFrame.setMaximumSize(QtCore.QSize(603, 44))

        else:
            self.SaveDatasetFrame.setMinimumSize(QtCore.QSize(603, 200))
            self.SaveDatasetFrame.setMaximumSize(QtCore.QSize(603, 200))
            self.DatasetExpand.setIcon(QIcon("Icons/CollapseArrow.png"))
            self.SavedDataExpand.setIcon(QIcon("Icons/ExpandArrow.png"))
            self.LiveVideoExpand.setIcon(QIcon("Icons/ExpandArrow.png"))
            self.SavePicExpand.setIcon(QIcon("Icons/ExpandArrow.png"))
            self.SavedDataFrame.setMinimumSize(QtCore.QSize(603, 44))
            self.SavedDataFrame.setMaximumSize(QtCore.QSize(603, 44))
            self.VideoControlsFrame.setMinimumSize(QtCore.QSize(603, 44))
            self.VideoControlsFrame.setMaximumSize(QtCore.QSize(603, 44))
            self.SavePicFrame.setMinimumSize(QtCore.QSize(603, 44))
            self.SavePicFrame.setMaximumSize(QtCore.QSize(603, 44))
        
    #Variables to make sure all threads are terminated at end of program run. 
    #T1 = False #T1/thread1 = color video thread
    #T2 = False #T2/thread2 = depth video thread
    #T3 = False #T3/thread3 = depth image thread for depth calculations. 

    #Again with the static variables, the stops could definitely be combined, starts could maybe as well. 
    
    def colorCloseEvent(self):
        self.thread1.stop()
        self.thread2.stop()
        self.thread3.lastStop() #The pipeline itself has to be stopped right before the very last thread is stopped. 
        self.colorPipelineRunning = False
        self.recordingPipelineRunning = False
        self.replayPipelineRunning = False


    colorPipelineRunning = False
    recordingPipelineRunning = False
    replayPipelineRunning = False
    #There used to be individual start/stop buttons for depth and color video, now they're just combined into one. 
    def colorStartThread(self):
        if (self.recordingPipelineRunning or self.replayPipelineRunning): self.colorCloseEvent() #Stop the recording pipeline if it's running

        self.thread1 = VideoThread("live") #Create a thread to get the video image
        self.thread1.change_pixmap_signal.connect(self.update_color_image) #Connect its signal to the update_image slot
        self.thread1.start() #Start the thread

        self.thread2 = VideoThread("live") #Create a thread to get the depth image
        self.thread2.change_pixmap_signal2.connect(self.update_depth_image) #Connect its signal to the update_image slot
        self.thread2.start() #Start the thread

        self.depthDataStart("live") #Start the data thread too. 
        self.colorPipelineRunning = True

    def depthDataStart(self, x):
        self.thread3 = VideoThread(x) #Create a thread to get the depth data stream
        self.thread3.change_depth_signal.connect(self.update_Depth)
        self.thread3.start()
        #self.T3 = True

    #Capture and save a picture from color or depth feeds. These work if the video is live streaming or not. 
    def colorPic(self, x): 
        self.MainBody.setCursor(QCursor(QtCore.Qt.WaitCursor))
        ret, color_image, depth_image, unused = self.thread1.dc.get_frame()
        now = datetime.now()
        dtstring = now.strftime("%d:%m:%Y %H:%M:%S")
        if (isinstance(x, str)): picName = "color.jpeg" #This is so that datasets can be saved with a common name
        else: picName = "Color Image " + dtstring + ".jpeg"
        cv2.imwrite("../../Desktop/" + picName, color_image)
        self.MainBody.setCursor(QCursor(QtCore.Qt.ArrowCursor))

    def depthPic(self, x):
        self.MainBody.setCursor(QCursor(QtCore.Qt.WaitCursor))
        ret, color_image, depth_image, unused = self.thread2.dc.get_frame()
        now = datetime.now()
        dtstring = now.strftime("%d:%m:%Y %H:%M:%S")
        if(isinstance(x, str)): picName = "depth.jpeg"
        else: picName = "Depth Image " + dtstring + ".jpeg"
        cv2.imwrite("../../Desktop/" + picName, depth_image) #Home/Documents/Realsense 435i Project/
        self.MainBody.setCursor(QCursor(QtCore.Qt.ArrowCursor))

    #def loadDataset(self): #This just loads the pictures...
    #    fname = QFileDialog.getExistingDirectory(self, "Select a Directory") #load a directory name
    #    print("This is directory name: " + fname)
    #    cName = fname + "/color.jpeg"
    #    cPix = QPixmap(cName)
    #    dName = fname + "/depth.jpeg"
    #    dPix = QPixmap(dName)
    #    self.ColorVideo.setPixmap(cPix) #This sets the video frames to display the pictures. Yay!!! 
    #    self.DepthVideo.setPixmap(dPix)
    #    fname = fname + "/fileName.txt"
    #    file1 = open(fname, "r+")
    #    print(file1.readline())
   
    def loadDataset(self):
        fname = QFileDialog.getOpenFileName(self, "Open File", "", "ROS Files(*.bag)") #"Python Files(*.py) ;; Text Files(*.txt)") #To load a single file
        fileName = fname[0]
        FileName.fName = fileName
        print("This is the file name: " + fname[0])


        self.thread1 = VideoThread("replay")
        self.thread1.change_pixmap_signal.connect(self.update_color_image) #Connect its signal to the update_image slot
        self.thread1.start() #Start the thread

        self.thread2 = VideoThread("replay") #Create a thread to get the depth image
        self.thread2.change_pixmap_signal2.connect(self.update_depth_image) #Connect its signal to the update_image slot
        self.thread2.start() #Start the thread

        self.depthDataStart("replay") #Start the data thread too. 
        self.replayPipelineRunning = True

    #Functionallity for the play and pause buttons
    def pauseDataset(self):
        self.thread1.pause()
        self.thread2.pause()
        self.thread3.pause()
        
        #time.sleep(100) #Try adding in a delay. Delay doesn't seem to be necessary
        self.thread1.finalPause()
        self.thread2.finalPause()
        self.thread3.finalPause()
        print("Done calling pauses")

    def playDataset(self):
        self.thread1.play()
        self.thread2.play()
        self.thread3.play()

    recordingStart = 0 #Variable timing how long the recording is getting
    recording = False

    def saveDataset(self): 

        if(self.colorPipelineRunning or self.replayPipelineRunning): self.colorCloseEvent() #Stop all previously running threads/pipeline so the data save pipeline can be opened. 

        self.timer = QtCore.QTimer(self)
        self.timer.setSingleShot(True)

        self.thread1 = VideoThread("record")
        self.thread1.change_pixmap_signal.connect(self.update_color_image) #Connect its signal to the update_image slot
        self.thread1.start() #Start the thread

        self.thread2 = VideoThread("record") #Create a thread to get the depth image
        self.thread2.change_pixmap_signal2.connect(self.update_depth_image) #Connect its signal to the update_image slot
        self.thread2.start() #Start the thread

        self.depthDataStart("record") #Start the data thread too. 
        self.recordingPipelineRunning = True
        self.recordingStart = time.time() #Should get current time
        self.timer.singleShot(1000, self.updateRecordTime)
        #This allows the recording to be stopped after a certain length of time. TIME LIMIT = 5 minutes.  
        #TODO: This is going to really mess with things if it's already been stopped. 
        #self.start = time.time()
        #self.timer.singleShot(300000, self.colorCloseEvent) #Can't include paranthesis, it really screws things up.

    def updateRecordTime(self):
        tLength = int(time.time() - self.recordingStart)
        hours = str(int(tLength / 3600))
        minutes = str(int((tLength % 3600)/60))
        seconds = str(tLength % 60)
        if(len(hours) < 2) : hours = '0'+ hours
        if(len(minutes) < 2): minutes = '0'+ minutes
        if(len(seconds) < 2): seconds = '0'+ seconds
        
        #print(tLength)
        t = hours + ':' + minutes + ':' + seconds
        self.RecordingLength.setText(t)

        if(self.recordingPipelineRunning): #If we're still recording, keep updating the time. 
            self.timer = QtCore.QTimer(self)
            self.timer.setSingleShot(True)
            self.timer.singleShot(1000, self.updateRecordTime) 
        

    def stopSaveDataset(self):
        self.colorCloseEvent() #Stop the pipeline
        self.updateRecordTime() #Stop the timer

    #Bools for getting and displaying point depth
    pointDepth = 0.00 #Varable for point depth. 
    gPointX = 0
    gPointY = 0
    showPoint = False #Show dot on depth video
    noTwoSinglePoints = False #Show only one dot on video feeds. Sigh. No, this shouldn't be needed. 
    showPointDistance = False #Bool for updating PointDistance display

    #Bools for getting and displaying line distances. 
    showLinePoint1 = False
    showLinePoint2 = False
    linePoint1 = False
    linePoint2 = False
    lPointX1 = 0
    lPointX2 = 0
    lPointY1 = 0
    lPointY2 = 0
    lPointDepth1 = 0.00
    lPointDepth2 = 0.00
    lineDistance = 0.00
    showLineDistance = False
    showLine = False

    def enterPoint(self):
        self.showPoint = True
        self.PointSelect.setStyleSheet("QPushButton {background-color : rgb(255,173,0); }")
        self.ColorVideo.setCursor(QCursor(QtCore.Qt.CrossCursor)) #Change the cursor when over the videos
        self.DepthVideo.setCursor(QCursor(QtCore.Qt.CrossCursor))

    def enterLinePoint1(self):
        self.showLinePoint1 = True
        if(self.showLinePoint2 and self.LinePoint2.isEnabled()): #If the other function clicked and if button is still enabled
            self.showLinePoint2 = False
            self.LinePoint2.setStyleSheet("QPushButton {background-color : white;}")

        self.LinePoint1.setStyleSheet("QPushButton {background-color: rgb(57,255,20);}")
        self.ColorVideo.setCursor(QCursor(QtCore.Qt.CrossCursor))
        self.DepthVideo.setCursor(QCursor(QtCore.Qt.CrossCursor))

    def enterLinePoint2(self):
        self.showLinePoint2 = True
        if(self.showLinePoint1 and self.LinePoint1.isEnabled()):
            self.showLinePoint1 = False
            self.LinePoint1.setStyleSheet("QPushButton {background-color : white;}")

        self.LinePoint2.setStyleSheet("QPushButton {background-color : rgb(251,72,196);}")
        self.ColorVideo.setCursor(QCursor(QtCore.Qt.CrossCursor))
        self.DepthVideo.setCursor(QCursor(QtCore.Qt.CrossCursor))

    def showLineFunction(self):
        self.lPointX1 = int(self.LineX1.toPlainText()) #Update the entered coordinates
        self.lPointX2 = int(self.LineX2.toPlainText())
        self.lPointY1 = int(self.LineY1.toPlainText())
        self.lPointY2 = int(self.LineY2.toPlainText())
        
        self.showLine = True #display the end points and line
        self.linePoint1 = True
        self.linePoint2 = True
        self.showLinePoint1= True 
        self.showLinePoint2 = True
        #self.LinePoint1.setEnabled(False) #They can still edit the point, just not the click, so doesn't make sense to gray out. 
        #self.LinePoint2.setEnabled(False)

    #Function to get the point coords entered by user & display depth. 
    def calculatePointDepth(self):
        self.gPointX = int(self.PointX.toPlainText()) #Get the entered point coords from the GUI
        self.gPointY = int(self.PointY.toPlainText())
        self.showPoint = True #Show the distance and circle on the depth video stream
        self.showPointDistance = True

    #Function to get the 2 line point coords entered by user and display distance between them
    def calculateLineDistance(self):
        self.lPointX1 = int(self.LineX1.toPlainText())
        self.lPointX2 = int(self.LineX2.toPlainText())
        self.lPointY1 = int(self.LineY1.toPlainText())
        self.lPointY2 = int(self.LineY2.toPlainText())
        
        #depth_scale = test.dc.depth_scale #The depth scale is fixed at 0.001 plus a tiny bit for the 400 series camera. 
        color_intrin = self.thread2.dc.color_intrin
        Z1 = rs.rs2_deproject_pixel_to_point(color_intrin, [self.lPointX1, self.lPointY1], self.lPointDepth1)
        Z2 = rs.rs2_deproject_pixel_to_point(color_intrin, [self.lPointX2, self.lPointY2], self.lPointDepth2)

        #print(Z1)
        #result = rs.rs2_deproject_pixel_to_point()
        #print ("depth_scale: " + str(depth_scale))
        self.lineDistance = (math.sqrt(((Z1[0] - Z2[0])** 2) + ((Z1[1] - Z2[1]) ** 2) + ((Z1[2] - Z2[2]) ** 2)))
        #print ("distance: " + str(self.lineDistance))
        self.linePoint1 = True
        self.linePoint2 = True
        self.showLinePoint1= True 
        self.showLinePoint2 = True
        self.showLineDistance = True
        self.showLine = True
        self.LinePoint1.setEnabled(False)
        self.LinePoint2.setEnabled(False)

    #Function to clear the point depth coords, point distance. 
    def clearPointDepth(self):
        self.gPointX = 0 
        self.gPointY = 0
        self.PointX.clear()
        self.PointY.clear()
        self.PointDistance.clear()
        self.showPoint = False
        self.PointSelect.setStyleSheet("QPushButton {background-color : white; }")
        self.ColorVideo.setCursor(QCursor(QtCore.Qt.ArrowCursor)) #Set the cursors back to normal
        self.DepthVideo.setCursor(QCursor(QtCore.Qt.ArrowCursor))

    #Function to clear the line distance coords, line distance.
    def clearLineDistance(self):
        self.lPointX1 = 0
        self.lPointX2 = 0
        self.lPointY1 = 0
        self.lPointY2 = 0
        self.LineX1.clear()
        self.LineX2.clear()
        self.LineY1.clear()
        self.LineY2.clear()
        self.LineDistance.clear()
        self.LinePoint1.setEnabled(True)
        self.LinePoint2.setEnabled(True)
        self.LinePoint1.setStyleSheet("QPushButton {background-color : white;}")
        self.LinePoint2.setStyleSheet("QPushButton {background-color : white;}")
        self.showLinePoint1 = False
        self.showLinePoint2 = False
        self.linePoint1 = False
        self.linePoint2 = False
        self.showLine = False
        self.ColorVideo.setCursor(QCursor(QtCore.Qt.ArrowCursor))
        self.DepthVideo.setCursor(QCursor(QtCore.Qt.ArrowCursor))

    #Get the position on either video label where the mouse clicked. 
    def getPosition(self, event):
        x = event.pos().x()
        y = event.pos().y()
        if (self.pointCoordinate and self.showPoint):
            self.PointX.setPlainText(str(x))
            self.PointY.setPlainText(str(y))
            self.gPointX = x
            self.gPointY = y

        if(self.LineDistance and self.showLinePoint1 and not self.linePoint1):
            self.LineX1.setPlainText(str(x))
            self.LineY1.setPlainText(str(y))
            self.lPointX1 = x
            self.lPointY1 = y
            self.linePoint1 = True
            self.LinePoint1.setEnabled(False)
            self.ColorVideo.setCursor(QCursor(QtCore.Qt.ArrowCursor))
            self.DepthVideo.setCursor(QCursor(QtCore.Qt.ArrowCursor))

        if(self.LineDistance and self.showLinePoint2 and not self.linePoint2):
            self.LineX2.setPlainText(str(x))
            self.LineY2.setPlainText(str(y))
            self.lPointX2 = x
            self.lPointY2 = y
            self.linePoint2 = True
            self.LinePoint2.setEnabled(False)
            self.ColorVideo.setCursor(QCursor(QtCore.Qt.ArrowCursor))
            self.DepthVideo.setCursor(QCursor(QtCore.Qt.ArrowCursor))
        #print("X = " + str(x) + ", Y = " + str(y))

    #Connecting the actual Qt slots to the video feeds so they can be displayed
    @pyqtSlot(np.ndarray) #This line can be optional 
    def update_color_image(self, cv_img):
        #Updates the image_label with a new opencv image
        circleImg = cv_img
        if(self.showPoint):
            A = self.PointX.toPlainText()
            B = self.PointY.toPlainText()
            if( A.isdigit() and B.isdigit()): #Prevent the dot from showing up before first click.
                #print("Point from gPoint: " + str(self.gPointX) + ", " + str(self.gPointY))
                point = (self.gPointX, self.gPointY)
                lPoint1A = (self.gPointX - 10, self.gPointY)
                lPoint1B = (self.gPointX + 10, self.gPointY)
                lPoint2A = (self.gPointX, self.gPointY - 10)
                lPoint2B = (self.gPointX, self.gPointY + 10)
                circleImg = cv2.circle(circleImg, point, 10, (0, 0, 0), -1) #Black circle with neon orange border
                circleImg = cv2.circle(circleImg, point, 10, (0,173,255), 2) 
                circleImg = cv2.line(circleImg, lPoint1A, lPoint1B, (255,255,255), 1)
                circleImg = cv2.line(circleImg, lPoint2A, lPoint2B, (255,255,255), 1)
        
        if(self.showLinePoint1 and self.linePoint1): #This will make it so that only one point is ever shown, not two points....
            point = (self.lPointX1, self.lPointY1)
            lPoint1A = (self.lPointX1 - 10, self.lPointY1)
            lPoint1B = (self.lPointX1 + 10, self.lPointY1)
            lPoint2A = (self.lPointX1, self.lPointY1 - 10)
            lPoint2B = (self.lPointX1, self.lPointY1 + 10)
            circleImg = cv2.circle(circleImg, point, 10, (0, 0, 0), -1) #Black circle with neon green border
            circleImg = cv2.circle(circleImg, point, 10, (57,255,20), 2)
            circleImg = cv2.line(circleImg, lPoint1A, lPoint1B, (255,255,255), 1)
            circleImg = cv2.line(circleImg, lPoint2A, lPoint2B, (255,255,255), 1)

        if(self.showLinePoint2 and self.linePoint2):
            point = (self.lPointX2, self.lPointY2)
            lPoint1A = (self.lPointX2 - 10, self.lPointY2)
            lPoint1B = (self.lPointX2 + 10, self.lPointY2)
            lPoint2A = (self.lPointX2, self.lPointY2 - 10)
            lPoint2B = (self.lPointX2, self.lPointY2 + 10)
            circleImg = cv2.circle(circleImg, point, 10, (0, 0, 0), -1) #Black circle with neon pink border
            circleImg = cv2.circle(circleImg, point, 10, (251,72,196), 2)
            circleImg = cv2.line(circleImg, lPoint1A, lPoint1B, (255,255,255), 1)
            circleImg = cv2.line(circleImg, lPoint2A, lPoint2B, (255,255,255), 1)

        if(self.showLine):
            A = (self.lPointX1, self.lPointY1)
            B = (self.lPointX2, self.lPointY2)
            circleImg = cv2.line(circleImg, A, B, (0,0,0), 4)
            circleImg = cv2.line(circleImg, A, B, (255,255,255), 1)

        #print("The value of show point is: " + str(self.showPoint))
        qt_img = self.convert_cv_qt(circleImg)
        self.ColorVideo.setPixmap(qt_img) #self.image_label.setPixmap(qt_img)

    def update_depth_image(self, dv_img):
        #Updates the image_label with a new opencv image
        circleImg = dv_img
        if(self.showPoint):
            A = self.PointX.toPlainText()
            B = self.PointY.toPlainText()
            if( A.isdigit() and B.isdigit()): #Prevent the dot from showing up before first click.
                #print("Point from gPoint: " + str(self.gPointX) + ", " + str(self.gPointY))
                point = (self.gPointX, self.gPointY)
                lPoint1A = (self.gPointX - 10, self.gPointY)
                lPoint1B = (self.gPointX + 10, self.gPointY)
                lPoint2A = (self.gPointX, self.gPointY - 10)
                lPoint2B = (self.gPointX, self.gPointY + 10)
                circleImg = cv2.circle(circleImg, point, 10, (0, 0, 0), -1) #Black circle with neon orange border
                circleImg = cv2.circle(circleImg, point, 10, (0,173,255), 2)
                circleImg = cv2.line(circleImg, lPoint1A, lPoint1B, (255,255,255), 1)
                circleImg = cv2.line(circleImg, lPoint2A, lPoint2B, (255,255,255), 1)
        
        if(self.showLinePoint1 and self.linePoint1): #This will make it so that only one point is ever shown, not two points....
            point = (self.lPointX1, self.lPointY1)
            lPoint1A = (self.lPointX1 - 10, self.lPointY1)
            lPoint1B = (self.lPointX1 + 10, self.lPointY1)
            lPoint2A = (self.lPointX1, self.lPointY1 - 10)
            lPoint2B = (self.lPointX1, self.lPointY1 + 10)
            circleImg = cv2.circle(circleImg, point, 10, (0, 0, 0), -1) #Black circle with neon green border
            circleImg = cv2.circle(circleImg, point, 10, (57,255,20), 2)
            circleImg = cv2.line(circleImg, lPoint1A, lPoint1B, (255,255,255), 1)
            circleImg = cv2.line(circleImg, lPoint2A, lPoint2B, (255,255,255), 1)

        if(self.showLinePoint2 and self.linePoint2):
            point = (self.lPointX2, self.lPointY2)
            lPoint1A = (self.lPointX2 - 10, self.lPointY2)
            lPoint1B = (self.lPointX2 + 10, self.lPointY2)
            lPoint2A = (self.lPointX2, self.lPointY2 - 10)
            lPoint2B = (self.lPointX2, self.lPointY2 + 10)
            circleImg = cv2.circle(circleImg, point, 10, (0, 0, 0), -1) #Black circle with neon pink border
            circleImg = cv2.circle(circleImg, point, 10, (251,72,196), 2)
            circleImg = cv2.line(circleImg, lPoint1A, lPoint1B, (255,255,255), 1)
            circleImg = cv2.line(circleImg, lPoint2A, lPoint2B, (255,255,255), 1)

        if(self.showLine):
            A = (self.lPointX1, self.lPointY1)
            B = (self.lPointX2, self.lPointY2)
            circleImg = cv2.line(circleImg, A, B, (0,0,0), 4)
            circleImg = cv2.line(circleImg, A, B, (255,255,255), 1)

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
        self.pointDepth = depth_frame.get_distance(self.gPointX, self.gPointY)
        self.lPointDepth1 = depth_frame.get_distance(self.lPointX1, self.lPointY1)
        self.lPointDepth2 = depth_frame.get_distance(self.lPointX2, self.lPointY2)
        if (self.showPointDistance): #The bool allows the point distance to be set instantly and accurately. 
            self.PointDistance.setText(str(round(self.pointDepth, 5)))
            self.showPointDistance = False #If not reset, then can have a running display of the point distance. Maybe useful?

        if (self.showLineDistance):
            self.LineDistance.setText(str(round(self.lineDistance, 5)))
            self.showLineDistance = False
        
        #depth = depth_frame[y,x] #object type not subscriptable. Sigh. 
        #print("distance: " + str(round(self.depth, 5)))


#The stuff necessary to actually show the window
if __name__=="__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = QtWidgets.QMainWindow()
    a = App(w)
    w.show() #a.show()
    sys.exit(app.exec_())