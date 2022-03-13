import pathlib
import numpy as np
import pandas as pd
import streamlit as st

# load data from excel files
data_path = pathlib.Path(__file__).parent / 'data'
excel_files = list(data_path.glob('*.xlsx'))
# store all dates and game data
game_data = [pd.read_excel(e, sheet_name=['Basics', 'TeamA', 'TeamB', 'Rundown'])
             for e in excel_files]
dates = pd.Series([pd.to_datetime(e.name.split('_')[0], dayfirst=True) for e in excel_files])
# sort by date
dates.sort_values(inplace=True)
game_data = [game_data[i] for i in dates.index]


# build streamlit page
st.set_page_config(page_title="Flamingo Fadaways", page_icon="🦩", layout="wide", initial_sidebar_state="expanded",
                   menu_items={'About': "### Source Code on [Github](https://github.com/woldeaman/flamingo_stats)"})
# setup page with logo
with st.container():
    im_col1, im_col2, im_col3, im_col4, im_col5 = st.columns(5)
    with im_col3:
        st.image('logo.jpg', use_column_width=True)

# build sidebar
st.sidebar.title('Flamingo Fadaways 🦩')
dates_str = [d.strftime("%d.%m.%Y") for d in dates]
game_selector = st.sidebar.selectbox('Spieldatum', options=dates_str)
game_idx = [i for i, d in enumerate(dates_str) if d in game_selector][0]

# display selected game data
for dat_lbl in ['Basics', 'TeamA', 'TeamB']: # ['Basics', 'TeamA', 'TeamB', 'Rundown'],
    st.dataframe(game_data[game_idx][dat_lbl])