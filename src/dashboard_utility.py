import pandas as pd
import altair as alt
import streamlit as st
import numpy as np
from src.parsers import parse_all_comdirect, parse_all_traderepublic, parse_all_olb
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans
from sklearn.manifold import TSNE
import umap
import plotly.io as pio

pio.templates.default = "plotly"


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


@st.cache_data
def embed_transaction_details(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    spending_df = df[df["amount"] < 0]
    spending_df["amount"] = df["amount"].abs()

    income_df = df[df["amount"] >= 0]

    model = load_model()

    agg_list = []

    for df in [spending_df, income_df]:
        embeddings = model.encode(df["details"].tolist(), normalize_embeddings=True)
        kmeans = KMeans(n_clusters=10, random_state=9042003)

        df["cluster"] = kmeans.fit_predict(embeddings)

        tsne = TSNE(n_components=2, perplexity=30, learning_rate=200, metric="cosine")

        df[["x", "y"]] = tsne.fit_transform(embeddings)

        agg = df.groupby(["details", "cluster"]).agg(total_amount=("amount", "sum"), x=("x", "mean"), y=("y", "mean")).reset_index()

        agg["cluster"] = agg["cluster"].astype("category")

        agg.reset_index(drop=True, inplace=True)

        agg_list.append(agg)

    return agg_list[0], agg_list[1]


@st.cache_resource
def load_model():
    return SentenceTransformer("all-MiniLM-L6-v2")
