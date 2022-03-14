import pathlib
import pandas as pd
import streamlit as st


# @st.cache()
def load_data(data_path: pathlib.Path = pathlib.Path(__file__).parent / 'data'):
    """
    Load data from excel files.
    """
    excel_files = list(data_path.glob('*.xlsx'))
    # store all dates and game data
    game_data = [pd.read_excel(e, sheet_name=['Basics', 'TeamA', 'TeamB', 'Rundown']) for e in excel_files]
    dates = pd.Series([pd.to_datetime(e.name.split('_')[0], dayfirst=True) for e in excel_files])
    # sort by date
    dates.sort_values(inplace=True)
    game_data = [game_data[i] for i in dates.index]

    return dates, game_data


# @st.cache()
def build_rundown(game_data):
    """
    Build markdown match rundown.
    """
    raw_rundown, teamA_data, teamB_data = game_data['Rundown'], game_data['TeamA'], game_data['TeamB']
    teamA, teamB = game_data['Basics']['Name'].values
    nicer_rundown = [f'## Minute &nbsp; Score {teamA}:{teamB} &nbsp; Play']
    minute = 0
    score = {'A': 0, 'B': 0}
    whoscored = ''
    # TODO: include fouls and quarters in rundown
    for row in raw_rundown.iterrows():
        if row[1].Minute >= 0:  # gather current minute
            minute = row[1].Minute
        if row[1]['# A'] >= 0:  # gather player and team name
            whoscored = 'A'
            team = teamA
            assert (row[1]['# A'] == teamA_data['#']).sum(), f'Error: Wrong player number in minute {minute}!'
            name = teamA_data[row[1]['# A'] == teamA_data['#']].Name.values[0]
        elif row[1]['# B'] >= 0:
            whoscored = 'B'
            team = teamB
            assert (row[1]['# B'] == teamB_data['#']).sum(), f'Error: Wrong player number in minute {minute}!'
            name = teamB_data[row[1]['# B'] == teamB_data['#']].Name.values[0]
        else:  # catching second free throw case
            pass  # same player and team scores
        #  gather scoring type
        points = row[1][f'Score {whoscored}'] - score[whoscored] if str(row[1][f'Score {whoscored}']).isdigit() else 0
        if points == 3:
            play = 'hit a three 🎯'
        elif points == 2:
            play = 'made a bucket ⛹️‍♂️'
        elif points == 1:
            play = 'made a free throw 🏀'
        else:
            assert row[1][f'Score {whoscored}'] in '-', 'Error: No valid number of points made but also no sign for missed freethrow!'
            play = 'missed a free throw 🧱'
        score[whoscored] += points
        # make entry for nicer rundown
        scoreA, scoreB = score.values()
        line = f'{int(minute):02d}: &nbsp; {int(scoreA):02d}:{int(scoreB):02d} &nbsp; {team}: {name} {play}'
        nicer_rundown.append(line)

    return nicer_rundown


# build streamlit page
st.set_page_config(page_title="Flamingo Fadaways", page_icon="🦩", layout="wide", initial_sidebar_state="expanded",
                   menu_items={'About': "### Source Code on [Github](https://github.com/woldeaman/flamingo_stats)"})

# build sidebar
dates, game_data = load_data()
st.sidebar.title('Flamingo Fadaways 🦩')
dates_str = [d.strftime("%d.%m.%Y") for d in dates]
game_selector = st.sidebar.selectbox('Matchday', options=dates_str)
game_idx = [i for i, d in enumerate(dates_str) if d in game_selector][0]

# setup main page with logo and average stats
with st.container():
    col1, col2, col3 = st.columns(3)
    col2.image('logo.jpg', width=250)
with st.container():
    col1, col2, col3 = st.columns(3)
    col1.metric("League Seat", 9, delta=10)
    col2.metric("PPG", "47 pts", "-10 pts")
    col3.metric("FT%", "55%", "5%")

# compute nicer rundown
rundown = build_rundown(game_data[game_idx])

with st.container():
    # display selected game data
    for dat_lbl in ['Basics', 'TeamA', 'TeamB']:
        st.dataframe(game_data[game_idx][dat_lbl])
    for line in rundown:
        st.write(line)