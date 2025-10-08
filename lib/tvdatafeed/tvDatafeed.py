import requests
import pandas as pd
from datetime import datetime
import time
import json
import re
import websocket
import threading
import base64
import hashlib
import hmac
import random
import os
from enum import Enum

class Interval(Enum):
    in_1_minute = 60
    in_5_minutes = 300
    in_15_minutes = 900
    in_30_minutes = 1800
    in_1_hour = 3600
    in_2_hours = 7200
    in_4_hours = 14400
    in_1_day = 86400
    in_1_week = 604800
    in_1_month = 2592000

class TvDatafeed:
    def __init__(self, username=None, password=None):
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.base_url = 'https://www.tradingview.com'
        self.ws_url = 'wss://data.tradingview.com/socket.io/websocket'
        self.auth_token = None
        self.ws = None
        self.ws_thread = None

    def login(self):
        login_url = f'{self.base_url}/accounts/signin/'
        response = self.session.get(login_url)
        csrf_token = response.cookies.get('csrf_token')
        headers = {
            'X-CSRFToken': csrf_token,
            'User-Agent': 'Mozilla/5.0'
        }
        payload = {
            'username': self.username,
            'password': self.password,
            'remember': 'on'
        }
        login_response = self.session.post(login_url, headers=headers, data=payload)
        if login_response.status_code == 200:
            print("Login successful")
        else:
            print("Login failed")

    def get_hist(self, symbol, exchange, interval, n_bars=5000):
        url = f'{self.base_url}/chart/history'
        params = {
            'symbol': f'{exchange}:{symbol}',
            'resolution': interval.value,
            'from': int(time.time()) - (n_bars * interval.value),
            'to': int(time.time())
        }
        response = self.session.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            df = pd.DataFrame(data)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            return df
        else:
            print("Failed to fetch data")
            return None

    def _on_message(self, message):
        print(f"Received message: {message}")

    def _on_error(self, error):
        print(f"Error: {error}")

    def _on_close(self):
        print("Connection closed")

    def _on_open(self):
        print("Connection opened")
        self.ws.send('{"session_id": "your_session_id"}')

    def start_ws(self):
        self.ws = websocket.WebSocketApp(
            self.ws_url,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close
        )
        self.ws.on_open = self._on_open
        self.ws_thread = threading.Thread(target=self.ws.run_forever)
        self.ws_thread.start()

    def stop_ws(self):
        if self.ws:
            self.ws.close()
            self.ws_thread.join()
