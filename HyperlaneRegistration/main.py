import asyncio
import aiohttp
import pandas as pd
from sys import stderr
from loguru import logger
from eth_account.account import Account
from eth_account.messages import encode_typed_data

logger.remove()
logger.add(stderr,
           format="<lm>{time:HH:mm:ss}</lm> | <level>{level}</level> | <blue>{function}:{line}</blue> "
                  "| <lw>{message}</lw>")


def async_error_handler(error_msg, retries=3):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            for i in range(0, retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    logger.error(f"{error_msg}: {str(e)}")
                    if i == retries - 1:
                        return 0
                    await asyncio.sleep(2)

        return wrapper

    return decorator


class HyperLaneRegistration:
    def __init__(self, private_key: str, proxy: str, number_acc: int) -> None:
        self.private_key = private_key
        self.account = Account().from_key(private_key=private_key)
        self.proxy: str = f"http://{proxy}" if proxy is not None else None
        self.id: int = number_acc
        self.client = None

    async def create_message(self, amount) -> str and int:

        message = {
            "domain": {
                "name": "Hyperlane",
                "version": "1"
            },
            "message": {
                "eligibleAddress": self.account.address,
                "chainId": "10",
                "amount": amount,
                "receivingAddress": self.account.address,
                "tokenType": "HYPER"
            },
            "primaryType": "Message",
            "types": {
                "EIP712Domain": [
                    {
                        "name": "name",
                        "type": "string"
                    },
                    {
                        "name": "version",
                        "type": "string"
                    }
                ],
                "Message": [
                    {
                        "name": "eligibleAddress",
                        "type": "string"
                    },
                    {
                        "name": "chainId",
                        "type": "uint256"
                    },
                    {
                        "name": "amount",
                        "type": "string"
                    },
                    {
                        "name": "receivingAddress",
                        "type": "string"
                    },
                    {
                        "name": "tokenType",
                        "type": "string"
                    }
                ]
            }
        }

        signature = Account.sign_message(encode_typed_data(full_message=message), self.private_key).signature.hex()
        return signature

    @async_error_handler('check_eligible')
    async def check_eligible(self) -> None:
        async with aiohttp.ClientSession(headers={
            'authority': 'claim.hyperlane.foundation',
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9,ru;q=0.8',
            'referer': 'https://claim.hyperlane.foundation/',
            'sec-ch-ua': '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/126.0.0.0 Safari/537.36',
        }) as client:
            self.client = client

            response: aiohttp.ClientResponse = await self.client.get(
                f'https://claim.hyperlane.foundation/api/check-eligibility',
                params={'address': self.account.address},
                proxy=self.proxy,
            )
            response_json: dict = await response.json()

            if response_json['response']['isEligible']:
                amount = response_json["response"]["eligibilities"][0]["amount"]
                response: aiohttp.ClientResponse = await self.client.get(
                    f'https://claim.hyperlane.foundation/api/get-registration-for-address',
                    params={'address': self.account.address},
                    proxy=self.proxy,
                )
                response_json: dict = await response.json()
                if response_json['message'] == 'Success':
                    logger.info(f'#{self.id} | {self.account.address} eligible | {amount} HYPER | already registered')
                    return

                logger.info(f'#{self.id} | {self.account.address} eligible | {amount} HYPER | not registered')

                signature = await HyperLaneRegistration.create_message(self, amount=amount)

                response: aiohttp.ClientResponse = await self.client.post(
                    f'https://claim.hyperlane.foundation/api/save-registration',
                    json={
                        'wallets': [
                            {
                                'eligibleAddress': self.account.address,
                                'chainId': 10,
                                'eligibleAddressType': 'ethereum',
                                'receivingAddress': self.account.address,
                                'signature': f'0x{signature}',
                                'tokenType': 'HYPER',
                                'amount': amount,
                            },
                        ],
                    },
                    proxy=self.proxy,
                )
                response_json: dict = await response.json()

                if response_json['validationResult']['success']:
                    logger.success(f'#{self.id} | {self.account.address} success registered')

                else:
                    logger.info(f'#{self.id} | {self.account.address} not registered')

            else:
                logger.info(f'#{self.id} | {self.account.address} not eligible')


async def start_work(account: list, id_acc: int, semaphore) -> None:
    async with semaphore:
        acc = HyperLaneRegistration(private_key=account[0], proxy=account[1], number_acc=id_acc)

        try:

            await acc.check_eligible()

        except Exception as e:
            logger.error(f'ID account:{id_acc} Failed: {str(e)}')


async def main() -> None:
    semaphore: asyncio.Semaphore = asyncio.Semaphore(1)  # колличество потоков

    tasks: list[asyncio.Task] = [
        asyncio.create_task(coro=start_work(account=account, id_acc=idx, semaphore=semaphore))
        for idx, account in enumerate(accounts, start=1)
    ]
    await asyncio.gather(*tasks)


if __name__ == '__main__':
    with open('accounts_data.xlsx', 'rb') as file:
        exel = pd.read_excel(file)
    accounts: list[list] = [
        [
            row["Private key"],
            row["Proxy"] if isinstance(row["Proxy"], str) else None
        ]
        for index, row in exel.iterrows()
    ]
    logger.info(f'My channel: https://t.me/CryptoMindYep')
    logger.info(f'Total wallets: {len(accounts)}\n')

    asyncio.run(main())

    logger.success('The work completed')
    logger.info('Thx for donat: 0x5AfFeb5fcD283816ab4e926F380F9D0CBBA04d0e')
