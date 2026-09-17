import polars as pl


def strip_all_str(df: pl.DataFrame):
    df_strip = df.with_columns(
        pl.col(pl.String).str.strip_chars()
    )
    return df_strip