import json
import os
import sys
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QToolBar,
    QToolButton,
    QLineEdit,
    QStatusBar,
    QStyle,
    QTabWidget,
    QProgressBar,
    QLabel,
    QPushButton,
    QMenu,
    QDialog,
    QVBoxLayout,
    QListWidget,
    QListWidgetItem,
    QHBoxLayout,
)
from PyQt6.QtGui import QAction, QIcon, QKeySequence, QCursor, QPixmap, QPainter, QFont, QColor
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl, QSize, QTimer, Qt

HOME_HTML = os.path.join(os.path.dirname(__file__), "home.html")
HOMEPAGE = QUrl.fromLocalFile(HOME_HTML).toString()
BOOKMARKS_FILE = os.path.join(os.path.dirname(__file__), "bookmarks.json")
DEFAULT_BOOKMARKS = [
    ("Google", "https://www.google.com"),
    ("GitHub", "https://github.com"),
    ("YouTube", "https://www.youtube.com"),
    ("Stack Overflow", "https://stackoverflow.com"),
]

class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.setWindowTitle("Gnoiss")
        self.setWindowIcon(QIcon.fromTheme("internet-web-browser"))
        self.resize(1360, 860)

        self.bookmarks = self.load_bookmarks()
        self.history = []

        self.create_tabs()
        self.create_menu_bar()
        self.create_toolbar()
        self.create_status_bar()
        self.apply_styles()

        self.add_new_tab(HOMEPAGE, "New tab")
        self.showMaximized()

    def create_tabs(self):
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.on_tab_changed)

        self.new_tab_button = QToolButton()
        self.new_tab_button.setText("+")
        self.new_tab_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.new_tab_button.setToolTip("New tab")
        self.new_tab_button.setAutoRaise(True)
        self.new_tab_button.clicked.connect(self.open_new_tab)
        self.tabs.setCornerWidget(self.new_tab_button, Qt.Corner.TopRightCorner)

        self.setCentralWidget(self.tabs)

    def create_menu_bar(self):
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")
        new_tab_action = QAction("New &Tab", self)
        new_tab_action.setShortcut(QKeySequence("Ctrl+T"))
        new_tab_action.triggered.connect(self.open_new_tab)
        file_menu.addAction(new_tab_action)

        close_tab_action = QAction("&Close Tab", self)
        close_tab_action.setShortcut(QKeySequence("Ctrl+W"))
        close_tab_action.triggered.connect(lambda: self.close_tab(self.tabs.currentIndex()))
        file_menu.addAction(close_tab_action)

        file_menu.addSeparator()
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        view_menu = menu_bar.addMenu("&View")
        zoom_in_action = QAction("Zoom &In", self)
        zoom_in_action.setShortcut(QKeySequence("Ctrl++"))
        zoom_in_action.triggered.connect(self.zoom_in)
        view_menu.addAction(zoom_in_action)

        zoom_out_action = QAction("Zoom &Out", self)
        zoom_out_action.setShortcut(QKeySequence("Ctrl+-"))
        zoom_out_action.triggered.connect(self.zoom_out)
        view_menu.addAction(zoom_out_action)

        reset_zoom_action = QAction("&Reset Zoom", self)
        reset_zoom_action.setShortcut(QKeySequence("Ctrl+0"))
        reset_zoom_action.triggered.connect(self.reset_zoom)
        view_menu.addAction(reset_zoom_action)

        view_menu.addSeparator()
        home_action = QAction("Home", self)
        home_action.setShortcut(QKeySequence("Alt+Home"))
        home_action.triggered.connect(self.navigate_home)
        view_menu.addAction(home_action)

        self.history_menu = menu_bar.addMenu("&History")
        self.update_history_menu()

        self.bookmarks_menu = menu_bar.addMenu("&Bookmarks")
        self.bookmarks_menu.addAction("Manage bookmarks", self.show_bookmark_manager)
        self.bookmarks_menu.addSeparator()
        self.update_bookmarks_menu()

    def update_bookmarks_menu(self):
        self.bookmarks_menu.clear()
        self.bookmarks_menu.addAction("Manage bookmarks", self.show_bookmark_manager)
        self.bookmarks_menu.addSeparator()

        if not self.bookmarks:
            no_bookmarks = QAction("No bookmarks yet", self)
            no_bookmarks.setEnabled(False)
            self.bookmarks_menu.addAction(no_bookmarks)
            return

        for title, url in self.bookmarks:
            action = QAction(title, self)
            action.setData(url)
            action.triggered.connect(lambda checked=False, url=url: self.add_new_tab(url, title))
            self.bookmarks_menu.addAction(action)

    def update_history_menu(self):
        self.history_menu.clear()
        if not self.history:
            no_history = QAction("No history available", self)
            no_history.setEnabled(False)
            self.history_menu.addAction(no_history)
            return

        for title, url in reversed(self.history[-10:]):
            label = title if len(title) <= 45 else f"{title[:42]}..."
            action = QAction(label, self)
            action.setData(url)
            action.triggered.connect(lambda checked=False, url=url: self.open_url_in_current_tab(url))
            self.history_menu.addAction(action)

        self.history_menu.addSeparator()
        clear_history = QAction("Clear history", self)
        clear_history.triggered.connect(self.clear_history)
        self.history_menu.addAction(clear_history)

    def load_bookmarks(self):
        try:
            with open(BOOKMARKS_FILE, "r", encoding="utf-8") as file:
                data = json.load(file)
                if isinstance(data, list):
                    return [(item.get("title", item.get("url", "")), item.get("url", "")) for item in data if isinstance(item, dict) and item.get("url")]
        except (OSError, ValueError):
            pass
        return list(DEFAULT_BOOKMARKS)

    def save_bookmarks(self):
        try:
            with open(BOOKMARKS_FILE, "w", encoding="utf-8") as file:
                json.dump([{"title": title, "url": url} for title, url in self.bookmarks], file, indent=2)
        except OSError:
            pass

    def create_bookmark_icon(self, symbol: str, size: int = 20):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = QFont("Segoe UI Emoji", int(size * 0.9))
        painter.setFont(font)
        painter.setPen(QColor("#334155"))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, symbol)
        painter.end()
        return QIcon(pixmap)

    def is_bookmarked(self, url):
        return any(url == existing_url for _, existing_url in self.bookmarks)

    def remove_bookmark(self, url):
        self.bookmarks = [(title, link) for title, link in self.bookmarks if link != url]
        self.save_bookmarks()
        self.update_bookmarks_menu()
        self.update_bookmark_buttons()

    def update_bookmark_buttons(self):
        current_url = self.current_browser().url().toString() if self.current_browser() else ""
        bookmarked = bool(current_url and self.is_bookmarked(current_url))
        self.bookmark_add_button.setEnabled(bool(current_url and not bookmarked))
        self.bookmark_remove_button.setEnabled(bookmarked)

    def remove_bookmark_current(self):
        browser = self.current_browser()
        if not browser:
            return
        url = browser.url().toString()
        if not self.is_bookmarked(url):
            self.status.showMessage("Current page is not bookmarked")
            return
        title = browser.title() or url
        self.remove_bookmark(url)
        self.status.showMessage(f"Removed bookmark '{title}'")

    def open_url_in_current_tab(self, url):
        browser = self.current_browser()
        if browser:
            browser.setUrl(QUrl(url))
        else:
            self.add_new_tab(url, "New tab")

    def add_history_entry(self, title, url):
        if not url:
            return
        if self.history and self.history[-1][1] == url:
            return
        self.history.append((title or url, url))
        self.history = self.history[-50:]
        self.update_history_menu()

    def clear_history(self):
        self.history.clear()
        self.update_history_menu()
        self.status.showMessage("History cleared")

    def create_toolbar(self):
        self.navbar = QToolBar("Navigation")
        self.navbar.setIconSize(QSize(24, 24))
        self.navbar.setMovable(False)
        self.addToolBar(self.navbar)

        style = self.style()
        self.back_button = QAction(style.standardIcon(QStyle.StandardPixmap.SP_ArrowBack), "", self)
        self.back_button.setToolTip("Go back")
        self.back_button.triggered.connect(lambda: self.current_browser().back())
        self.navbar.addAction(self.back_button)

        self.forward_button = QAction(style.standardIcon(QStyle.StandardPixmap.SP_ArrowForward), "", self)
        self.forward_button.setToolTip("Go forward")
        self.forward_button.triggered.connect(lambda: self.current_browser().forward())
        self.navbar.addAction(self.forward_button)

        reload_icon = QIcon.fromTheme("view-refresh", style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.reload_button = QAction(reload_icon, "", self)
        self.reload_button.setToolTip("Reload page")
        self.reload_button.triggered.connect(lambda: self.current_browser().reload())
        self.navbar.addAction(self.reload_button)

        self.stop_button = QAction(style.standardIcon(QStyle.StandardPixmap.SP_BrowserStop), "", self)
        self.stop_button.setToolTip("Stop loading")
        self.stop_button.triggered.connect(lambda: self.current_browser().stop())
        self.navbar.addAction(self.stop_button)

        home_icon = QIcon.fromTheme("go-home", style.standardIcon(QStyle.StandardPixmap.SP_DirHomeIcon))
        self.home_button = QAction(home_icon, "", self)
        self.home_button.setToolTip("Go home")
        self.home_button.triggered.connect(self.navigate_home)
        self.navbar.addAction(self.home_button)

        self.navbar.addSeparator()

        add_bookmark_icon = self.create_bookmark_icon("📚+")
        self.bookmark_add_button = QAction(add_bookmark_icon, "", self)
        self.bookmark_add_button.setToolTip("Add bookmark")
        self.bookmark_add_button.triggered.connect(self.add_bookmark)
        self.navbar.addAction(self.bookmark_add_button)

        remove_bookmark_icon = self.create_bookmark_icon("📚−")
        self.bookmark_remove_button = QAction(remove_bookmark_icon, "", self)
        self.bookmark_remove_button.setToolTip("Remove bookmark")
        self.bookmark_remove_button.triggered.connect(self.remove_bookmark_current)
        self.navbar.addAction(self.bookmark_remove_button)

        self.navbar.addSeparator()

        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("Search or type a web address")
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        self.url_bar.setClearButtonEnabled(True)
        self.url_bar.setMinimumWidth(520)
        self.navbar.addWidget(self.url_bar)


    def create_status_bar(self):
        self.status = QStatusBar()
        self.setStatusBar(self.status)

        self.download_button = QPushButton("Downloads")
        self.download_button.setFlat(True)
        self.download_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.download_button.clicked.connect(self.open_download_folder)
        self.status.addPermanentWidget(self.download_button)

        self.download_bar = QProgressBar()
        self.download_bar.setMaximumWidth(180)
        self.download_bar.setTextVisible(False)
        self.download_bar.setVisible(False)
        self.status.addPermanentWidget(self.download_bar)

        self.progress = QProgressBar()
        self.progress.setMaximumWidth(180)
        self.progress.setTextVisible(False)
        self.status.addPermanentWidget(self.progress)

        self.status.showMessage("Ready")

    def show_bookmark_manager(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Bookmarks")
        dialog.setMinimumSize(400, 360)

        layout = QVBoxLayout(dialog)

        list_widget = QListWidget(dialog)
        for title, url in self.bookmarks:
            item = QListWidgetItem(f"{title} — {url}")
            item.setData(Qt.ItemDataRole.UserRole, url)
            list_widget.addItem(item)

        layout.addWidget(list_widget)

        button_row = QHBoxLayout()
        open_button = QPushButton("Open")
        delete_button = QPushButton("Delete")
        close_button = QPushButton("Close")
        button_row.addWidget(open_button)
        button_row.addWidget(delete_button)
        button_row.addWidget(close_button)

        layout.addLayout(button_row)

        def open_selected():
            item = list_widget.currentItem()
            if item:
                self.open_url_in_current_tab(item.data(Qt.ItemDataRole.UserRole))
                dialog.accept()

        def delete_selected():
            item = list_widget.currentItem()
            if item:
                url = item.data(Qt.ItemDataRole.UserRole)
                self.bookmarks = [(t, u) for t, u in self.bookmarks if u != url]
                self.save_bookmarks()
                self.update_bookmarks_menu()
                list_widget.takeItem(list_widget.row(item))
                self.status.showMessage("Bookmark removed")

        open_button.clicked.connect(open_selected)
        delete_button.clicked.connect(delete_selected)
        close_button.clicked.connect(dialog.reject)

        dialog.exec()

    def apply_styles(self):
        self.setStyleSheet(
            "QMainWindow { background: #F3F6FF; font-family: 'Segoe UI', sans-serif; }"
            "QToolBar { background: #FFFFFF; spacing: 10px; padding: 10px 12px; border-bottom: 1px solid #D8E0EE; }"
            "QToolBar QToolButton { min-width: 38px; min-height: 38px; border: none; border-radius: 10px; padding: 6px; background: transparent; color: #334155; }"
            "QToolBar QToolButton:hover { background: #EEF2FF; }"
            "QTabWidget::pane { border: 1px solid #D8E0EE; border-radius: 14px; background: #FFFFFF; margin-top: -1px; }"
            "QTabBar::tab { background: #F8FAFC; border: 1px solid #D8E0EE; border-bottom: none; border-top-left-radius: 10px; border-top-right-radius: 10px; padding: 10px 14px; margin-right: 4px; color: #334155; }"
            "QTabBar::tab:selected { background: #FFFFFF; border-color: #A9B1C8; color: #0F172A; }"
            "QTabBar::tab:hover { background: #EFF4FF; }"
            "QTabBar::close-button { subcontrol-origin: padding; subcontrol-position: right center; width: 16px; height: 16px; margin: 0 4px 0 0; }"
            "QTabBar::close-button:hover { background: rgba(0,0,0,0.05); }"
            "QLineEdit { border: 1px solid #CBD4E4; border-radius: 14px; padding: 9px 14px; background: #F7F9FC; color: #111827; }"
            "QLineEdit:focus { border-color: #5B78FF; background: #FFFFFF; }"
            "QLineEdit::clear-button { subcontrol-origin: content; subcontrol-position: right center; margin-right: 8px; width: 16px; height: 16px; }"
            "QStatusBar { background: #FFFFFF; color: #475569; padding: 5px 12px; border-top: 1px solid #E2E8F0; }"
            "QMenuBar { background: #FFFFFF; color: #334155; }"
            "QMenuBar::item:selected { background: #EEF2FF; }"
            "QMenu { background: #FFFFFF; border: 1px solid #D8E0EE; }"
            "QMenu::item:selected { background: #EEF2FF; }"
        )

    def current_browser(self):
        widget = self.tabs.currentWidget()
        return widget if isinstance(widget, QWebEngineView) else None

    def update_navigation_buttons(self):
        browser = self.current_browser()
        if browser:
            history = browser.history()
            self.back_button.setEnabled(history.canGoBack())
            self.forward_button.setEnabled(history.canGoForward())
        else:
            self.back_button.setEnabled(False)
            self.forward_button.setEnabled(False)

    def add_new_tab(self, url=HOMEPAGE, label="New tab"):
        browser = QWebEngineView()
        browser.setUrl(QUrl(url))
        browser.page().profile().downloadRequested.connect(self.on_download_requested)
        browser.urlChanged.connect(self.update_url)
        browser.titleChanged.connect(lambda title, browser=browser: self.update_tab_title(browser, title))
        browser.loadStarted.connect(self.on_load_started)
        browser.loadProgress.connect(self.on_load_progress)
        browser.loadFinished.connect(self.on_load_finished)

        index = self.tabs.addTab(browser, label)
        self.tabs.setCurrentIndex(index)
        self.url_bar.setText(browser.url().toString())
        self.update_navigation_buttons()

    def open_new_tab(self):
        self.add_new_tab(HOMEPAGE, "New tab")

    def close_tab(self, index):
        if self.tabs.count() == 1:
            self.add_new_tab(HOMEPAGE, "New tab")
        self.tabs.removeTab(index)

    def on_tab_changed(self, _index):
        browser = self.current_browser()
        if browser:
            self.url_bar.setText(browser.url().toString())
            self.status.showMessage("Ready")
        self.update_navigation_buttons()
        self.update_bookmark_buttons()

    def navigate_home(self):
        browser = self.current_browser()
        if browser:
            browser.setUrl(QUrl(HOMEPAGE))

    def navigate_to_url(self):
        browser = self.current_browser()
        if not browser:
            return

        url_text = self.url_bar.text().strip()
        if not url_text:
            return

        if not url_text.startswith(("http://", "https://")):
            if "." not in url_text:
                url_text = f"https://www.google.com/search?q={QUrl.toPercentEncoding(url_text).data().decode()}"
            else:
                url_text = f"https://{url_text}"

        browser.setUrl(QUrl(url_text))

    def update_url(self, qurl):
        browser = self.current_browser()
        if browser and self.sender() == browser:
            self.url_bar.setText(qurl.toString())

    def update_tab_title(self, browser, title):
        for index in range(self.tabs.count()):
            if self.tabs.widget(index) is browser:
                self.tabs.setTabText(index, title if title else "New tab")
                break

    def on_load_started(self):
        self.status.showMessage("Loading...")
        self.progress.setValue(0)

    def on_load_progress(self, progress):
        self.progress.setValue(progress)
        self.status.showMessage(f"Loading... {progress}%")

    def on_load_finished(self, ok):
        self.progress.setValue(100 if ok else 0)
        self.status.showMessage("Ready" if ok else "Failed to load page")
        if ok:
            browser = self.current_browser()
            if browser:
                self.add_history_entry(browser.title(), browser.url().toString())
        self.update_navigation_buttons()

    def on_download_requested(self, download):
        if not download:
            return

        if not download.path():
            download.setPath(os.path.join(os.path.expanduser("~"), os.path.basename(download.url().path()) or "download"))

        download.accept()
        self.download_button.setText("Downloading…")
        self.download_bar.setVisible(True)
        self.download_bar.setValue(0)
        self.status.showMessage("Downloading…")

        download.downloadProgress.connect(self.update_download_progress)
        download.finished.connect(lambda: self.on_download_finished(download))

    def update_download_progress(self, received, total):
        if total > 0:
            percent = int(received * 100 / total)
            self.download_bar.setValue(percent)
            self.status.showMessage(f"Downloading… {percent}%")
        else:
            self.download_bar.setMaximum(0)
            self.status.showMessage("Downloading…")

    def on_download_finished(self, download):
        try:
            if download.state() == 3:  # QWebEngineDownloadItem.DownloadCompleted
                self.status.showMessage(f"Downloaded {os.path.basename(download.path())}")
            else:
                self.status.showMessage("Download canceled or failed")
        except Exception:
            self.status.showMessage("Download finished")

        self.download_button.setText("Downloads")
        QTimer.singleShot(3500, self.clear_download_status)

    def clear_download_status(self):
        self.download_bar.setVisible(False)
        self.download_bar.setMaximum(100)
        self.download_button.setText("Downloads")

    def open_download_folder(self):
        download_folder = os.path.join(os.path.expanduser("~"), "Downloads")
        if not os.path.isdir(download_folder):
            download_folder = os.path.expanduser("~")
        try:
            os.startfile(download_folder)
        except Exception:
            self.status.showMessage(f"Cannot open {download_folder}")

    def add_bookmark(self):
        browser = self.current_browser()
        if not browser:
            return

        title = browser.title() or browser.url().toString()
        url = browser.url().toString()

        if self.is_bookmarked(url):
            self.remove_bookmark(url)
            self.status.showMessage(f"Removed bookmark '{title}'")
            return

        self.bookmarks.append((title, url))
        self.save_bookmarks()
        self.update_bookmarks_menu()
        self.update_bookmark_buttons()
        self.status.showMessage(f"Bookmarked '{title}'")

    def zoom_in(self):
        browser = self.current_browser()
        if browser:
            browser.setZoomFactor(browser.zoomFactor() + 0.1)

    def zoom_out(self):
        browser = self.current_browser()
        if browser:
            browser.setZoomFactor(browser.zoomFactor() - 0.1)

    def reset_zoom(self):
        browser = self.current_browser()
        if browser:
            browser.setZoomFactor(1.0)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    app.exec()