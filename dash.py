import streamlit as st
import pandas as pd
import altair as alt
from urllib.error import URLError
from src.parsers import parse_all_comdirect
from src.dashboard_utility import get_monthly_data

comdirect_df = parse_all_comdirect("finance_data/comdirect/")

st.write("# Comdirect Bank Transactions")
st.write(comdirect_df)


st.write("# Income and spending per month")
monthly_data = get_monthly_data(comdirect_df)

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


# DEMO CODE FROM STREAMLIT

# @st.cache_data
# def get_un_data() -> pd.DataFrame:
#     aws_bucket_url = "https://streamlit-demo-data.s3-us-west-2.amazonaws.com"
#     df = pd.read_csv(aws_bucket_url + "/agri.csv.gz")
#     return df.set_index("Region")


# try:
#     df = get_un_data()
#     countries = st.multiselect("Choose countries", list(df.index), ["China", "United States of America"])
#     if not countries:
#         st.error("Please select at least one country.")
#     else:
#         data = df.loc[countries]
#         data /= 1000000.0
#         st.subheader("Gross agricultural production ($B)")
#         st.dataframe(data.sort_index())

#         data = data.T.reset_index()
#         data = pd.melt(data, id_vars=["index"]).rename(columns={"index": "year", "value": "Gross Agricultural Product ($B)"})
#         chart = (
#             alt.Chart(data)
#             .mark_area(opacity=0.3)
#             .encode(
#                 x="year:T",
#                 y=alt.Y("Gross Agricultural Product ($B):Q", stack=None),
#                 color="Region:N",
#             )
#         )
#         st.altair_chart(chart, use_container_width=True)
# except URLError as e:
#     st.error(f"This demo requires internet access. Connection error: {e.reason}")
