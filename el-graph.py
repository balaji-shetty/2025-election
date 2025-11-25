import os
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
from datetime import datetime

# ---------- Page config ----------
st.set_page_config(page_title="Nanded Election Dashboard (All Graphs)",
                   layout="wide",
                   initial_sidebar_state="expanded")

st.title("🗳️ Nanded Election Dashboard — All Visuals (Tabs + Expanders)")

# ---------- Helpful defaults ----------
DEFAULT_PATH = "/mnt/data/Nanded_Election_20251125_0726.xlsx"  # default uploaded file path

# ---------- File load ----------
uploaded_file = st.sidebar.file_uploader("Upload Election Excel File (or leave to use default)", type=["xlsx"])

if uploaded_file is not None:
    df = pd.read_excel(uploaded_file)
    st.sidebar.success("File uploaded ✔")
else:
    if os.path.exists(DEFAULT_PATH):
        df = pd.read_excel(DEFAULT_PATH)
        st.sidebar.info(f"Loaded default file: {DEFAULT_PATH}")
    else:
        st.info("Please upload an Excel file or place it at the default path.")
        st.stop()

# ---------- Basic cleaning ----------
# Ensure expected columns exist
expected_cols = {"Team Number","Name","Mobile","Date","Time","Male","Female","Transgender","Constitution"}
missing = expected_cols - set(df.columns)
if missing:
    st.error(f"Missing expected columns: {missing}. Please ensure file has all required columns.")
    st.stop()

# Normalize date/time columns
df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.date
df["Time"] = df["Time"].astype(str).str.strip()

# Convert numeric columns
for col in ["Male","Female","Transgender"]:
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

# Add derived columns
df["Total"] = df[["Male","Female","Transgender"]].sum(axis=1)
# For time ordering, create a categorical ordered column if times are consistent
time_order = ["09:00","11:00","13:00","15:00","17:00","18:00"]
df["Time"] = pd.Categorical(df["Time"], categories=time_order, ordered=True)

# ---------- Sidebar filters (including Time) ----------
st.sidebar.header("Filters")

team_opts = ["All"] + sorted(df["Team Number"].dropna().unique().tolist())
selected_team = st.sidebar.selectbox("Team Number", team_opts)

const_opts = ["All"] + sorted(df["Constitution"].dropna().unique().tolist())
selected_const = st.sidebar.selectbox("Constitution", const_opts)

date_opts = ["All"] + sorted(df["Date"].dropna().astype(str).unique().tolist())
selected_date = st.sidebar.selectbox("Date", date_opts)

time_opts = ["All"] + [t for t in time_order if t in df["Time"].cat.categories]
selected_time = st.sidebar.selectbox("Time", time_opts)

male_min, male_max = int(df["Male"].min()), int(df["Male"].max())
female_min, female_max = int(df["Female"].min()), int(df["Female"].max())
trans_min, trans_max = int(df["Transgender"].min()), int(df["Transgender"].max())

male_range = st.sidebar.slider("Male range", male_min, male_max, (male_min, male_max))
female_range = st.sidebar.slider("Female range", female_min, female_max, (female_min, female_max))
trans_range = st.sidebar.slider("Transgender range", trans_min, trans_max, (trans_min, trans_max))

# Apply filters
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
]

# ---------- Top-line metrics ----------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Records (Filtered)", len(fdf))
c2.metric("Total Male", int(fdf["Male"].sum()))
c3.metric("Total Female", int(fdf["Female"].sum()))
c4.metric("Total Transgender", int(fdf["Transgender"].sum()))

st.markdown("---")

# ---------- Tabs (Top level) ----------
tab_records, tab_charts, tab_summary, tab_download = st.tabs([
    "📄 Records", "📊 Charts", "🧮 Team & Constituency Summary", "⬇ Download"
])

# ---------- TAB: Records ----------
with tab_records:
    st.subheader("Filtered Records")
    st.dataframe(fdf.reset_index(drop=True), use_container_width=True)

