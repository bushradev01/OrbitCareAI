
import os
import pandas as pd

DATA_FOLDER = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "raw"
)

files_to_inspect = [
    "LSDS-8_Comprehensive_Metabolic_Panel_CMP_TRANSFORMED.csv",
    "LSDS-8_Multiplex_serum_cardiovascular_EvePanel_TRANSFORMED.csv",
    "LSDS-8_Multiplex_serum_immune_AlamarPanel_TRANSFORMED.csv",
    "LSDS-8_Multiplex_serum_immune_EvePanel_TRANSFORMED.csv",
]

print("\n========== ORBITCARE AI ==========")
print("NASA OSD-575 DATASET INSPECTION")
print("=================================\n")

for filename in files_to_inspect:

    filepath = os.path.join(DATA_FOLDER, filename)

    print("\n---------------------------------")
    print("FILE:", filename)
    print("---------------------------------")

    if not os.path.exists(filepath):
        print("File not found!")
        continue

    try:
        df = pd.read_csv(filepath)

        print("Rows:", df.shape[0])
        print("Columns:", df.shape[1])

        print("\nColumn names:")
        for column in df.columns:
            print("-", column)

        print("\nFirst 3 records:")
        print(df.head(3).to_string(index=False))

        print("\nMissing values:")
        print(df.isnull().sum().to_string())

    except Exception as error:
        print("Error reading file:", error)

print("\n========== INSPECTION COMPLETE ==========")
