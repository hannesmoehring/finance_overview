import streamlit as st
import pandas as pd
import altair as alt
from urllib.error import URLError
from src.parsers import parse_all_comdirect, COLUMNS, COMDIRECT_PROCESS_MAPPING, TRADEREPUBLIC_PROCESS_MAPPING, OLB_PROCESS_MAPPING
from src.dashboard_utility import get_monthly_data, get_all_bank_data

banks = ["Comdirect", "TradeRepublic", "OLB"]
process_types = list(set(set(COMDIRECT_PROCESS_MAPPING.values()) | set(TRADEREPUBLIC_PROCESS_MAPPING.values()) | set(OLB_PROCESS_MAPPING.values())))
comdirect_df, traderepublic_df, olb_df = get_all_bank_data()

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


spending_data = df[df["amount"] < 0]
spending_data["amount"] = spending_data["amount"].abs()

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
    .mark_circle()
    .encode(
        x=alt.X(
            "details:N",
            sort="-y",
            axis=None,
        ),
        y=alt.Y("total_amount:Q", title="Total amount"),
        size=alt.Size("total_amount:Q", title="Total amount"),
        tooltip=["details", "total_amount"],
    )
)

st.altair_chart(chart, use_container_width=True)
