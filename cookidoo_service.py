"""
Cookidoo Service

Module to encapsulate all cookidoo-api logic for interacting with the Cookidoo platform.
"""

import os
from typing import Optional, Any, Dict, List
from dotenv import load_dotenv
from aiohttp import ClientSession
from cookidoo_api import Cookidoo, CookidooConfig
from cookidoo_api.helpers import (
    get_localization_options,
)
import aiohttp
import time
import re
from annotations import build_instructions_from_steps


def load_cookidoo_credentials() -> tuple[str, str]:
    """
    Load Cookidoo credentials from .env file.
    
    Returns:
        tuple[str, str]: Email and password
        
    Raises:
        ValueError: If credentials are not found in environment variables
    """
    load_dotenv()
    
    email = os.getenv("COOKIDOO_EMAIL")
    password = os.getenv("COOKIDOO_PASSWORD")
    
    if not email or not password:
        raise ValueError(
            "Missing Cookidoo credentials. Please set COOKIDOO_EMAIL and "
            "COOKIDOO_PASSWORD in your .env file"
        )
    
    return email, password


class CookidooService:
    """Service class for managing Cookidoo API interactions."""
    
    def __init__(self, email: str, password: str):
        """
        Initialize the Cookidoo service with credentials.
        
        Args:
            email: Cookidoo account email
            password: Cookidoo account password
        """
        self.email = email
        self.password = password
        self._api_client: Optional[Cookidoo] = None
        self._session: Optional[ClientSession] = None
    
    async def login(self) -> Cookidoo:
        """
        Authenticate with Cookidoo and return the API client.
        
        Returns:
            Cookidoo: Authenticated Cookidoo API client
            
        Raises:
            Exception: If authentication fails
        """
        try:
            # Create aiohttp ClientSession with a timeout
            self._session = ClientSession(connector=aiohttp.TCPConnector(verify_ssl=False))
            

            # Create CookidooConfig with credentials
            config = CookidooConfig(
                email=self.email,
                password=self.password,
                localization=(
                    await get_localization_options(country="fr", language="fr-FR")
                )[0],
            )
            
            # Create Cookidoo API client with session and config
            self._api_client = Cookidoo(session=self._session, cfg=config)
            
            # Perform login (no parameters needed - uses config)
            await self._api_client.login()
            
            return self._api_client
            
        except Exception as e:
            # Clean up session if login fails
            if self._session:
                await self._session.close()
            raise Exception(f"Failed to authenticate with Cookidoo: {str(e)}") from e
    
    async def close(self) -> None:
        """Close the aiohttp session."""
        if self._session:
            await self._session.close()
    
    async def create_custom_recipe(
        self,
        name: str,
        ingredients: list[str],
        steps: list[str],
        servings: int = 4,
        prep_time: int = 30,
        total_time: int = 60,
        hints: Optional[list[str]] = None,
    ) -> str:
        """
        Create a completely new custom recipe from scratch using the undocumented API.
        
        Args:
            name: Recipe name
            ingredients: List of ingredient descriptions
            steps: List of cooking step descriptions
            servings: Number of servings (default: 4)
            prep_time: Preparation time in minutes (default: 30)
            total_time: Total cooking time in minutes (default: 60)
            hints: Optional list of hints/tips for the recipe
            
        Returns:
            str: The created recipe ID
            
        Raises:
            Exception: If recipe creation fails
        """
        if not self._api_client or not self._session:
            raise Exception("Not authenticated. Please call login() first.")
        
        try:
            # Get the access token from the authenticated client
            auth_data = self._api_client.auth_data
            if not auth_data:
                raise Exception("No authentication data available")
            
            localization = self._api_client.localization
            # Extract base domain from the URL (e.g., "https://cookidoo.fr/foundation/fr-FR" -> "https://cookidoo.fr")
            url_parts = localization.url.split("/")
            base_url = f"{url_parts[0]}//{url_parts[2]}"  # protocol + domain
            locale = localization.language 
            
            # Headers for the undocumented API
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_client.auth_data.access_token}"
            }
            
            # Use the API client's session to ensure cookies are shared
            api_session = self._api_client._session
        
            
            # Step 1: Create the recipe with just the name
            create_url = f"{base_url}/created-recipes/{locale}"
            create_data = {"recipeName": name}
            
            async with api_session.post(
                create_url, json=create_data, headers=headers
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(
                        f"Failed to create recipe. Status: {response.status}, Error: {error_text}"
                    )
                
                result = await response.json()
                recipe_id = result.get("recipeId")
                
                if not recipe_id:
                    raise Exception("No recipe ID returned from creation")
            
            # Step 2: Update recipe with ingredients and (optional) annotations
            update_url = f"{base_url}/created-recipes/{locale}/{recipe_id}"
            
            # PATCH requires a complete recipe structure with ALL required fields
            update_data = {
                "name": name,
                "image": None,  # Can be null or match pattern: ^((prod|nonprod)/img/customer-recipe/)?[A-Za-z0-9-_]{1,}.(bmp|jpe|jpeg|jpg|png)$
                "isImageOwnedByUser": False,
                "tools": ["TM6"],
                "yield": {"value": servings, "unitText": "portion"},
                "prepTime": prep_time * 60,  # Convert minutes to seconds
                "cookTime": 0,
                "totalTime": total_time * 60,  # Convert minutes to seconds
                "ingredients": [{"type": "INGREDIENT", "text": ing} for ing in ingredients],
                "instructions": build_instructions_from_steps(steps),
                "hints": "\n".join(hints) if hints and isinstance(hints, list) else (hints if hints else ""),
                "workStatus": "PRIVATE",
                "recipeMetadata": {
                    "requiresAnnotationsCheck": False
                }
            }
            
            time.sleep(5)

            async with api_session.patch(update_url, json=update_data, headers=headers) as response:
                print(f"  Response Status: {response.status}")
                response_text = await response.text()
                print(f"  Response Body: {response_text}")
                
                if response.status not in [200, 204]:
                    raise Exception(f"Failed to update recipe: {response_text}")
            
            return recipe_id
            
        except Exception as e:
            raise Exception(f"Failed to create custom recipe: {str(e)}") from e
    
    @property
    def api_client(self) -> Optional[Cookidoo]:
        """Get the current API client instance."""
        return self._api_client

    async def update_custom_recipe(
        self,
        recipe_id: str,
        update_data: Dict[str, Any],
    ) -> None:
        """
        Update an existing custom recipe using the undocumented API.

        This helper expects a *complete* recipe payload, as the PATCH endpoint
        requires all mandatory fields to be present. It can be used to send
        advanced instructions with annotations.

        Example structure for annotated instructions (see NOTES.md):

            {
              "instructions": [
                {
                  "type": "STEP",
                  "text": "test30 min/65°C/vitesse 3 eau",
                  "annotations": [
                    {
                      "type": "TTS",
                      "data": {
                        "speed": "3",
                        "time": 1800,
                        "temperature": {"value": "65", "unit": "C"}
                      },
                      "position": {"offset": 4, "length": 21}
                    },
                    {
                      "type": "INGREDIENT",
                      "data": {"description": "eau"},
                      "position": {"offset": 26, "length": 3}
                    }
                  ]
                }
              ]
            }

        Args:
            recipe_id: ID of the existing custom recipe
                      (e.g. "01KBHZPGSKAHAJATWQR23PWYM8").
            update_data: Full JSON-serializable payload to send in the PATCH
                        request. Must include all mandatory recipe fields.

        Raises:
            Exception: If authentication is missing or the update fails.
        """
        if not self._api_client or not self._session:
            raise Exception("Not authenticated. Please call login() first.")

        try:
            auth_data = self._api_client.auth_data
            if not auth_data:
                raise Exception("No authentication data available")

            localization = self._api_client.localization
            url_parts = localization.url.split("/")
            base_url = f"{url_parts[0]}//{url_parts[2]}"
            locale = localization.language

            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {auth_data.access_token}",
            }

            api_session = self._api_client._session
            update_url = f"{base_url}/created-recipes/{locale}/{recipe_id}"

            async with api_session.patch(
                update_url, json=update_data, headers=headers
            ) as response:
                response_text = await response.text()
                print(f"Update custom recipe status: {response.status}")
                print(f"Update custom recipe body: {response_text}")

                if response.status not in [200, 204]:
                    raise Exception(
                        f"Failed to update custom recipe {recipe_id}: "
                        f"HTTP {response.status} - {response_text}"
                    )

        except Exception as e:
            raise Exception(f"Failed to update custom recipe: {str(e)}") from e

    @staticmethod
    def _parse_custom_recipes_html(html: str, base_url: str) -> List[Dict[str, str]]:
        """
        Parse the created-recipes HTML page and extract custom recipe tiles.

        The HTML structure looks like:
            <core-tiles-list>
              <core-tile id="cr-01KBHZPGSKAHAJATWQR23PWYM8">
                <a href="/created-recipes/fr-FR/01KBHZPGSKAHAJATWQR23PWYM8">
                  ...
                  <p class="core-tile__description-text"> test </p>
                  ...

        We extract:
          - recipe_id: "01KBHZPGSKAHAJATWQR23PWYM8"
          - name: inner text of .core-tile__description-text
          - url: absolute URL to the recipe page
        """
        recipes: List[Dict[str, str]] = []

        # Find each tile region by its \"cr-\" id, without assuming a specific tag
        id_pattern = re.compile(
            r'id=\"cr-(?P<id>[^\"]+)\"',
            re.IGNORECASE,
        )

        # Inside each tile region, find the href to the recipe and the description text
        href_pattern = re.compile(
            r'<a[^>]*href="(?P<href>/created-recipes[^"]+)"',
            re.IGNORECASE,
        )
        name_pattern = re.compile(
            r'<p[^>]*class=\"[^\"]*core-tile__description-text[^\"]*\"[^>]*>(?P<name>.*?)</p>',
            re.DOTALL | re.IGNORECASE,
        )

        id_matches = list(id_pattern.finditer(html))

        for idx, match in enumerate(id_matches):
            recipe_id = match.group("id").strip()

            # Define a slice of HTML that likely contains this tile's content:
            # from this id up to the next id (or end of document).
            start = match.start()
            end = id_matches[idx + 1].start() if idx + 1 < len(id_matches) else len(html)
            tile_html = html[start:end]

            href_match = href_pattern.search(tile_html)
            name_match = name_pattern.search(tile_html)

            if not href_match or not name_match:
                continue

            href = href_match.group("href").strip()
            name_html = name_match.group("name")
            # Very lightweight HTML cleanup for the name
            name = re.sub(r"<[^>]+>", "", name_html).strip()

            # Build absolute URL
            url = f"{base_url}{href}"

            recipes.append(
                {
                    "id": recipe_id,
                    "name": name,
                    "url": url,
                }
            )

        return recipes

    async def get_custom_recipe(self, recipe_id: str) -> Dict[str, Any]:
        """
        Fetch the raw JSON for a custom (created) recipe by ID using the
        undocumented created-recipes API.

        This is useful for reading back instructions and annotations.
        """
        if not self._api_client or not self._session:
            raise Exception("Not authenticated. Please call login() first.")

        auth_data = self._api_client.auth_data
        if not auth_data:
            raise Exception("No authentication data available")

        localization = self._api_client.localization
        url_parts = localization.url.split("/")
        base_url = f"{url_parts[0]}//{url_parts[2]}"
        locale = localization.language

        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {auth_data.access_token}",
        }

        api_session = self._api_client._session
        recipe_url = f"{base_url}/created-recipes/{locale}/{recipe_id}"

        async with api_session.get(recipe_url, headers=headers) as response:
            if response.status != 200:
                text = await response.text()
                raise Exception(
                    f"Failed to fetch custom recipe {recipe_id}: "
                    f"HTTP {response.status} - {text}"
                )
            return await response.json()

    async def list_custom_recipes(self) -> List[Dict[str, str]]:
        """
        List your custom recipes by scraping the created-recipes page.

        It calls the authenticated created-recipes page
        (e.g. https://cookidoo.fr/created-recipes/fr-FR) and parses the HTML
        tiles to return basic information about each recipe.

        Returns:
            List of dictionaries with at least:
              - "id": recipe id (e.g. "01KBHZPGSKAHAJATWQR23PWYM8")
              - "name": recipe name (e.g. "test")
              - "url": full URL to the recipe page
        """
        if not self._api_client or not self._session:
            raise Exception("Not authenticated. Please call login() first.")

        localization = self._api_client.localization
        url_parts = localization.url.split("/")
        base_url = f"{url_parts[0]}//{url_parts[2]}"
        locale = localization.language

        # This is the same URL you see in the browser location bar
        created_recipes_url = f"{base_url}/created-recipes/{locale}"

        # Optionally enrich the request with a browser cookie from .env;
        # this is needed because the HTML UI uses a separate CIAM login.
        from dotenv import load_dotenv  # local import to avoid circular issues

        load_dotenv()
        browser_cookie = os.getenv("COOKIDOO_COOKIE")

        headers = {}
        if browser_cookie:
            headers["Cookie"] = browser_cookie

        api_session = self._api_client._session
        async with api_session.get(created_recipes_url, headers=headers) as response:
            html = await response.text()

        return self._parse_custom_recipes_html(html, base_url)
