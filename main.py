import json
import os
import requests
import urllib
from apscheduler.schedulers.background import BlockingScheduler
from datetime import datetime
from dotenv import load_dotenv

# load ".env" file var
load_dotenv()


# api doc available @ https://pinnacleapi.github.io/


soccer_id = 29
odds_url = "https://api.ps3838.com/v3/odds"
fixtures_url = "https://api.ps3838.com/v3/fixtures"
settled_fixtures_url = "https://api.ps3838.com/v3/fixtures/settled"
today_date = datetime.utcnow().strftime("%Y-%m-%d")
ps3838_api_key = os.getenv("PS3838_API_KEY")
tg_api_key = os.getenv("TELEGRAM_API_KEY")
tg_chat_id = os.getenv("TELEGRAM_CHAT_ID")


def selectFixtures(sport_id, odds_url, fixtures_url, date, ps3838_api_key):
    try:
        URL = f"{fixtures_url}?sportId={sport_id}"
        HEADER = {'Accept': 'application/json', 'Authorization': f'Basic {ps3838_api_key}'}
        response = requests.get(url=URL, headers=HEADER)
        print(f"Fixtures...{response.reason}")
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
                            "fixture": f"event['home'] - event['away']"
                    }
        
        URL = f"{odds_url}?sportId={soccer_id}&oddsFormat=Decimal"
        response = requests.get(url=URL, headers=HEADER)
        print(f"Odds...{response.reason}")
        data = response.json()
        leagues = data["leagues"]

        for league in leagues:
            for event in league["events"]:
                if(event["id"] in selected_fixtures):
                    for period in event["periods"]:
                        if("moneyline" in period and period["number"] == 0):
                            match_odds = period["moneyline"]
                            match_odds_margin = round((1/match_odds["home"] + 1/match_odds["draw"] + 1/match_odds["away"])-1, 2)
                            home_odd = round((3*match_odds["home"])/(3-match_odds_margin*match_odds["home"]), 2)
                            draw_odd = round((3*match_odds["draw"])/(3-match_odds_margin*match_odds["draw"]), 2)
                            away_odd = round((3*match_odds["away"])/(3-match_odds_margin*match_odds["away"]), 2)
                            if(home_odd >= draw_odd >= away_odd >= 2):
                                for over_under in period["totals"]:
                                    if(over_under["points"] == 2.5 and over_under["over"] >= 2):
                                        over_under_margin = round((1/over_under["over"] + 1/over_under["under"])-1, 2)
                                        over_odd = round((2*over_under["over"])/(2-over_under_margin*over_under["over"]), 2)
                                        under_odd = round((2*over_under["under"])/(2-over_under_margin*over_under["under"]), 2)
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
            print(f"Selected fixtures saved to file @ {datetime.utcnow()}")
    except:
        print("Failed to execute \'selectFixtures()\'")

def updateOdds(soccer_id, odds_url, ps3838_api_key):
    try:
        with open("selected_fixtures.json", "r") as fp:
            selected_fixtures = json.load(fp)
        
        URL = f"{odds_url}?sportId={soccer_id}&oddsFormat=Decimal"
        HEADER = {'Accept': 'application/json', 'Authorization': f'Basic {ps3838_api_key}'}
        response = requests.get(url=URL, headers=HEADER)
        print(f"Odds...{response.reason}")
        data = response.json()
        leagues = data["leagues"]

        for league in leagues:
            for event in league["events"]:
                if(str(event["id"]) in selected_fixtures):
                    for period in event["periods"]:
                        if("moneyline" in period and period["number"] == 0):
                            match_odds = period["moneyline"]
                            match_odds_margin = round((1/match_odds["home"] + 1/match_odds["draw"] + 1/match_odds["away"])-1, 2)
                            draw_odd = round((3*match_odds["draw"])/(3-match_odds_margin*match_odds["draw"]), 2)
                            odd_movement = round(draw_odd - selected_fixtures[str(event["id"])]["draw"], 2)
                            selected_fixtures[str(event["id"])]["draw_odd_movement"] = odd_movement

        with open("selected_fixtures.json", "w") as fp:
            json.dump(selected_fixtures, fp, indent="")
            print(f"Odds update saved to file @ {datetime.utcnow()}")
    except:
        print("Failed to execute \'updateOdds()\'")


