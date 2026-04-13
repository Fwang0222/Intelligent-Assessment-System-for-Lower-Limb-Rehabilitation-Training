"""Main application window and page registration."""

from app.ui.fluent_compat import FluentWindow, get_icon
from app.ui.pages.analysis_page import AnalysisPage
from app.ui.pages.history_page import HistoryPage
from app.ui.pages.home_page import HomePage
from app.ui.pages.plan_page import PlanPage
from app.ui.pages.profile_page import ProfilePage
from app.ui.pages.realtime_training_page import RealtimeTrainingPage
from app.ui.pages.result_page import ResultPage


class RehabMainWindow(FluentWindow):
    def __init__(self, db, user, parent=None):
        super().__init__(parent)
        self.db = db
        self.user = user
        self.setWindowTitle("Lower-Limb Rehabilitation Intelligent Assessment System - English Demo")
        self.resize(1400, 900)
        self.init_pages()

    def init_pages(self) -> None:
        self.home_page = HomePage(self.db, self.user)
        self.profile_page = ProfilePage(self.db, self.user)
        self.realtime_page = RealtimeTrainingPage(self.db, self.user, refresh_callback=self.refresh_all_pages)
        self.result_page = ResultPage(self.db, self.user)
        self.plan_page = PlanPage(self.db, self.user, refresh_callback=self.refresh_all_pages)
        self.history_page = HistoryPage(self.db, self.user)
        self.analysis_page = AnalysisPage(self.db, self.user)

        page_defs = [
            (self.home_page, "home_page", "Dashboard"),
            (self.profile_page, "profile_page", "Rehab Profile"),
            (self.realtime_page, "realtime_page", "Real-Time Training"),
            (self.result_page, "result_page", "Training Results"),
            (self.plan_page, "plan_page", "Training Plans"),
            (self.history_page, "history_page", "History Records"),
            (self.analysis_page, "analysis_page", "Data Analysis"),
        ]

        icon = get_icon()
        for page, name, title in page_defs:
            page.setObjectName(name)
            self.addSubInterface(page, icon, title)

    def refresh_all_pages(self) -> None:
        for page in [
            self.home_page,
            self.profile_page,
            self.realtime_page,
            self.result_page,
            self.plan_page,
            self.history_page,
            self.analysis_page,
        ]:
            if hasattr(page, "refresh_data"):
                page.refresh_data()
