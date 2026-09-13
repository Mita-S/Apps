"""
Build a Digit Dataset — entry point
====================================
A stripped-down sibling of Digit Canvas Studio: no model, no preprocessing
tour, no local-disk backend. It does one job — collect handwritten digits
and append them to a Google Sheet, one row per digit, MNIST-shaped.

Two pages, both behind Google sign-in:

  - Collect (pages/collect.py) -- anyone signed in draws a digit, labels it,
                                  and saves it straight to the Sheet.
  - Review  (pages/review.py)  -- only emails listed under `[admin] emails`
                                  in .streamlit/secrets.toml see this page;
                                  it approves or rejects pending samples and
                                  exports the approved set as CSV.

Setup (Google sign-in + the Sheet): SETUP.md

Run with:  streamlit run app.py
"""

import streamlit as st

import auth

st.set_page_config(
    page_title="Build a Digit Dataset",
    page_icon="🔢",
    layout="wide",
    initial_sidebar_state="expanded",
)

auth.require_login()  # stops here with a "Sign in with Google" screen if needed
auth.user_badge()

pages = [st.Page("pages/collect.py", title="Collect", icon="✍️", default=True)]

if auth.is_admin():
    pages.append(st.Page("pages/review.py", title="Review", icon="🛠️"))

st.navigation(pages).run()