# ---------- TAB: Charts (with expanders grouped) ----------
with tab_charts:
    st.subheader("Comprehensive Visualizations")
    
    # -- Expander Group A: Gender Overview --
    with st.expander("A. Gender Overview (Bar / Pie / Area)"):
        # Bar: Male/Female/Transgender totals
        gender_totals = fdf[["Male","Female","Transgender"]].sum()
        st.write("### Totals by Gender")
        st.bar_chart(pd.DataFrame(gender_totals).T)

        # Pie/Donut with plotly
        fig_pie = px.pie(names=gender_totals.index, values=gender_totals.values,
                         title="Gender Share (Filtered)", hole=0.35)
        st.plotly_chart(fig_pie, use_container_width=True)

        # Area: cumulative over time (if time dimension present)
        if fdf["Time"].notna().any():
            area_df = fdf.groupby("Time")[["Male","Female","Transgender"]].sum().sort_index()
            st.write("### Cumulative area chart over time (Filtered)")
            st.area_chart(area_df)

    # -- Expander Group B: Constitution & Team Comparisons --
    with st.expander("B. Constitution & Team Comparisons (Bar / Stacked / Radar / Bubble)"):
        # Constitution-wise stacked bar
        st.write("### Constitution-wise (Stacked by Gender)")
        const_stack = fdf.groupby("Constitution")[["Male","Female","Transgender"]].sum()
        # Ensure ordering
        st.bar_chart(const_stack)

        # Top 5 constituencies by total votes
        top5 = const_stack.assign(Total=lambda x: x.sum(axis=1)).sort_values("Total", ascending=False).head(5)
        st.write("### Top 5 Constituencies by Total Votes")
        st.dataframe(top5)

        # Radar-like plot (using polar in plotly) for top 5 (multi-parameter)
        try:
            radar_df = top5.reset_index().melt(id_vars="Constitution", value_vars=["Male","Female","Transgender"], var_name="Category", value_name="Count")
            fig_rad = px.line_polar(radar_df, r="Count", theta="Category", color="Constitution", line_close=True, title="Top 5 Constituency Profile (Radar)")
            st.plotly_chart(fig_rad, use_container_width=True)
        except Exception:
            st.info("Radar chart not available (not enough distinct constituencies).")

        # Bubble chart: constituencies sized by total turnout
        bubble_df = const_stack.assign(Total=lambda x: x.sum(axis=1)).reset_index()
        fig_bub = px.scatter(bubble_df, x="Constitution", y="Total", size="Total", color="Total",
                             title="Constituency Bubble Chart (size = total votes)", hover_name="Constitution")
        st.plotly_chart(fig_bub, use_container_width=True)

    # -- Expander Group C: Time-based Trends (Line / Heatmap / Stacked by Time) --
    with st.expander("C. Time-based Trends (Line / Heatmap / Stacked)"):
        # Time progression per constituency (line chart)
        st.write("### Time progression per Constituency (Male / Female / Transgender)")
        time_const = fdf.groupby(["Time","Constitution"])[["Male","Female","Transgender"]].sum().reset_index()
        if not time_const.empty:
            # Example: line chart for selected constitution OR overall (aggregated)
            sel_const_for_line = st.selectbox("Pick a constituency to see its time trend (or 'All')", ["All"] + sorted(df["Constitution"].unique().tolist()))
            if sel_const_for_line != "All":
                tdf = time_const[time_const["Constitution"] == sel_const_for_line].set_index("Time").sort_index()
                st.line_chart(tdf[["Male","Female","Transgender"]])
            else:
                agg_time = time_const.groupby("Time")[["Male","Female","Transgender"]].sum().sort_index()
                st.line_chart(agg_time)

        # Heatmap: Constitution x Time (Total)
        st.write("### Heatmap: Constitution × Time (Total votes)")
        heat = fdf.groupby(["Constitution","Time"])["Total"].sum().unstack(fill_value=0)
        if not heat.empty:
            fig, ax = plt.subplots(figsize=(10, max(4, len(heat)*0.4)))
            sns.heatmap(heat, annot=True, fmt="d", linewidths=.5, cmap="YlOrRd", ax=ax)
            plt.ylabel("")
            st.pyplot(fig)

        # Stacked bar by Time for entire district
        st.write("### Stacked bar: Time-wise totals (district)")
        time_stack = fdf.groupby("Time")[["Male","Female","Transgender"]].sum().sort_index()
        st.bar_chart(time_stack)

    # -- Expander Group D: Advanced / Comparative charts --
    with st.expander("D. Advanced & Comparative Charts (5PM→6PM Growth, Scatter, Top Teams)"):
        # 5 PM vs 6 PM growth per constituency
        st.write("### 5 PM → 6 PM Growth (per Constituency)")
        t5 = fdf[fdf["Time"] == "17:00"].groupby("Constitution")["Total"].sum()
        t6 = fdf[fdf["Time"] == "18:00"].groupby("Constitution")["Total"].sum()
        growth = pd.concat([t5, t6], axis=1).fillna(0)
        growth.columns = ["T_17", "T_18"]
        growth["Growth"] = growth["T_18"] - growth["T_17"]
        growth = growth.sort_values("Growth", ascending=False)
        st.dataframe(growth)

        fig_growth = px.bar(growth.reset_index(), x="Constitution", y=["T_17","T_18"],
                            title="Comparison: 5 PM vs 6 PM (per Constituency)")
        st.plotly_chart(fig_growth, use_container_width=True)

        # Scatter: Male vs Female by Team (size = total)
        st.write("### Scatter: Male vs Female (Team-level)")
        team_scatter = fdf.groupby("Team Number")[["Male","Female","Total"]].sum().reset_index()
        fig_sc = px.scatter(team_scatter, x="Male", y="Female", size="Total", color="Total",
                            hover_name="Team Number", title="Male vs Female (Team level)")
        st.plotly_chart(fig_sc, use_container_width=True)

        # Top teams by turnout
        st.write("### Top Teams by Total Votes")
        top_teams = team_scatter.sort_values("Total", ascending=False).head(10)
        st.dataframe(top_teams)

    # -- Expander Group E: Distribution & Outliers --
    with st.expander("E. Distribution & Outliers (Boxplots, Histograms)"):
        # Boxplots for Male/Female/Transgender
        st.write("### Boxplots")
        fig_box, ax = plt.subplots(1,3, figsize=(15,4))
        sns.boxplot(y=fdf["Male"], ax=ax[0]); ax[0].set_title("Male")
        sns.boxplot(y=fdf["Female"], ax=ax[1]); ax[1].set_title("Female")
        sns.boxplot(y=fdf["Transgender"], ax=ax[2]); ax[2].set_title("Transgender")
        st.pyplot(fig_box)

        # Histograms
        st.write("### Histograms")
        fig_hist, ax = plt.subplots(figsize=(10,4))
        ax.hist(fdf["Total"], bins=20)
        ax.set_title("Total Votes Distribution")
        st.pyplot(fig_hist)

