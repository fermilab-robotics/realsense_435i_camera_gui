import pyrealsense2 as rs
import numpy as np
import cv2
import math 
import matplotlib.pyplot as plt
 
# Configure depth and color streams
pipeline = rs.pipeline()
config = rs.config()
 
# Get camera device and enable stream
pipeline_wrapper = rs.pipeline_wrapper(pipeline)
pipeline_profile = config.resolve(pipeline_wrapper)
device = pipeline_profile.get_device()
device_product_line = str(device.get_info(rs.camera_info.product_line))
 
config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
 
# Start streaming
profile = pipeline.start(config)
 
align_to = rs.stream.depth #These 4 lines not in other example...
align = rs.align(align_to)
depth_sensor = profile.get_device().first_depth_sensor()
depth_scale = depth_sensor.get_depth_scale()
 
 
try:
   while True:
 
       # Wait for a coherent pair of frames: depth and color
       frames = pipeline.wait_for_frames()
       depth_frame = frames.get_depth_frame()
       color_frame = frames.get_color_frame()
       if not depth_frame or not color_frame:
           continue
 
       # Convert images to numpy arrays
       depth_intrin = depth_frame.profile.as_video_stream_profile().intrinsics
       depth_image = np.asanyarray(depth_frame.get_data())
       color_image = np.asanyarray(color_frame.get_data())
 
       # Apply colormap on depth image (image must be converted to 8-bit per pixel first)
       depth_colormap = cv2.applyColorMap(cv2.convertScaleAbs(depth_image, alpha=0.10), cv2.COLORMAP_JET)
 
       depth_colormap_dim = depth_colormap.shape
       color_colormap_dim = color_image.shape
 
       # If depth and color resolutions are different, resize color image to match depth image for display
       if depth_colormap_dim != color_colormap_dim:
           resized_color_image = cv2.resize(color_image, dsize=(depth_colormap_dim[1], depth_colormap_dim[0]), interpolation=cv2.INTER_AREA)
           images = np.hstack((resized_color_image, depth_colormap))
       else:
           images = np.hstack((color_image, depth_colormap))
 
        # Show images
       cv2.namedWindow('Camera View', cv2.WINDOW_AUTOSIZE)
       cv2.imshow('Camera View', images)
       key = cv2.waitKey(1)
       if key & 0xFF == ord('q') or key == 27:
           cv2.destroyAllWindows()
 
       if key==115: # Press 's' to save
           img = cv2.waitKey(0)
           print('picture was taken')
          
       if key==114: # Press 'r' for distance between two points
           xOne = input("Enter the first x-coordinate: ")
           yOne = input("Enter the first y-coordinate: ")
           zOne = 0;
 
           xTwo = input("Enter the second x-coordinate: ")
           yTwo = input("Enter the second y-coordinate: ")
           zTwo = 0;
 
           distTwoPoints = round(math.sqrt(((int(xTwo) - int(xOne)) ** 2) + ((int(yTwo) - int(yOne)) ** 2) + ((int(zTwo) - int(zOne)) ** 2)), 3)
           # Converts from pixels to meters
           distTwoPoints = round(distTwoPoints * 0.0002645833, 3)       
           print("The distance between the two coordinates is: ", distTwoPoints, "meters")
 
       if key==111: # Press 'o' for distance from middle pixel
           x, y = 320, 240  # this had to be half of the resolution 640x480, this takes the distance from the center of the window
 
           depth = round(depth_frame.get_distance(x, y), 3)
           color_intrin = color_frame.profile.as_video_stream_profile().intrinsics
           dx ,dy, dz = rs.rs2_deproject_pixel_to_point(color_intrin, [x,y], depth)
           distance = round(math.sqrt(((dx)**2) + ((dy)**2) + ((dz)**2)), 3)
 
           print("Distance from camera to pixel (meters):", distance)
           print("Z-depth from camera surface to pixel surface (meters):", depth)
 
       if key==109: # Press 'm' for meshgrid
           x = np.linspace(0, 639, 640)
           y = np.linspace(0, 479, 480)
           xx, yy = np.meshgrid(x, y)
           zz = np.sqrt(xx**2 + yy**2) # use distance formula?
           xs, ys = np.meshgrid(x, y)
           zs = np.sqrt(xs**2 + ys**2)
           xs.shape, ys.shape, zs.shape
           np.array_equal(zz, zs)
 
           h = plt.contourf(x, y, zs)
           plt.axis('scaled')
           plt.title("Distance Values")
           plt.xlabel("640")
           plt.ylabel("480")
           plt.colorbar()
           plt.show()
 
       if key==108: # Press 'l' for clicking points in image window
     
           class DrawLineWidget(object):
               def __init__(self):
                   self.image = cv2.imread('phone3.png')
 
                   cv2.namedWindow('window')
                   cv2.setMouseCallback('window', self.extract_coordinates)
 
                   self.image_xcoord = []
                   self.image_ycoord = []
              
               def extract_coordinates(self, event, x, y, flags, paramaters):
                   font = cv2.FONT_HERSHEY_SIMPLEX
                   if event == cv2.EVENT_LBUTTONDOWN:
                       self.image_coords = [x,y]
                       self.image_xcoord = [x]
                       self.image_ycoord = [y]
                     
                   elif event == cv2.EVENT_LBUTTONUP:
                       self.image_xcoord.append(x)
                       self.image_ycoord.append(y)
 
                       print('START:({}, {}) END:({}, {})'.format(self.image_xcoord[0], self.image_ycoord[0], self.image_xcoord[1], self.image_ycoord[1]))
                       cv2.line(self.image, ((self.image_xcoord[0]), self.image_ycoord[0]), (self.image_xcoord[1], self.image_ycoord[1]), (0,255,0), thickness=3, lineType=4)
                              
                       color_intrin = color_frame.profile.as_video_stream_profile().intrinsics
 
                       depth1 = depth_frame.get_distance(self.image_xcoord[0], self.image_ycoord[0])
                       depth2 = depth_frame.get_distance(self.image_xcoord[1], self.image_ycoord[1])
 
                       distance = np.sqrt(((self.image_xcoord[1] - self.image_xcoord[0]) ** 2) + ((self.image_ycoord[1] - self.image_ycoord[0]) ** 2) + ((depth2 - depth1) ** 2))
                       distance = round(distance * 0.0002645833, 3)
                      
                       cv2.putText(self.image, str(distance) + 'meters', fontFace=font, org=(self.image_xcoord[0], self.image_ycoord[0]), fontScale=0.65, color=(255,0,0), thickness=2)
 
               def show_image(self):
                   return self.image
 
           if __name__ == "__main__":
                   draw_line_widget = DrawLineWidget()
                   while True:
                       cv2.imshow('window', draw_line_widget.show_image())
                       key = cv2.waitKey(1)
 
                       if key == ord('q'):
                           cv2.destroyAllWindows()
                           exit(1)
                
finally:
 
   # Stop streaming
   pipeline.stop()