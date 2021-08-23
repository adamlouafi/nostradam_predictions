import json
import os
import requests
import urllib
from apscheduler.schedulers.background import BlockingScheduler
from datetime import datetime, timedelta
from dotenv import load_dotenv

# load ".env" file var
load_dotenv()


# api doc available @ https://pinnacleapi.github.io/


soccer_id = 29
odds_url = "https://api.ps3838.com/v3/odds"
fixtures_url = "https://api.ps3838.com/v3/fixtures"
settled_fixtures_url = "https://api.ps3838.com/v3/fixtures/settled"
ps3838_api_key = os.getenv("PS3838_API_KEY")
tg_api_key = os.getenv("TELEGRAM_API_KEY")
tg_chat_id = os.getenv("TELEGRAM_CHAT_ID")
selected_fixtures = {}
settled_fixtures = {}


def selectFixtures(sport_id, odds_url, fixtures_url, date, ps3838_api_key):
    try:
        URL = f'{fixtures_url}?sportId={sport_id}'
        HEADER = {'Accept': 'application/json', 'Authorization': f'Basic {ps3838_api_key}'}
        response = requests.get(url=URL, headers=HEADER)
        print(f'Fixtures...{response.reason}')
        data = response.json()
        leagues = data["league"]
        selected_fixtures = {}

        for league in leagues:
            for event in league["events"]:
                if(event["starts"].split('T')[0] == date and event["liveStatus"] != 1 and event["resultingUnit"] == "Regular"):
                    selected_fixtures[event["id"]] = {
                        "date": date,
                        "time": event["starts"].split("T")[1].strip("Z"),
                        "league": league["name"],
                        "fixture": f'{event["home"]} - {event["away"]}'
                    }
        
        URL = f'{odds_url}?sportId={soccer_id}&oddsFormat=Decimal'
        response = requests.get(url=URL, headers=HEADER)
        data = response.json()
        leagues = data["leagues"]

        for league in leagues:
            for event in league["events"]:
                if(event["id"] in selected_fixtures):
                    for period in event["periods"]:
                        if("moneyline" in period and period["number"] == 0):
                            match_odds = period["moneyline"]
                            match_odds_margin = 1/match_odds["home"] + 1/match_odds["draw"] + 1/match_odds["away"]
                            home_odd = round(match_odds["home"]*match_odds_margin, 2)
                            draw_odd = round(match_odds["draw"]*match_odds_margin, 2)
                            away_odd = round(match_odds["away"]*match_odds_margin, 2)
                            if(4 >= home_odd >= draw_odd >= away_odd >= 2):
                                for over_under in period["totals"]:
                                    if(over_under["points"] == 2.5 and over_under["over"] >= 2):
                                        over_under_odds_margin = 1/over_under["over"] + 1/over_under["under"]
                                        over_odd = round(over_under["over"]*over_under_odds_margin, 2)
                                        under_odd = round(over_under["under"]*over_under_odds_margin, 2)
                                        selected_fixtures[event["id"]] = {
                                            "date": selected_fixtures[event["id"]]["date"],
                                            "time": selected_fixtures[event["id"]]["time"],
                                            "league": selected_fixtures[event["id"]]["league"],
                                            "fixture": selected_fixtures[event["id"]]["fixture"],
                                            "home":home_odd,
                                            "draw":draw_odd,
                                            "away":away_odd,
                                            "o2.5":over_odd,
                                            "u2.5":under_odd,
                                        }

        # remove fixtures not matching criteria                            
        for x in list(selected_fixtures):
            if not selected_fixtures[x].get("home"):
                del selected_fixtures[x]

        # sort dic by time
        selected_fixtures = dict(sorted(selected_fixtures.items(), key=lambda x: x[1]["time"]))

        with open("selected_fixtures.json", "w") as fp:
            json.dump(selected_fixtures, fp, indent="")
            print(f'Selected fixtures saved to file @ {datetime.utcnow()}')
    except Exception as e:
        print(f'Failed to execute \'selectFixtures()\' => {e}')


def updateOdds(soccer_id, odds_url, ps3838_api_key):
    try:
        with open("selected_fixtures.json", "r") as fp:
            selected_fixtures = json.load(fp)
        
        URL = f'{odds_url}?sportId={soccer_id}&oddsFormat=Decimal'
        HEADER = {'Accept': 'application/json', 'Authorization': f'Basic {ps3838_api_key}'}
        response = requests.get(url=URL, headers=HEADER)
        print(f'Odds...{response.reason}')
        data = response.json()
        leagues = data["leagues"]

        for league in leagues:
            for event in league["events"]:
                if(str(event["id"]) in selected_fixtures):
                    for period in event["periods"]:
                        if("moneyline" in period and period["number"] == 0):
                            match_odds = period["moneyline"]
                            match_odds_margin = 1/match_odds["home"] + 1/match_odds["draw"] + 1/match_odds["away"]
                            draw_odd = round(match_odds["draw"]*match_odds_margin, 2)
                            odd_movement = round(draw_odd - selected_fixtures[str(event["id"])]["draw"], 2)
                            selected_fixtures[str(event["id"])]["draw_odd_movement"] = odd_movement

        with open("selected_fixtures.json", "w") as fp:
            json.dump(selected_fixtures, fp, indent="")
            print(f'Odds update saved to file @ {datetime.utcnow()}')
    except Exception as e:
        print(f'Failed to execute \'updateOdds()\' => {e}')


