import pandas as pd
import os
from glob import glob
from pypdf import PdfReader
import dateparser


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
    df.columns = ["date", "process", "details", "amount"]

    df = df[df["date"].notna()]

    df["amount"] = pd.to_numeric(df["amount"].str.replace(".", "").str.replace(",", "."))
    df["process"] = df["process"].astype("category")
    df["details"] = df["details"].astype("string")
    df["short_details"] = df["details"].str.slice(0, 30).astype("string")

    return df


def parse_all_comdirect(dir_path: str) -> pd.DataFrame:
    all_files = glob(os.path.join(dir_path, "umsaetze_*.csv"))
    df_list = [parse_comdirect_csv(file) for file in all_files]
    combined_df = pd.concat(df_list, ignore_index=True)
    combined_df.sort_values(by="date", inplace=True)
    combined_df.reset_index(drop=True, inplace=True)

    combined_df = combined_df.drop_duplicates()
    combined_df = combined_df[combined_df["amount"].notna()]
    combined_df = combined_df[combined_df["process"].notna()]
    return combined_df


def parse_all_traderepublic(dir_path: str) -> pd.DataFrame:
    all_files = glob(os.path.join(dir_path, "*.pdf"))
    df_list = [parse_traderepublic_pdf(file) for file in all_files]
    combined_df = pd.concat(df_list, ignore_index=True)
    combined_df.sort_values(by="date", inplace=True)
    combined_df.reset_index(drop=True, inplace=True)

    combined_df = combined_df.drop_duplicates()
    combined_df = combined_df[combined_df["amount"].notna()]
    combined_df = combined_df[combined_df["process"].notna()]
    return combined_df


def parse_traderepublic_pdf(path: str) -> pd.DataFrame:
    reader = PdfReader(path)

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

    traderepublic_df = pd.DataFrame(columns=["date", "process", "details", "amount"])

    new_row_template = {"date": "", "process": "", "details": "", "amount": ""}
    for line in filtered_lines:
        new_row = new_row_template.copy()
        line_split = line.split(" ")
        dates = line_split[:3]
        dt1 = dateparser.parse(" ".join(dates), settings={"DATE_ORDER": "DMY", "PREFER_DAY_OF_MONTH": "first"})
        assert dt1 is not None
        new_row["date"] = dt1.date()  # type: ignore
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

    return traderepublic_df
