import pandas as pd


def prepare_evaluate_date():
    df = pd.read_csv("../data/evaluate_raw.tsv",
                             sep="\t",
                             usecols=["item_en", "hscode"],
                     dtype=str)

    df = df[df["hscode"].str.len() == 10]

    df["hscode"] = df["hscode"].str[:6]

    df.to_csv("../data/evaluate_processed.tsv", sep="\t", index=False)


prepare_evaluate_date()