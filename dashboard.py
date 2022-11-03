import pathlib
import numpy as np
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
    # collect stats
    raw_rundown, teamA_data, teamB_data = game_data['Rundown'], game_data['TeamA'], game_data['TeamB']
    teamA, teamB = game_data['Basics']['Name'].values
    stats = ['Player', 'PF', 'FGM', '3PM', 'FTM', 'FTA', 'FT%', 'PTS']
    player_stats = {team: pd.DataFrame(0, index=game_data[ord]['Name'], columns=stats)
                    for ord, team in zip(['TeamA', 'TeamB'], [teamA, teamB])}

    # running variables
    minute = 0
    score = {'A': 0, 'B': 0}
    whoscored = ''
    nicer_rundown = [f'## Minute &nbsp; Score {teamA}:{teamB} &nbsp; Play']
    for row in raw_rundown.iterrows():
        if row[1].Minute >= 0:  # gather current minute
            minute = row[1].Minute

        # look for fouls in this minute
        fouled_A = (teamA_data.iloc[:, 3:] == minute).sum(1).astype(bool)
        fouled_B = (teamB_data.iloc[:, 3:] == minute).sum(1).astype(bool)
        if fouled_A.sum() or fouled_B.sum():  # if multiple players fouled in the same min, this will only print the 1st
            player_fouled = teamA_data[fouled_A].Name.values[0] if fouled_A.sum() else teamB_data[fouled_B].Name.values[0]
            team_fouled = teamA if fouled_A.sum() else teamB
            foul_line = f'{int(minute):02d}: &nbsp; {team_fouled}: {player_fouled} commited a foul 🚨'
            if foul_line not in nicer_rundown:  # only print once
                nicer_rundown.append(foul_line)
                player_stats[team_fouled].loc[player_fouled, 'PF'] += 1  # add foul to player stats

        if row[1]['# A'] >= 0:  # gather scoring player and team name
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
            player_stats[team].loc[name, '3PM'] += 1  # add to player stats
        elif points == 2:
            play = 'made a bucket ⛹️‍♂️'
            player_stats[team].loc[name, 'FGM'] += 1  # add to player stats
        elif points == 1:
            play = 'made a free throw 🏀'
            player_stats[team].loc[name, 'FTM'] += 1  # add to player stats
            player_stats[team].loc[name, 'FTA'] += 1
        else:
            assert row[1][f'Score {whoscored}'] in '-', 'Error: No valid number of points made but also no sign for missed freethrow!'
            play = 'missed a free throw 🧱'
            player_stats[team].loc[name, 'FTA'] += 1  # add to player stats

        score[whoscored] += points
        player_stats[team].loc[name, 'PTS'] += points  # add to player stats

        # make entry for nicer rundown
        scoreA, scoreB = score.values()
        line = f'{int(minute):02d}: &nbsp; {int(scoreA):02d}:{int(scoreB):02d} &nbsp; {team}: {name} {play}'
        nicer_rundown.append(line)

        # add line for end of quarter
        if minute % 10 == 0 and minute < 40:
            position = {1: 'st', 2: 'nd', 3: 'rd'}
            qtr = int(minute // 10)
            qtr_line = f'----- &nbsp; End of {qtr}{position[qtr]} quarter - Score: {int(scoreA):02d}:{int(scoreB):02d} &nbsp; -----'
            if raw_rundown.iloc[row[0] + 1].Minute > minute:  # only print at the end
                nicer_rundown.append(qtr_line)

    # add lines for end of game
    winner = teamA if scoreA > scoreB else teamB
    end = [f'----- &nbsp; End of 4th quarter - Score: {int(scoreA):02d}:{int(scoreB):02d} &nbsp; -----',
           f'----- &nbsp; End of Game, Team {winner} wins: {int(scoreA):02d}:{int(scoreB):02d} &nbsp; -----']
    nicer_rundown += end
    # calculate overall FT percentage and add nbr
    for team in [teamA, teamB]:
        player_stats[team]['FT%'] = 100 * player_stats[team]['FTM'] / player_stats[team]['FTA']
    for ord, team in zip(['TeamA', 'TeamB'], [teamA, teamB]):
        player_stats[team]['Player'] = player_stats[team].index
        player_stats[team].index = [game_data[ord]['#'].values]

    return nicer_rundown, player_stats


def print_game_stats(game_dat):
    """
    Display nice game stats.
    """
    # generate rundown
    rundown, player_stats = build_rundown(game_dat)

    # display selected game data
    tab1, tab2 = st.tabs(["Stats", "Play by Play"])

    with tab1:
        st.dataframe(game_dat['Basics'].set_index('Team'))
        col1, col2 = st.columns(2)
        for col, team in zip([col1, col2], game_dat['Basics'].Name.values):
            with col:
                st.dataframe(player_stats[team])
        # TODO: make the formatting look nice here and add team data with altair
    # print rundown
    with tab2:
        for line in rundown:
            st.write(line)
        # TODO: make the rundown look nicer and add barplot with altair

        # make_game_plot(rundown, game_dat['Basics']['Name'][0], game_dat['Basics']['Name'][1])



# def make_game_plot(rundown, teamA, teamB):
#     """
#     Make a bar plot for the game rundown.
#     """
#     # generate data from rundown
#     seriesA, seriesB = pd.DataFrame(columns=['min', 'scoreA']), pd.DataFrame(columns=['min', 'scoreB'])
#     for i, line in enumerate(rundown[1:]):
#         min = int(line[:2])
#         if teamA in line:
#             seriesA.loc[i, 'min'] = min
#             seriesA.loc[i, 'scoreA'] = int(line[3:].split(':')[0][-3:])
#         elif teamB in line:
#             seriesB.loc[i, 'min'] = min
#             seriesB.loc[i, 'scoreB'] = int(line[3:].split(':')[1][:3])

#     plot_df = pd.DataFrame(np.array([np.array(scoreA), -np.array(scoreB)]).T,
#                            columns=['scoreA', 'scoreB'],
#                            index=np.array(minutes))
#     st.bar_chart(plot_df)


def print_player_stats(player):
    """
    Display player stats.
    """
    st.write(f'{player} Player Stats')
#     # TODO: calculate player stats averaged over multpiple games


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
    print_game_stats(game_data[game_idx])
if show_player:
    print_player_stats(player_selector)
