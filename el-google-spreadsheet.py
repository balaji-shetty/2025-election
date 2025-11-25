# app.py
import os
import time
import io
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
from datetime import datetime

# ---------- Page config ----------
st.set_page_config(
    page_title="Nanded Election Dashboard (All Graphs)",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🗳️ Nanded Election Dashboard — All Visuals (Tabs + Expanders)")

# ---------- Helpful defaults ----------
# Use the uploaded file path from the session (developer note)
DEFAULT_PATH = "/mnt/data/Nanded_Election_20251125_0726.xlsx"

# ---------- Sidebar: Data Source + Auto-refresh ----------
st.sidebar.header("Data source & Controls")

auto_refresh = st.sidebar.checkbox("Auto-refresh every 10 seconds (live)")

# If auto_refresh checked: wait then rerun at top of script loop
if auto_refresh:
    # Pause for 10s then rerun so the app refreshes continuously
    time.sleep(10)
    st.experimental_rerun()

uploaded_file = st.sidebar.file_uploader("Upload Election Excel File (optional)", type=["xlsx"])

google_sheet_url = st.sidebar.text_input(
    "OR Paste Google Sheet URL (Share → Anyone with link → Viewer):",
    value=""
)

# ---------- Helper to load Google Sheet as CSV ----------
def load_google_sheet_as_df(url: str):
    """Attempt to convert a variety of Google Sheets share URLs into a CSV export URL and load as DataFrame."""
    url = url.strip()
    if not url:
        return None
    try:
        if "docs.google.com" not in url:
            st.sidebar.error("Provided URL doesn't look like a Google Sheets URL.")
            return None

        # Common patterns:
        # 1) https://docs.google.com/spreadsheets/d/<SPREADSHEET_ID>/edit#gid=<GID>
        # 2) https://docs.google.com/spreadsheets/d/<ID>/copy
        # 3) share link with export?format=csv
        # We'll try to extract spreadsheet ID and gid if present.
        csv_url = None
        if "/spreadsheets/d/" in url:
            # Extract base id
            parts = url.split("/spreadsheets/d/")
            if len(parts) >= 2:
                tail = parts[1]
                # tail like "<ID>/edit#gid=0" or "<ID>/"
                sid = tail.split("/")[0]
                gid = None
                if "gid=" in url:
                    gid = url.split("gid=")[-1].split("&")[0]
                if gid:
                    csv_url = f"https://docs.google.com/spreadsheets/d/{sid}/export?format=csv&gid={gid}"
                else:
                    # default to first sheet (no gid)
                    csv_url = f"https://docs.google.com/spreadsheets/d/{sid}/export?format=csv"
        else:
            # Fallback: try to append export
            if url.endswith("/"):
                csv_url = url + "export?format=csv"
            else:
                csv_url = url + "/export?format=csv"

        if csv_url is None:
            st.sidebar.error("Couldn't construct CSV URL for that Google Sheet.")
            return None

        # Read CSV into DataFrame
        df_gs = pd.read_csv(csv_url)
        return df_gs

    except Exception as e:
        st.sidebar.error(f"Failed to load Google Sheet: {e}")
        return None

# ---------- Load data (priority: uploaded file > google sheet > default file) ----------
df = None
if uploaded_file is not None:
    try:
        df = pd.read_excel(uploaded_file)
        st.sidebar.success("Excel file uploaded ✔")
    except Exception as e:
        st.sidebar.error(f"Failed to read uploaded Excel file: {e}")
        st.stop()
elif google_sheet_url.strip() != "":
    df = load_google_sheet_as_df(google_sheet_url)
    if df is not None:
        st.sidebar.success("Google Sheet loaded ✔")
    else:
        st.stop()
elif os.path.exists(DEFAULT_PATH):
    try:
        df = pd.read_excel(DEFAULT_PATH)
        st.sidebar.info(f"Loaded default file: {DEFAULT_PATH}")
    except Exception as e:
        st.sidebar.error(f"Failed to load default Excel file: {e}")
        st.stop()
else:
    st.info("Please upload an Excel file or paste a Google Sheet URL, or place the default file at: " + DEFAULT_PATH)
    st.stop()

# ---------- Basic cleaning & validation ----------
expected_cols = {"Team Number","Name","Mobile","Date","Time","Male","Female","Transgender","Constitution"}
missing = expected_cols - set(df.columns)
if missing:
    st.error(f"Missing expected columns: {missing}. Please ensure file has the required columns.")
    st.stop()

# Normalize date/time columns
df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.date
df["Time"] = df["Time"].astype(str).str.strip()

# Convert numeric columns
for col in ["Male","Female","Transgender"]:
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

# Derived columns
df["Total"] = df[["Male","Female","Transgender"]].sum(axis=1)

# For ordering times, provide a default order if expected values present
time_order = ["09:00","11:00","13:00","15:00","17:00","18:00"]
# Keep only times found in data for the sidebar
found_times = [t for t in time_order if t in df["Time"].unique()]
if len(found_times) == 0:
    # fallback: unique sorted times from data
    found_times = sorted(df["Time"].unique().tolist())
df["Time"] = pd.Categorical(df["Time"], categories=found_times, ordered=True)

# ---------- Sidebar filters ----------
st.sidebar.header("Filters")

team_opts = ["All"] + sorted(df["Team Number"].dropna().unique().tolist())
selected_team = st.sidebar.selectbox("Team Number", team_opts)

const_opts = ["All"] + sorted(df["Constitution"].dropna().unique().tolist())
selected_const = st.sidebar.selectbox("Constitution", const_opts)

date_opts = ["All"] + sorted(df["Date"].dropna().astype(str).unique().tolist())
selected_date = st.sidebar.selectbox("Date", date_opts)

time_opts = ["All"] + found_times
selected_time = st.sidebar.selectbox("Time", time_opts)

male_min, male_max = int(df["Male"].min()), int(df["Male"].max())
female_min, female_max = int(df["Female"].min()), int(df["Female"].max())
trans_min, trans_max = int(df["Transgender"].min()), int(df["Transgender"].max())

male_range = st.sidebar.slider("Male range", male_min, male_max, (male_min, male_max))
female_range = st.sidebar.slider("Female range", female_min, female_max, (female_min, female_max))
trans_range = st.sidebar.slider("Transgender range", trans_min, trans_max, (trans_min, trans_max))

# Quick button to reset filters
if st.sidebar.button("Reset Filters"):
    st.experimental_rerun()

# ---------- Apply filters ----------
fdf = df.copy()
if selected_team != "All":
    fdf = fdf[fdf["Team Number"] == selected_team]
if selected_const != "All":
    fdf = fdf[fdf["Constitution"] == selected_const]
if selected_date != "All":
    fdf = fdf[fdf["Date"].astype(str) == selected_date]
if selected_time != "All":
    fdf = fdf[fdf["Time"] == selected_time]

fdf = fdf[
    (fdf["Male"].between(male_range[0], male_range[1])) &
    (fdf["Female"].between(female_range[0], female_range[1])) &
    (fdf["Transgender"].between(trans_range[0], trans_range[1]))
].copy()

# ---------- Top-line metrics ----------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Records (Filtered)", len(fdf))
c2.metric("Total Male", int(fdf["Male"].sum()))
c3.metric("Total Female", int(fdf["Female"].sum()))
c4.metric("Total Transgender", int(fdf["Transgender"].sum()))

st.markdown("---")

# ---------- Tabs ----------
tab_records, tab_charts, tab_summary, tab_download = st.tabs([
    "📄 Records", "📊 Charts", "🧮 Team & Constituency Summary", "⬇ Download"
])

# ---------- TAB: Records ----------
with tab_records:
    st.subheader("Filtered Records")
    st.dataframe(fdf.reset_index(drop=True), use_container_width=True)

# ---------- TAB: Charts ----------
with tab_charts:
    st.subheader("Comprehensive Visualizations")

    # Expander A: Gender Overview
    with st.expander("A. Gender Overview (Bar / Pie / Area)"):
        gender_totals = fdf[["Male","Female","Transgender"]].sum()
        st.write("### Totals by Gender")
        st.bar_chart(pd.DataFrame(gender_totals).T)

        fig_pie = px.pie(names=gender_totals.index, values=gender_totals.values,
                         title="Gender Share (Filtered)", hole=0.35)
        st.plotly_chart(fig_pie, use_container_width=True)

        if fdf["Time"].notna().any():
            area_df = fdf.groupby("Time")[["Male","Female","Transgender"]].sum().sort_index()
            st.write("### Cumulative area chart over time (Filtered)")
            st.area_chart(area_df)

    # Expander B: Constitution & Team Comparisons
    with st.expander("B. Constitution & Team Comparisons (Bar / Stacked / Radar / Bubble)"):
        st.write("### Constitution-wise (Stacked by Gender)")
        const_stack = fdf.groupby("Constitution")[["Male","Female","Transgender"]].sum()
        st.bar_chart(const_stack)

        top5 = const_stack.assign(Total=lambda x: x.sum(axis=1)).sort_values("Total", ascending=False).head(5)
        st.write("### Top 5 Constituencies by Total Votes")
        st.dataframe(top5)

        try:
            radar_df = top5.reset_index().melt(id_vars="Constitution", value_vars=["Male","Female","Transgender"], var_name="Category", value_name="Count")
            fig_rad = px.line_polar(radar_df, r="Count", theta="Category", color="Constitution", line_close=True, title="Top 5 Constituency Profile (Radar)")
            st.plotly_chart(fig_rad, use_container_width=True)
        except Exception:
            st.info("Radar chart not available.")

        bubble_df = const_stack.assign(Total=lambda x: x.sum(axis=1)).reset_index()
        fig_bub = px.scatter(bubble_df, x="Constitution", y="Total", size="Total", color="Total",
                             title="Constituency Bubble Chart (size = total votes)", hover_name="Constitution")
        st.plotly_chart(fig_bub, use_container_width=True)

    # Expander C: Time-based Trends
    with st.expander("C. Time-based Trends (Line / Heatmap / Stacked)"):
        st.write("### Time progression per Constituency (Male / Female / Transgender)")
        time_const = fdf.groupby(["Time","Constitution"])[["Male","Female","Transgender"]].sum().reset_index()
        if not time_const.empty:
            sel_const_for_line = st.selectbox("Pick a constituency to see its time trend (or 'All')", ["All"] + sorted(df["Constitution"].unique().tolist()))
            if sel_const_for_line != "All":
                tdf = time_const[time_const["Constitution"] == sel_const_for_line].set_index("Time").sort_index()
                st.line_chart(tdf[["Male","Female","Transgender"]])
            else:
                agg_time = time_const.groupby("Time")[["Male","Female","Transgender"]].sum().sort_index()
                st.line_chart(agg_time)

        st.write("### Heatmap: Constitution × Time (Total votes)")
        heat = fdf.groupby(["Constitution","Time"])["Total"].sum().unstack(fill_value=0)
        if not heat.empty:
            fig, ax = plt.subplots(figsize=(10, max(4, len(heat)*0.4)))
            sns.heatmap(heat, annot=True, fmt="d", linewidths=.5, cmap="YlOrRd", ax=ax)
            plt.ylabel("")
            st.pyplot(fig)

        st.write("### Stacked bar: Time-wise totals (district)")
        time_stack = fdf.groupby("Time")[["Male","Female","Transgender"]].sum().sort_index()
        st.bar_chart(time_stack)

    # Expander D: Advanced & Comparative
    with st.expander("D. Advanced & Comparative Charts (5PM→6PM Growth, Scatter, Top Teams)"):
        st.write("### 5 PM → 6 PM Growth (per Constituency)")
        t5 = fdf[fdf["Time"] == "17:00"].groupby("Constitution")["Total"].sum()
        t6 = fdf[fdf["Time"] == "18:00"].groupby("Constitution")["Total"].sum()
        growth = pd.concat([t5, t6], axis=1).fillna(0)
        growth.columns = ["T_17", "T_18"]
        growth["Growth"] = growth["T_18"] - growth["T_17"]
        growth = growth.sort_values("Growth", ascending=False)
        st.dataframe(growth)

        fig_growth = px.bar(growth.reset_index(), x="Constitution", y=["T_17","T_18"], title="Comparison: 5 PM vs 6 PM (per Constituency)")
        st.plotly_chart(fig_growth, use_container_width=True)

        st.write("### Scatter: Male vs Female (Team-level)")
        team_scatter = fdf.groupby("Team Number")[["Male","Female","Total"]].sum().reset_index()
        fig_sc = px.scatter(team_scatter, x="Male", y="Female", size="Total", color="Total", hover_name="Team Number", title="Male vs Female (Team level)")
        st.plotly_chart(fig_sc, use_container_width=True)

        st.write("### Top Teams by Total Votes")
        top_teams = team_scatter.sort_values("Total", ascending=False).head(10)
        st.dataframe(top_teams)

    # Expander E: Distribution & Outliers
    with st.expander("E. Distribution & Outliers (Boxplots, Histograms)"):
        st.write("### Boxplots")
        fig_box, ax = plt.subplots(1,3, figsize=(15,4))
        sns.boxplot(y=fdf["Male"], ax=ax[0]); ax[0].set_title("Male")
        sns.boxplot(y=fdf["Female"], ax=ax[1]); ax[1].set_title("Female")
        sns.boxplot(y=fdf["Transgender"], ax=ax[2]); ax[2].set_title("Transgender")
        st.pyplot(fig_box)

        st.write("### Histograms")
        fig_hist, ax = plt.subplots(figsize=(10,4))
        ax.hist(fdf["Total"], bins=20)
        ax.set_title("Total Votes Distribution")
        st.pyplot(fig_hist)

# ---------- TAB: Team & Constituency Summary ----------
with tab_summary:
    st.subheader("Aggregated Summaries")
    st.write("### Constitution Summary")
    csum = fdf.groupby("Constitution")[["Male","Female","Transgender","Total"]].sum().sort_values("Total", ascending=False)
    st.dataframe(csum, use_container_width=True)

    st.write("### Team Summary")
    tsum = fdf.groupby("Team Number")[["Male","Female","Transgender","Total"]].sum().sort_values("Total", ascending=False)
    st.dataframe(tsum, use_container_width=True)

    st.write("### Drill-down: Select a Constituency to see time-series")
    sel_const_drill = st.selectbox("Drill constituency", ["All"] + list(csum.index))
    if sel_const_drill != "All":
        drill_df = fdf[fdf["Constitution"] == sel_const_drill].groupby("Time")[["Male","Female","Transgender"]].sum().sort_index()
        st.line_chart(drill_df)

# ---------- TAB: Download ----------
with tab_download:
    st.subheader("Download filtered data")
    csv = fdf.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV", data=csv, file_name="filtered_election_data.csv", mime="text/csv")

    # Excel download
    try:
        with io.BytesIO() as buffer:
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                fdf.to_excel(writer, index=False, sheet_name="FilteredData")
            st.download_button("Download Excel", data=buffer.getvalue(), file_name="filtered_election_data.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception as e:
        st.warning(f"Excel download not available: {e}")

    st.write("Preview of filtered data:")
    st.dataframe(fdf.head(), use_container_width=True)

# ---------- Footer ----------
st.markdown("---")
st.caption("Dashboard generated: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
