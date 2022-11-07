import pathlib
import pandas as pd
import streamlit as st
import altair as alt


#############
# FUNCTIONS #
############################################################################################################################
# @st.cache()
# NOTE: this could also be hosted on google drive instad of inside the repo
def load_data(data_path: pathlib.Path = pathlib.Path(__file__).parent / 'data') -> tuple:
    """
    Load data from excel files in pre-defined format

    :param data_path:               path to excel files
    :return dates:                  return dates of matchdays
    :return game_data:              return corresponding game data in dataframe
    :return roster:                 return flamingos player roster in dataframe
    ```
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
def build_rundown(game_data: dict) -> tuple:
    """
    Build markdown formatted rundown listing game events.

    :param game_data:               dictionary containing dataframes of game data based on match report
    :return nicer_rundown:          list of markdown formatted strings for each game event
    :return player_stats:           detailed stats for each player
    ```
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
    nicer_rundown = [f'| Minute | {teamA} | Score | {teamB} |', '|:---:|:-----------|:-----:|-----------:|']
    for row in raw_rundown.iterrows():
        if row[1].Minute >= 0:  # gather current minute
            minute = row[1].Minute

        # look for fouls in this minute
        fouled_A = (teamA_data.iloc[:, 3:] == minute).sum(1).astype(bool)
        fouled_B = (teamB_data.iloc[:, 3:] == minute).sum(1).astype(bool)
        if fouled_A.sum() or fouled_B.sum():  # if multiple players fouled in the same min, this will only print the 1st
            player_fouled = teamA_data[fouled_A].Name.values[0] if fouled_A.sum() else teamB_data[fouled_B].Name.values[0]
            team_fouled = teamA if fouled_A.sum() else teamB
            fl_entry_A = f'{player_fouled} commited a foul 🚨' if team_fouled in teamA else ''
            fl_entry_B = f'{player_fouled} commited a foul 🚨' if team_fouled in teamB else ''
            scoreA, scoreB = score.values()
            foul_line = f'| {int(minute):02d} | {fl_entry_A} |{int(scoreA):d}:{int(scoreB):d} | {fl_entry_B} |'
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
            assert row[1][f'Score {whoscored}'] in '-', 'Error: No valid number of points made but also \
                no sign for missed freethrow!'
            play = 'missed a free throw 🧱'
            player_stats[team].loc[name, 'FTA'] += 1  # add to player stats

        score[whoscored] += points
        player_stats[team].loc[name, 'PTS'] += points  # add to player stats

        # make entry for nicer rundown
        scoreA, scoreB = score.values()
        entry_A = f'{name} {play}' if team in teamA else ''
        entry_B = f'{name} {play}' if team in teamB else ''
        line = f'| {int(minute):02d} | {entry_A} |{int(scoreA):d}:{int(scoreB):d} | {entry_B} |'
        nicer_rundown.append(line)

        # add line for end of quarter
        if minute % 10 == 0 and minute < 40:
            position = {1: 'st', 2: 'nd', 3: 'rd'}
            qtr = int(minute // 10)
            qtr_line = f'||||| **End of {qtr}{position[qtr]} quarter**'
            if raw_rundown.iloc[row[0] + 1].Minute > minute:  # only print at the end
                nicer_rundown.append(qtr_line)

    # add lines for end of game
    winner = teamA if scoreA > scoreB else teamB
    end = ['||||| **End of 4th quarter**', f'||||| ***End of Game, Team {winner} wins***']
    nicer_rundown += end
    nicer_rundown = '\n'.join(nicer_rundown)
    # calculate overall FT percentage and add nbr
    for team in [teamA, teamB]:
        player_stats[team]['FT%'] = 100 * player_stats[team]['FTM'] / player_stats[team]['FTA']
    for ord, team in zip(['TeamA', 'TeamB'], [teamA, teamB]):
        player_stats[team]['Player'] = player_stats[team].index
        player_stats[team].index = [game_data[ord]['#'].values]

    return nicer_rundown, player_stats


def general_game_info(game_basics: pd.DataFrame) -> None:
    """
    Generate page for general game info

    :param game_basics:      dataframe containing basic game info
    ```
    """
    t1_col1, t1_col2, t1_col3 = st.columns(3)  # columns for orientation
    for i, col in enumerate([t1_col1, t1_col3]):
        with col:  # print team scores
            st.markdown(f'## {game_basics["Final"].values[i]} PTS')
            st.markdown(f'### {game_basics["Name"].values[i]}')
    with t1_col2:
        st.markdown('&nbsp;')
        st.markdown('&nbsp;')
        st.markdown('### vs.')


def team_stat_charts(player_stats: dict) -> list:
    """
    Build charts for team specific statistics.

    ```
    :param player_stats:         dictionary of dataframes containing player stats
    :return charts:              list containing altair charts of team stats
    ```
    """
    stats = ['FGM', '3PM', 'FT%', 'PF']
    # create team stats dataframe
    team_stats = pd.DataFrame(0, columns=stats, index=player_stats.keys())
    for team in team_stats.index:
        team_stats.loc[team] = player_stats[team].agg({'FGM': sum, '3PM': sum, 'FT%': 'mean', 'PF': sum})
    team_stats['Team'] = team_stats.index

    base = alt.Chart(team_stats)  # create altair donut charts for each stat
    charts = [base.mark_arc(innerRadius=50).encode(theta=f'{stat}:Q',
                                                   tooltip=['Team'],
                                                   color=alt.Color('Team:O',
                                                                   scale=alt.Scale(scheme='pastel1'),
                                                                   legend=None)).properties(title=stat)
              for stat in stats]

    return charts


def game_details_page(game_dat: dict) -> None:
    """
    Build page to display nice game stats.

    :param game_dat:      dictionary containing dataframes with game info
    """
    # generate rundown
    rundown, player_stats = build_rundown(game_dat)

    # display selected game data
    general_game_info(game_dat['Basics'])
    tab1, tab2 = st.tabs(["Statistics", "Play by Play"])

    with tab1:
        # print team stats in donut charts
        altair_charts = team_stat_charts(player_stats)
        cols = st.columns(len(altair_charts))
        for col, chart in zip(cols, altair_charts):
            with col:
                st.altair_chart(chart, use_container_width=True)

        # generate table for stats by quarter
        min_qtr_score = game_dat['Basics'].iloc[:, 2:-1].min().min()
        max_qtr_score = game_dat['Basics'].iloc[:, 2:-1].max().max()
        styled_basics = game_dat['Basics'].set_index('Team').style.background_gradient(cmap='YlOrRd',
                                                                                       subset=['1/4', '2/4', '3/4', '4/4'],
                                                                                       vmin=min_qtr_score,
                                                                                       vmax=max_qtr_score)
        with st.container():
            st.caption("Scores by Quarter")
            st.dataframe(styled_basics, use_container_width=True)
            st.markdown('&nbsp;')

        with st.container():  # print player stats in tables
            col1, col2 = st.columns(2)
            for col, team in zip([col1, col2], game_dat['Basics'].Name.values):
                with col:
                    st.caption(team)
                    styled_stats = player_stats[team].style.format(precision=0, na_rep='No FTA')
                    st.dataframe(styled_stats, use_container_width=True)

    with tab2:  # print game rundown
        with st.container():
            st.markdown(rundown)


def build_sidebar(dates: list) -> tuple:
    """
    Build sidebar of web app.

    ```
    :param dates:           matchdates
    :return game_idx:       index of the match to display
    :return show_match:     whether or not to show match info
    :return back_to_main:   whether or not to go back to main page
    ```
    """
    # build sidebar
    st.sidebar.title('Flamingo Fadaways 🦩')
    dates_str = [d.strftime("%d.%m.%Y") for d in dates]
    game_selector = st.sidebar.selectbox('Matchday Stats', options=dates_str)
    show_match = st.sidebar.button('Show', key='show_match')
    game_idx = [i for i, d in enumerate(dates_str) if d in game_selector][0]
    # clicking this button will take you back to the main page
    st.sidebar.button('Back to Homepage', key='home')

    return show_match, game_idx
############################################################################################################################


########
# MAIN #
############################################################################################################################
def main():
    dates, game_data, roster = load_data()  # load data
    # build streamlit page
    st.set_page_config(page_title="Flamingo Fadaways", page_icon="🦩", layout="wide", initial_sidebar_state="expanded",
                       menu_items={'About': "### Source Code on [Github](https://github.com/woldeaman/flamingo_stats)"})
    # build sidebar
    show_match, game_idx = build_sidebar(dates)

    # setup main page with logo and average stats
    with st.container():
        col1, col2, col3 = st.columns(3)
        col2.image('logo.jpg', width=250)
    if not show_match:
        with st.container():
            col1, col2, col3 = st.columns(3)
            col1.metric("League Seat", 10)  # TODO: maybe scrape this from FBL page?
            # TODO: make this update automatically for latest game
            col2.metric("PPG", "47 pts", "-10 pts")
            col3.metric("FT%", "55%", "5%")

    # print game rundown depending on selection
    if show_match:
        game_details_page(game_data[game_idx])

    # TODO: add this at a later stage
    # player_selector = st.sidebar.selectbox('Player Stats', options=roster['Name'].values)
    # show_player = st.sidebar.button('Show', key='show_player')
    # if show_player:
    #     print_player_stats(player_selector)


# can't have if __name__ == 'main' here for streamlit to work
main()
############################################################################################################################
