from typing import Any, Dict, List, Optional
import plotly.graph_objects as go
from frontend.components.theme import (
    COLOR_AMBER,
    COLOR_AMBER_LIGHT,
    COLOR_BORDER_GREY,
    COLOR_CORAL,
    COLOR_CORAL_LIGHT,
    COLOR_NAVY,
    COLOR_TEAL,
    COLOR_TEAL_LIGHT,
    COLOR_TEAL_MID,
    COLOR_WHITE,
    COLOR_MUTED_GREY,
    get_status_display,
)


def build_feature_drift_chart(per_feature_results: List[Dict[str, Any]]) -> Optional[go.Figure]:
    """Horizontal bar chart of per-feature drift test statistics.
    
    Teal for no drift, Amber for drift, with clear threshold indicators.
    """
    if not per_feature_results:
        return None

    features = []
    stats = []
    colors = []
    hover_texts = []

    for item in per_feature_results:
        feat = str(item.get("feature", "Unknown"))
        stat = float(item.get("statistic", 0.0))
        status = str(item.get("status", "no_drift")).lower()
        test_name = str(item.get("test_name", "")).replace("_", " ").title()
        p_val = item.get("p_value")
        p_str = f"{p_val:.4f}" if isinstance(p_val, (int, float)) else "N/A"

        features.append(feat)
        stats.append(stat)

        if status == "drift":
            colors.append(COLOR_AMBER)
        elif status == "significant_low_effect":
            colors.append(COLOR_AMBER_LIGHT)
        elif "skipped" in status:
            colors.append(COLOR_MUTED_GREY)
        else:
            colors.append(COLOR_TEAL)

        hover_texts.append(
            f"<b>{feat}</b><br>"
            f"Test: {test_name}<br>"
            f"Statistic: {stat:.4f}<br>"
            f"p-value: {p_str}<br>"
            f"Status: {status}"
        )

    fig = go.Figure(
        go.Bar(
            y=features,
            x=stats,
            orientation="h",
            marker=dict(color=colors),
            text=[f"{s:.3f}" for s in stats],
            textposition="auto",
            hovertext=hover_texts,
            hoverinfo="text",
        )
    )

    fig.update_layout(
        title="Per-Feature Distribution Shift (Test Statistic)",
        xaxis_title="Statistic (KS D / Chi² / TVD)",
        yaxis_title="Feature",
        height=max(320, len(features) * 32),
        margin=dict(l=20, r=20, t=40, b=30),
    )
    return fig


def build_confusion_matrix_heatmap(
    confusion_matrix: List[List[int]],
    class_labels: List[str],
) -> Optional[go.Figure]:
    """Heatmap for confusion matrix using Teal sequential palette."""
    if not confusion_matrix:
        return None

    z = confusion_matrix
    x = [f"Pred {c}" for c in class_labels]
    y = [f"True {c}" for c in class_labels]

    text = [[str(val) for val in row] for row in z]

    fig = go.Figure(
        data=go.Heatmap(
            z=z,
            x=x,
            y=y,
            colorscale=[[0, COLOR_WHITE], [0.5, COLOR_TEAL_MID], [1.0, COLOR_TEAL]],
            text=text,
            texttemplate="%{text}",
            textfont=dict(size=14, color=COLOR_NAVY),
            showscale=False,
        )
    )

    fig.update_layout(
        title="Confusion Matrix",
        margin=dict(l=40, r=20, t=40, b=40),
        height=320,
    )
    return fig


def build_metric_comparison_chart(
    baseline_metrics: Dict[str, Any],
    incoming_metrics: Dict[str, Any],
) -> Optional[go.Figure]:
    """Grouped bar chart comparing baseline vs incoming metrics."""
    metrics_to_show = ["accuracy", "f1", "precision", "recall"]
    labels = ["Accuracy", "Macro F1", "Precision", "Recall"]

    base_vals = [float(baseline_metrics.get(m, 0.0) or 0.0) for m in metrics_to_show]
    inc_vals = [float(incoming_metrics.get(m, 0.0) or 0.0) for m in metrics_to_show]

    fig = go.Figure(
        data=[
            go.Bar(name="Baseline", x=labels, y=base_vals, marker_color=COLOR_NAVY),
            go.Bar(name="Incoming Stream", x=labels, y=inc_vals, marker_color=COLOR_TEAL),
        ]
    )

    fig.update_layout(
        barmode="group",
        title="Baseline vs. Current Evaluated Performance",
        yaxis=dict(range=[0, 1.05], tickformat=".0%"),
        height=320,
        margin=dict(l=20, r=20, t=40, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig
