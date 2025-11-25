import pandas as pd
import os
from glob import glob


def parse_comdirect_csv(file_path: str) -> pd.DataFrame:
    df = pd.read_csv(
        file_path,
        sep=";",
        encoding="cp1252",
        engine="python",
        header=None,
        skip_blank_lines=True,
        on_bad_lines="warn",
        na_values=["--"],
        skiprows=6,
        parse_dates=[0],
        dayfirst=True,
    )
    df.drop(columns=[0], inplace=True)
    df.drop(columns=[5], inplace=True)
    df.columns = ["buchungstag", "vorgang", "text", "betrag"]

    df = df[df["buchungstag"].notna()]

    df["betrag"] = pd.to_numeric(df["betrag"].str.replace(".", "").str.replace(",", "."))
    df["vorgang"] = df["vorgang"].astype("category")
    df["text"] = df["text"].astype("string")
    df["short_text"] = df["text"].str.slice(0, 30).astype("string")

    return df


def parse_all_comdirect(dir_path: str) -> pd.DataFrame:
    all_files = glob(os.path.join(dir_path, "umsaetze_*.csv"))
    df_list = [parse_comdirect_csv(file) for file in all_files]
    combined_df = pd.concat(df_list, ignore_index=True)
    combined_df.sort_values(by="buchungstag", inplace=True)
    combined_df.reset_index(drop=True, inplace=True)

    combined_df = combined_df.drop_duplicates()
    combined_df = combined_df[combined_df["betrag"].notna()]
    combined_df = combined_df[combined_df["vorgang"].notna()]
    return combined_df
