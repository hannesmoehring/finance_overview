import pandas as pd
import os
from glob import glob
from pypdf import PdfReader
import dateparser

COMDIRECT_PROCESS_MAPPING = {
    "Übertrag / Überweisung": "Transfer",
    "Lastschrift / Belastung": "Card_Transaction",
    "Gutschrift": "Credit",
    "Dauerauftrag": "Standing Order",
    "Kartenverfügung": "Card_Transaction",
    "Zinsen": "Interest",
    "Gebühren": "Fees",
}

TRADEREPUBLIC_PROCESS_MAPPING = {
    "Kauf": "Buy",
    "Verkauf": "Sell",
    "Überweisung": "Transfer",
    "Kartentransaktion": "Card_Transaction",
}

OLB_PROCESS_MAPPING = {
    "Transfer": "Transfer",
}

COLUMNS = [
    "date",
    "process",
    "details",
    "amount",
    "datetime",
    "monthday",
    "weekday",
]


def _parse_comdirect_csv(file) -> pd.DataFrame:
    df = pd.read_csv(
        file,
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
    df[6] = pd.NaT
    df[7] = pd.NaT
    df[8] = pd.NaT
    df.columns = COLUMNS

    df["datetime"] = pd.to_datetime(df["date"], errors="coerce")
    df["date"] = pd.to_datetime(df["date"], format="%d.%m.%Y", errors="coerce").dt.date
    df["weekday"] = df["datetime"].dt.weekday  # type: ignore
    df["monthday"] = df["datetime"].dt.day  # type: ignore
    df["amount"] = pd.to_numeric(df["amount"].str.replace(".", "").str.replace(",", "."))
    df["process"] = df["process"].astype("category")
    df["details"] = df["details"].astype("string")

    return df


def parse_all_comdirect(files=None) -> pd.DataFrame:
    if not files:
        dir_path = os.path.join("finance_data", "comdirect")
        all_files = glob(os.path.join(dir_path, "*.csv"))
    else:
        all_files = files

    df_list = [_parse_comdirect_csv(file) for file in all_files]
    combined_df = pd.concat(df_list, ignore_index=True)

    combined_df.dropna(inplace=True)

    combined_df.sort_values(by="date", inplace=True)
    combined_df.reset_index(drop=True, inplace=True)

    combined_df = combined_df.drop_duplicates()
    combined_df = combined_df[combined_df["amount"].notna()]
    combined_df = combined_df[combined_df["process"].notna()]

    # fixing some encoding issues and improving quality
    combined_df["process"] = combined_df["process"].str.replace("ï¿½bertrag / ï¿½berweisung", "Übertrag / Überweisung")
    combined_df["process"] = combined_df["process"].str.replace("Kartenverfï¿½gung", "Kartenverfügung")

    combined_df["process"] = combined_df["process"].map(COMDIRECT_PROCESS_MAPPING).fillna(combined_df["process"])

    combined_df["long_details"] = combined_df["details"]
    combined_df["details"] = combined_df["details"].str.split(" ").str[1:4].str.join(" ")
    combined_df["weekday"] = combined_df["weekday"].astype(int)
    combined_df["monthday"] = combined_df["monthday"].astype(int)

    return combined_df


def parse_all_traderepublic(files=None) -> pd.DataFrame:
    if not files:
        dir_path = os.path.join("finance_data", "traderepublic")
        all_files = glob(os.path.join(dir_path, "*.pdf"))
    else:
        all_files = files

    df_list = [_parse_traderepublic_pdf(file) for file in all_files]
    combined_df = pd.concat(df_list, ignore_index=True)
    combined_df.sort_values(by="date", inplace=True)
    combined_df.reset_index(drop=True, inplace=True)

    combined_df = combined_df.drop_duplicates()
    combined_df = combined_df[combined_df["amount"].notna()]
    combined_df = combined_df[combined_df["process"].notna()]

    combined_df["amount"] = pd.to_numeric(combined_df["amount"])
    combined_df["process"] = combined_df["process"].map(TRADEREPUBLIC_PROCESS_MAPPING).fillna(combined_df["process"])

    return combined_df


def _parse_traderepublic_pdf(file) -> pd.DataFrame:
    reader = PdfReader(file)

    all_text = []
    for page in reader.pages:
        text = page.extract_text()
        all_text.append(text)

    full_text = "\n\n\n".join(all_text)
    lines = full_text.splitlines()
    filtered_lines = []
    i = 0
    while i < len(lines):
        if "Kauf" in lines[i] or "Verkauf" in lines[i]:
            new_line = lines[i] + " " + lines[i + 1]
            filtered_lines.append(new_line)
            i += 2
            continue
        if "Überweisung" in lines[i] or "Kartentransaktion" in lines[i]:
            dates = lines[i - 3] + lines[i - 2] + lines[i - 1]
            if len(dates) > 14:
                new_line = lines[i - 1] + lines[i]
                filtered_lines.append(new_line)
                i += 1
                continue
            new_line = lines[i - 3] + lines[i - 2] + lines[i - 1] + " " + lines[i]
            filtered_lines.append(new_line)
            i += 1
            continue
        else:
            i += 1

    traderepublic_df = pd.DataFrame(columns=COLUMNS)

    new_row_template = {"date": "", "process": "", "details": "", "amount": ""}
    for line in filtered_lines:
        new_row = new_row_template.copy()
        line_split = line.split(" ")
        dates = line_split[:3]
        dt1 = dateparser.parse(" ".join(dates), settings={"DATE_ORDER": "DMY", "PREFER_DAY_OF_MONTH": "first"})
        assert dt1 is not None
        new_row["date"] = dt1.date()  # type: ignore
        new_row["datetime"] = dt1  # type: ignore
        new_row["weekday"] = new_row["datetime"].weekday()  # type: ignore
        new_row["monthday"] = new_row["datetime"].day  # type: ignore
        new_row["process"] = line_split[3]
        new_row["amount"] = line_split[-2].split("\xa0")[0].replace(".", "").replace(",", ".")
        if line_split[3] == "Überweisung":
            if line_split[4] == "Outgoing":
                new_row["details"] = " ".join(line_split[6:9])
                new_row["amount"] = "-" + new_row["amount"]
            elif line_split[4] == "Incoming":
                new_row["details"] = " ".join(line_split[6:9])
        else:
            new_row["details"] = " ".join(line_split[4:6])
        if new_row["process"] == "Kartentransaktion" or new_row["process"] == "Kauf":
            new_row["amount"] = "-" + new_row["amount"]

        # print(new_row)
        traderepublic_df = pd.concat([traderepublic_df, pd.DataFrame([new_row])], ignore_index=True)
        traderepublic_df["weekday"] = traderepublic_df["weekday"].astype(int)
        traderepublic_df["monthday"] = traderepublic_df["monthday"].astype(int)

    return traderepublic_df


def _parse_olb_csv(file) -> pd.DataFrame:
    df = pd.read_csv(file, sep=";", encoding="cp1252")
    df["Empfänger/Auftraggeber"] = df["Empfï¿½nger/Auftraggeber"]
    olb_df = pd.DataFrame(columns=COLUMNS)
    # olb_df["datetime"] = pd.to_datetime(df["Buchungsdatum"].apply(lambda x: dateparser.parse(x, languages=["de"])), format="%Y-%m-%d").dt
    olb_df["date"] = pd.to_datetime(df["Buchungsdatum"].apply(lambda x: dateparser.parse(x, languages=["de"])), format="%Y-%m-%d").dt.date
    olb_df["datetime"] = pd.to_datetime(df["Buchungsdatum"].apply(lambda x: dateparser.parse(x, languages=["de"])))
    olb_df["weekday"] = (olb_df["datetime"].dt.weekday).astype(int)  # type: ignore
    olb_df["monthday"] = (olb_df["datetime"].dt.day).astype(int)  # type: ignore
    olb_df["process"] = "Transfer"
    olb_df["details"] = df["Empfänger/Auftraggeber"]
    olb_df["amount"] = df["Betrag"].str.replace(".", "").str.replace(",", ".").astype(float)

    return olb_df


def parse_all_olb(files=None) -> pd.DataFrame:

    if not files:
        dir_path = os.path.join("finance_data", "olb")
        all_files = glob(os.path.join(dir_path, "*.csv"))
    else:
        all_files = files

    df_list = [_parse_olb_csv(file) for file in all_files]
    combined_df = pd.concat(df_list, ignore_index=True)
    combined_df.sort_values(by="date", inplace=True)
    combined_df.reset_index(drop=True, inplace=True)

    combined_df = combined_df.drop_duplicates()
    combined_df = combined_df[combined_df["amount"].notna()]
    combined_df = combined_df[combined_df["process"].notna()]
    combined_df["process"] = combined_df["process"].map(OLB_PROCESS_MAPPING).fillna(combined_df["process"])

    return combined_df
