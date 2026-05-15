"""History page for browsing previous training sessions."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSplitter, QSizePolicy, QTableWidgetItem, QVBoxLayout, QWidget

from app.ui.base import BasePage
from app.ui.fluent_compat import BodyLabel, PageTitleLabel, TableWidget, TextEdit

MATPLOTLIB_OK = False
SEABORN_OK = False
try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure

    MATPLOTLIB_OK = True
except Exception:
    MATPLOTLIB_OK = False
try:
    import seaborn as sns

    SEABORN_OK = True
except Exception:
    SEABORN_OK = False


class HistoryPage(BasePage):
    def __init__(self, db, user, parent=None):
        super().__init__(db, user, parent)
        self.records = []
        self.setup_ui()
        self.refresh_data()

    def setup_ui(self) -> None:
        self.main_layout.addWidget(PageTitleLabel("History Records"))

        card, card_layout = self.create_section_card()
        mini_title = BodyLabel("Session History")
        mini_title.setStyleSheet("font-weight: 700; color: #0F172A; background: transparent; border: none;")
        mini_title.setFixedHeight(16)
        card_layout.addWidget(mini_title)
        splitter = QSplitter(Qt.Horizontal)
        left_wrap = QWidget()
        left_layout = QVBoxLayout(left_wrap)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)
        self.table = TableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Record ID", "Action", "Avg Score", "Completion", "Pain", "End Time"])
        self.table.cellClicked.connect(self.show_record_detail)
        left_layout.addWidget(self.table)
        if MATPLOTLIB_OK:
            self.trend_fig = Figure(figsize=(6.2, 3.5), dpi=100)
            self.trend_canvas = FigureCanvas(self.trend_fig)
            self.trend_canvas.setMinimumHeight(280)
            self.trend_canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            left_layout.addWidget(self.trend_canvas)
        left_layout.setStretch(0, 5)
        left_layout.setStretch(1, 4)
        self.detail_text = TextEdit()
        self.detail_text.setReadOnly(True)
        splitter.addWidget(left_wrap)
        splitter.addWidget(self.detail_text)
        splitter.setSizes([760, 420])
        card_layout.addWidget(splitter)
        self.main_layout.addWidget(card, 1)

    def _render_history_trend(self) -> None:
        if not MATPLOTLIB_OK:
            return
        if SEABORN_OK:
            sns.set_theme(style="whitegrid", rc={"axes.labelsize": 8, "axes.titlesize": 10, "xtick.labelsize": 8, "ytick.labelsize": 8})
        self.trend_fig.clear()
        ax = self.trend_fig.add_subplot(111)
        if self.records:
            values = list(reversed([row["avg_score"] or 0 for row in self.records[:15]]))
            x = list(range(1, len(values) + 1))
            if SEABORN_OK:
                sns.lineplot(x=x, y=values, marker="o", ax=ax, color="#2563EB")
            else:
                ax.plot(x, values, marker="o", color="#2563EB")
            ax.set_ylim(0, 100)
            ax.set_title("Recent Score Trend", fontsize=10, pad=8)
            ax.set_xlabel("Order", fontsize=8)
            ax.set_ylabel("Avg Score", fontsize=8)
            ax.tick_params(axis="both", labelsize=8)
        else:
            ax.text(0.5, 0.5, "No data", ha="center", va="center")
            ax.set_axis_off()
        self.trend_fig.tight_layout(pad=0.8)
        self.trend_canvas.draw()

    def refresh_data(self) -> None:
        self.records = self.db.get_records(self.user["id"], limit=50)
        self.table.setRowCount(len(self.records))
        for row, record in enumerate(self.records):
            values = [
                record["id"],
                record["action_name"],
                record["avg_score"],
                f"{round((record['completion_rate'] or 0) * 100, 2)}%",
                record["pain_feedback"],
                record["session_end"],
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(str(value)))
        self._render_history_trend()
        if self.records:
            self.show_record_detail(0, 0)
        else:
            self.detail_text.setPlainText("No historical training records are available.")

    def show_record_detail(self, row: int, column: int) -> None:
        if not self.records or row < 0 or row >= len(self.records):
            return

        record_id = self.records[row]["id"]
        details = self.db.get_record_details(record_id)
        record = details["record"]
        errors = details["errors"]
        compensations = details["compensations"]
        feedbacks = details["feedbacks"]

        if not record:
            self.detail_text.setPlainText("This record does not exist.")
            return

        lines = [
            "[Session Overview]",
            f"- Record ID: {record['id']}",
            f"- Action: {record['action_name']}",
            f"- Average score: {record['avg_score']}",
            f"- Completion rate: {round((record['completion_rate'] or 0) * 100, 2)}%",
            f"- Summary: {record['summary']}",
            "",
            "[Error Actions]",
        ]
        for item in errors:
            lines.append(f"- {item['error_type']} x {item['error_count']}")
        if not errors:
            lines.append("- None")

        lines.extend(["", "[Compensation Actions]"])
        for item in compensations:
            lines.append(f"- {item['compensation_type']} x {item['detected_count']}")
        if not compensations:
            lines.append("- None")

        lines.extend(["", "[Feedback Records]"])
        for item in feedbacks[-5:]:
            lines.append(f"- {item['feedback_content']}")
        if not feedbacks:
            lines.append("- No feedback available.")

        self.detail_text.setPlainText("\n".join(lines))
