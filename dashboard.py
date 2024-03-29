import pathlib
import requests
import pandas as pd
import altair as alt
from lxml import html
import streamlit as st


#############
# FUNCTIONS #
############################################################################################################################
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


def generate_foul_line(minute: float, score: dict, teamA_data: pd.DataFrame,
                       teamB_data: pd.DataFrame, teamA: str, teamB: str) -> tuple:
    """
    Generate line for foul play in rundown.

    ```
    :param minute:         current minute of the match
    :param teamA_data:     player data for Team A
    :param teamB_data:     player data for Team B
    :param teamA:          name of Team A
    :param teamB:          name of Team B
    :return foul_line:     line for foul play in rundown
    ```
    """
    fouled_A = (teamA_data.iloc[:, 3:] == minute).sum(1).astype(bool)
    fouled_B = (teamB_data.iloc[:, 3:] == minute).sum(1).astype(bool)
    if fouled_A.sum() or fouled_B.sum():  # if multiple players fouled in the same min, this will only print the 1st
        player_fouled = teamA_data[fouled_A].Name.values[0] if fouled_A.sum() else teamB_data[fouled_B].Name.values[0]
        team_fouled = teamA if fouled_A.sum() else teamB
        fl_entry_A = f'{player_fouled} commited a foul 🚨' if team_fouled in teamA else ''
        fl_entry_B = f'{player_fouled} commited a foul 🚨' if team_fouled in teamB else ''
        scoreA, scoreB = score.values()
        foul_line = f'| {int(minute):02d} | {fl_entry_A} | {int(scoreA):d}:{int(scoreB):d} | {fl_entry_B} |'
    else:
        foul_line, team_fouled, player_fouled = None, None, None

    return foul_line, team_fouled, player_fouled


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
    minute, foul_min = 0, 0
    score = {'A': 0, 'B': 0}
    whoscored = ''
    nicer_rundown = [f'| Minute | {teamA} | Score | {teamB} |', '|:---:|:-----------|:-----:|-----------:|']
    for row in raw_rundown.iterrows():
        if row[1].Minute >= 0:  # gather current minute
            minute = row[1].Minute

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
            # look for fouls in this minute since there were free throws
            foul_line, team_fouled, player_fouled = generate_foul_line(minute, score, teamA_data, teamB_data, teamA, teamB)
            if foul_line and foul_min != minute:  # only print once
                foul_min = minute
                nicer_rundown.append(foul_line)
                player_stats[team_fouled].loc[player_fouled, 'PF'] += 1  # add foul to player stats

            play = 'made a free throw 🏀'
            player_stats[team].loc[name, 'FTM'] += 1  # add to player stats
            player_stats[team].loc[name, 'FTA'] += 1
        else:
            assert row[1][f'Score {whoscored}'] in '-', 'Error: No valid number of points made but also \
                no sign for missed freethrow!'
            # look for fouls in this minute since there were free throws
            foul_line, team_fouled, player_fouled = generate_foul_line(minute, score, teamA_data, teamB_data, teamA, teamB)
            if foul_line and foul_min != minute:  # only print once
                foul_min = minute
                nicer_rundown.append(foul_line)
                player_stats[team_fouled].loc[player_fouled, 'PF'] += 1  # add foul to player stats

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

        # look for fouls in this minute not related to free throws
        foul_line, team_fouled, player_fouled = generate_foul_line(minute, score, teamA_data, teamB_data, teamA, teamB)
        if foul_line and foul_min != minute:  # only print once
            foul_min = minute
            nicer_rundown.append(foul_line)
            player_stats[team_fouled].loc[player_fouled, 'PF'] += 1  # add foul to player stats

        # add line for end of quarter
        if minute % 10 == 0 and minute < 40:
            position = {1: 'st', 2: 'nd', 3: 'rd'}
            qtr = int(minute // 10)
            qtr_line = f'||||| **End of {qtr}{position[qtr]} quarter**'
            if raw_rundown.iloc[row[0] + 1].Minute > minute:  # only print at the end
                nicer_rundown.append(qtr_line)

    # add lines for end of game
    winner = teamA if scoreA > scoreB else teamB
    end = ['||||| **End of 4th quarter**', f'||||| ***End of Game, Team {winner} Wins***']
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

    # create altair donut charts for each stat
    charts_base = [alt.Chart(team_stats).encode(theta=alt.Theta(f'{stat}:Q', stack=True),
                                                tooltip=['Team', alt.Tooltip(field=stat, format=",.0f")],
                                                color=alt.Color('Team:O',
                                                                scale=alt.Scale(scheme='pastel1'),
                                                                legend=None)).properties(title=stat) for stat in stats]
    charts_donuts_1 = [cbase.mark_arc(innerRadius=50, stroke="#fff") for cbase in charts_base]
    # TODO: try printing number next to chart...
    # charts_numbers = [cbase.mark_text(radius=170, size=20).encode(text=alt.Text(f'{stat}:Q', format=",.0f"))
    #                   for cbase, stat in zip(charts_base, stats)]
    # charts = [donut_1 for donut_1, number in zip(charts_donuts_1, charts_numbers)]

    return charts_donuts_1


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

        with st.container():
            st.caption("Team Scores by Quarter")
            st.dataframe(game_dat['Basics'].set_index('Team'), use_container_width=True)
            st.markdown('&nbsp;')

        with st.container():  # print player stats in tables
            col1, col2 = st.columns(2)
            for col, team in zip([col1, col2], game_dat['Basics'].Name.values):
                with col:
                    st.caption(f'Player Statistics {team}')
                    styled_stats = player_stats[team].sort_index().style.format(precision=0, na_rep='No FTA')
                    st.dataframe(styled_stats, use_container_width=True)

    with tab2:  # print game rundown
        with st.container():
            st.markdown(rundown)


def check_team_performance(game_data: list) -> list:
    """
    For homepage check current team performance in comparison to last game.

    ```
    :param game_data:         list of all game data
    :return :
    ```
    """
    stats = ['PTS', 'FGM', '3PM', 'FT%', 'PF']
    team_data = []  # create team stats dataframe for each match
    for game in game_data:
        _, player_stats = build_rundown(game)
        team_stats = pd.DataFrame(0, columns=stats, index=player_stats.keys())
        for team in team_stats.index:
            team_stats.loc[team] = player_stats[team].agg({'FGM': sum, '3PM': sum, 'FT%': 'mean', 'PF': sum})
        team_stats['Team'] = team_stats.index
        for team, pts in zip(game['Basics']['Name'].values, game['Basics']['Final'].values):
            team_stats.loc[team, 'PTS'] = pts
        team_data.append(team_stats)

    return team_data


def scrape_league_seat(webpage: str = 'https://fbl.berlin/tabellen') -> int:
    """
    Scrape our current table placement from the FBL webpage.

    ```
    :param webpage:         link to page for table
    :return league_seat:    current ranking in table
    ```
    """
    page = requests.get(webpage)  # parse website
    page_tree = html.fromstring(page.content)  # get page as xml
    # use xpath query to find flamingos team
    teams = page_tree.body.xpath('//*[@data-label="Team"]')  # gather all teams
    flamingos = [team for team in teams if team.text and 'Flamingo' in team.text]  # look for our team
    league_seat = int(flamingos[0].getparent().xpath('.//*[@data-label="Pos."]')[0].text)  # extract league seat info

    return league_seat


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
    # clicking this button will take you back to the main page
    st.sidebar.button('Back to Homepage', key='home')
    # build sidebar
    st.sidebar.title('Flamingo Fadaways 🦩')
    dates_str = [d.strftime("%d.%m.%Y") for d in dates]
    form = st.sidebar.form('Select Match')
    game_selector = form.selectbox('Matchday Stats', options=dates_str)
    show_match = form.form_submit_button('Show')
    game_idx = [i for i, d in enumerate(dates_str) if d in game_selector][0]

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
            st.markdown('### Team Performance')
            col1, col2, col3 = st.columns(3)
            with st.spinner('Loading Team Stats...'):
                try:  # try finding team league seat
                    league_seat = scrape_league_seat()
                except Exception:  # if it couldn't be scraped, set to zero
                    league_seat = 0

            col1.metric("League Seat", league_seat)
            col1.markdown('')  # space since no diff is shown
            # fill in team performance and trends
            team_stats = check_team_performance(game_data)
            latest = team_stats[-1][team_stats[-1]['Team'] == 'Flamingo Fadaways']
            previous = team_stats[-2][team_stats[-2]['Team'] == 'Flamingo Fadaways']
            for stat, txt, col in zip(['PTS', 'FT%', 'FGM', '3PM', 'PF'],
                                      ['PTS', '%', 'FGs', 'TPs', 'Fouls'],
                                      [col2, col3, col1, col2, col3]):
                current = latest[stat].values[0]
                diff = latest[stat].values[0] - previous[stat].values[0]
                col.metric(stat, f"{int(current)} {txt}", f"{int(diff)} {txt}")

    # print game rundown depending on selection
    if show_match:
        game_details_page(game_data[game_idx])

    # TODO: add this for player stats at a later stage
    # player_selector = st.sidebar.selectbox('Player Stats', options=roster['Name'].values)
    # show_player = st.sidebar.button('Show', key='show_player')
    # if show_player:
    #     print_player_stats(player_selector)


# can't have if __name__ == 'main' here for streamlit to work
main()
############################################################################################################################
