import json
import os
import random

import aiohttp
from web3 import AsyncWeb3, AsyncHTTPProvider, Web3

from database import User, session as db_session
from utils.utils import generate_basic_header, get_current_time
from config import config



class Project:
    def __init__(self, user: User):
        self.user = user
        self.basic_header = generate_basic_header()
        self.current_time = get_current_time()
        self.session = None
        self.w3 = AsyncWeb3(AsyncHTTPProvider('https://rpc-base.harpie.io'))


    # TODO: разобраться с рефкой
    registration_header = {
        'referer': f'https://harpie.io/onboarding/basic/?referralCode={""}',
        'Content-Type': 'application/json',
    }


    async def init_session(self) -> None:
        session = aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar())
        session.cookie_jar.update_cookies(self.user.cookie)
        session._default_proxy = self.user.proxy
        self.session = session

    async def close_session(self) -> None:
        cookies_dict = {cookie.key: cookie.value for cookie in self.session.cookie_jar._cookies.values()}
        self.user.cookie = cookies_dict
        db_session.commit()
        db_session.close()



    async def generate_random_wallet(self) -> str:
        private_key = Web3.keccak(os.urandom(32))
        wallet = Web3.eth.account.privateKeyToAccount(private_key)
        return wallet.address



    async def send_transaction(self) -> None:
        random_value = random.uniform(*config.min_max_sending_amount)
        from_address = self.user.wallet
        to_address = await self.generate_random_wallet()
        checksum_address = self.w3.to_checksum_address(self.user.wallet)
        amount_in_wei = self.w3.to_wei(random_value, 'ether')

        gas_estimate = await self.w3.eth.estimate_gas(
            {'from': from_address, 'to': to_address, 'value': amount_in_wei}
        )
        gas_price = await self.w3.eth.gas_price
        nonce = await self.w3.eth.get_transaction_count(checksum_address)

        transaction = {
            'from': from_address,
            'to': to_address,
            'value': amount_in_wei,
            'gas': gas_estimate,
            'gasPrice': gas_price,
            'nonce': nonce,
            'chainId': 8453,
        }

        signed_transaction = self.w3.eth.account.sign_transaction(transaction, self.user.private_key)
        await self.w3.eth.send_raw_transaction(signed_transaction.raw_transaction)

# TODO: подписать транзу и получить сигнатуру
    async def sign_received_transaction(self, transaction) -> dict:
        signed_transaction = {}
        return signed_transaction


    async def receive_websocket_transaction(self, ws: aiohttp.ClientWebSocketResponse = None):
        if not ws:
            ws = self.session.ws_connect(f'wss://rpc-base.harpie.io/{self.user.wallet}')
        transaction = await ws.receive_json()
        try:
            data = json.loads(transaction)
            if "action" in data and data["action"] == "pendingConfirmation":
                transaction = data['data']['transaction']
                return ws, transaction
            else:
                await self.receive_websocket_transaction(ws=ws)
        except json.JSONDecodeError:
            raise Exception(f"Received non-JSON data: {data}")
        except Exception as e:
            raise Exception(f"Error processing data: {e}")


    async def send_websocket_message(self, ws: aiohttp.ClientWebSocketResponse, message: json):
        await ws.send_json(message)
        await ws.close()

# TODO: сделать сообщение с сигнатурой
    async def create_message_with_signed_transaction(self, signed_transaction: dict) -> dict:
        message = {}
        return message


    async def scan_wallet_request(self) -> str:
        async with self.session.post(f"https://harpie.io/api/addresses/{self.user.wallet}/queue-health/",
                                headers=self.basic_header, params={"chainId": 8453, "manualScan": "true"}) as response:
            return await response.json()


    async def get_referral_code(self):
        async with self.session.post("https://harpie.io/api/hooks/get-referral-code/", headers=self.basic_header,
                                params={"address:" f"{self.user.wallet}"}) as response:
            response_json = await response.json()
            return response_json["referralCode"]


    async def update_points_and_transactions_count(self) -> None:
        async with self.session.post("https://harpie.io/api/hooks/get-leaderboard-info/", headers=self.basic_header,
                                params={"address": self.user.wallet, "chainId": 8453,
                                        "includeLeaderboard": "false", "skipCache": "true"}) as response:
            response_json = await response.json()
            points = response_json["personalPoints"]
            transactions_count = len(response_json["personalPointEvents"])
            self.user.points = int(points)
            self.user.transactions_count = transactions_count
            db_session.commit()


    async def check_registration_request(self) -> bool:
        try:
            async with self.session.post("https://harpie.io/api/hooks/get-basic-dashboard/", headers=self.basic_header,
                                    json={"dashboardId": self.user.wallet, "chainId": 8453}) as response:
                data = await response.json()
                if data["email"]:
                    return True
        except Exception:
            return False


    async def registration_request(self) -> str:
        async with self.session.post("https://harpie.io/api/hooks/create-campaign/", headers=self.registration_header,
                                json={
            "contactInfo": self.user.email,
            "campaignName": "ONBOARDING_DROPOFF",
            "data":
                {
                    "finished_onboarding": False,
                    "address": self.user.wallet,
                    "date": get_current_time()}
                }) as response:
            return await response.json()


    async def create_basic_dashboard(self):
        async with self.session.post("https://harpie.io/api/hooks/create-basic-dashboard", headers=self.basic_header,
                                json={"wallet": self.user.wallet}) as response:
            return await response.json()