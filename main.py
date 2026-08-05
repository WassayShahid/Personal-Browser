import sys
from PyQt6.QtWidgets import *
from PyQt6.QtGui import QAction
from PyQt6.QtWebEngineWidgets import *
from PyQt6.QtCore import *

class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.browser = QWebEngineView()
        self.browser.setUrl(QUrl("https://www.google.com"))
        self.setCentralWidget(self.browser)
        self.setWindowTitle("Gnoiss")
        self.showMaximized()

        # Navbar
        self.navbar = QToolBar()
        self.addToolBar(self.navbar)

        # URL bar
        self.url_bar = QLineEdit()
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        self.navbar.addWidget(self.url_bar)
        self.browser.urlChanged.connect(self.update_url)

        # Back button
        self.back_button = QAction("Back", self)
        self.back_button.triggered.connect(self.browser.back)
        self.navbar.addAction(self.back_button)

        # Forward button
        self.forward_button = QAction("Forward", self)
        self.forward_button.triggered.connect(self.browser.forward)
        self.navbar.addAction(self.forward_button)

        # Reload button
        self.reload_button = QAction("Reload", self)
        self.reload_button.triggered.connect(self.browser.reload)
        self.navbar.addAction(self.reload_button)

        # Home button
        self.home_button = QAction("Home", self)
        self.home_button.triggered.connect(self.navigate_home)
        self.navbar.addAction(self.home_button)

    def navigate_home(self):
        self.browser.setUrl(QUrl("https://www.google.com"))

    def navigate_to_url(self):
        url = self.url_bar.text()
        if not url.startswith("http"):
            url = "http://" + url
        self.browser.setUrl(QUrl(url))

    def update_url(self, q):
        self.url_bar.setText(q.toString())

app = QApplication(sys.argv)
window = MainWindow()
window.showMaximized()
app.exec()