import json
import os
import re
import sys
from urllib.parse import quote_plus

from PyQt6.QtCore import QSize, QStandardPaths, Qt, QTimer, QUrl
from PyQt6.QtGui import QAction, QColor, QFont, QIcon, QKeySequence, QPainter, QPixmap
from PyQt6.QtWebEngineCore import QWebEngineDownloadRequest, QWebEngineProfile, QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QStatusBar,
    QStyle,
    QTabWidget,
    QToolBar,
    QToolButton,
    QVBoxLayout,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HOME_HTML = os.path.join(BASE_DIR, "home.html")
CHROME_QSS = os.path.join(BASE_DIR, "chrome.qss")
BOOKMARKS_FILE = os.path.join(BASE_DIR, "bookmarks.json")
HISTORY_FILE = os.path.join(BASE_DIR, "history.json")
SEARCH_URL = "https://www.google.com/search?q={query}"
DEFAULT_BOOKMARKS = [
    ("Google", "https://www.google.com"),
    ("GitHub", "https://github.com"),
    ("YouTube", "https://www.youtube.com"),
    ("Stack Overflow", "https://stackoverflow.com"),
]
def homepage_url():
    return QUrl.fromLocalFile(HOME_HTML).toString()


def is_homepage_url(qurl: QUrl) -> bool:
    if not qurl.isLocalFile():
        return False
    return os.path.normcase(os.path.normpath(qurl.toLocalFile())) == os.path.normcase(
        os.path.normpath(HOME_HTML)
    )


def looks_like_url(text: str) -> bool:
    text = text.strip()
    if not text or " " in text:
        return False
    lowered = text.lower()
    if lowered.startswith(("http://", "https://", "file://", "about:")):
        return True
    host = text.split("/")[0].split("?")[0].split("#")[0]
    if host.lower().startswith("localhost") or re.match(r"^(\d{1,3}\.){3}\d{1,3}(:\d+)?$", host):
        return True
    return "." in host and not host.endswith(".")


def resolve_address(text: str) -> str:
    text = text.strip()
    if not text:
        return homepage_url()
    lowered = text.lower()
    if lowered.startswith(("http://", "https://", "file://", "about:")):
        return text
    if looks_like_url(text):
        return f"https://{text}"
    return SEARCH_URL.format(query=quote_plus(text))


def load_json_pairs(path, fallback):
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
        if isinstance(data, list):
            pairs = []
            for item in data:
                if isinstance(item, dict) and item.get("url"):
                    pairs.append((item.get("title") or item["url"], item["url"]))
            return pairs
    except (OSError, ValueError):
        pass
    return list(fallback)


def save_json_pairs(path, pairs):
    try:
        with open(path, "w", encoding="utf-8") as file:
            json.dump([{"title": title, "url": url} for title, url in pairs], file, indent=2)
    except OSError:
        pass


def paint_icon(symbol: str, color="#334155", size=20):
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setFont(QFont("Segoe UI", int(size * 0.7), QFont.Weight.DemiBold))
    painter.setPen(QColor(color))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, symbol)
    painter.end()
    return QIcon(pixmap)


