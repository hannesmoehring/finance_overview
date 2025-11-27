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


# @st.cache_data this is unsafe, cached data is global
def get_all_bank_data(files=None, is_local: bool = False) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if is_local:
        comdirect_df = parse_all_comdirect()
        traderepublic_df = parse_all_traderepublic()
        olb_df = parse_all_olb()
    else:
        if files is None or len(files) == 0:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        comdirect_files = [file for file in files if "umsaetze" in file.name]
        traderepublic_files = [file for file in files if file.name.endswith(".pdf")]
        olb_files = [file for file in files if "CSV-Export" in file.name]

        comdirect_df = parse_all_comdirect(comdirect_files)
        traderepublic_df = parse_all_traderepublic(traderepublic_files)
        olb_df = parse_all_olb(olb_files)

    return comdirect_df, traderepublic_df, olb_df


# @st.cache_data this is unsafe, cached data is global
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
        n_samples = embeddings.shape[0]
        perplexity = min(30, max(5, n_samples // 2))
        tsne = TSNE(n_components=2, perplexity=perplexity, learning_rate=200, metric="cosine")

        df[["x", "y"]] = tsne.fit_transform(embeddings)

        agg = df.groupby(["details", "cluster"]).agg(total_amount=("amount", "sum"), x=("x", "mean"), y=("y", "mean")).reset_index()
        agg["total_amount"] = agg["total_amount"]
        agg["cluster"] = agg["cluster"].astype("category")

        agg.reset_index(drop=True, inplace=True)

        # agg["total_amount"].agg(lambda x: round(x, 2), inplace=True)

        agg_list.append(agg)

    return agg_list[0], agg_list[1]


@st.cache_resource
def load_model():
    return SentenceTransformer("all-MiniLM-L6-v2")


def session_cache(key, fn, is_local: bool, file_hash):
    if "is_local" not in st.session_state:
        st.session_state["is_local"] = is_local
    if "file_hash" not in st.session_state:
        st.session_state["file_hash"] = file_hash

    if st.session_state["is_local"] != is_local or st.session_state["file_hash"] != file_hash:
        print(f"Clearing session state for key {key} due to change in is_local or file_hash")
        # if key in st.session_state:
        #     del st.session_state[key]
        st.session_state.clear()
        st.session_state["is_local"] = is_local
        st.session_state["file_hash"] = file_hash

    if key not in st.session_state:
        st.session_state[key] = fn()
    return st.session_state[key]
