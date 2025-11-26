import pandas as pd
import altair as alt
import streamlit as st
import numpy as np
from src.parsers import parse_all_comdirect, parse_all_traderepublic, parse_all_olb


def get_monthly_data(df: pd.DataFrame) -> pd.DataFrame:
    df["date"] = pd.to_datetime(df["date"], dayfirst=True)

    df["month"] = df["date"].dt.to_period("M").dt.to_timestamp()  # type: ignore
    df["type"] = np.where(df["amount"] >= 0, "Income", "Spending")

    monthly: pd.Series = df.groupby(["month", "type"], as_index=False)["amount"].sum()
    monthly.loc[monthly["type"] == "Spending", "amount"] *= -1

    monthly["month"] = monthly["month"].dt.strftime("%Y-%m")
    return pd.DataFrame(monthly)


@st.cache_data
def get_all_bank_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    comdirect_df = parse_all_comdirect()
    traderepublic_df = parse_all_traderepublic()
    olb_df = parse_all_olb()
    return comdirect_df, traderepublic_df, olb_df
