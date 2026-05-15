"""Analysis page showing trends, distributions, and adaptive recommendations."""

from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QSizePolicy, QWidget

from app.ui.base import BasePage
from app.ui.fluent_compat import BodyLabel, PageTitleLabel

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


class AnalysisPage(BasePage):
    def __init__(self, db, user, parent=None):
        super().__init__(db, user, parent)
        self.setup_ui()
        self.refresh_data()

    def setup_ui(self) -> None:
        self.main_layout.addWidget(PageTitleLabel("Data Analysis"))

        summary_card, summary_layout = self.create_section_card("Key Indicators")
        self.summary_line_1 = BodyLabel("")
        self.summary_line_2 = BodyLabel("")
        self.summary_line_1.setStyleSheet("color: #0F172A; font-weight: 600; background: transparent; border: none;")
        self.summary_line_2.setStyleSheet("color: #334155; background: transparent; border: none;")
        summary_layout.addWidget(self.summary_line_1)
        summary_layout.addWidget(self.summary_line_2)
        self.main_layout.addWidget(summary_card)

        chart_card, chart_card_layout = self.create_section_card("Charts")
        chart_wrap = QWidget()
        chart_layout = QHBoxLayout(chart_wrap)
        chart_layout.setContentsMargins(0, 0, 0, 0)
        chart_layout.setSpacing(10)

        self.chart_info = BodyLabel("")
        if MATPLOTLIB_OK:
            self.score_fig = Figure(figsize=(6.2, 4.3), dpi=100)
            self.score_canvas = FigureCanvas(self.score_fig)
            self.score_canvas.setMinimumHeight(380)
            self.score_canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.dist_fig = Figure(figsize=(6.2, 4.3), dpi=100)
            self.dist_canvas = FigureCanvas(self.dist_fig)
            self.dist_canvas.setMinimumHeight(380)
            self.dist_canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            chart_layout.addWidget(self.score_canvas)
            chart_layout.addWidget(self.dist_canvas)
        else:
            self.chart_info.setText("Matplotlib is not available. Install it to enable charts.")
            chart_layout.addWidget(self.chart_info)
        chart_card_layout.addWidget(chart_wrap)
        self.main_layout.addWidget(chart_card, 3)

        detail_card, detail_layout = self.create_section_card("Analysis Highlights")
        detail_grid = QGridLayout()
        detail_grid.setContentsMargins(0, 0, 0, 0)
        detail_grid.setHorizontalSpacing(10)
        detail_grid.setVerticalSpacing(10)
        self.overview_label = self._create_detail_block(detail_grid, 0, 0, "Overview")
        self.risk_label = self._create_detail_block(detail_grid, 0, 1, "Risk Focus")
        self.snapshot_label = self._create_detail_block(detail_grid, 1, 0, "Latest Snapshot")
        self.plan_label = self._create_detail_block(detail_grid, 1, 1, "Plan Follow-up")
        detail_layout.addLayout(detail_grid)
        self.main_layout.addWidget(detail_card, 2)

    def _create_detail_block(self, grid: QGridLayout, row: int, column: int, title: str):
        card, layout = self.create_section_card(title)
        label = BodyLabel("")
        label.setWordWrap(True)
        label.setStyleSheet("color: #334155; background: transparent; border: none; line-height: 1.45;")
        layout.addWidget(label)
        grid.addWidget(card, row, column)
        return label

    @staticmethod
    def _style_axis(ax, title: str = "", xlabel: str = "", ylabel: str = "") -> None:
        ax.set_title(title, fontsize=10, pad=8)
        ax.set_xlabel(xlabel, fontsize=8)
        ax.set_ylabel(ylabel, fontsize=8)
        ax.tick_params(axis="both", labelsize=8)
        for spine in ax.spines.values():
            spine.set_color("#CBD5E1")

    def _render_charts(self, trend_rows, error_dist, comp_dist) -> None:
        if not MATPLOTLIB_OK:
            return

        if SEABORN_OK:
            sns.set_theme(style="whitegrid", rc={"axes.labelsize": 8, "axes.titlesize": 10, "xtick.labelsize": 8, "ytick.labelsize": 8})

        self.score_fig.clear()
        ax1 = self.score_fig.add_subplot(111)
        if trend_rows:
            x_labels = [str(item["id"]) for item in trend_rows]
            y_scores = [item["avg_score"] or 0 for item in trend_rows]
            y_completion = [(item["completion_rate"] or 0) * 100 for item in trend_rows]
            if SEABORN_OK:
                sns.lineplot(x=x_labels, y=y_scores, marker="o", ax=ax1, label="Avg Score", color="#2563EB")
                sns.lineplot(x=x_labels, y=y_completion, marker="s", ax=ax1, label="Completion %", color="#0EA5A4")
            else:
                ax1.plot(x_labels, y_scores, marker="o", label="Avg Score", color="#2563EB")
                ax1.plot(x_labels, y_completion, marker="s", label="Completion %", color="#0EA5A4")
            ax1.set_ylim(0, 100)
            self._style_axis(ax1, "Score & Completion Trend", "Session ID", "Value")
            legend = ax1.legend(frameon=False, fontsize=8)
            if legend:
                legend.set_title(None)
        else:
            ax1.text(0.5, 0.5, "No trend data", ha="center", va="center")
            ax1.set_axis_off()
        self.score_fig.tight_layout(pad=0.8)
        self.score_canvas.draw()

        self.dist_fig.clear()
        ax2 = self.dist_fig.add_subplot(111)
        labels = []
        values = []
        colors = []
        for item in error_dist[:4]:
            labels.append(f"E:{item['label']}")
            values.append(item["count"] or 0)
            colors.append("#EF4444")
        for item in comp_dist[:4]:
            labels.append(f"C:{item['label']}")
            values.append(item["count"] or 0)
            colors.append("#F59E0B")

        if values:
            if SEABORN_OK:
                sns.barplot(x=values, y=labels, hue=labels, dodge=False, palette=colors, legend=False, ax=ax2)
            else:
                y_pos = list(range(len(labels)))
                ax2.barh(y_pos, values, color=colors)
                ax2.set_yticks(y_pos)
                ax2.set_yticklabels(labels)
            self._style_axis(ax2, "Error & Compensation Distribution", "Count", "Label")
        else:
            ax2.text(0.5, 0.5, "No distribution data", ha="center", va="center")
            ax2.set_axis_off()
        self.dist_fig.tight_layout(pad=0.8)
        self.dist_canvas.draw()

    def refresh_data(self) -> None:
        info = self.db.get_analysis_summary(self.user["id"])
        trend_rows = self.db.get_score_trend(self.user["id"], limit=10)
        error_dist = self.db.get_error_distribution(self.user["id"], limit=6)
        comp_dist = self.db.get_compensation_distribution(self.user["id"], limit=6)
        adjustments = self.db.get_plan_adjustments(self.user["id"])
        adaptive = self.db.build_adaptive_plan_suggestion(self.user["id"])
        active_plan = self.db.get_active_plan(self.user["id"])

        self.summary_line_1.setText(
            f"Session Count: {info['session_count']}   |   Average Score: {info['avg_score']}   |   Best Score: {info['best_score']}"
        )
        self.summary_line_2.setText(
            f"Trend: {info['trend']}   |   Average Completion: {info['avg_completion']}%   |   Average Pain Score: {info['avg_pain']}"
        )
        self._render_charts(trend_rows, error_dist, comp_dist)

        top_error = error_dist[0]["label"] if error_dist else "None"
        top_comp = comp_dist[0]["label"] if comp_dist else "None"
        latest = trend_rows[-1] if trend_rows else None
        prev = trend_rows[-2] if len(trend_rows) > 1 else None
        delta = 0
        if latest and prev:
            delta = round((latest.get("avg_score") or 0) - (prev.get("avg_score") or 0), 2)
        adjust_line = f"Score change vs previous: {delta:+}" if latest and prev else "Score change vs previous: N/A"
        latest_line = "- No recent session." if not latest else (
            f"- Session #{latest['id']} | Score {latest['avg_score']} | "
            f"Completion {round((latest['completion_rate'] or 0) * 100, 2)}%"
        )

        overview_lines = [
            f"Trend: {info['trend']}",
            f"Sessions: {info['session_count']} | Avg: {info['avg_score']} | Best: {info['best_score']}",
            f"Completion: {info['avg_completion']}% | Pain: {info['avg_pain']}",
            adjust_line,
        ]
        risk_lines = [
            f"Main error: {top_error}",
            f"Main compensation: {top_comp}",
            f"Attention level: {'Elevated' if top_error != 'None' or top_comp != 'None' else 'Stable'}",
        ]
        snapshot_lines = [latest_line.replace("- ", "", 1)]
        if trend_rows:
            snapshot_lines.append(f"Recent sessions reviewed: {min(len(trend_rows), 10)}")
        else:
            snapshot_lines.append("Recent sessions reviewed: 0")

        if self.user.get("role") == "doctor":
            plan_lines = [
                f"Decision: {adaptive.get('decision', '-')}",
                f"Basis: {adaptive.get('basis', '-')}",
            ]
            if adaptive.get("diff"):
                plan_lines.append("Key changes:")
                for item in adaptive.get("diff")[:3]:
                    plan_lines.append(f"- {item}")
        else:
            plan_lines = [
                f"Current action: {active_plan.get('target_action', '-') if active_plan else '-'}",
                (
                    f"Target volume: {active_plan.get('sets_count', '-')} sets x "
                    f"{active_plan.get('reps_count', '-')} reps"
                ) if active_plan else "Target volume: -",
                "Plan changes are reviewed by the care team.",
            ]
        if adjustments:
            recent_adjustments = [f"- {item['created_at']} | {item['adjustment_reason']}" for item in adjustments[:2]]
            plan_lines.append("Recent plan updates:")
            plan_lines.extend(recent_adjustments)

        self.overview_label.setText("\n".join(overview_lines))
        self.risk_label.setText("\n".join(risk_lines))
        self.snapshot_label.setText("\n".join(snapshot_lines))
        self.plan_label.setText("\n".join(plan_lines))