# ---------- TAB: Team & Constituency Summary ----------
with tab_summary:
    st.subheader("Aggregated Summaries")

    # Constitution aggregated table
    st.write("### Constitution Summary")
    csum = fdf.groupby("Constitution")[["Male","Female","Transgender","Total"]].sum().sort_values("Total", ascending=False)
    st.dataframe(csum, use_container_width=True)

    # Team aggregated table
    st.write("### Team Summary")
    tsum = fdf.groupby("Team Number")[["Male","Female","Transgender","Total"]].sum().sort_values("Total", ascending=False)
    st.dataframe(tsum, use_container_width=True)

    # Quick filters for deep dive
    st.write("### Drill-down: Select a Constituency to see time-series")
    sel_const_drill = st.selectbox("Drill constituency", ["All"] + list(csum.index))
    if sel_const_drill != "All":
        drill_df = fdf[fdf["Constitution"] == sel_const_drill].groupby("Time")[["Male","Female","Transgender"]].sum().sort_index()
        st.line_chart(drill_df)

# ---------- TAB: Download ----------
with tab_download:
    st.subheader("Download filtered data")
    st.write("You can download the currently filtered dataset (CSV / Excel).")

    csv = fdf.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV", data=csv, file_name="filtered_election_data.csv", mime="text/csv")

    # Excel
    try:
        import io
        with io.BytesIO() as buffer:
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                fdf.to_excel(writer, index=False, sheet_name="FilteredData")
            st.download_button("Download Excel", data=buffer.getvalue(),
                               file_name="filtered_election_data.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception as e:
        st.warning(f"Excel download not available: {e}")

    st.write("Preview of filtered data:")
    st.dataframe(fdf.head(), use_container_width=True)

# ---------- End ----------
st.markdown("---")
st.caption("Dashboard generated: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