def settleFixtures(soccer_id, settled_fixtures_url, ps3838_api_key):
    try:    
        with open("settled_fixtures.json", "r") as fp:
            if os.path.getsize("settled_fixtures.json") > 0:
                settled_fixtures = json.load(fp)
            else:
                settled_fixtures = {}
        
        URL = f'{settled_fixtures_url}?sportId={soccer_id}'
        HEADER = {'Accept': 'application/json', 'Authorization': f'Basic {ps3838_api_key}'}
        response = requests.get(url=URL, headers=HEADER)
        print(f'Settled Fixtures...{response.reason}')
        data = response.json()
        leagues = data["leagues"]

        for league in leagues:
            for event in league["events"]:
                if(str(event["id"]) in settled_fixtures):
                    for period in event["periods"]:
                        if(period["number"] == 0 and (period["status"] == 1 or period["status"] == 2)):
                            settled_fixtures[str(event["id"])]["score"] = f'{period["team1Score"]} - {period["team2Score"]}' 
                        elif(period["number"] == 1 and (period["status"] == 1 or period["status"] == 2)):
                            settled_fixtures[str(event["id"])]["ht_score"] = f'{period["team1Score"]} - {period["team2Score"]}'
        
        with open("settled_fixtures.json", "w") as fp:
            json.dump(settled_fixtures, fp, indent="")
            print(f'Settled fixtures saved to file @ {datetime.utcnow()}')
    except Exception as e:
        print(f'Failed to execute \'settleFixtures()\' => {e}')


def sendPicks(tg_api_key, chat_id):
    try:
        with open("selected_fixtures.json", "r") as fp:
            selected_fixtures = json.load(fp)
        
        with open("settled_fixtures.json", "r") as fp:
            settled_fixtures = json.load(fp)
        
        text_message = ""
        time_in_10mins = (datetime.utcnow() + timedelta(minutes=10)).strftime("%X")
        current_time = datetime.utcnow().strftime("%X")
        picks_sent = False

        for x in selected_fixtures:
            if(time_in_10mins >= selected_fixtures[x]["time"] > current_time and x not in settled_fixtures):
                picks_sent = True
                settled_fixtures[x] = selected_fixtures[x]
                
                text_message += (f'\N{alarm clock} {selected_fixtures[x]["time"][:-3]} (UTC)\n\N{stadium} {selected_fixtures[x]["league"]}\n'
                                f'\N{soccer ball} {selected_fixtures[x]["fixture"]}\n'
                                f'\N{direct hit} Draw odd (3% commission factored in): {round((selected_fixtures[x]["draw"]-0.03)/(1-0.03),2)}\n\n')
        
        
        with open("settled_fixtures.json", "w") as fp:
            json.dump(settled_fixtures, fp, indent="")
        
        if picks_sent:
            # url encoding needed for '\n' characters
            tg_url = f'https://api.telegram.org/bot{tg_api_key}/sendMessage?chat_id={chat_id}&text={urllib.parse.quote(text_message)}'
            requests.get(tg_url)
            print(f'Selected fixtures sent to TG channel & added to settlement file @ {datetime.utcnow()}')
    except Exception as e:
        print(f'Failed to execute \'sendPicks()\' => {e}')    


def purgeLogs():
    try:
        with open("logs.txt", "w") as fp:
            pass
    except Exception as e:
        print(f'Failed to execute \'purgeLogs()\' => {e}')


def jobsHandling(tg_api_key, tg_chat_id, soccer_id, odds_url, fixtures_url,settled_fixtures_url, ps3838_api_key):
    try:
        today_date = datetime.utcnow().strftime("%Y-%m-%d")
        purgeLogs()
        settleFixtures(soccer_id, settled_fixtures_url, ps3838_api_key)
        selectFixtures(soccer_id, odds_url, fixtures_url, today_date, ps3838_api_key)
        sendPicks(tg_api_key, tg_chat_id)
    except Exception as e:
        print(f'Failed to execute \'jobsHandling()\' => {e}')


def main():
    try:
        scheduler = BlockingScheduler(timezone='UTC')
        scheduler.add_job(jobsHandling,trigger='interval', args=[tg_api_key, tg_chat_id, soccer_id, odds_url, fixtures_url, settled_fixtures_url, ps3838_api_key], minutes=1, next_run_time=datetime.utcnow())

        scheduler.start()
    except Exception as e:
        print(f'Failed to execute \'main()\' => {e}')


if __name__ == '__main__':
    main()
    pass