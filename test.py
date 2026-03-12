import pandas as pd

excel_path = 'data/sample_business_data.xlsx'
df = pd.read_excel(excel_path, sheet_name='매출데이터', parse_dates=['날짜'])
df_jan1 = df[(df['날짜'].dt.month == 1) & (df['날짜'].dt.day == 1)]
total_sales = df_jan1['매출액'].sum()
print(total_sales)