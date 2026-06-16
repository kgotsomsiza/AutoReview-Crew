"""Compatibility entrypoint for Streamlit Community Cloud.

The final hackathon companion app lives in app.py. Some deployment templates
default to streamlit_app.py, so importing app keeps both entrypoints equivalent.
"""

import app  # noqa: F401
