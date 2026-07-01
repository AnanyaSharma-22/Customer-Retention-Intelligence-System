import pandas as pd


#def validate_dataset(df: pd.DataFrame):
   # """
    #Validate uploaded dataset.
    #"""

    #required_columns = [
        #"InvoiceNo",
        #"StockCode",
        #"Description",
        #"Quantity",
        #"InvoiceDate",
       # "UnitPrice",
      #  "CustomerID",
     #   "Country",
    #]

    #missing_columns = [
       # column
      #  for column in required_columns
     #   if column not in df.columns
    #]

    #if missing_columns:
    #    raise ValueError(
   #         f"Missing required columns: {missing_columns}"
  #      )
#
#    return True


def load_uploaded_file(file_path: str):
    """
    Load CSV or Excel uploaded by user.
    """

    if file_path.endswith(".csv"):
        return pd.read_csv(file_path)

    if file_path.endswith(".xlsx"):
        return pd.read_excel(file_path)

    if file_path.endswith(".xls"):
        return pd.read_excel(file_path)

    raise ValueError("Unsupported file format.")

def get_uploaded_columns(df: pd.DataFrame):
    """
    Return uploaded column names.
    """

    return df.columns.tolist()