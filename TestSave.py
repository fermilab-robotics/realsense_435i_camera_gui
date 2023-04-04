#It worked!!! I was able to record a bag file of a video and then load it into realsense viewer! 

import pyrealsense2 as rs
import time

pipeline = rs.pipeline()
config = rs.config()
#config.enable_stream(rs.stream.depth, 1280, 720, rs.format.z16, 6)
config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)

config.enable_record_to_file("BagFile.bag")
pipeline.start(config)

try:
    start= time.time()
    while (time.time() - start < 10):
        pipeline.wait_for_frames()
#frames = pipeline.wait_for_frames()

finally:
    pipeline.stop()