def settleFixtures(soccer_id, settled_fixtures_url, ps3838_api_key):
    try:    
        with open("selected_fixtures.json", "w+") as fp:
                selected_fixtures = json.load(fp)
        
        if os.path.isfile("./settled_fixtures.json"):
            with open("settled_fixtures.json", "r") as fp:
                settled_fixtures = json.load(fp)
        else:
            settled_fixtures = {}
        
        URL = f"{settled_fixtures_url}?sportId={soccer_id}"
        HEADER = {'Accept': 'application/json', 'Authorization': f'Basic {ps3838_api_key}'}
        response = requests.get(url=URL, headers=HEADER)
        print(f"Settled Fixtures...{response.reason}")
        data = response.json()
        leagues = data["leagues"]

        for league in leagues:
            for event in league["events"]:
                if(str(event["id"]) in selected_fixtures):
                    for period in event["periods"]:
                        if(period["number"] == 0 and (period["status"] == 1 or period["status"] == 2)):
                            settled_fixtures[str(event["id"])] = {
                                "date": selected_fixtures[str(event["id"])]["date"],
                                "time": selected_fixtures[str(event["id"])]["time"],
                                "league": selected_fixtures[str(event["id"])]["league"],
                                "fixture": selected_fixtures[str(event["id"])]["fixture"],
                                "home":selected_fixtures[str(event["id"])]["home"],
                                "draw":selected_fixtures[str(event["id"])]["draw"],
                                "away":selected_fixtures[str(event["id"])]["away"],
                                "o2.5":selected_fixtures[str(event["id"])]["o2.5"],
                                "u2.5":selected_fixtures[str(event["id"])]["u2.5"],
                                "draw_odd_movement":selected_fixtures[str(event["id"])]["draw_odd_movement"],
                                "score": f"period['team1Score'] - period['team2Score']"    
                            }
        
        with open("settled_fixtures.json", "w") as fp:
            json.dump(settled_fixtures, fp, indent="")
            print(f"Settled fixtures saved to file @ {datetime.utcnow()}")
    except:
        print("Failed to execute \'settleFixtures()\'")

def sendPicks(date, tg_api_key, chat_id):
    try:
        with open("selected_fixtures.json", "r") as fp:
            selected_fixtures = json.load(fp)

        text_message = f"Predictions for {date}\n\n"

        fixture_number = 1
        for x in selected_fixtures:
            text_message += "# %s\n\N{alarm clock} %s (UTC)\n\N{stadium} %s\n\N{soccer ball} %s\n" "\N{direct hit} Draw: %s\n\n" \
                    % (fixture_number, selected_fixtures[x]["time"][:-3], selected_fixtures[x]["league"], selected_fixtures[x]["fixture"], selected_fixtures[x]["draw"])

            fixture_number += 1
        
        # url encoding needed for '\n' characters
        tg_url = f"https://api.telegram.org/bot{tg_api_key}/sendMessage?chat_id={chat_id}&text={urllib.parse.quote(text_message)}" 
        requests.get(tg_url)
        print(f"Selected fixtures sent to TG channel @ {datetime.utcnow()}")
    except:
        print("Failed to execute \'sendPicks()\'")    


def main():
    # settleFixtures(soccer_id, settled_fixtures_url, ps3838_api_key)
    selectFixtures(soccer_id, odds_url, fixtures_url, today_date, ps3838_api_key)
    # sendPicks(today_date, tg_api_key, tg_chat_id)
    # updateOdds(soccer_id, odds_url, ps3838_api_key)

    try:
        scheduler = BlockingScheduler(timezone='UTC')

        scheduler.add_job(settleFixtures,trigger='cron', args=[soccer_id, settled_fixtures_url, ps3838_api_key], hour=7, minute=50, misfire_grace_time=600)
        scheduler.add_job(selectFixtures,trigger='cron', args=[soccer_id, odds_url, fixtures_url, today_date, ps3838_api_key], hour=7, minute=55, misfire_grace_time=600)
        scheduler.add_job(sendPicks,trigger='cron', args=[today_date, tg_api_key, tg_chat_id], hour=8, minute=00, misfire_grace_time=600)
        scheduler.add_job(updateOdds,trigger='interval',args=[soccer_id, odds_url, ps3838_api_key], minutes=2, misfire_grace_time=600)

        scheduler.start()
    except:
        print("Failed to execute \'main()\'")


if __name__ == '__main__':
    main()
    pass