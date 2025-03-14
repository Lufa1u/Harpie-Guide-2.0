import asyncio
import json
import os
import random
import time

import aiohttp
from eth_account.datastructures import SignedTransaction
from eth_account.messages import encode_defunct
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
        if self.user.cookie:
            session.cookie_jar.update_cookies(self.user.cookie)
        session._default_proxy = self.user.proxy
        self.session = session

    async def close_session(self) -> None:
        cookies_dict = {cookie.key: cookie.value for cookie in self.session.cookie_jar._cookies.values()}
        self.user.cookie = cookies_dict
        db_session.commit()
        db_session.close()



    async def generate_random_wallet(self) -> str:
        w3 = Web3()
        private_key = w3.keccak(os.urandom(32))
        wallet = w3.eth.account.from_key(private_key)
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

        asyncio.create_task(self.w3.eth.send_raw_transaction(signed_transaction.raw_transaction))

# TODO: подписать транзу и получить сигнатуру
    async def sign_received_transaction(self, transaction) -> SignedTransaction:
        transaction = {
            "nonce": transaction["nonce"],
            "gasPrice": int(transaction["gasPrice"]["hex"], 16),
            "gas": int(transaction["gasLimit"]["hex"], 16),
            "to": transaction["to"],
            "value": int(transaction["value"]["hex"], 16),
            "data": transaction["data"],
            "chainId": transaction["chainId"]
        }
        signed_transaction = self.w3.eth.account.sign_transaction(transaction, self.user.private_key)
        return signed_transaction

    # TODO: сделать сообщение с сигнатурой
    async def create_message_with_signed_transaction(self, signed_transaction: SignedTransaction) -> dict:
        tx_hash = signed_transaction.hash.hex()
        timestamp = str(int(time.time() * 1000))
        verification_string = signed_transaction.rawTransaction.hex()[2:66]

        eip712_message = {
            "types": {
                "AuthorizePendingTransactionToken": [
                    {"name": "txHash", "type": "string"},
                    {"name": "message", "type": "string"},
                    {"name": "signedAt", "type": "string"},
                    {"name": "verificationString", "type": "string"},
                ],
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                ]
            },
            "domain": {
                "name": "Harpie Login",
                "version": "1",
                "chainId": hex(8453)
            },
            "primaryType": "AuthorizePendingTransactionToken",
            "message": {
                "txHash": tx_hash,
                "message": "Click 'sign' to approve this transaction and send it out to the blockchain.\n\nThis signature will not trigger a blockchain transaction or cost any gas fees. Harpie will never ask for your seed phrase or private key. Your session will be valid for 5 minutes.",
                "signedAt": timestamp,
                "verificationString": verification_string
            }
        }

        encoded_message = encode_defunct(text=json.dumps(eip712_message))
        signature = self.w3.eth.account.sign_message(encoded_message, private_key=self.user.private_key).signature.hex()

        return signature


    async def receive_websocket_transaction(self, ws: aiohttp.ClientWebSocketResponse = None):
        if not ws:
            ws = await self.session.ws_connect(f'wss://rpc-base.harpie.io/{self.user.wallet}')
        data = await ws.receive_json()
        try:
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