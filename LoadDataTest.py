from PyQt5 import QtGui
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtCore import pyqtSignal, pyqtSlot, Qt, QThread
from PyQt5.QtGui import QPixmap, QIcon, QCursor
import sys
import cv2
from LoadDataGUI import *

class App(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self, window):
        #Set up the initial window
        super().__init__()
        ui = Ui_MainWindow()
        ui.setupUi(self)
        self.setupUi(window)


        self.Button.clicked.connect(lambda state: self.LoadData())

    def LoadData(self):
        fname = QFileDialog.getOpenFileName(self, "Open File", "", "JPEG Files (*.jpeg)")
        fileName = fname[0]
        print("This is the file name: " + fname[0])

        pixmap = QPixmap(fileName)
        self.Data.setPixmap(pixmap)

if __name__=="__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = QtWidgets.QMainWindow()
    a = App(w)
    w.show() #a.show()
    sys.exit(app.exec_())