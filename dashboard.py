import pathlib
import pandas as pd
import streamlit as st


# @st.cache()
def load_data(data_path: pathlib.Path = pathlib.Path(__file__).parent / 'data'):
    """
    Load data from excel files.
    """
    game_path = data_path / 'games/'
    excel_files = list(game_path.glob('*.xlsx'))
    # store all dates and game data
    game_data = [pd.read_excel(e, sheet_name=['Basics', 'TeamA', 'TeamB', 'Rundown']) for e in excel_files]
    dates = pd.Series([pd.to_datetime(e.name.split('_')[-1].split('.')[0], dayfirst=True) for e in excel_files])
    # sort by date
    dates.sort_values(inplace=True)
    game_data = [game_data[i] for i in dates.index]
    # read roster
    roster = pd.read_excel(data_path / 'roster.xlsx')

    return dates, game_data, roster


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
            assert (row[1]['# A'] == teamA_data['#']).sum(), f'Error: Wrong player numbeexitr in minute {minute}!'
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


def print_game_stats(game_idx):
    """
    Display nice game stats.
    """
    # generate rundown
    rundown = build_rundown(game_data[game_idx])

    # display selected game data
    with st.container():
        st.dataframe(game_data[game_idx]['Basics'])
        col1, col2 = st.columns(2)
        for col, team in zip([col1, col2], ['TeamA', 'TeamB']):
            with col:
                st.dataframe(game_data[game_idx][team])
    # print rundown
    with st.container():
        for line in rundown:
            st.write(line)

    # TODO: make this look nicer


def print_player_stats(player):
    """
    Display player stats.
    """
    st.write(f'{player} Player Stats')
    # TODO: calculate player stats


# build streamlit page
st.set_page_config(page_title="Flamingo Fadaways", page_icon="🦩", layout="wide", initial_sidebar_state="expanded",
                   menu_items={'About': "### Source Code on [Github](https://github.com/woldeaman/flamingo_stats)"})

# build sidebar
dates, game_data, roster = load_data()
st.sidebar.title('Flamingo Fadaways 🦩')
dates_str = [d.strftime("%d.%m.%Y") for d in dates]
game_selector = st.sidebar.selectbox('Matchday Stats', options=dates_str)
show_match = st.sidebar.button('Show', key='show_match')
game_idx = [i for i, d in enumerate(dates_str) if d in game_selector][0]
player_selector = st.sidebar.selectbox('Player Stats', options=roster['Name'].values)
show_player = st.sidebar.button('Show', key='show_player')

# setup main page with logo and average stats
with st.container():
    col1, col2, col3 = st.columns(3)
    col2.image('logo.jpg', width=250)
with st.container():
    col1, col2, col3 = st.columns(3)
    col1.metric("League Seat", 9, delta=10)
    col2.metric("PPG", "47 pts", "-10 pts")
    col3.metric("FT%", "55%", "5%")

# print either game rundown or player stats, depending on selection
if show_match:
    print_game_stats(game_idx)
if show_player:
    print_player_stats(player_selector)
