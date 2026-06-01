"""
ui.py — thin re-export shim.
All rendering logic lives in the focused sub-modules below.
Import from here for backwards compatibility with app.py.
"""
from src.ui_shared import (  # noqa: F401
    ACCENTURE_PURPLE_CORE,
    ACCENTURE_PURPLE_DARK,
    ACCENTURE_PURPLE_DARKEST,
    ACCENTURE_PURPLE_LIGHT,
    ACCENTURE_PURPLE_LIGHTEST,
    load_custom_css,
    render_hero_header,
    render_sidebar_controls,
    render_sidebar_filters,
    render_process_auth_gate,
    render_logout_control,
)
from src.ui_process import render_process_pre, render_process_post  # noqa: F401
from src.ui_results import render_tab_resultados  # noqa: F401
from src.ui_opportunities import render_tab_opportunities  # noqa: F401
from src.ui_initiatives import render_tab_initiatives  # noqa: F401
from src.ui_logs import render_tab_logs  # noqa: F401
from src.ui_reporting import render_tab_reporting  # noqa: F401
