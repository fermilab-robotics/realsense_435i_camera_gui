# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'LoadDataTest.ui'
#
# Created by: PyQt5 UI code generator 5.14.1
#
# WARNING! All changes made in this file will be lost!


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(682, 568)
        MainWindow.setStyleSheet("background-color: rgb(114, 159, 207);")
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.DataFrame = QtWidgets.QFrame(self.centralwidget)
        self.DataFrame.setGeometry(QtCore.QRect(20, 20, 640, 480))
        self.DataFrame.setStyleSheet("background-color: rgb(0, 0, 0);")
        self.DataFrame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.DataFrame.setFrameShadow(QtWidgets.QFrame.Raised)
        self.DataFrame.setObjectName("DataFrame")
        self.Data = QtWidgets.QLabel(self.DataFrame)
        self.Data.setGeometry(QtCore.QRect(0, 0, 640, 480))
        self.Data.setObjectName("Data")
        self.Button = QtWidgets.QPushButton(self.centralwidget)
        self.Button.setGeometry(QtCore.QRect(270, 520, 131, 31))
        self.Button.setStyleSheet("background-color: rgb(255, 255, 255);")
        self.Button.setObjectName("Button")
        MainWindow.setCentralWidget(self.centralwidget)

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "MainWindow"))
        self.Data.setText(_translate("MainWindow", "TextLabel"))
        self.Button.setText(_translate("MainWindow", "Select Data"))


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.show()
    sys.exit(app.exec_())
