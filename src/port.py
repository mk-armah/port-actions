import httpx
import logging
from typing import Any, Dict, List, Tuple


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class PortAPI:
    def __init__(self,port_client_id:str,port_client_secret:str):
        self.base_url = "https://api.getport.io/v1"
        self.port_client_id = port_client_id
        self.port_client_secret = port_client_secret

    @property
    async def headers(self)->Dict[str,str]:

        access_token_object:dict = await self.get_token()
        access_token:str = access_token_object["accessToken"]

        port_headers = {"Authorization": f"Bearer {access_token}"}
        return port_headers

    async def get_token(self):
        credentials = {"clientId": self.port_client_id, "clientSecret": self.port_client_secret}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/auth/access_token",
                    json=credentials
                )
                logging.info(f"Successfully retrieved port token")
                response.raise_for_status()
                return response.json()
            except httpx.RequestError as exc:
                logging.error(f"An error occurred while requesting {exc.request.url!r}: {exc}")
            except httpx.HTTPStatusError as exc:
                logging.error(f"Error response {exc.response.status_code} while requesting {exc.request.url!r}: {exc.response.text}")


    async def add_entity(self, blueprint_id: str, entity_object: Dict[str, Any]):
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/blueprints/{blueprint_id}/entities?upsert=true&merge=true",
                    json=entity_object,
                    headers=await self.headers,
                ) #https://api.getport.io/v1/blueprints/githubTeam/entities?upsert=true&merge=true
                response.raise_for_status()
                logging.info(f"Entity added: {response.json()}")
            except httpx.RequestError as exc:
                logging.error(f"An error occurred while requesting {exc.request.url!r}: {exc}")
            except httpx.HTTPStatusError as exc:
                logging.error(f"Error response {exc.response.status_code} while requesting {exc.request.url!r}: {exc.response.text}")