class BrowserView(QWebEngineView):
    def __init__(self, main_window):
        super().__init__()
        self._main = main_window
        settings = self.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        self.page().fullScreenRequested.connect(self._main.on_fullscreen_requested)

    def createWindow(self, _window_type):
        return self._main.add_new_tab(url=None, label="New tab")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gnoiss")
        self.setWindowIcon(paint_icon("G", "#4F46E5", 32))
        self.resize(1360, 860)

        self.bookmarks = load_json_pairs(BOOKMARKS_FILE, DEFAULT_BOOKMARKS)
        self.history = load_json_pairs(HISTORY_FILE, [])[-80:]
        self.closed_tabs = []
        self._was_maximized = True

        self.profile = QWebEngineProfile.defaultProfile()
        self.profile.downloadRequested.connect(self.on_download_requested)

        self.create_tabs()
        self.create_menu_bar()
        self.create_toolbar()
        self.create_status_bar()
        self.apply_styles()
        self.add_new_tab(homepage_url(), "New tab")
        self.showMaximized()

    def create_tabs(self):
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setElideMode(Qt.TextElideMode.ElideRight)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.on_tab_changed)
        self.tabs.tabBar().setExpanding(False)
        self.tabs.tabBar().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabs.tabBar().customContextMenuRequested.connect(self.show_tab_menu)
        self.tabs.tabBar().setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

        self.new_tab_button = QToolButton()
        self.new_tab_button.setText("+")
        self.new_tab_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.new_tab_button.setToolTip("New tab (Ctrl+T)")
        self.new_tab_button.setAutoRaise(True)
        self.new_tab_button.setObjectName("newTabButton")
        self.new_tab_button.setFixedSize(32, 32)
        self.new_tab_button.clicked.connect(self.open_new_tab)
        self.tabs.setCornerWidget(self.new_tab_button, Qt.Corner.TopRightCorner)
        self.setCentralWidget(self.tabs)

    def create_menu_bar(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File")
        self._add_action(file_menu, "New &Tab", "Ctrl+T", self.open_new_tab)
        self._add_action(file_menu, "&Duplicate Tab", "Ctrl+Shift+D", self.duplicate_tab)
        self._add_action(file_menu, "Reopen Closed Tab", "Ctrl+Shift+T", self.reopen_closed_tab)
        self._add_action(file_menu, "&Close Tab", "Ctrl+W", lambda: self.close_tab(self.tabs.currentIndex()))
        file_menu.addSeparator()
        self._add_action(file_menu, "E&xit", "Ctrl+Q", self.close)

        edit_menu = menu_bar.addMenu("&Edit")
        self._add_action(edit_menu, "&Find", "Ctrl+F", self.focus_find_bar)
        self._add_action(edit_menu, "Focus Address Bar", "Ctrl+L", self.focus_url_bar)

        view_menu = menu_bar.addMenu("&View")
        reload_action = self._add_action(
            view_menu, "&Reload", "F5", lambda: self.current_browser() and self.current_browser().reload()
        )
        reload_action.setShortcuts([QKeySequence("F5"), QKeySequence("Ctrl+R")])
        self._add_action(view_menu, "Stop", "Esc", self.stop_or_close_find)
        view_menu.addSeparator()
        self._add_action(view_menu, "Zoom &In", "Ctrl+=", self.zoom_in)
        self._add_action(view_menu, "Zoom In", "Ctrl++", self.zoom_in)
        self._add_action(view_menu, "Zoom &Out", "Ctrl+-", self.zoom_out)
        self._add_action(view_menu, "&Reset Zoom", "Ctrl+0", self.reset_zoom)
        view_menu.addSeparator()
        self._add_action(view_menu, "Home", "Alt+Home", self.navigate_home)
        self._add_action(view_menu, "Next Tab", "Ctrl+Tab", lambda: self.cycle_tab(1))
        self._add_action(view_menu, "Previous Tab", "Ctrl+Shift+Tab", lambda: self.cycle_tab(-1))

        self.history_menu = menu_bar.addMenu("&History")
        self.bookmarks_menu = menu_bar.addMenu("&Bookmarks")
        self.update_history_menu()
        self.update_bookmarks_menu()

        for number in range(1, 9):
            action = QAction(self)
            action.setShortcut(QKeySequence(f"Ctrl+{number}"))
            action.triggered.connect(lambda checked=False, i=number - 1: self.tabs.setCurrentIndex(i) if i < self.tabs.count() else None)
            self.addAction(action)

        bookmark_shortcut = QAction(self)
        bookmark_shortcut.setShortcut(QKeySequence("Ctrl+D"))
        bookmark_shortcut.triggered.connect(self.toggle_bookmark)
        self.addAction(bookmark_shortcut)

    def _add_action(self, menu, title, shortcut, slot):
        action = QAction(title, self)
        action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(slot)
        menu.addAction(action)
        return action

    def apply_styles(self):
        try:
            with open(CHROME_QSS, "r", encoding="utf-8") as file:
                self.setStyleSheet(file.read())
        except OSError:
            pass

    def current_browser(self):
        widget = self.tabs.currentWidget()
        return widget if isinstance(widget, QWebEngineView) else None

    def create_toolbar(self):
        self.navbar = QToolBar("Navigation")
        self.navbar.setIconSize(QSize(20, 24))
        self.navbar.setMovable(False)
        self.addToolBar(self.navbar)
        style = self.style()

        self.back_button = QAction(style.standardIcon(QStyle.StandardPixmap.SP_ArrowBack), "Back", self)
        self.back_button.setToolTip("Back (Alt+Left)")
        self.back_button.setShortcut(QKeySequence("Alt+Left"))
        self.back_button.triggered.connect(lambda: self.current_browser() and self.current_browser().back())
        self.navbar.addAction(self.back_button)

        self.forward_button = QAction(style.standardIcon(QStyle.StandardPixmap.SP_ArrowForward), "Forward", self)
        self.forward_button.setToolTip("Forward (Alt+Right)")
        self.forward_button.setShortcut(QKeySequence("Alt+Right"))
        self.forward_button.triggered.connect(lambda: self.current_browser() and self.current_browser().forward())
        self.navbar.addAction(self.forward_button)

        self.reload_button = QAction(
            QIcon.fromTheme("view-refresh", style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload)),
            "Reload",
            self,
        )
        self.reload_button.setToolTip("Reload (F5)")
        self.reload_button.triggered.connect(lambda: self.current_browser() and self.current_browser().reload())
        self.navbar.addAction(self.reload_button)

        self.home_button = QAction(
            QIcon.fromTheme("go-home", style.standardIcon(QStyle.StandardPixmap.SP_DirHomeIcon)),
            "Home",
            self,
        )
        self.home_button.setToolTip("Home")
        self.home_button.triggered.connect(self.navigate_home)
        self.navbar.addAction(self.home_button)

        self.navbar.addSeparator()
        self.bookmark_button = QAction(paint_icon("☆"), "Bookmark", self)
        self.bookmark_button.setToolTip("Bookmark this page (Ctrl+D)")
        self.bookmark_button.triggered.connect(self.toggle_bookmark)
        self.navbar.addAction(self.bookmark_button)
        self.navbar.addSeparator()

        self.security_badge = QLabel("⌂")
        self.security_badge.setObjectName("securityBadge")
        self.navbar.addWidget(self.security_badge)

        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("Search or type a web address")
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        self.url_bar.setClearButtonEnabled(True)
        self.url_bar.setMinimumWidth(360)
        self.navbar.addWidget(self.url_bar)

        self.find_bar = QLineEdit()
        self.find_bar.setObjectName("findBar")
        self.find_bar.setPlaceholderText("Find in page")
        self.find_bar.setClearButtonEnabled(True)
        self.find_bar.setVisible(False)
        self.find_bar.textChanged.connect(self.find_in_page)
        self.find_bar.returnPressed.connect(self.find_in_page)
        self.navbar.addWidget(self.find_bar)

    def create_status_bar(self):
        self.status = QStatusBar()
        self.setStatusBar(self.status)

        self.download_button = QPushButton("Downloads")
        self.download_button.setFlat(True)
        self.download_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.download_button.clicked.connect(self.open_download_folder)
        self.status.addPermanentWidget(self.download_button)

        self.download_bar = QProgressBar()
        self.download_bar.setMaximumWidth(160)
        self.download_bar.setTextVisible(False)
        self.download_bar.setVisible(False)
        self.status.addPermanentWidget(self.download_bar)

        self.progress = QProgressBar()
        self.progress.setMaximumWidth(160)
        self.progress.setTextVisible(False)
        self.status.addPermanentWidget(self.progress)
        self.status.showMessage("Ready")

    def add_new_tab(self, url=None, label="New tab"):
        browser = BrowserView(self)
        browser.urlChanged.connect(self.update_url)
        browser.titleChanged.connect(lambda title, view=browser: self.update_tab_title(view, title))
        browser.iconChanged.connect(lambda icon, view=browser: self.update_tab_icon(view, icon))
        browser.loadStarted.connect(self.on_load_started)
        browser.loadProgress.connect(self.on_load_progress)
        browser.loadFinished.connect(self.on_load_finished)
        if url:
            browser.setUrl(QUrl(url))
        index = self.tabs.addTab(browser, label)
        self.tabs.setCurrentIndex(index)
        self.refresh_chrome()
        return browser

    def open_new_tab(self):
        self.add_new_tab(homepage_url(), "New tab")

    def duplicate_tab(self):
        browser = self.current_browser()
        if browser:
            self.add_new_tab(browser.url().toString(), browser.title() or "New tab")

    def close_tab(self, index):
        browser = self.tabs.widget(index)
        if isinstance(browser, QWebEngineView):
            url = browser.url().toString()
            if url:
                self.closed_tabs.append(url)
                self.closed_tabs = self.closed_tabs[-20:]
        if self.tabs.count() == 1:
            self.add_new_tab(homepage_url(), "New tab")
        self.tabs.removeTab(index)

    def reopen_closed_tab(self):
        if not self.closed_tabs:
            self.status.showMessage("No recently closed tabs")
            return
        self.add_new_tab(self.closed_tabs.pop(), "New tab")

    def cycle_tab(self, step):
        count = self.tabs.count()
        if count:
            self.tabs.setCurrentIndex((self.tabs.currentIndex() + step) % count)

    def show_tab_menu(self, position):
        index = self.tabs.tabBar().tabAt(position)
        if index < 0:
            return
        menu = QMenu(self)
        menu.addAction("New tab", self.open_new_tab)
        menu.addAction("Duplicate tab", self.duplicate_tab)
        menu.addAction("Close tab", lambda: self.close_tab(index))
        menu.addAction("Close other tabs", lambda: self.close_other_tabs(index))
        menu.exec(self.tabs.tabBar().mapToGlobal(position))

    def close_other_tabs(self, keep_index):
        for index in range(self.tabs.count() - 1, -1, -1):
            if index != keep_index:
                self.close_tab(index)

    def on_tab_changed(self, _index):
        self.refresh_chrome()
        self.status.showMessage("Ready")

    def refresh_chrome(self):
        self.update_navigation_buttons()
        self.update_bookmark_button()
        self.update_security_badge()
        browser = self.current_browser()
        if browser:
            self.url_bar.setText(self.display_url(browser.url()))

    def display_url(self, qurl: QUrl) -> str:
        if is_homepage_url(qurl):
            return ""
        return qurl.toString()

    def update_security_badge(self):
        browser = self.current_browser()
        if not browser:
            self.security_badge.setText("")
            return
        url = browser.url()
        if is_homepage_url(url):
            self.security_badge.setText("⌂")
            self.security_badge.setToolTip("New tab")
        elif url.scheme() == "https":
            self.security_badge.setText("🔒")
            self.security_badge.setToolTip("Secure connection")
        elif url.scheme() == "http":
            self.security_badge.setText("!")
            self.security_badge.setToolTip("Not secure")
        else:
            self.security_badge.setText("•")
            self.security_badge.setToolTip(url.scheme() or "Local")

    def update_navigation_buttons(self):
        browser = self.current_browser()
        if not browser:
            self.back_button.setEnabled(False)
            self.forward_button.setEnabled(False)
            return
        history = browser.history()
        self.back_button.setEnabled(history.canGoBack())
        self.forward_button.setEnabled(history.canGoForward())

    def navigate_home(self):
        browser = self.current_browser()
        if browser:
            browser.setUrl(QUrl(homepage_url()))

    def navigate_to_url(self):
        browser = self.current_browser()
        if not browser:
            return
        browser.setUrl(QUrl(resolve_address(self.url_bar.text())))

    def open_url_in_current_tab(self, url):
        browser = self.current_browser()
        if browser:
            browser.setUrl(QUrl(url))
        else:
            self.add_new_tab(url, "New tab")

    def update_url(self, qurl):
        if self.sender() is self.current_browser():
            self.url_bar.setText(self.display_url(qurl))
            self.update_security_badge()
            self.update_bookmark_button()
            self.update_navigation_buttons()

    def update_tab_title(self, browser, title):
        for index in range(self.tabs.count()):
            if self.tabs.widget(index) is browser:
                self.tabs.setTabText(index, title or "New tab")
                break

    def update_tab_icon(self, browser, icon):
        for index in range(self.tabs.count()):
            if self.tabs.widget(index) is browser:
                self.tabs.setTabIcon(index, icon)
                break

    def on_load_started(self):
        if self.sender() is self.current_browser():
            self.status.showMessage("Loading…")
            self.progress.setValue(0)

    def on_load_progress(self, progress):
        if self.sender() is self.current_browser():
            self.progress.setValue(progress)
            self.status.showMessage(f"Loading… {progress}%")

    def on_load_finished(self, ok):
        browser = self.sender()
        if not isinstance(browser, QWebEngineView):
            return
        if ok and not is_homepage_url(browser.url()):
            self.add_history_entry(browser.title(), browser.url().toString())
        if browser is self.current_browser():
            self.progress.setValue(100 if ok else 0)
            self.status.showMessage("Ready" if ok else "Failed to load page")
            self.refresh_chrome()

    def focus_url_bar(self):
        self.url_bar.setFocus()
        self.url_bar.selectAll()

    def focus_find_bar(self):
        self.find_bar.setVisible(True)
        self.find_bar.setFocus()
        self.find_bar.selectAll()

    def stop_or_close_find(self):
        if self.find_bar.isVisible():
            self.find_bar.clear()
            self.find_bar.setVisible(False)
            browser = self.current_browser()
            if browser:
                browser.findText("")
            return
        browser = self.current_browser()
        if browser:
            browser.stop()

    def find_in_page(self):
        browser = self.current_browser()
        if browser:
            browser.findText(self.find_bar.text())

    def is_bookmarked(self, url):
        return any(url == existing for _, existing in self.bookmarks)

    def update_bookmarks_menu(self):
        self.bookmarks_menu.clear()
        self.bookmarks_menu.addAction("Bookmark this page", self.toggle_bookmark)
        self.bookmarks_menu.addAction("Manage bookmarks", self.show_bookmark_manager)
        self.bookmarks_menu.addSeparator()
        if not self.bookmarks:
            empty = QAction("No bookmarks yet", self)
            empty.setEnabled(False)
            self.bookmarks_menu.addAction(empty)
            return
        for title, url in self.bookmarks:
            action = QAction(title, self)
            action.triggered.connect(lambda checked=False, link=url, name=title: self.add_new_tab(link, name))
            self.bookmarks_menu.addAction(action)

    def update_history_menu(self):
        self.history_menu.clear()
        self.history_menu.addAction("Show history", self.show_history_manager)
        self.history_menu.addSeparator()
        if not self.history:
            empty = QAction("No history yet", self)
            empty.setEnabled(False)
            self.history_menu.addAction(empty)
            return
        for title, url in reversed(self.history[-12:]):
            label = title if len(title) <= 48 else f"{title[:45]}…"
            action = QAction(label, self)
            action.triggered.connect(lambda checked=False, link=url: self.open_url_in_current_tab(link))
            self.history_menu.addAction(action)
        self.history_menu.addSeparator()
        self.history_menu.addAction("Clear history", self.clear_history)

    def add_history_entry(self, title, url):
        if not url or url.startswith("file:"):
            return
        if self.history and self.history[-1][1] == url:
            self.history[-1] = (title or url, url)
        else:
            self.history.append((title or url, url))
        self.history = self.history[-80:]
        save_json_pairs(HISTORY_FILE, self.history)
        self.update_history_menu()

    def clear_history(self):
        self.history.clear()
        save_json_pairs(HISTORY_FILE, self.history)
        self.update_history_menu()
        self.status.showMessage("History cleared")

    def toggle_bookmark(self):
        browser = self.current_browser()
        if not browser:
            return
        url = browser.url().toString()
        title = browser.title() or url
        if self.is_bookmarked(url):
            self.bookmarks = [(name, link) for name, link in self.bookmarks if link != url]
            self.status.showMessage(f"Removed bookmark “{title}”")
        else:
            self.bookmarks.append((title, url))
            self.status.showMessage(f"Bookmarked “{title}”")
        save_json_pairs(BOOKMARKS_FILE, self.bookmarks)
        self.update_bookmarks_menu()
        self.update_bookmark_button()

    def update_bookmark_button(self):
        browser = self.current_browser()
        url = browser.url().toString() if browser else ""
        starred = bool(url and self.is_bookmarked(url))
        self.bookmark_button.setIcon(paint_icon("★" if starred else "☆", "#EAB308" if starred else "#334155"))
        self.bookmark_button.setToolTip("Remove bookmark" if starred else "Bookmark this page (Ctrl+D)")

    def show_list_dialog(self, title, pairs, on_open, on_delete=None):
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setMinimumSize(460, 400)
        layout = QVBoxLayout(dialog)
        list_widget = QListWidget(dialog)
        for name, url in pairs:
            item = QListWidgetItem(f"{name}\n{url}")
            item.setData(Qt.ItemDataRole.UserRole, url)
            list_widget.addItem(item)
        layout.addWidget(list_widget)
        buttons = QHBoxLayout()
        open_button = QPushButton("Open")
        open_button.setObjectName("primaryButton")
        close_button = QPushButton("Close")
        buttons.addWidget(open_button)
        if on_delete:
            delete_button = QPushButton("Delete")
            buttons.addWidget(delete_button)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

        def open_selected():
            item = list_widget.currentItem()
            if item:
                on_open(item.data(Qt.ItemDataRole.UserRole))
                dialog.accept()

        open_button.clicked.connect(open_selected)
        list_widget.itemDoubleClicked.connect(lambda _item: open_selected())
        if on_delete:
            def delete_selected():
                item = list_widget.currentItem()
                if item:
                    on_delete(item.data(Qt.ItemDataRole.UserRole))
                    list_widget.takeItem(list_widget.row(item))
            delete_button.clicked.connect(delete_selected)
        close_button.clicked.connect(dialog.reject)
        dialog.exec()

    def show_bookmark_manager(self):
        def delete_url(url):
            self.bookmarks = [(name, link) for name, link in self.bookmarks if link != url]
            save_json_pairs(BOOKMARKS_FILE, self.bookmarks)
            self.update_bookmarks_menu()
            self.update_bookmark_button()
            self.status.showMessage("Bookmark removed")

        self.show_list_dialog(
            "Bookmarks",
            self.bookmarks,
            lambda url: self.open_url_in_current_tab(url),
            delete_url,
        )

    def show_history_manager(self):
        self.show_list_dialog(
            "History",
            list(reversed(self.history)),
            lambda url: self.open_url_in_current_tab(url),
        )

    def on_download_requested(self, download: QWebEngineDownloadRequest):
        suggested = download.suggestedFileName() or download.downloadFileName() or "download"
        folder = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
        path, _ = QFileDialog.getSaveFileName(self, "Save file", os.path.join(folder, suggested))
        if not path:
            download.cancel()
            return
        download.setDownloadDirectory(os.path.dirname(path))
        download.setDownloadFileName(os.path.basename(path))
        download.accept()
        self.download_button.setText("Downloading…")
        self.download_bar.setVisible(True)
        self.download_bar.setValue(0)
        self.status.showMessage("Downloading…")
        download.receivedBytesChanged.connect(lambda: self.update_download_progress(download))
        download.isFinishedChanged.connect(lambda: self.on_download_finished(download) if download.isFinished() else None)

    def update_download_progress(self, download):
        received = download.receivedBytes()
        total = download.totalBytes()
        if total > 0:
            percent = int(received * 100 / total)
            self.download_bar.setMaximum(100)
            self.download_bar.setValue(percent)
            self.status.showMessage(f"Downloading… {percent}%")
        else:
            self.download_bar.setMaximum(0)
            self.status.showMessage("Downloading…")

    def on_download_finished(self, download):
        name = download.downloadFileName()
        if download.state() == QWebEngineDownloadRequest.DownloadState.DownloadCompleted:
            self.status.showMessage(f"Downloaded {name}")
        else:
            self.status.showMessage("Download canceled or failed")
        self.download_button.setText("Downloads")
        QTimer.singleShot(3500, self.clear_download_status)

    def clear_download_status(self):
        self.download_bar.setVisible(False)
        self.download_bar.setMaximum(100)
        self.download_button.setText("Downloads")

    def open_download_folder(self):
        folder = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
        if not os.path.isdir(folder):
            folder = os.path.expanduser("~")
        try:
            os.startfile(folder)
        except OSError:
            self.status.showMessage(f"Cannot open {folder}")

    def on_fullscreen_requested(self, request):
        request.accept()
        if request.toggleOn():
            self._was_maximized = self.isMaximized()
            self.menuBar().hide()
            self.navbar.hide()
            self.status.hide()
            self.tabs.tabBar().hide()
            self.showFullScreen()
        else:
            self.menuBar().show()
            self.navbar.show()
            self.status.show()
            self.tabs.tabBar().show()
            if self._was_maximized:
                self.showMaximized()
            else:
                self.showNormal()

    def zoom_in(self):
        browser = self.current_browser()
        if browser:
            browser.setZoomFactor(min(browser.zoomFactor() + 0.1, 3.0))

    def zoom_out(self):
        browser = self.current_browser()
        if browser:
            browser.setZoomFactor(max(browser.zoomFactor() - 0.1, 0.3))

    def reset_zoom(self):
        browser = self.current_browser()
        if browser:
            browser.setZoomFactor(1.0)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Gnoiss")
    app.setOrganizationName("Gnoiss")
    window = MainWindow()
    app.exec()
