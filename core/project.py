import os
import random

import aiohttp
from web3 import AsyncWeb3, AsyncHTTPProvider, Web3

from database import User
from utils.utils import generate_basic_header, get_current_time
from config import config



class Project:
    def __init__(self, user: User):
        self.user = user
        self.basic_header = generate_basic_header()
        self.current_time = get_current_time()
        self.session = None
        self.w3 = AsyncWeb3(AsyncHTTPProvider('https://rpc-base.harpie.io'))

    async def init_session(self) -> None:
        session = aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar())
        session.cookie_jar.update_cookies(self.user.cookie)
        session._default_proxy = self.user.proxy
        self.session = session

    async def close_session(self) -> None:
        cookies_dict = {cookie.key: cookie.value for cookie in self.session.cookie_jar._cookies.values()}
        self.user.cookie = cookies_dict
        self.session.commit()
        self.session.close()


    async def generate_random_wallet(self) -> str:
        private_key = Web3.keccak(os.urandom(32))
        wallet = Web3.eth.account.privateKeyToAccount(private_key)
        return wallet.address



    async def send_base_transaction(self) -> None:
        random_value = random.uniform(config.minimum_sending_amount, config.maximum_sending_amount)
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


