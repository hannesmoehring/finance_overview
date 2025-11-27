import streamlit as st
import pandas as pd
import altair as alt
from urllib.error import URLError
from src.parsers import parse_all_comdirect, COLUMNS, COMDIRECT_PROCESS_MAPPING, TRADEREPUBLIC_PROCESS_MAPPING, OLB_PROCESS_MAPPING
from src.dashboard_utility import embed_transaction_details, get_monthly_data, get_all_bank_data
import plotly.express as px

banks = ["Comdirect", "TradeRepublic", "OLB"]
process_types = list(set(set(COMDIRECT_PROCESS_MAPPING.values()) | set(TRADEREPUBLIC_PROCESS_MAPPING.values()) | set(OLB_PROCESS_MAPPING.values())))
comdirect_df, traderepublic_df, olb_df = get_all_bank_data()

# COMDIRECTDF, TRADEREPUBLICDF, OLBDF = (comdirect_df.copy(), traderepublic_df.copy(), olb_df.copy())

selected_banks = st.multiselect("Choose countries", banks, default=["Comdirect", "OLB", "TradeRepublic"])
selected_processes = st.multiselect("Choose process types", process_types, default=["Transfer", "Card_Transaction"])

df = pd.DataFrame(columns=COLUMNS)
if "Comdirect" in selected_banks:
    df = pd.concat([df, comdirect_df], ignore_index=True)
if "TradeRepublic" in selected_banks:
    df = pd.concat([df, traderepublic_df], ignore_index=True)
if "OLB" in selected_banks:
    df = pd.concat([df, olb_df], ignore_index=True)

df = df[df["process"].isin(selected_processes)]
df.sort_values(by="date", inplace=True)
df.reset_index(drop=True, inplace=True)

CURRENT_DF = df.copy()

all_dates = df["date"].sort_values().unique()

start_default = all_dates[0]
end_default = all_dates[-1]

start_date, end_date = st.select_slider(
    "Select date range",
    options=all_dates,
    value=(start_default, end_default),
    format_func=lambda x: x.strftime("%Y-%m-%d"),
)

mask = (df["date"] >= start_date) & (df["date"] <= end_date)
df = df.loc[mask]

st.write("# selected bank data")
st.write(df)


st.write("# Income and spending per month")
monthly_data = get_monthly_data(df)

color_scale = alt.Scale(domain=["Income", "Spending"], range=["green", "red"])

chart = (
    alt.Chart(monthly_data)
    .mark_bar()
    .encode(
        x=alt.X("month:N", title="Month"),
        xOffset="type:N",  # thos splits the bars
        y=alt.Y("amount:Q", title="Amount"),
        color=alt.Color("type:N", scale=color_scale, title="Type"),
        tooltip=["month", "amount", "type"],
    )
    .properties(width=1000)
)

st.altair_chart(chart, use_container_width=True)

st.divider()

st.write("# Spending / Income breakdown")
is_spending = st.toggle("Income/Spending", value=True)

st.write("showing (absolute) data for: __{}__".format("Spending" if is_spending else "Income"))


if is_spending:
    spending_data = df[df["amount"] < 0]
    spending_data["amount"] = spending_data["amount"].abs()
else:
    spending_data = df[df["amount"] >= 0]

flow_df = spending_data.copy()

min_spending, max_spending = st.select_slider(
    "Select minimum and maximum spending amount to be considered",
    options=spending_data["amount"].sort_values().unique(),
    value=(spending_data["amount"].min(), spending_data["amount"].max()),
    format_func=lambda x: f"{x:.2f} €",
)
mask = (spending_data["amount"] >= min_spending) & (spending_data["amount"] <= max_spending)
spending_data = spending_data.loc[mask]

spending_data = spending_data.groupby("details", as_index=False)["amount"].sum().rename(columns={"amount": "total_amount"})

chart = (
    alt.Chart(spending_data)
    .mark_bar()
    .encode(
        x=alt.X(
            "details:N",
            sort="-y",
            axis=None,
        ),
        y=alt.Y("total_amount:Q", title="Total amount"),
        tooltip=["details", "total_amount"],
    )
)

st.altair_chart(chart, use_container_width=True)

agg_spending, agg_income = embed_transaction_details(df)
if is_spending:
    agg = agg_spending
else:
    agg = agg_income

st.write("## Clustering of transaction details")
num_clusters = agg["cluster"].astype(int).unique()
num_clusters.sort()

if "selected_clusters" not in st.session_state:
    st.session_state.selected_clusters = list(num_clusters)


if st.button("Reset clusters"):
    st.session_state.selected_clusters = list(num_clusters)
    st.rerun()

options = st.multiselect(
    "Show clusters",
    num_clusters,
    key="selected_clusters",
)

filtered_agg = agg[agg["cluster"].isin(st.session_state.selected_clusters)]

cluster_sum = agg.groupby("cluster", as_index=False)["total_amount"].sum()

fig = px.scatter(filtered_agg, x="x", size="total_amount", color="cluster", hover_name="details", size_max=50, hover_data={"x": False, "y": False})
for trace in fig.data:
    cluster_id = trace.name  # type: ignore
    total = cluster_sum.loc[cluster_sum["cluster"] == int(cluster_id), "total_amount"].values[0]
    trace.name = f"{cluster_id} -- {total:.2f} €"  # type: ignore

fig.update_layout(
    xaxis_title=None,
    yaxis_title=None,
    xaxis=dict(
        showticklabels=False,
        showgrid=True,
        zeroline=True,
    ),
    yaxis=dict(
        showticklabels=False,
        showgrid=True,
        zeroline=True,
    ),
)

st.plotly_chart(fig, use_container_width=True)


week_agg = flow_df.groupby("weekday")["amount"].sum().reset_index()
month_agg = flow_df.groupby("monthday")["amount"].sum().reset_index()

weekday_heatmap = (
    alt.Chart(week_agg)
    .mark_rect()
    .encode(
        x=alt.X("weekday:O", title="Weekday"),
        y=alt.Y("sum(amount):Q", title="Total Spend"),
        color=alt.Color("amount:Q", scale=alt.Scale(scheme="blues")),
        tooltip=["weekday", "amount"],
    )
)


month_heatmap = (
    alt.Chart(month_agg)
    .mark_rect()
    .encode(
        x=alt.X("monthday:O", title="Day of month"),
        y=alt.Y("sum(amount):Q", title="Total Spend"),
        color=alt.Color("amount:Q", scale=alt.Scale(scheme="greens")),
        tooltip=["monthday", "amount"],
    )
)

st.write("## Heatmaps")
st.write("### Spending / Income by weekday")
st.altair_chart(weekday_heatmap)
st.write("### Spending / Income by monthday")
st.altair_chart(month_heatmap)
